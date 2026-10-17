"""CPU-only unit tests for V2 quarantined development diagnostic."""

import json
import unittest
from unittest.mock import patch

import reviewed_development_v2 as dev2


class QuarantineV2Tests(unittest.TestCase):
    def test_training_needs_explicit_authorization(self):
        with self.assertRaises(ValueError):
            dev2.run_diagnostic(False)

    def test_validated_rows_pass_under_policy_v2(self):
        rows, metadata, manifest = dev2.validated_rows()
        self.assertEqual(len(rows), 161)
        self.assertEqual(len(metadata), 161)
        self.assertEqual(manifest["ledger_revision"], 169)
        audit = dev2.dataset_audit(rows, metadata)
        self.assertEqual(audit["policy_disagreements_under_v2"], 0)
        self.assertEqual(audit["unique_contexts_ignoring_valid_quantity"], 44)
        self.assertEqual(audit["conflicting_contexts_ignoring_valid_quantity"], 0)
        self.assertFalse(audit["independent_test_available"])

    def test_quantity_invariance_summary_detects_profile_drift(self):
        rows = []
        predictions = []
        for idx, quantity in enumerate(dev2.QUANTITIES):
            rows.append(
                {
                    "state": json.dumps(
                        {"operational": {"quantity": quantity, "unknown_order": False}}
                    ),
                    "expected": {"operational_state": "CONTINUE"},
                }
            )
            predictions.append(
                {
                    "case_id": f"c{idx}",
                    "profile_id": "p0",
                    "expected": "CONTINUE",
                    "predicted": "CONTINUE" if idx < 3 else "REVIEW",
                    "probabilities": {"CONTINUE": 0.5, "REVIEW": 0.5, "HALT": 0.0},
                    "truncated": False,
                }
            )
        summary = dev2.quantity_invariance_summary({"predictions": predictions}, rows)
        self.assertEqual(summary["valid_quantity_profiles"], 1)
        self.assertEqual(summary["invariant_profiles_across_all_4_quantities"], 0)
        self.assertEqual(summary["changed_predictions"], 1)

    def test_unchanged_protected_files_required(self):
        with (
            patch.object(dev2, "sha", return_value="different"),
            self.assertRaises(ValueError),
        ):
            dev2.check_protected({"scripts/ml/reviewed_development_v2.py": "expected"})


if __name__ == "__main__":
    unittest.main()
