"""Tamper detection tests with UNIT_ONLY event data, never user decisions."""
import copy
import hashlib
import json
import unittest
from adjudicate_stale_review import verify_ledger, apply


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.source='a'*64
        event={'revision':1,'case_id':'UNIT_ONLY','entry':{'human_label':'REVIEW'},'previous_hash':self.source}
        event['hash']=hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest()
        self.state={'revision':1,'audit':[event],'entries':{'UNIT_ONLY':copy.deepcopy(event['entry'])}}

    def test_valid_chain(self):
        verify_ledger(self.state,self.source)

    def test_changed_entry_detected(self):
        self.state['entries']['UNIT_ONLY']['human_label']='HALT'
        with self.assertRaises(ValueError): verify_ledger(self.state,self.source)

    def test_changed_event_detected(self):
        self.state['audit'][0]['entry']['human_label']='HALT'
        with self.assertRaises(ValueError): verify_ledger(self.state,self.source)

    def test_changed_source_detected(self):
        with self.assertRaises(ValueError): verify_ledger(self.state,'b'*64)

    def test_revision_mismatch_detected(self):
        self.state['revision']=2
        with self.assertRaises(ValueError): verify_ledger(self.state,self.source)

    def test_no_implicit_adjudication(self):
        with self.assertRaisesRegex(ValueError,'explicit human'): apply(None,False)


if __name__=='__main__':
    unittest.main()
