"""CPU-only tests; no actual approval, training or checkpoint mutation."""

import json
import unittest
from unittest.mock import patch

import reviewed_development as dev


class QuarantineTests(unittest.TestCase):
    def test_training_needs_explicit_authorization(self):
        with self.assertRaises(ValueError):
            dev.run_diagnostic(False)

    def test_no_external_eval_and_fixed_recipe(self):
        args = dev.official_args("unit.jsonl", "UNIT_ONLY", seed=29)
        self.assertNotIn("--eval", args)
        self.assertIn("--freeze-encoder", args)
        self.assertEqual(args[args.index("--epochs") + 1], "8")
        self.assertEqual(args[args.index("--seed") + 1], "29")
        self.assertEqual(args[args.index("--micro-batch") + 1], "1")
        self.assertEqual(args[args.index("--grad-accum") + 1], "1")

    def test_dry_run_no_output(self):
        args = dev.official_args("unit.jsonl", dry_run=True)
        self.assertIn("--dry-run", args)
        self.assertNotIn("--out", args)

    def test_variant_count_is_not_independence(self):
        rows = []
        for quantity in ("0.0001", "0.0002"):
            state = json.dumps(
                {"operational": {"quantity": quantity, "unknown_order": True}}
            )
            rows.append({"state": state, "expected": {"operational_state": "HALT"}})
        metadata = [
            {
                "parent_scenario_group": "UNIT_ONLY",
                "source_capture_group": "same",
                "origin": "SYNTHETIC_DERIVED",
            }
        ] * 2
        report = dev.dataset_audit(rows, metadata)
        self.assertEqual(report["exact_unique_states"], 2)
        self.assertEqual(report["unique_contexts_ignoring_only_quantity"], 1)
        self.assertFalse(report["independent_test_available"])
        self.assertFalse(report["order_type_and_side_in_model_input"])

    def test_unchanged_protected_files_required(self):
        with (
            patch.object(dev, "sha", return_value="different"),
            self.assertRaises(ValueError),
        ):
            dev.check_protected({"scripts/ml/reviewed_development.py": "expected"})


if __name__ == "__main__":
    unittest.main()
