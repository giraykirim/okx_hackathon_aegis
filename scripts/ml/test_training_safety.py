"""CPU-only fault injection into training orchestration; no GPU/model/order calls.

Every positive approval/checkpoint below is an ephemeral UNIT_ONLY fixture, never
a human review, real checkpoint or assertion about AEGIS model quality.
"""

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import reviewed_learning as learning
import test_reviewed_learning as fixture


class ApprovalBoundaryTests(unittest.TestCase):
    setUp = fixture.BundleTests.setUp
    tearDown = fixture.BundleTests.tearDown
    save = fixture.BundleTests.save

    def test_ai_assisted_cannot_claim_blind_true(self):
        self.meta[60].update(
            blind_first_pass=True,
            ai_assisted=True,
            review_method="AI_ASSISTED_HUMAN_CONFIRMED",
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "blind"):
            learning.validate_bundle(self.directory, self.control)

    def test_false_ai_flag_cannot_mask_ai_review_method(self):
        self.meta[60].update(
            blind_first_pass=True,
            ai_assisted=False,
            review_method="AI_ASSISTED_HUMAN_CONFIRMED",
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "blind"):
            learning.validate_bundle(self.directory, self.control)

    def test_string_ai_flag_is_not_a_boolean(self):
        self.meta[60]["ai_assisted"] = "false"
        self.save()
        with self.assertRaises(ValueError):
            learning.validate_bundle(self.directory, self.control)

    def test_extra_expected_channel_rejected(self):
        path = self.directory / "train.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]["expected"]["UNIT_EXTRA_CHANNEL"] = "UNIT_ONLY"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.save()
        with self.assertRaisesRegex(ValueError, "row|channel"):
            learning.validate_bundle(self.directory, self.control)

    def test_no_intent_quantity_sibling_not_independent(self):
        path = self.directory / "val.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        context = json.loads(rows[0]["state"])["operational"]
        context.update(feed_age_seconds=1, quantity="9999")
        rows[0]["state"], _ = learning.state_from_context(context)
        trace = self.traces[60]
        trace["context"] = context
        self.meta[60]["trace_hash"] = hashlib.sha256(
            json.dumps(trace, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.save()
        with self.assertRaisesRegex(ValueError, "semantic|quantity"):
            learning.validate_bundle(self.directory, self.control)

    def test_open_policy_difference_blocks(self):
        manifest = json.loads((self.directory / "manifest.json").read_text())
        manifest["policy_disagreements_open"] = [
            {"case_id": "UNIT_ONLY", "status": "OPEN"}
        ]
        learning.write(self.directory / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "policy"):
            learning.validate_bundle(self.directory, self.control)

    def test_explicit_training_denial_blocks(self):
        manifest = json.loads((self.directory / "manifest.json").read_text())
        manifest["training_approved"] = False
        learning.write(self.directory / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "approval|approved"):
            learning.validate_bundle(self.directory, self.control)

    def test_explicit_independence_denial_blocks(self):
        manifest = json.loads((self.directory / "manifest.json").read_text())
        manifest["source_independence_approved"] = False
        learning.write(self.directory / "manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "approval|approved"):
            learning.validate_bundle(self.directory, self.control)

    def test_real_final_review_cannot_be_ai_assisted(self):
        self.meta[90].update(
            blind_first_pass=False,
            ai_assisted=True,
            review_method="AI_ASSISTED_HUMAN_CONFIRMED",
        )
        self.save()
        with self.assertRaisesRegex(ValueError, "blind"):
            learning.validate_bundle(self.directory, self.control)

    def test_fabricated_future_review_timestamp_blocks(self):
        self.meta[0]["reviewed_at_utc"] = "2999-01-01T00:00:00+00:00"
        self.save()
        with self.assertRaisesRegex(ValueError, "timestamp"):
            learning.validate_bundle(self.directory, self.control)

    def test_changed_backend_commit_blocks(self):
        self.meta[0]["backend_commit"] = "b" * 40
        self.save()
        with self.assertRaisesRegex(ValueError, "commit"):
            learning.validate_bundle(self.directory, self.control)

    def test_changed_trace_context_blocks(self):
        self.traces[0]["context"]["quantity"] = "9999"
        self.save()
        with self.assertRaisesRegex(ValueError, "trace"):
            learning.validate_bundle(self.directory, self.control)


class MetricBoundaryTests(unittest.TestCase):
    @staticmethod
    def perfect():
        return [
            {"expected": label, "predicted": label}
            for label in learning.LABELS
            for _ in range(100)
        ]

    def test_one_halt_to_continue_blocks_even_high_macro_f1(self):
        rows = self.perfect()
        rows[-1]["predicted"] = "CONTINUE"
        result = learning.metrics(rows)
        self.assertGreater(result["macro_f1"], 0.99)
        self.assertFalse(result["accepted"])

    def test_one_review_to_continue_blocks_even_high_macro_f1(self):
        rows = self.perfect()
        rows[100]["predicted"] = "CONTINUE"
        result = learning.metrics(rows)
        self.assertGreater(result["macro_f1"], 0.99)
        self.assertFalse(result["accepted"])

    def test_continue_recall_exactly_eighty_percent_can_pass(self):
        rows = self.perfect()
        for row in rows[:20]:
            row["predicted"] = "HALT"
        self.assertTrue(learning.metrics(rows)["accepted"])

    def test_continue_recall_seventy_nine_percent_blocks(self):
        rows = self.perfect()
        for row in rows[:21]:
            row["predicted"] = "HALT"
        self.assertFalse(learning.metrics(rows)["accepted"])

    def test_confusing_halt_and_review_below_macro_threshold_blocks(self):
        rows = self.perfect()
        for row in rows[100:]:
            row["predicted"] = "HALT" if row["expected"] == "REVIEW" else "REVIEW"
        result = learning.metrics(rows)
        self.assertEqual(result["halt_to_continue"], 0)
        self.assertEqual(result["review_to_continue"], 0)
        self.assertFalse(result["accepted"])

    def test_invalid_output_never_ignored(self):
        rows = self.perfect()
        rows[-1]["predicted"] = "UNIT_ONLY_INVALID"
        self.assertFalse(learning.metrics(rows)["accepted"])

    def test_high_confidence_cannot_override_unsafe_prediction(self):
        rows = self.perfect()
        rows[-1].update(predicted="CONTINUE", confidence=1.0)
        self.assertFalse(learning.metrics(rows)["accepted"])


class FakeChild:
    def __init__(self, returncode=0, timeout=False):
        self.returncode = returncode
        self.timeout = timeout
        self.killed = False

    def wait(self, timeout=None):
        if self.timeout and not self.killed:
            raise subprocess.TimeoutExpired("UNIT_ONLY", timeout)
        return self.returncode

    def kill(self):
        self.killed = True


class OrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="aegis-orchestration-UNIT_ONLY-"
        )
        self.root = Path(self.temporary.name).resolve()
        self.directory = self.root / "data/reviewed_learning/UNIT_ONLY"
        self.directory.mkdir(parents=True)
        self.control = self.root / "ml/debug_learning/UNIT_ONLY/result.json"
        self.control.parent.mkdir(parents=True)
        self.bundle = {
            name: [{"UNIT_ONLY_SPLIT": name}] for name in ("train", "val", "test")
        }
        self.calls, self.children = [], []
        self.losses = ["1.0"] * 8
        self.child_returncode = 0
        self.timeout = False
        self.accepted = False
        self.final_accepted = False
        self.patches = [
            patch.object(learning, "ROOT", self.root),
            patch.object(
                learning,
                "validate_bundle",
                return_value=({"UNIT_ONLY": True}, self.bundle),
            ),
            patch.object(learning, "evaluate", side_effect=self.evaluate),
            patch.object(learning.subprocess, "Popen", side_effect=self.spawn),
        ]
        for context in self.patches:
            context.start()

    def tearDown(self):
        for context in reversed(self.patches):
            context.stop()
        self.temporary.cleanup()

    def evaluate(self, checkpoint, rows):
        self.calls.append((Path(checkpoint), rows[0]["UNIT_ONLY_SPLIT"]))
        is_final = rows is self.bundle["test"]
        return {
            "accepted": self.final_accepted if is_final else self.accepted,
            "halt_to_continue": 0,
            "review_to_continue": 0,
            "macro_f1": 0.9,
            "continue_recall": 1.0,
            "invalid_outputs": 0,
            "truncated_rows": 0,
        }

    def spawn(self, command, stdout, stderr):
        for epoch, loss in enumerate(self.losses, 1):
            stdout.write(f"epoch {epoch}/8 mean loss {loss}\n")
        stdout.flush()
        out = Path(command[command.index("--output") + 1])
        out.mkdir(parents=True)
        (out / "UNIT_ONLY.bin").write_bytes(b"NOT_A_REAL_CHECKPOINT")
        child = FakeChild(self.child_returncode, self.timeout)
        self.children.append(child)
        return child

    def run_training(self):
        learning.train(self.directory, self.control)
        return json.loads(
            (self.root / "ml/reviewed_learning/UNIT_ONLY/result.json").read_text()
        )

    def test_validation_failure_never_starts_a_worker(self):
        with (
            patch.object(
                learning, "validate_bundle", side_effect=ValueError("UNIT_ONLY_BLOCKED")
            ),
            self.assertRaises(ValueError),
        ):
            learning.train(self.directory, self.control)
        self.assertEqual(self.children, [])
        self.assertEqual(self.calls, [])

    def test_failed_val_never_reads_final(self):
        result = self.run_training()
        self.assertFalse(any(split == "test" for _, split in self.calls))
        self.assertEqual(len(self.children), 2)
        self.assertEqual(result["outcome"], "DATA/INTEGRATION BLOCKED")

    def test_timeout_kills_child_without_retry(self):
        self.timeout = True
        result = self.run_training()
        self.assertEqual(len(self.children), 1)
        self.assertTrue(self.children[0].killed)
        self.assertEqual(result["reason"], "training timeout")
        self.assertFalse(any(split == "test" for _, split in self.calls))

    def test_worker_failure_never_retries_or_reads_final(self):
        self.child_returncode = 1
        result = self.run_training()
        self.assertEqual(len(self.children), 1)
        self.assertIn("no OOM retries", result["reason"])
        self.assertFalse(any(split == "test" for _, split in self.calls))

    def test_nan_loss_stops_before_selection(self):
        self.losses[-1] = "nan"
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            self.run_training()
        self.assertEqual(len(self.children), 1)
        self.assertFalse(any(split == "test" for _, split in self.calls))

    def test_infinite_loss_stops_before_selection(self):
        self.losses[-1] = "inf"
        with self.assertRaisesRegex(ValueError, "nonfinite"):
            self.run_training()
        self.assertEqual(len(self.children), 1)

    def test_missing_epoch_stops_before_selection(self):
        self.losses.pop()
        with self.assertRaisesRegex(ValueError, "missing"):
            self.run_training()

    def test_final_runs_only_once_after_val_pass(self):
        self.accepted = self.final_accepted = True
        result = self.run_training()
        self.assertEqual(sum(split == "test" for _, split in self.calls), 1)
        self.assertEqual(result["outcome"], "SHADOW CANDIDATE")
        self.assertFalse(result["production_approved"])
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["existing_selected_checkpoint_replaced"])

    def test_repeat_request_cannot_repeat_final(self):
        self.accepted = self.final_accepted = True
        self.run_training()
        count = len(self.calls)
        with self.assertRaises((FileExistsError, ValueError)):
            learning.train(self.directory, self.control)
        self.assertEqual(len(self.calls), count)

    def test_final_failure_does_not_promote(self):
        self.accepted = True
        result = self.run_training()
        self.assertEqual(result["outcome"], "DATA/INTEGRATION BLOCKED")
        self.assertFalse(result["final_accepted"])
        self.assertTrue((self.directory / "final-test-started.lock").exists())

    def test_tie_selection_is_predeclared_seed_not_final(self):
        self.accepted = self.final_accepted = True
        self.assertEqual(self.run_training()["seed"], 17)

    def test_existing_final_marker_blocks_workers_early(self):
        (self.directory / "final-test-started.lock").write_text(
            "UNIT_ONLY_PRIOR_ATTEMPT"
        )
        with self.assertRaisesRegex(ValueError, "final"):
            learning.train(self.directory, self.control)
        self.assertEqual(self.children, [])

    def test_existing_checkpoint_not_overwritten(self):
        out = self.root / "models/reviewed_learning/UNIT_ONLY/seed-17"
        out.mkdir(parents=True)
        (out / "preserve.bin").write_bytes(b"UNIT_ONLY_ORIGINAL")
        with self.assertRaisesRegex(ValueError, "existing"):
            self.run_training()
        self.assertEqual((out / "preserve.bin").read_bytes(), b"UNIT_ONLY_ORIGINAL")
        self.assertEqual(self.children, [])

    def test_worker_rejects_unapproved_seed_before_imports(self):
        with self.assertRaises(ValueError):
            learning.worker(
                self.directory,
                self.control,
                99,
                self.root / "models/reviewed_learning/UNIT_ONLY",
            )

    def test_worker_rejects_output_outside_quarantine(self):
        with self.assertRaises(ValueError):
            learning.worker(self.directory, self.control, 17, self.root / "OUTSIDE")


if __name__ == "__main__":
    unittest.main()
