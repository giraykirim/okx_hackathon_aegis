"""Oracle precedence, realistic lifecycle subsets and no-leakage structural checks."""
import copy
import json
from pathlib import Path
import unittest
from trade_lifecycle_data import oracle, trace_fixture, ROOT, REGULAR, ALGO


BASE = {'symbol':'BTC-USDT','site':'tr','source_mode':'OKX_DEMO','feed_age_seconds':2,
    'intent_requested':True,'quantity':'0.0001','account_known':True,'approval_available':True,
    'permission':'granted','journal':'clear','reconciliation':'verified','rpc_outcome':'not_submitted',
    'phase':'preflight'}


class LifecycleTests(unittest.TestCase):
    def result(self, **updates):
        return oracle({**BASE, **updates})[0]

    def test_continue_is_only_monitoring(self):
        self.assertEqual(self.result(), 'CONTINUE')

    def test_submit_timeout_not_ordinary_read_timeout(self):
        self.assertEqual(self.result(rpc_outcome='timeout_after_submit'), 'HALT')
        self.assertEqual(self.result(rpc_outcome='transport_failed_before_submit'), 'REVIEW')

    def test_halt_precedes_review(self):
        self.assertEqual(self.result(unknown_order=True, account_known=False), 'HALT')

    def test_missing_required_context(self):
        for field in ('account_known','approval_available'):
            self.assertEqual(self.result(**{field:False}), 'REVIEW')

    def test_monitoring_needs_no_trade_permission(self):
        self.assertEqual(self.result(intent_requested=False,account_known=False,
            approval_available=False,permission='not_required'), 'CONTINUE')

    def test_ack_is_not_terminal_confirmation(self):
        for outcome in ('cancel_ack_only','amend_ack_only'):
            self.assertEqual(self.result(rpc_outcome=outcome), 'REVIEW')

    def test_conflicting_receipts(self):
        self.assertEqual(self.result(reconciliation='conflict'), 'HALT')

    def test_no_unsupported_symbol_shortcut_in_main_data(self):
        self.assertEqual(self.result(symbol='ETH-USDT'), 'HALT')  # Existing scope unchanged.

    def test_invalid_quantities(self):
        for quantity in ('NaN','-1','0','not-a-number',True):
            self.assertEqual(self.result(quantity=quantity), 'HALT')

    def test_boundaries(self):
        self.assertEqual(self.result(feed_age_seconds=15), 'CONTINUE')
        self.assertEqual(self.result(feed_age_seconds=15.001), 'HALT')
        self.assertEqual(self.result(feed_age_seconds=None), 'REVIEW')

    def test_fok_never_partially_filled(self):
        for kind in ('fok','market'):
            facts = {**BASE,'phase':'reconciled'}
            trace = trace_fixture(facts, {'instId':'BTC-USDT','ordType':kind,'sz':'0.00002'}, 1)
            self.assertNotEqual(trace[-1]['response_subset']['state'],'partially_filled')

    def test_market_amend_not_fabricated(self):
        facts = {**BASE,'phase':'reconciling'}
        trace = trace_fixture(facts, {'instId':'BTC-USDT','ordType':'market','sz':'0.00002'}, 1)
        self.assertEqual(facts['rpc_outcome'],'place_ack_only')
        self.assertEqual(len(trace),2)

    def test_algo_effective_not_treated_as_filled(self):
        for kind in ALGO:
            facts = {**BASE,'phase':'terminal'}
            trace = trace_fixture(facts, {'instId':'BTC-USDT','ordType':kind,'sz':'0.00002'}, 0)
            self.assertEqual(trace[-1]['response_subset']['state'],'canceled')
            self.assertNotIn('accFillSz',trace[-1]['response_subset'])

    def test_data_targets_separate_from_input(self):
        capture = ROOT/'data/trade_lifecycle/20261017T103022Z'
        if not capture.exists():
            self.skipTest('capture not present')
        rows = [json.loads(line) for line in (capture/'candidates.jsonl').read_text().splitlines()]
        metadata = json.loads((capture/'metadata.json').read_text())
        self.assertEqual(len(rows),720)
        for row, meta in zip(rows, metadata):
            state = json.loads(row['state'])
            self.assertNotIn('expected',state)
            self.assertNotIn('oracle_reasons',state)
            self.assertEqual(state['operational']['symbol'],'BTC-USDT')
            self.assertEqual(meta['human_review_status'],'PENDING_HUMAN_REVIEW')
            self.assertFalse(meta['request_executed'])

    def test_fixture_quantities_match_real_instrument_grid(self):
        from decimal import Decimal
        capture = ROOT/'data/trade_lifecycle/20261017T103022Z'
        if not capture.exists():
            self.skipTest('capture not present')
        instrument = next(x for x in json.loads((ROOT/'data/atk_spot/20261017T102105Z/instruments.json').read_text())
            if x['instId']=='BTC-USDT')
        lot, tick, minimum = (Decimal(instrument[k]) for k in ('lotSz','tickSz','minSz'))
        for fixture in json.loads((capture/'fixtures.json').read_text()):
            request = fixture['request_fixture']
            size = Decimal(request['sz'])
            self.assertGreaterEqual(size, minimum)
            self.assertEqual(size % lot, 0)
            self.assertEqual(request['tdMode'], 'cash')
            for key in ('px','pxLimit','triggerPx','slTriggerPx','tpTriggerPx'):
                if key in request:
                    self.assertEqual(Decimal(request[key]) % tick, 0)


if __name__ == '__main__':
    unittest.main()
