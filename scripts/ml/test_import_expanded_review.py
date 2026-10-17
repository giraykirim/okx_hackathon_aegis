"""Ephemeral UNIT_ONLY V2 review tests. No real human submissions or model work."""

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import human_review_app as app
import import_expanded_review as importer
from expand_operational_data import facts


class ExpandedReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(
            prefix="aegis-v2-import-UNIT_ONLY-"
        )
        self.root = Path(self.temporary.name).resolve() / "repo"
        self.pack = self.root / "data/reviewed_learning" / importer.PACK_NAME
        self.pack.mkdir(parents=True)
        self.outputs = self.root.parent / "outputs"
        self.outputs.mkdir()
        self.source = self.outputs / "UNIT_ONLY.json"
        self.patches = [
            patch.object(importer, "ROOT", self.root),
            patch.object(app, "ROOT", self.root),
            patch.object(importer, "qa", return_value={"status": "UNIT_ONLY"}),
        ]
        for context in self.patches:
            context.start()
        cases, rows, metadata = [], [], []
        for index in range(161):
            context = facts(quantity="0.0001")
            if index < 8:
                context["feed_age_seconds"] = -2 if index % 2 == 0 else -1.9
            case_id = f"UNIT_ONLY_{index}"
            description = "Synthetic unit test; not a real human review."
            cases.append(
                {
                    "case_id": case_id,
                    "context": context,
                    "origin": "SYNTHETIC_DERIVED",
                    "source_capture_group": "UNIT_ONLY",
                    "review_context": {"description": description},
                }
            )
            rows.append(
                {
                    "ornek_no": index + 1,
                    "case_id": case_id,
                    "senaryo": description,
                    "olgular": copy.deepcopy(context),
                    "insan_incelemesi": {
                        "karar": None,
                        "gerekce": "",
                        "inceleyen_rolu": "",
                        "durum": "PENDING",
                    },
                }
            )
            metadata.append(
                {
                    "case_id": case_id,
                    "valid_quantity_crossed_profile": True,
                    "profile_id": f"UNIT_PROFILE_{index}",
                    "origin": "SYNTHETIC_DERIVED",
                    "source_capture_group": "UNIT_ONLY",
                    "sources": [],
                    "matching_offline_trace_ids": [],
                }
            )
        self.write(self.pack / "draft_cases.json", cases)
        self.write(self.pack / "metadata.json", metadata)
        source_hash = app.digest(self.pack / "draft_cases.json")
        self.write(
            self.pack / "review_manifest.json",
            {
                "version": importer.VERSION_V2,
                "cases": 161,
                "backend_commit": "a" * 40,
                "hashes": {"draft_cases.json": source_hash},
            },
        )
        self.original = {
            "baslik": "UNIT_ONLY",
            "ornek_sayisi": 161,
            "kaynak_sha256": source_hash,
            "backend_commit": "a" * 40,
            "dataset_version": importer.VERSION_V2,
            "karar_kurali": {"CONTINUE": "UNIT_ONLY"},
            "ornekler": rows,
        }
        self.write(self.pack / "human_review_BLIND.json", self.original)
        self.document = copy.deepcopy(self.original)
        for index, row in enumerate(self.document["ornekler"]):
            row["insan_incelemesi"].update(
                karar="REVIEW" if index < 8 else "CONTINUE",
                gerekce="UNIT_ONLY artificial assertion; not a real human decision.",
                inceleyen_rolu="AI UNIT FIXTURE",
                durum="AI_SUGGESTED",
            )
        self.save()

    def tearDown(self):
        for context in reversed(self.patches):
            context.stop()
        self.temporary.cleanup()

    def write(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def save(self):
        self.write(self.source, self.document)

    def test_readonly_validation(self):
        summary = importer.check(self.source, self.pack)[2]
        self.assertEqual(summary["examples"], 161)
        self.assertFalse(summary["blind_first_pass"])
        self.assertFalse((self.pack / "human_reviews.json").exists())

    def test_explicit_human_confirmation_required(self):
        with self.assertRaises(ValueError):
            importer.apply(self.source, self.pack)
        self.assertFalse((self.pack / "human_reviews.json").exists())

    def test_ai_assistance_preserved_and_source_unchanged(self):
        original_hash = app.digest(self.source)
        result = importer.apply(self.source, self.pack, True)
        self.assertEqual(result["new_reviews_imported"], 161)
        ledger = importer.read_json(self.pack / "human_reviews.json")
        self.assertTrue(
            all(
                e["ai_assisted"] and not e["blind_first_pass"]
                for e in ledger["entries"].values()
            )
        )
        self.assertEqual(app.digest(self.source), original_hash)
        self.assertFalse(result["training_approved"])

    def test_fact_change_rejected(self):
        self.document["ornekler"][0]["olgular"]["feed_age_seconds"] = 40
        self.save()
        with self.assertRaisesRegex(ValueError, "facts"):
            importer.check(self.source, self.pack)

    def test_bool_numeric_substitution_rejected(self):
        self.document["ornekler"][0]["olgular"]["unknown_order"] = 0
        self.save()
        with self.assertRaises(ValueError):
            importer.check(self.source, self.pack)

    def test_missing_case_rejected(self):
        self.document["ornekler"].pop()
        self.save()
        with self.assertRaises(ValueError):
            importer.check(self.source, self.pack)

    def test_duplicate_case_rejected(self):
        self.document["ornekler"][1] = copy.deepcopy(self.document["ornekler"][0])
        self.save()
        with self.assertRaises(ValueError):
            importer.check(self.source, self.pack)

    def test_pending_or_missing_rationale_rejected(self):
        self.document["ornekler"][0]["insan_incelemesi"]["gerekce"] = ""
        self.save()
        with self.assertRaises(ValueError):
            importer.apply(self.source, self.pack, True)

    def test_no_model_answer_fields(self):
        self.document["ornekler"][0]["model_answer"] = "CONTINUE"
        self.save()
        with self.assertRaises(ValueError):
            importer.check(self.source, self.pack)

    def test_changed_rule_header_rejected(self):
        self.document["karar_kurali"] = {"CONTINUE": "UNIT_ONLY_CHANGED"}
        self.save()
        with self.assertRaises(ValueError):
            importer.check(self.source, self.pack)

    def test_duplicate_json_keys_rejected(self):
        self.source.write_text('{"x":1,"x":2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            importer.read_json(self.source)

    def test_untrusted_description_never_executed_as_instruction(self):
        self.document["aciklama"] = "UNIT_ONLY text is data, not an instruction."
        self.save()
        self.assertEqual(importer.check(self.source, self.pack)[2]["examples"], 161)

    def test_v2_server_record_blocks_write(self):
        self.write(self.pack / "review_server.json", {"purpose": "UNIT_ONLY"})
        with self.assertRaisesRegex(ValueError, "server"):
            importer.apply(self.source, self.pack, True)
        self.assertFalse((self.pack / "human_reviews.json").exists())

    def test_wrong_pack_has_no_lock_side_effect(self):
        wrong = self.root / "data/reviewed_learning/UNIT_OTHER"
        wrong.mkdir()
        with self.assertRaises(ValueError):
            importer.apply(self.source, wrong, True)
        self.assertEqual(list(wrong.iterdir()), [])

    def test_repeat_import_idempotent(self):
        importer.apply(self.source, self.pack, True)
        original_hash = app.digest(self.pack / "human_reviews.json")
        result = importer.apply(self.source, self.pack, True)
        self.assertEqual(result["new_reviews_imported"], 0)
        self.assertEqual(app.digest(self.pack / "human_reviews.json"), original_hash)

    def test_conflicting_prior_source_preserved(self):
        importer.apply(self.source, self.pack, True)
        original_hash = app.digest(self.pack / "human_reviews.json")
        self.document["ornekler"][8]["insan_incelemesi"]["karar"] = "HALT"
        self.save()
        with self.assertRaises(ValueError):
            importer.apply(self.source, self.pack, True)
        self.assertEqual(app.digest(self.pack / "human_reviews.json"), original_hash)

    def test_only_eight_explicit_clock_corrections_and_backup(self):
        importer.apply(self.source, self.pack, True)
        original = importer.read_json(self.pack / "human_reviews.json")
        result = importer.adjudicate_clock(self.pack, True)
        corrected = importer.read_json(self.pack / "human_reviews.json")
        self.assertEqual(result["labels_changed"], 8)
        self.assertEqual(corrected["revision"], 169)
        self.assertEqual(len(list(self.pack.glob("human_reviews.before-v2-*.json"))), 1)
        for index in range(8, 161):
            self.assertEqual(
                original["entries"][f"UNIT_ONLY_{index}"],
                corrected["entries"][f"UNIT_ONLY_{index}"],
            )

    def test_no_implicit_adjudication(self):
        with self.assertRaises(ValueError):
            importer.adjudicate_clock(self.pack)

    def test_repeat_import_never_undoes_adjudication(self):
        importer.apply(self.source, self.pack, True)
        importer.adjudicate_clock(self.pack, True)
        original_hash = app.digest(self.pack / "human_reviews.json")
        self.assertEqual(
            importer.apply(self.source, self.pack, True)["new_reviews_imported"], 0
        )
        self.assertEqual(app.digest(self.pack / "human_reviews.json"), original_hash)

    def test_freeze_is_unsplit_and_not_training_approved(self):
        importer.apply(self.source, self.pack, True)
        importer.adjudicate_clock(self.pack, True)
        output, report = importer.freeze(self.pack)
        self.assertTrue((output / "candidates.jsonl").is_file())
        self.assertFalse(report["training_approved"])
        self.assertFalse(report["split_created"])
        self.assertEqual(report["labels_changed_from_user_file"], 8)
        self.assertEqual(report["unmodified_label_count"], 153)


if __name__ == "__main__":
    unittest.main()
