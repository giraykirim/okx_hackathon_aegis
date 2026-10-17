"""Apply ONLY the explicit human adjudication for ten 40s stale-feed cases.

Original review, source JSON, rationale and every prior decision stay in history.
No model, backend ACK, data split or training gate is automatically approved.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json

from human_review_app import ReviewStore, atomic, digest
from import_human_review import server_stopped


def verify_ledger(state,source_hash):
    previous=source_hash
    replay={}
    for revision,event in enumerate(state['audit'],1):
        if event['revision']!=revision or event['previous_hash']!=previous:
            raise ValueError('review chain revision/link mismatch')
        unsigned={k:v for k,v in event.items() if k!='hash'}
        if hashlib.sha256(json.dumps(unsigned,sort_keys=True).encode()).hexdigest()!=event['hash']:
            raise ValueError('review chain hash mismatch')
        previous=event['hash']; replay[event['case_id']]=event['entry']
    if len(state['audit'])!=state['revision'] or replay!=state['entries']:
        raise ValueError('review materialized entries mismatch')


def apply(directory,human_confirmed=False):
    if not human_confirmed:
        raise ValueError('explicit human stale-feed adjudication required')
    if not server_stopped():
        raise ValueError('stop verified review server first')
    store=ReviewStore(directory)
    verify_ledger(store.state,store.source_hash)
    if len(store.state['entries'])!=120:
        raise ValueError('all original human reviews required before targeted adjudication')
    cases=[c for c in store.cases if c['source_event_group']=='stale']
    if len(cases)!=10 or any(c['context']['feed_age_seconds']!=40 for c in cases):
        raise ValueError('expected exactly ten 40-second stale-feed examples')
    before_hash=digest(store.file)
    state=json.loads(json.dumps(store.state))
    updated=[]; now=datetime.now(timezone.utc).isoformat()
    for case in cases:
        case_id=case['case_id']; prior=state['entries'][case_id]
        if prior.get('human_label')=='HALT' and prior.get('adjudication_id')=='USER_STALE40_HALT_20261017':
            continue
        if prior.get('human_label')!='REVIEW' or prior.get('review_status')!='APPROVED':
            raise ValueError('unexpected prior label, requires separate human resolution')
        entry={**prior,'human_label':'HALT','reviewed_at_utc':now,'adjudicated_at_utc':now,
            'prior_rationale':prior['rationale'],
            'rationale':'Kullanıcı açık talimatıyla mevcut politika uyumu: 40 saniye veri yaşı 15 saniyelik sınırı aşar; veri yenilenip doğrulanana kadar HALT. Önceki REVIEW gerekçesi geçmişte korunur.',
            'adjudication_id':'USER_STALE40_HALT_20261017',
            'adjudication_source':'Explicit user reply: Mevcut politikayla uyumlu HALT olarak düzelt (önerilen)',
            'blind_first_pass':False,'ai_assisted':True,
            'review_method':'AI_ASSISTED_HUMAN_CONFIRMED',
            'submitted_via':'explicit-human-stale-adjudication'}
        event={'revision':state['revision']+1,'case_id':case_id,'entry':entry,
            'previous_hash':state['audit'][-1]['hash']}
        event['hash']=hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest()
        state['audit'].append(event); state['entries'][case_id]=entry; state['revision']+=1
        updated.append(case_id)
    verify_ledger(state,store.source_hash)
    if updated:
        if digest(store.file)!=before_hash:
            raise ValueError('concurrent review write; refusing overwrite')
        backup=store.directory/f'human_reviews.before-stale-{before_hash[:12]}.json'
        with backup.open('xb') as handle:
            handle.write(store.file.read_bytes())
        atomic(store.file,state)
        store.state=state; store.export_csv_file()
        atomic(store.directory/'review_progress.json',{'total':120,'approved':120,'unresolved':0,
            'human_review_complete':True,'training_approved':False,'source_independence_approved':False,
            'backend_context_mapping_approved':False,'blind_first_pass':False,'ai_assisted':True,
            'label_counts':dict(Counter(e['human_label'] for e in state['entries'].values())),
            'updated_at':now})
    return {'updated_case_ids':updated,'changed':len(updated),'old_review_backup_sha256':before_hash,
        'label_counts':dict(Counter(e['human_label'] for e in state['entries'].values())),
        'ledger_chain_valid':True,'training_approved':False}


if __name__=='__main__':
    from pathlib import Path
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--confirm-user-stale-halt',action='store_true')
    args=parser.parse_args()
    print(json.dumps(apply(args.directory,args.confirm_user_stale_halt),ensure_ascii=False))
