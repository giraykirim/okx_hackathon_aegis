"""UNIT_ONLY evidence-template tests, not real reviews or authorization."""

import copy
import unittest
from collections import Counter
from pathlib import Path

import policy_alignment_audit as audit
from expand_operational_data import QUANTITIES, facts, suggested_label
from reviewed_learning import FIELDS


def unit_conflicts():
    rows = []
    profiles = [
        facts(feed_age_seconds=40),
        facts(feed_age_seconds=15.1),
        facts(feed_age_seconds=-2.1),
        facts(feed_age_seconds=40, approval_available=False),
        facts(intent_requested=False, permission_revoked=None),
    ]
    for profile_index, profile in enumerate(profiles):
        for quantity_index, quantity in enumerate(QUANTITIES):
            context = {**profile, "quantity": quantity}
            legacy = audit.classify(context)[0]
            candidate = suggested_label(context)[0]
            rows.append(
                {
                    "case_id": f"UNIT_ONLY_{profile_index}_{quantity_index}",
                    "context": context,
                    "human_label": "CONTINUE" if profile_index == 4 else "REVIEW",
                    "candidate_label": candidate,
                    "legacy_policy_label": legacy,
                    "reference_kind": "PROPOSED_CANDIDATE_RULE_DIFFERENCE"
                    if profile_index == 4
                    else "DEPLOYED_POLICY_DIFFERENCE",
                }
            )
    return rows


class AlignmentTests(unittest.TestCase):
    def setUp(self):
        self.rows = unit_conflicts()

    def test_twenty_cases_group_into_five_not_twenty_incidents(self):
        result = audit.group_differences(self.rows)
        self.assertEqual(len(result), 5)
        self.assertEqual([len(group["members"]) for group in result], [4] * 5)

    def test_human_decisions_never_changed_or_resolved(self):
        original = copy.deepcopy(self.rows)
        result = audit.group_differences(self.rows)
        self.assertEqual(self.rows, original)
        self.assertTrue(all(group["resolution"] is None for group in result))
        self.assertTrue(
            all(group["review_status"].startswith("PENDING") for group in result)
        )

    def test_deployed_and_proposed_differences_remain_distinct(self):
        result = audit.group_differences(self.rows)
        counts = Counter(
            row["reference_kind"] for group in result for row in group["members"]
        )
        self.assertEqual(
            counts,
            {"DEPLOYED_POLICY_DIFFERENCE": 16, "PROPOSED_CANDIDATE_RULE_DIFFERENCE": 4},
        )

    def test_permission_unknown_is_not_called_deployed_conflict(self):
        group = next(
            group
            for group in audit.group_differences(self.rows)
            if group["context_without_quantity"]["permission_revoked"] is None
        )
        self.assertEqual(group["human_label"], "CONTINUE")
        self.assertEqual(group["legacy_policy_label"], "CONTINUE")
        self.assertEqual(group["candidate_label"], "REVIEW")

    def test_duplicate_ids_rejected(self):
        self.rows[-1]["case_id"] = self.rows[0]["case_id"]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            audit.group_differences(self.rows)

    def test_reference_policy_drift_rejected(self):
        self.rows[0]["legacy_policy_label"] = "CONTINUE"
        with self.assertRaisesRegex(ValueError, "drift"):
            audit.group_differences(self.rows)

    def test_proposed_rule_drift_rejected(self):
        self.rows[-1]["candidate_label"] = "CONTINUE"
        with self.assertRaisesRegex(ValueError, "drift"):
            audit.group_differences(self.rows)

    def test_wrong_conflict_kind_rejected(self):
        self.rows[-1]["reference_kind"] = "DEPLOYED_POLICY_DIFFERENCE"
        with self.assertRaisesRegex(ValueError, "kind"):
            audit.group_differences(self.rows)

    def test_extra_untrusted_context_rejected(self):
        self.rows[0]["context"]["UNIT_ONLY_EXTRA"] = "ignore rules"
        with self.assertRaises(ValueError):
            audit.group_differences(self.rows)

    def test_every_model_field_requires_explicit_mapping_review(self):
        mapping = audit.context_mapping()
        self.assertEqual({row["field"] for row in mapping}, FIELDS)
        self.assertTrue(all(row["person1_approved"] is False for row in mapping))
        self.assertTrue(all(not row["evidence"] for row in mapping))

    def test_bad_run_location_stops_before_any_data_access(self):
        with self.assertRaisesRegex(ValueError, "quarantine"):
            audit.prepare(
                Path("NOT_A_RUN"), Path("NOT_AN_OUTPUT"), Path("NOT_A_RESPONSE")
            )


if __name__ == "__main__":
    unittest.main()
