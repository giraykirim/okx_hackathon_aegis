"""Adapter unit tests: no network, model, auth or order calls."""
from datetime import datetime,timezone
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ml.context_adapter import adapt_legacy, BOOLS
from reviewed_learning import state_from_context

NOW=datetime(2026,10,17,12,tzinfo=timezone.utc)


def envelope():
    return {'state':{'symbol':'BTC-USDT','observed_at':'2026-10-17T11:59:58+00:00',
        'account_known':True,'price':'50000','ask':'50001','bid':'49999'},
        'run_id':'UNIT_ONLY','correlation_id':'UNIT_ONLY'}


def trusted():
    return {'site':'tr','source_mode':'MOCK','intent_requested':False,'quantity':'0.0001',
        **{key:False for key in BOOLS},'account_known':True}


class AdapterTests(unittest.TestCase):
    def test_legacy_alone_abstains(self):
        result=adapt_legacy(envelope(),now=NOW)
        self.assertFalse(result['eligible_for_shadow_inference'])
        self.assertEqual(result['fallback']['label'],'REVIEW')
        self.assertTrue(result['fallback']['abstained'])
        self.assertIsNone(result['facts']['unknown_order'])
        self.assertIsNone(result['facts']['intent_requested'])

    def test_approval_not_inferred(self):
        result=adapt_legacy(envelope(),trusted_context=trusted(),now=NOW)
        self.assertFalse(result['eligible_for_shadow_inference'])

    def test_complete_approved_test_context_matches_training_serializer(self):
        result=adapt_legacy(envelope(),trusted_context=trusted(),mapping_approved=True,now=NOW)
        self.assertTrue(result['eligible_for_shadow_inference'])
        state,missing=state_from_context(result['facts'])
        self.assertFalse(missing)
        self.assertEqual(state,result['normalized_state'])
        self.assertFalse(result['execution_authority'])
        self.assertIsNone(result['fallback'])

    def test_unknown_context_never_defaults_false(self):
        context=trusted(); context['unknown_order']=None
        result=adapt_legacy(envelope(),trusted_context=context,mapping_approved=True,now=NOW)
        self.assertFalse(result['eligible_for_shadow_inference'])

    def test_naive_timestamp_missing(self):
        request=envelope(); request['state']['observed_at']='2026-10-17T12:00:00'
        result=adapt_legacy(request,now=NOW)
        self.assertIsNone(result['facts']['feed_age_seconds'])

    def test_pii_in_observation_not_copied(self):
        request=envelope(); request['state']['untrusted_text']='UNIT_SECRET_SENTINEL'
        result=adapt_legacy(request,now=NOW)
        self.assertNotIn('UNIT_SECRET_SENTINEL',str(result))
        self.assertNotIn('UNIT_ONLY',str(result))

    def test_extra_requester_context_rejected(self):
        request=envelope(); request['requester_context']=trusted()
        with self.assertRaises(ValueError): adapt_legacy(request,now=NOW)

    def test_boolean_fake_numeric_quantity_rejected(self):
        context=trusted(); context['quantity']=True
        with self.assertRaises(ValueError): adapt_legacy(envelope(),trusted_context=context,now=NOW)

    def test_conflicting_account_rejected(self):
        context=trusted(); context['account_known']=False
        with self.assertRaises(ValueError): adapt_legacy(envelope(),trusted_context=context,now=NOW)

    def test_no_new_site_or_mode_authority(self):
        for update in ({'site':'global'},{'source_mode':'LIVE'},{'extra_private_data':'UNIT_ONLY'}):
            with self.assertRaises(ValueError): adapt_legacy(envelope(),trusted_context={**trusted(),**update},now=NOW)


if __name__=='__main__':
    unittest.main()
