"""Offline synthetic unit/integration fixtures, never human reviews or exchange data."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import data_expansion_offline as offline
import expand_operational_data as expansion


class CandidatePolicyTests(unittest.TestCase):
    def test_reference_is_monitoring_only_continue(self):
        self.assertEqual(expansion.suggested_label(expansion.facts())[0], "CONTINUE")

    def test_every_unknown_required_flag_abstains(self):
        for key in expansion.BOOLS:
            with self.subTest(key=key):
                self.assertEqual(
                    expansion.suggested_label(expansion.facts(**{key: None}))[0],
                    "REVIEW",
                )

    def test_known_failure_precedes_unknown(self):
        context = expansion.facts(injection_detected=True, approval_available=None)
        self.assertEqual(expansion.suggested_label(context)[0], "HALT")

    def test_age_boundaries(self):
        for age, label in (
            (14.9, "CONTINUE"),
            (15, "CONTINUE"),
            (15.1, "HALT"),
            (-2, "CONTINUE"),
            (-2.1, "HALT"),
            (None, "REVIEW"),
        ):
            with self.subTest(age=age):
                self.assertEqual(
                    expansion.suggested_label(expansion.facts(feed_age_seconds=age))[0],
                    label,
                )

    def test_valid_size_is_not_a_label_proxy(self):
        for _, _, changes in expansion.coverage_specs():
            if "quantity" in changes:
                continue
            labels = {
                expansion.suggested_label(expansion.facts(quantity=q, **changes))[0]
                for q in expansion.QUANTITIES
            }
            self.assertEqual(len(labels), 1)

    def test_invalid_size_cases_remain_halt(self):
        for quantity in ("0", "-0.0001", "NaN", "Infinity", "-Infinity"):
            self.assertEqual(
                expansion.suggested_label(expansion.facts(quantity=quantity))[0], "HALT"
            )

    def test_new_missing_categories_are_present(self):
        contexts = [
            expansion.facts(**changes) for _, _, changes in expansion.coverage_specs()
        ]
        for key in (
            "injection_detected",
            "deployment_integrity_failure",
            "excess_exposure",
        ):
            self.assertTrue(any(c[key] is True for c in contexts))
            self.assertTrue(any(c[key] is None for c in contexts))

    def test_negative_and_positive_size_not_same_actual_state(self):
        positive, _ = expansion.state_from_context(expansion.facts(quantity="0.0001"))
        negative, _ = expansion.state_from_context(expansion.facts(quantity="-0.0001"))
        self.assertNotEqual(positive, negative)

    def test_serializer_rejects_untrusted_text(self):
        context = expansion.facts()
        context["tool_text"] = "UNIT_ONLY_UNTRUSTED_TEXT"
        with self.assertRaises(ValueError):
            expansion.suggested_label(context)

    def test_policy_does_not_mutate_context(self):
        context = expansion.facts(unknown_order=None)
        before = copy.deepcopy(context)
        expansion.suggested_label(context)
        self.assertEqual(context, before)


class OfflineBackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="aegis-unit-snapshot-")
        snapshot = Path(cls.temporary.name)
        for name in offline.MODULES:
            source = offline.ROOT / "backend/aegis" / (name + ".py")
            (snapshot / (name + ".py")).write_bytes(source.read_bytes())
        cls.backend = offline.load_backend(snapshot)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def replay(self, scenario):
        return offline.lifecycle_replay(self.backend, expansion.QUANTITIES[1], scenario)

    def test_pre_submit_timeout_has_no_claim(self):
        trace = self.replay("read_timeout_before_submit")
        self.assertFalse(trace["pending_journal"])
        self.assertTrue(trace["context_updates"]["api_timeout"])
        self.assertFalse(trace["execution_component_loaded"])

    def test_unknown_submit_is_real_unresolved_store_state(self):
        trace = self.replay("submit_timeout_unknown")
        self.assertTrue(trace["pending_journal"])
        self.assertTrue(trace["context_updates"]["unknown_order"])
        self.assertFalse(trace["backend_gate"]["approved"])
        self.assertIn("unresolved_prior_order", trace["backend_gate"]["reasons"])

    def test_ack_is_not_terminal(self):
        trace = self.replay("place_ack_only")
        self.assertIsNone(trace["context_updates"]["unknown_order"])
        self.assertTrue(trace["pending_journal"])
        self.assertFalse(trace["backend_gate"]["approved"])

    def test_partial_is_known_active_not_unknown_submission(self):
        trace = self.replay("active_partial")
        self.assertFalse(trace["context_updates"]["unknown_order"])
        self.assertFalse(trace["context_updates"]["intent_requested"])
        self.assertTrue(trace["pending_journal"])
        self.assertFalse(trace["backend_gate"]["approved"])
        event = next(
            e for e in trace["events"] if e["step"] == "injected_known_active_query"
        )
        self.assertEqual(event["fixture_order_type"], "ioc")

    def test_terminal_clears_unresolved(self):
        for scenario in ("filled_terminal", "canceled_terminal"):
            self.assertFalse(self.replay(scenario)["pending_journal"])

    def test_duplicate_rejected_after_terminal(self):
        trace = self.replay("duplicate_after_terminal")
        self.assertTrue(trace["context_updates"]["duplicate_intent"])
        self.assertIn("duplicate_intent", trace["backend_gate"]["reasons"])

    def test_second_pending_claim_is_rejected(self):
        trace = self.replay("new_intent_while_pending")
        event = next(e for e in trace["events"] if e["step"] == "second_intent")
        self.assertFalse(event["accepted"])

    def test_diagnostic_inputs_not_mislabeled_training_rows(self):
        probes = offline.gate_probes(self.backend)
        self.assertEqual(len(probes), 11)
        self.assertTrue(all(p["model_training_candidate"] is False for p in probes))
        self.assertTrue(all(p["actual_exchange_receipt"] is False for p in probes))
        self.assertTrue(
            any("invalid_quantity" in p["backend_gate"]["reasons"] for p in probes)
        )

    def test_all_outputs_json_serializable(self):
        for scenario in offline.LIFECYCLE_SCENARIOS:
            json.dumps(self.replay(scenario), allow_nan=False)

    def evidence(self):
        result = []
        for scenario in offline.LIFECYCLE_SCENARIOS:
            for quantity in expansion.QUANTITIES:
                trace = offline.lifecycle_replay(self.backend, quantity, scenario)
                trace["trace_id"] = hashlib.sha256(
                    json.dumps(trace, sort_keys=True).encode()
                ).hexdigest()
                trace["backend_commit"] = "a" * 40
                result.append(trace)
        return result

    def reseal(self, trace):
        unsigned = {
            k: v for k, v in trace.items() if k not in ("trace_id", "backend_commit")
        }
        trace["trace_id"] = hashlib.sha256(
            json.dumps(unsigned, sort_keys=True).encode()
        ).hexdigest()

    def test_trace_integrity_and_complete_matrix(self):
        traces = self.evidence()
        expansion.validate_traces(traces, "a" * 40)
        with self.assertRaises(ValueError):
            expansion.validate_traces(traces[:-1], "a" * 40)

    def test_trace_tamper_rejected(self):
        traces = self.evidence()
        traces[0]["pending_journal"] = not traces[0]["pending_journal"]
        with self.assertRaises(ValueError):
            expansion.validate_traces(traces, "a" * 40)

    def test_fabricated_real_exchange_claim_rejected(self):
        traces = self.evidence()
        traces[0]["actual_exchange_receipt"] = True
        self.reseal(traces[0])
        with self.assertRaises(ValueError):
            expansion.validate_traces(traces, "a" * 40)

    def test_fok_partial_fixture_rejected(self):
        traces = self.evidence()
        trace = next(t for t in traces if t["scenario"] == "active_partial")
        event = next(
            e for e in trace["events"] if e["step"] == "injected_known_active_query"
        )
        event["fixture_order_type"] = "fok"
        self.reseal(trace)
        with self.assertRaises(ValueError):
            expansion.validate_traces(traces, "a" * 40)


if __name__ == "__main__":
    unittest.main()
