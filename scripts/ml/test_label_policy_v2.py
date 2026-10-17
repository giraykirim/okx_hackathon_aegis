"""Offline tests for label policy v2 (human-preserved). No model, network or training.

Checks against the REAL frozen human-reviewed bundle (v2-r169): v2 must agree with
every human decision, including the 20 formerly open differences, without
editing any label, ledger or the v1 policy.
"""
import hashlib
import json
import unittest
from collections import Counter
from pathlib import Path

from ml import label_policy as v1
from ml import label_policy_v2 as v2

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'data/reviewed_learning/expanded-v2-20261017T120738Z'
FROZEN = PACK / 'human_confirmed_unsplit_v2-r169'
FROZEN_SHA = '0bb717f012d071e57ffeebcd917843010ca90e89771f2d77f6b8fc0ec23c2dcf'
PERSON1_GROUPS = {  # group_id -> agreed label (Person 1 coordination, commit da8d0c2)
    '6035c658446bc766': 'REVIEW', 'b507903e784e923b': 'REVIEW', 'bd4f3224298b7c68': 'REVIEW',
    'c328abb0010e5796': 'REVIEW', 'cb09120331fb2593': 'CONTINUE'}

BASE = {'symbol': 'BTC-USDT', 'site': 'tr', 'source_mode': 'MOCK', 'feed_age_seconds': 2,
        'intent_requested': True, 'quantity': '0.0001', 'account_known': True,
        'approval_available': True, 'api_timeout': False, 'agents_disagree': False,
        'unknown_order': False, 'duplicate_intent': False, 'permission_revoked': False,
        'injection_detected': False, 'deployment_integrity_failure': False, 'excess_exposure': False}


def group_id(context):
    normalized = {k: v for k, v in context.items() if k != 'quantity'}
    encoded = json.dumps(normalized, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()[:16]


class PolicyV2Semantics(unittest.TestCase):
    def test_versions_and_questions_shared(self):
        self.assertEqual(v1.VERSION, 'aegis-operational-v1')
        self.assertNotEqual(v2.VERSION, v1.VERSION)
        self.assertEqual(v2.PARENT_VERSION, v1.VERSION)
        self.assertIs(v2.QUESTIONS, v1.QUESTIONS)
        self.assertEqual(v2.LABELS, v1.LABELS)

    def test_stale_and_future_are_review_with_or_without_intent(self):
        for intent in (True, False):
            for age in (15.001, 15.1, 40, 300, -2.001, -2.1):
                with self.subTest(intent=intent, age=age):
                    label, reasons = v2.classify(BASE | {'intent_requested': intent, 'feed_age_seconds': age})
                    self.assertEqual(label, 'REVIEW')
                    self.assertIn('stale_or_future_feed', reasons)
                    self.assertEqual(v1.classify(BASE | {'intent_requested': intent,
                                                         'feed_age_seconds': age})[0], 'HALT')

    def test_boundaries_unchanged(self):
        for age in (15, -2, -1.9, 0):
            self.assertEqual(v2.classify(BASE | {'feed_age_seconds': age})[0], 'CONTINUE')
        self.assertEqual(v2.classify(BASE | {'feed_age_seconds': None})[0], 'REVIEW')

    def test_non_numeric_or_non_finite_timestamp_stays_halt(self):
        for age in (float('nan'), float('inf'), float('-inf'), True, '40'):
            with self.subTest(age=age):
                label, reasons = v2.classify(BASE | {'feed_age_seconds': age})
                self.assertEqual(label, 'HALT')
                self.assertIn('invalid_feed_timestamp', reasons)

    def test_any_halt_reason_dominates_stale_feed(self):
        hazards = [{'unknown_order': True}, {'duplicate_intent': True}, {'injection_detected': True},
                   {'permission_revoked': True}, {'deployment_integrity_failure': True},
                   {'excess_exposure': True}, {'source_mode': 'LIVE'}, {'site': 'global'},
                   {'symbol': 'ETH-USDT'}, {'quantity': '0'}, {'quantity': True}]
        for hazard in hazards:
            with self.subTest(hazard=hazard):
                self.assertEqual(v2.classify(BASE | {'feed_age_seconds': 40} | hazard)[0], 'HALT')

    def test_unknown_permission_without_intent_stays_continue(self):
        facts = BASE | {'intent_requested': False, 'permission_revoked': None}
        self.assertEqual(v2.classify(facts), ('CONTINUE', ['monitoring_only']))

    def test_stale_plus_missing_approval_is_review_not_continue(self):
        label, reasons = v2.classify(BASE | {'feed_age_seconds': 40, 'approval_available': False})
        self.assertEqual(label, 'REVIEW')
        self.assertEqual(set(reasons), {'stale_or_future_feed', 'execution_context_unavailable'})

    def test_unknown_safety_flag_with_intent_is_review(self):
        for field in v2.UNKNOWN_BLOCKS_INTENT:
            with self.subTest(field=field):
                label, reasons = v2.classify(BASE | {field: None})
                self.assertEqual(label, 'REVIEW')
                self.assertIn('safety_flag_unknown_with_intent', reasons)
                self.assertEqual(v1.classify(BASE | {field: None})[0], 'CONTINUE')
                absent = {k: v for k, v in BASE.items() if k != field}
                self.assertEqual(v2.classify(absent)[0], 'REVIEW')

    def test_unknown_safety_flag_without_intent_stays_continue(self):
        for field in v2.UNKNOWN_BLOCKS_INTENT:
            with self.subTest(field=field):
                self.assertEqual(v2.classify(BASE | {'intent_requested': False, field: None})[0], 'CONTINUE')

    def test_v2_equals_v1_for_fully_known_fresh_facts(self):
        variants = [{}, {'intent_requested': False}, {'approval_available': False}, {'account_known': False},
                    {'api_timeout': True}, {'feed_age_seconds': None}, {'unknown_order': True},
                    {'intent_requested': False, 'permission_revoked': None}, {'source_mode': 'LIVE'},
                    {'quantity': '-1'}]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(v2.classify(BASE | variant)[0], v1.classify(BASE | variant)[0])


@unittest.skipUnless((FROZEN / 'manifest.json').exists(), 'frozen human bundle not present')
class PolicyV2AgainstFrozenHumanBundle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((FROZEN / 'manifest.json').read_text(encoding='utf-8'))
        cls.rows = [json.loads(line) for line in
                    (FROZEN / 'candidates.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]

    def test_bundle_is_the_frozen_r169_export(self):
        digest = hashlib.sha256((FROZEN / 'candidates.jsonl').read_bytes()).hexdigest()
        self.assertEqual(digest, self.manifest['hashes']['candidates.jsonl'])
        self.assertEqual(self.manifest['ledger_revision'], 169)
        self.assertEqual(len(self.rows), 161)

    def test_v2_matches_every_human_label(self):
        mismatches, v1_mismatches = [], 0
        for row in self.rows:
            facts = json.loads(row['state'])['operational']
            human = row['expected']['operational_state']
            if v2.classify(facts)[0] != human:
                mismatches.append((facts, human))
            v1_mismatches += v1.classify(facts)[0] != human
        self.assertEqual(mismatches, [])
        self.assertEqual(v1_mismatches, 48)  # 16 stale/future + 32 intent-with-null-flag (missed by 20-case audit)

    def test_twenty_open_differences_resolved_per_person1_group(self):
        differences = self.manifest['policy_disagreements_open']
        self.assertEqual(len(differences), 20)
        per_group = Counter()
        for item in differences:
            gid = group_id(item['context'])
            self.assertIn(gid, PERSON1_GROUPS)
            self.assertEqual(item['human_label'], PERSON1_GROUPS[gid])
            self.assertEqual(v2.classify(item['context'])[0], item['human_label'])
            per_group[gid] += 1
        self.assertEqual(per_group, Counter({gid: 4 for gid in PERSON1_GROUPS}))


if __name__ == '__main__':
    unittest.main()
