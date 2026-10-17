"""Ephemeral UNIT_ONLY import fixtures; never approves user review cases."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import human_review_app as app
import import_human_review as importer
from reviewed_learning import BOOLS


class JsonImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='aegis-import-UNIT_ONLY-')
        self.root=Path(self.tmp.name).resolve()/'repo'; self.root.mkdir()
        self.patches=[patch.object(app,'ROOT',self.root),patch.object(importer,'ROOT',self.root),
            patch.object(importer,'server_stopped',return_value=True)]
        for p in self.patches:p.start()
        self.pack=self.root/'data/reviewed_learning/UNIT_ONLY'; self.pack.mkdir(parents=True)
        self.output=self.root.parent/'outputs'; self.output.mkdir()
        self.source=self.output/'unit-review.json'
        cases=[]; rows=[]
        for i in range(120):
            context={'symbol':'BTC-USDT','site':'tr','source_mode':'MOCK','quantity':str(i+1),
                'intent_requested':False,'feed_age_seconds':2,**{key:False for key in BOOLS}}
            cases.append({'case_id':f'UNIT_ONLY_{i}','context':context,
                'review_context':{'description':'Yapay birim testi; gerçek inceleme değil.',
                    'order_type':'limit','side':'buy'}})
            rows.append({'case_id':f'UNIT_ONLY_{i}','ornek_no':i+1,'senaryo':cases[-1]['review_context']['description'],
                'emir_turu':'limit','yon':'ALIS','olgular':copy.deepcopy(context),
                'insan_incelemesi':{'karar':None,'gerekce':'','inceleyen_rolu':'','durum':'PENDING'}})
        (self.pack/'draft_cases.json').write_text(json.dumps(cases),encoding='utf-8')
        source_hash=app.digest(self.pack/'draft_cases.json')
        (self.pack/'review_manifest.json').write_text(json.dumps({'backend_commit':'a'*40,
            'hashes':{'draft_cases.json':source_hash}}),encoding='utf-8')
        self.doc={'kaynak_sha256':source_hash,'backend_commit':'a'*40,'ornekler':rows}
        self.save()

    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()

    def save(self):
        self.source.write_text(json.dumps(self.doc,ensure_ascii=False),encoding='utf-8')

    def decision(self):
        self.doc['ornekler'][0]['insan_incelemesi'].update(karar='REVIEW',
            gerekce='Bu yalnızca birim testi kararıdır; insan onayı değildir.',inceleyen_rolu='UNIT_TEST_ONLY')
        self.save()

    def test_empty_file_check_no_writes(self):
        result=importer.check(self.source,self.pack)[2]
        self.assertEqual(result['pending'],120)
        self.assertEqual(result['decisions_ready'],0)
        self.assertFalse((self.pack/'human_reviews.json').exists())

    def test_no_confirmation_no_write(self):
        self.decision()
        with self.assertRaises(ValueError): importer.apply(self.source,self.pack)
        self.assertFalse((self.pack/'human_reviews.json').exists())

    def test_source_facts_change_rejected(self):
        self.doc['ornekler'][0]['olgular']['feed_age_seconds']=90; self.save()
        with self.assertRaisesRegex(ValueError,'facts changed'): importer.check(self.source,self.pack)

    def test_boolean_numeric_substitution_rejected(self):
        self.doc['ornekler'][0]['olgular']['unknown_order']=0; self.save()
        with self.assertRaisesRegex(ValueError,'facts changed'): importer.check(self.source,self.pack)

    def test_duplicate_cases_rejected(self):
        self.doc['ornekler'][1]=self.doc['ornekler'][0]; self.save()
        with self.assertRaises(ValueError): importer.check(self.source,self.pack)

    def test_incomplete_rationale_not_approved(self):
        self.decision(); self.doc['ornekler'][0]['insan_incelemesi']['gerekce']=''; self.save()
        with self.assertRaisesRegex(ValueError,'rationale'): importer.apply(self.source,self.pack,True)

    def test_live_server_blocks_import(self):
        self.decision()
        with patch.object(importer,'server_stopped',return_value=False):
            with self.assertRaisesRegex(ValueError,'server still'): importer.apply(self.source,self.pack,True)

    def test_apply_partial_only_completed_explicit_decisions(self):
        self.decision(); old=app.digest(self.source)
        result=importer.apply(self.source,self.pack,True)
        self.assertEqual(result['new_reviews_imported'],1)
        self.assertEqual(app.digest(self.source),old)
        state=json.loads((self.pack/'human_reviews.json').read_text(encoding='utf-8'))
        self.assertEqual(len(state['entries']),1)
        self.assertEqual(state['entries']['UNIT_ONLY_0']['submitted_via'],'human-confirmed-json-import')
        progress=json.loads((self.pack/'review_progress.json').read_text(encoding='utf-8'))
        self.assertFalse(progress['human_review_complete'])
        self.assertFalse(progress['training_approved'])

    def test_repeat_import_idempotent(self):
        self.decision(); importer.apply(self.source,self.pack,True)
        old=app.digest(self.pack/'human_reviews.json')
        self.assertFalse(importer.apply(self.source,self.pack,True)['write_performed'])
        self.assertEqual(app.digest(self.pack/'human_reviews.json'),old)

    def test_prior_conflicting_decision_preserved(self):
        self.decision(); importer.apply(self.source,self.pack,True)
        old=app.digest(self.pack/'human_reviews.json')
        self.doc['ornekler'][0]['insan_incelemesi']['karar']='HALT'; self.save()
        with self.assertRaisesRegex(ValueError,'conflicting'): importer.apply(self.source,self.pack,True)
        self.assertEqual(app.digest(self.pack/'human_reviews.json'),old)

    def test_no_model_answers_allowed_in_case(self):
        self.doc['ornekler'][0]['model_prediction']='CONTINUE'; self.save()
        with self.assertRaises(ValueError): importer.check(self.source,self.pack)

    def test_unresolved_stays_unresolved(self):
        self.decision()
        self.doc['ornekler'][0]['insan_incelemesi'].update(karar=None,durum='UNRESOLVED'); self.save()
        importer.apply(self.source,self.pack,True)
        progress=json.loads((self.pack/'review_progress.json').read_text(encoding='utf-8'))
        self.assertEqual(progress['approved'],0)
        self.assertEqual(progress['unresolved'],1)

    def test_ai_suggestions_need_declared_mode(self):
        self.decision(); self.doc['ornekler'][0]['insan_incelemesi']['durum']='AI_SUGGESTED'; self.save()
        with self.assertRaises(ValueError): importer.check(self.source,self.pack)

    def test_ai_mode_still_requires_human_confirmation(self):
        self.decision(); self.doc['ornekler'][0]['insan_incelemesi']['durum']='AI_SUGGESTED'; self.save()
        with self.assertRaises(ValueError): importer.apply(self.source,self.pack,False,True)
        self.assertFalse((self.pack/'human_reviews.json').exists())

    def test_ai_assisted_confirmation_not_blind(self):
        self.decision(); self.doc['ornekler'][0]['insan_incelemesi'].update(durum='AI_SUGGESTED',inceleyen_rolu='AI UNIT FIXTURE'); self.save()
        importer.apply(self.source,self.pack,True,True)
        state=json.loads((self.pack/'human_reviews.json').read_text(encoding='utf-8'))
        entry=state['entries']['UNIT_ONLY_0']
        self.assertFalse(entry['blind_first_pass'])
        self.assertTrue(entry['ai_assisted'])
        self.assertEqual(entry['source_review_status'],'AI_SUGGESTED')
        self.assertEqual(entry['source_reviewer_role'],'AI UNIT FIXTURE')
        self.assertEqual(entry['review_method'],'AI_ASSISTED_HUMAN_CONFIRMED')


if __name__=='__main__':
    unittest.main()
