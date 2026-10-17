"""Temporary UI test fixtures ONLY; never submits or approves production review cases."""
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import human_review_app as app
from reviewed_learning import BOOLS


class HumanReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='aegis-review-UNIT_ONLY-')
        self.root=Path(self.tmp.name).resolve()
        self.patch=patch.object(app,'ROOT',self.root); self.patch.start()
        self.directory=self.root/'data/reviewed_learning/UNIT_ONLY'; self.directory.mkdir(parents=True)
        context={'symbol':'BTC-USDT','site':'tr','source_mode':'MOCK','quantity':'0.0001',
            'intent_requested':False,'feed_age_seconds':2,**{key:False for key in BOOLS}}
        case={'case_id':'UNIT_ONLY_opaque','context':context,
            'review_context':{'description':'Türkçe örnek açıklaması','order_type':'market','side':'buy',
                'backend_reasons':['MUST_NOT_BE_EXPOSED'],'backend_approved':True},
            'expected':'MUST_NOT_BE_EXPOSED','model_prediction':'MUST_NOT_BE_EXPOSED'}
        self.source=self.directory/'draft_cases.json'
        self.source.write_text(json.dumps([case],ensure_ascii=False),encoding='utf-8')
        (self.directory/'review_manifest.json').write_text(json.dumps({'backend_commit':'a'*40,
            'hashes':{'draft_cases.json':app.digest(self.source)}}),encoding='utf-8')
        self.store=app.ReviewStore(self.directory)

    def tearDown(self):
        self.patch.stop(); self.tmp.cleanup()

    def payload(self):
        return {'case_id':'UNIT_ONLY_opaque','human_label':'REVIEW','review_status':'APPROVED',
            'reviewer_role':'UNIT_TEST_NOT_HUMAN_REVIEW','rationale':'Bu yalnızca geçici birim testi verisidir.',
            'revision':0}

    def test_utf8_and_blind_allowlist(self):
        view=self.store.public()
        self.assertIn('Türkçe',view['cases'][0]['description'])
        self.assertNotIn('MUST_NOT_BE_EXPOSED',json.dumps(view))

    def test_start_empty_no_approval(self):
        self.assertEqual(self.store.reviews()['entries'],{})
        self.assertFalse(self.store.file.exists())

    def test_persist_resume_utf8_and_progress(self):
        self.store.save(self.payload())
        reloaded=app.ReviewStore(self.directory)
        self.assertIn('yalnızca',reloaded.reviews()['entries']['UNIT_ONLY_opaque']['rationale'])
        self.assertTrue((self.directory/'blind_review.csv').exists())
        progress=json.loads((self.directory/'review_progress.json').read_text(encoding='utf-8'))
        self.assertFalse(progress['training_approved'])

    def test_no_bulk_endpoint(self):
        payload=self.payload(); payload['approve_all']=True
        with self.assertRaises(ValueError): self.store.save(payload)

    def test_pending_rationale_rejected(self):
        payload=self.payload(); payload['rationale']=''
        with self.assertRaises(ValueError): self.store.save(payload)

    def test_conflicting_revision_rejected(self):
        self.store.save(self.payload())
        with self.assertRaises(RuntimeError): self.store.save(self.payload())

    def test_unresolved_not_approved(self):
        payload=self.payload(); payload.update(review_status='UNRESOLVED',human_label='')
        self.store.save(payload)
        p=json.loads((self.directory/'review_progress.json').read_text(encoding='utf-8'))
        self.assertEqual(p['approved'],0)
        self.assertEqual(p['unresolved'],1)

    def test_modified_source_blocks_save(self):
        self.source.write_text('[]',encoding='utf-8')
        with self.assertRaises(RuntimeError): self.store.save(self.payload())

    def test_manual_edit_cannot_erase_ai_assistance(self):
        self.store.state['entries']['UNIT_ONLY_opaque']={'ai_assisted':True,'blind_first_pass':False,
            'review_method':'AI_ASSISTED_HUMAN_CONFIRMED','source_review_status':'AI_SUGGESTED'}
        self.store.save(self.payload())
        entry=self.store.state['entries']['UNIT_ONLY_opaque']
        self.assertTrue(entry['ai_assisted'])
        self.assertFalse(entry['blind_first_pass'])
        self.assertEqual(entry['source_review_status'],'AI_SUGGESTED')

    def test_loopback_host_origin_and_safe_endpoint(self):
        server=app.create_server(self.store,0)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
            conn.request('GET','/api/cases'); response=conn.getresponse()
            self.assertEqual(response.status,200)
            self.assertNotIn('MUST_NOT_BE_EXPOSED',response.read().decode())
            conn.request('POST','/api/review',body=json.dumps(self.payload()),headers={'Content-Type':'application/json','Origin':'https://wrong.example'})
            response=conn.getresponse(); self.assertEqual(response.status,403); response.read()
            self.assertEqual(self.store.reviews()['entries'],{})
            conn.close()
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__=='__main__':
    unittest.main()
