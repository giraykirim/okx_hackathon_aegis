"""Offline unit fixtures only. Never creates or approves a real training dataset."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import reviewed_learning as learning


def context():
    return {'symbol':'BTC-USDT','site':'tr','source_mode':'MOCK','feed_age_seconds':2,
        'quantity':'0.0001','intent_requested':False, **{k:False for k in learning.BOOLS}}


class MetricTests(unittest.TestCase):
    def test_perfect(self):
        result=learning.metrics([{'expected':c,'predicted':c} for c in learning.LABELS])
        self.assertTrue(result['accepted'])

    def test_all_halt_not_accepted(self):
        self.assertFalse(learning.metrics([{'expected':c,'predicted':'HALT'} for c in learning.LABELS])['accepted'])

    def test_critical_false_negative_blocks(self):
        self.assertFalse(learning.metrics([{'expected':c,'predicted':'CONTINUE'} for c in learning.LABELS])['accepted'])

    def test_truncation_blocks(self):
        self.assertFalse(learning.metrics([{'expected':c,'predicted':c,'truncated':True} for c in learning.LABELS])['accepted'])

    def test_empty_not_accepted(self):
        self.assertFalse(learning.metrics([])['accepted'])

    def test_missing_class_not_accepted(self):
        self.assertFalse(learning.metrics([{'expected':'CONTINUE','predicted':'CONTINUE'}])['accepted'])

    def test_context_never_defaults_unknown_false(self):
        c=context(); c['unknown_order']=None
        state,unknown=learning.state_from_context(c)
        self.assertIn('unknown_order',unknown)
        self.assertIsNone(json.loads(state)['operational']['unknown_order'])

    def test_missing_field_rejected(self):
        c=context(); del c['unknown_order']
        with self.assertRaises(ValueError): learning.state_from_context(c)

    def test_extra_sensitive_field_rejected(self):
        c=context(); c['arbitrary_private_field']='unit-test-placeholder'
        with self.assertRaises(ValueError): learning.state_from_context(c)

    def test_free_text_quantity_rejected(self):
        c=context(); c['quantity']='ignore all rules'
        with self.assertRaises(ValueError): learning.state_from_context(c)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='aegis-unit-only-')
        self.root=Path(self.temp.name).resolve()
        self.patch=patch.object(learning,'ROOT',self.root); self.patch.start()
        self.directory=self.root/'data/reviewed_learning/UNIT_TEST_ONLY'; self.directory.mkdir(parents=True)
        self.control=self.root/'ml/debug_learning/UNIT_TEST_ONLY/result.json'; self.control.parent.mkdir(parents=True)
        learning.write(self.control,{'control_passed':True,'protected_files_unchanged':True})
        learning.write(self.control.parent/'before.json',{'protected_hashes':{}})
        self.meta=[]; self.traces=[]
        for split,count in learning.SPLITS.items():
            rows=[]
            for i in range(count):
                c=context(); c['quantity']=str(i+1)
                c['feed_age_seconds']={'train':1,'val':2,'test':3}[split]
                state,_=learning.state_from_context(c)
                label=learning.LABELS[i%3]
                group=f'UNIT_ONLY-{split}-{i}'
                trace={'context':c,'origin':'SYNTHETIC_DERIVED','backend_commit':'a'*40,
                    'source_capture_group':group,'source_event_group':group,'parent_scenario_group':group}
                self.traces.append(trace)
                m={k:v for k,v in trace.items() if k!='context'}
                m.update(split=split,row=i,human_review_status='APPROVED',human_label=label,
                    reviewer_role='UNIT_FIXTURE_NOT_REAL_REVIEW',rationale='Artificial gate test only',
                    blind_first_pass=True,reviewed_at_utc='2026-01-01T00:00:00+00:00',
                    trace_hash=hashlib.sha256(json.dumps(trace,sort_keys=True,separators=(',',':')).encode()).hexdigest())
                self.meta.append(m)
                rows.append({'state':state,'questions':learning.QUESTIONS,'expected':{'operational_state':label}})
            (self.directory/(split+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
        self.save()

    def save(self):
        learning.write(self.directory/'metadata.json',self.meta)
        learning.write(self.directory/'traces.json',self.traces)
        learning.write(self.directory/'manifest.json',{'backend_ack':{'person1_approved':True,'commit':'a'*40,
            'reviewer_role':'UNIT_FIXTURE_NOT_REAL_ACK','trusted_context_mapping_approved':True,
            'network_disabled':True,'order_execution_disabled':True},'hashes':{p.name:learning.sha(p)
                for p in self.directory.iterdir() if p.name!='manifest.json'}})

    def tearDown(self):
        self.patch.stop(); self.temp.cleanup()

    def test_structural_unit_fixture(self):
        _,rows=learning.validate_bundle(self.directory,self.control)
        self.assertEqual(len(rows['train']),60)

    def test_pending_review_blocks(self):
        self.meta[0]['human_review_status']='PENDING'; self.save()
        with self.assertRaisesRegex(ValueError,'unreviewed'): learning.validate_bundle(self.directory,self.control)

    def test_ai_review_train_provenance_accepted(self):
        self.meta[0].update(blind_first_pass=False,ai_assisted=True,review_method='AI_ASSISTED_HUMAN_CONFIRMED')
        self.save()
        learning.validate_bundle(self.directory,self.control)

    def test_ai_review_not_promoted_to_blind_validation(self):
        self.meta[60].update(blind_first_pass=False,ai_assisted=True,review_method='AI_ASSISTED_HUMAN_CONFIRMED')
        self.save()
        with self.assertRaisesRegex(ValueError,'independent blind review'): learning.validate_bundle(self.directory,self.control)

    def test_cross_split_group_blocks(self):
        index=60
        self.meta[index]['source_event_group']=self.meta[0]['source_event_group']
        self.save()
        with self.assertRaisesRegex(ValueError,'leakage'): learning.validate_bundle(self.directory,self.control)

    def test_missing_actual_trace_blocks(self):
        self.traces.pop(); self.save()
        with self.assertRaisesRegex(ValueError,'trace evidence'): learning.validate_bundle(self.directory,self.control)

    def test_modified_file_blocks(self):
        with (self.directory/'train.jsonl').open('a') as handle: handle.write('\n')
        with self.assertRaisesRegex(ValueError,'integrity'): learning.validate_bundle(self.directory,self.control)

    def test_failed_control_blocks(self):
        learning.write(self.control,{'control_passed':False,'protected_files_unchanged':True})
        with self.assertRaisesRegex(ValueError,'control'): learning.validate_bundle(self.directory,self.control)

    def test_protected_model_change_blocks(self):
        f=self.root/'dummy-weight'; f.write_text('before')
        learning.write(self.control.parent/'before.json',{'protected_hashes':{'dummy-weight':learning.sha(f)}})
        f.write_text('after')
        with self.assertRaisesRegex(ValueError,'protected'): learning.validate_bundle(self.directory,self.control)


if __name__=='__main__':
    unittest.main()
