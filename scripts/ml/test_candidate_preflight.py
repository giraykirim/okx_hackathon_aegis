"""Negative/transport tests only; no real dataset rewriting or model import."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import candidate_preflight as preflight


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.row = {
            "state": '{"UNIT_ONLY":true}',
            "questions": copy.deepcopy(preflight.QUESTIONS),
            "expected": {"operational_state": "CONTINUE"},
        }

    def encode(self):
        return (json.dumps(self.row) + "\n").encode()

    def reject(self):
        with self.assertRaises(ValueError):
            preflight.parse_rows(self.encode())

    def test_valid_contract_preserved(self):
        rows, changes = preflight.parse_rows(self.encode())
        self.assertEqual(rows, [self.row])
        self.assertFalse(changes["bom_removed"])

    def test_each_operational_label_supported(self):
        for label in preflight.LABELS:
            with self.subTest(label=label):
                self.row["expected"]["operational_state"] = label
                self.assertEqual(len(preflight.parse_rows(self.encode())[0]), 1)

    def test_extra_channel_rejected(self):
        self.row["expected"]["UNIT_ONLY"] = "HALT"
        self.reject()

    def test_missing_target_rejected(self):
        self.row["expected"] = {}
        self.reject()

    def test_unknown_label_not_remapped(self):
        self.row["expected"]["operational_state"] = "APPROVE_TRADE"
        self.reject()

    def test_lowercase_label_not_guessed(self):
        self.row["expected"]["operational_state"] = "continue"
        self.reject()

    def test_empty_state_rejected(self):
        self.row["state"] = "  "
        self.reject()

    def test_nontext_state_rejected(self):
        self.row["state"] = {"UNIT_ONLY": True}
        self.reject()

    def test_debug_control_never_mixed(self):
        self.row["state"] = "DEBUG_LABEL=CONTINUE"
        self.reject()

    def test_extra_gold_field_rejected(self):
        self.row["gold"] = {"operational_state": "HALT"}
        self.reject()

    def test_changed_question_rejected(self):
        self.row["questions"]["operational_state"]["instructions"] = "UNIT_ONLY_CHANGED"
        self.reject()

    def test_duplicate_json_keys_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            preflight.parse_rows(b'{"state":"a","state":"b"}\n')

    def test_nan_numeric_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            preflight.parse_rows(b'{"state":NaN}\n')

    def test_infinity_numeric_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            preflight.parse_rows(b'{"state":Infinity}\n')

    def test_overflow_numeric_rejected(self):
        with self.assertRaisesRegex(ValueError, "non-finite"):
            preflight.parse_rows(b'{"state":1e999}\n')

    def test_bom_requires_explicit_repair(self):
        with self.assertRaisesRegex(ValueError, "repair"):
            preflight.parse_rows(b"\xef\xbb\xbf" + self.encode())

    def test_blank_line_requires_explicit_repair(self):
        with self.assertRaisesRegex(ValueError, "repair"):
            preflight.parse_rows(self.encode() + b"\n")

    def test_invalid_row_not_silently_skipped(self):
        with self.assertRaises(ValueError):
            preflight.parse_rows(
                self.encode() + b"NOT_JSON\n", allow_transport_cleanup=True
            )

    def test_empty_dataset_rejected(self):
        with self.assertRaisesRegex(ValueError, "empty"):
            preflight.parse_rows(b"")

    def test_final_and_challenge_not_allowlisted(self):
        self.assertNotIn("data/test.jsonl", preflight.DATASETS)
        self.assertNotIn("data/challenge.jsonl", preflight.DATASETS)

    def test_official_skipped_items_never_pass(self):
        with self.assertRaisesRegex(ValueError, "skipped"):
            preflight.assert_complete(
                {"rows_read": 3, "valid_items": 3, "skipped": {"invalid_target": 1}}, 3
            )

    def test_official_missing_rows_never_pass(self):
        with self.assertRaises(ValueError):
            preflight.assert_complete(
                {"rows_read": 2, "valid_items": 2, "skipped": {}}, 3
            )

    def test_complete_official_summary_passes(self):
        preflight.assert_complete({"rows_read": 3, "valid_items": 3, "skipped": {}}, 3)

    def test_truncation_detected_not_hidden_by_format_pass(self):
        result = preflight.token_summary(
            [
                {"truncated": False, "state_tokens": 100, "state_tokens_dropped": 0},
                {"truncated": True, "state_tokens": 700, "state_tokens_dropped": 281},
            ]
        )
        self.assertEqual(result["rows_truncated"], 1)
        self.assertEqual(result["total_state_tokens_dropped"], 281)


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="aegis-preflight-UNIT_ONLY-"
        )
        self.root = Path(self.temporary.name).resolve()
        self.source = self.root / "data/train.jsonl"
        self.source.parent.mkdir()
        self.row = {
            "state": "UNIT_ONLY",
            "questions": preflight.QUESTIONS,
            "expected": {"operational_state": "REVIEW"},
        }
        self.raw = b"\xef\xbb\xbf" + json.dumps(self.row).encode() + b"\n\n"
        self.source.write_bytes(self.raw)
        self.destination = self.root / "data/qa_repairs/UNIT_ONLY/copy.jsonl"
        self.patcher = patch.object(preflight, "ROOT", self.root)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        self.temporary.cleanup()

    def test_transport_only_copy_preserves_source_state_and_label(self):
        result = preflight.transport_repair(self.source, self.destination)
        self.assertEqual(self.source.read_bytes(), self.raw)
        self.assertEqual(
            preflight.parse_rows(self.destination.read_bytes())[0], [self.row]
        )
        self.assertEqual(
            result["changes"], {"bom_removed": True, "blank_lines_removed": 1}
        )
        self.assertFalse(result["training_approved"])

    def test_existing_copy_never_overwritten(self):
        preflight.transport_repair(self.source, self.destination)
        with self.assertRaisesRegex(ValueError, "overwrite"):
            preflight.transport_repair(self.source, self.destination)

    def test_source_never_overwritten(self):
        with self.assertRaises(ValueError):
            preflight.transport_repair(self.source, self.source)
        self.assertEqual(self.source.read_bytes(), self.raw)

    def test_invalid_label_not_repaired(self):
        self.row["expected"]["operational_state"] = "INVALID_UNIT_ONLY"
        self.source.write_text(json.dumps(self.row) + "\n")
        with self.assertRaises(ValueError):
            preflight.transport_repair(self.source, self.destination)
        self.assertFalse(self.destination.exists())

    def test_final_test_never_repaired(self):
        final = self.root / "data/test.jsonl"
        final.write_bytes(self.raw)
        with self.assertRaises(ValueError):
            preflight.transport_repair(final, self.destination)

    def test_output_outside_quarantine_rejected(self):
        with self.assertRaises(ValueError):
            preflight.transport_repair(self.source, self.root / "data/APPROVED.jsonl")


if __name__ == "__main__":
    unittest.main()
