"""Regression tests for dataset QA. No checkpoint loading or test-set inference."""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('qa_dataset', Path(__file__).with_name('qa_dataset.py'))
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class DatasetQA(unittest.TestCase):
    def test_halt_precedes_missing_context_and_healthy_quotes(self):
        from ml.label_policy import classify
        for hazard in ('unknown_order', 'duplicate_intent', 'injection_detected', 'permission_revoked'):
            state = dict(source_mode='MARKET_ONLY', site='tr', symbol='BTC-USDT',
                         feed_age_seconds=1, intent_requested=True, quantity='0.0001',
                         account_known=False, approval_available=False, **{hazard: True})
            self.assertEqual(classify(state)[0], 'HALT')

    def test_numeric_and_freshness_boundaries(self):
        from ml.label_policy import classify
        state = dict(source_mode='MARKET_ONLY', site='tr', symbol='BTC-USDT',
                     feed_age_seconds=15, intent_requested=False)
        self.assertEqual(classify(state)[0], 'CONTINUE')
        self.assertEqual(classify(state | {'feed_age_seconds': 15.001})[0], 'HALT')
        self.assertEqual(classify(state | {'feed_age_seconds': -2.001})[0], 'HALT')
        self.assertEqual(classify(state | {'feed_age_seconds': None})[0], 'REVIEW')
        self.assertEqual(classify(state | {'intent_requested': True, 'quantity': True})[0], 'HALT')

    def mutate(self, name, fn):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'data'
            shutil.copytree(ROOT / 'data', target)
            path = target / name
            path.write_text(fn(path.read_text(encoding='utf-8')), encoding='utf-8')
            return qa.check(target)

    def test_candidates_pass_structure_not_review(self):
        report = qa.check(ROOT / 'data')
        self.assertEqual(report['structural_status'], 'PASS')
        self.assertFalse(report['training_approved'])

    def test_detects_leaked_family(self):
        result = self.mutate('metadata.csv', lambda text: text.replace('normal_monitoring', 'healthy_no_trade'))
        self.assertIn('Cross-split family/source leakage', result['errors'])

    def test_rejects_fabricated_human_review(self):
        result = self.mutate('metadata.csv', lambda text: text.replace('PENDING_HUMAN_REVIEW', 'HUMAN_REVIEWED', 1))
        self.assertIn('Unverified human review claim', result['errors'])

    def test_detects_file_tampering(self):
        result = self.mutate('sources.json', lambda text: text + ' ')
        self.assertIn('File hash mismatch: sources.json', result['errors'])

    def test_official_laya_reader(self):
        from laya.evals import Dataset
        for split in ('train', 'val', 'test', 'challenge'):
            parsed = Dataset.from_jsonl(str(ROOT / 'data' / f'{split}.jsonl'))
            expected = json.loads((ROOT / 'data/manifest.json').read_text())['counts'][split]
            self.assertEqual(len(parsed), sum(expected.values()))


if __name__ == '__main__':
    unittest.main()
