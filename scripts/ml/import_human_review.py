"""Check/import human-filled review JSON; never predicts or fills an answer.

Default check is read-only. Apply requires an explicit human-review attestation and
the loopback review server to be stopped; existing conflicting decisions are preserved.
"""
import argparse
from datetime import datetime, timezone
import errno
import hashlib
import json
from pathlib import Path
import socket

from human_review_app import ROOT, ReviewStore, atomic, digest
from reviewed_learning import LABELS


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


def check(source,directory,ai_assisted=False):
    source=source.resolve()
    if not source.is_relative_to(ROOT.parent/'outputs'):
        raise ValueError('review JSON must be explicitly supplied in task outputs directory')
    store=ReviewStore(directory)
    raw=source.read_bytes()
    obj=json.loads(raw.decode('utf-8-sig'))
    if not isinstance(obj,dict):
        raise ValueError('review document must be a JSON object')
    if obj.get('kaynak_sha256')!=store.source_hash or obj.get('backend_commit')!=store.commit:
        raise ValueError('review JSON source hash/backend commit mismatch')
    rows=obj.get('ornekler')
    if not isinstance(rows,list) or len(rows)!=len(store.cases) or len(rows)!=120:
        raise ValueError('exactly 120 original examples must remain in the file')
    seen=set(); ready=[]; pending=0; unresolved=0
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'ornek_no','case_id','senaryo','emir_turu','yon','olgular','insan_incelemesi'}:
            raise ValueError('case fields must match blinded export; no model/expected labels')
        case_id=row.get('case_id')
        if not isinstance(case_id,str) or case_id not in store.by_id or case_id in seen:
            raise ValueError('missing, duplicate or unknown case ID')
        seen.add(case_id)
        original=store.by_id[case_id]
        details=original.get('review_context',{})
        if canonical(row.get('olgular'))!=canonical(original['context']):
            raise ValueError('case facts changed; human labels cannot silently alter evidence')
        if (row.get('senaryo')!=details.get('description','') or row.get('emir_turu')!=details.get('order_type','')
            or row.get('yon')!=('ALIS' if details.get('side')=='buy' else 'SATIS')):
            raise ValueError('case description/order fixture changed')
        review=row.get('insan_incelemesi')
        if not isinstance(review,dict) or set(review)!={'karar','gerekce','inceleyen_rolu','durum'}:
            raise ValueError('human review fields do not match exported template')
        label=review['karar']; status=review['durum']
        if status not in (('PENDING','APPROVED','UNRESOLVED','AI_SUGGESTED') if ai_assisted else ('PENDING','APPROVED','UNRESOLVED')):
            raise ValueError('invalid review status; use PENDING, APPROVED or UNRESOLVED')
        if label is None and status=='PENDING':
            pending+=1
            continue  # Draft notes do not become an approved or unresolved decision.
        if label is None and status=='UNRESOLVED':
            unresolved+=1
        elif label not in LABELS or status=='UNRESOLVED':
            raise ValueError('invalid or missing decision')
        reason=review['gerekce']; role=review['inceleyen_rolu']
        if not isinstance(reason,str) or not 10<=len(reason.strip())<=2000:
            raise ValueError('each submitted decision needs a 10..2000 character rationale')
        if not isinstance(role,str) or not 2<=len(role.strip())<=80:
            raise ValueError('each submitted decision needs an actual reviewer role/alias')
        ready.append({'case_id':case_id,'human_label':label or '',
            'review_status':'UNRESOLVED' if status=='UNRESOLVED' else 'APPROVED',
            'reviewer_role':'User-confirmed final reviewer; AI analysis assistance' if ai_assisted else role.strip(),
            'rationale':reason.strip(),'blind_first_pass':not ai_assisted,
            'ai_assisted':ai_assisted,'source_review_status':status,'source_reviewer_role':role.strip(),
            'review_method':'AI_ASSISTED_HUMAN_CONFIRMED' if ai_assisted else 'HUMAN_JSON_REVIEW'})
    return store,ready,{'examples':120,'decisions_ready':len(ready)-unresolved,
        'unresolved':unresolved,'pending':pending,'source_file_sha256':hashlib.sha256(raw).hexdigest(),
        'write_performed':False,'human_confirmation_still_required':True,'training_approved':False,
        'ai_assisted':ai_assisted,'blind_first_pass':not ai_assisted}


def server_stopped():
    # Any listener on the review port blocks import to prevent stale in-memory UI overwrites.
    with socket.socket() as client:
        client.settimeout(3)
        code=client.connect_ex(('127.0.0.1',8768))
        if code==0:
            return False
        if code in (errno.ECONNREFUSED,10061):
            return True
        raise RuntimeError('cannot prove review server stopped; import blocked')


def apply(source,directory,confirmed=False,ai_assisted=False):
    if not confirmed:
        raise ValueError('explicit confirmation of actual human review required; no approvals imported')
    if not server_stopped():
        raise ValueError('review server still running; stop verified review process before import')
    store,ready,summary=check(source,directory,ai_assisted)
    if not ready:
        raise ValueError('no completed human decisions; empty rows cannot be approved')
    additions=[]
    for row in ready:
        old=store.state['entries'].get(row['case_id'])
        if old:
            if any(old.get(k)!=row[k] for k in ('human_label','review_status','reviewer_role','rationale')):
                raise ValueError('conflicting prior human review; reconcile explicitly instead of overwriting')
        else:
            additions.append(row)
    before_ledger=digest(store.file) if store.file.exists() else None
    state=json.loads(json.dumps(store.state))
    now=datetime.now(timezone.utc).isoformat()
    for row in additions:
        entry={k:row[k] for k in ('human_label','review_status','reviewer_role','rationale')}
        entry.update(reviewed_at_utc=now,submitted_at_utc=now,
            review_time_source='explicit import confirmation; original reading time not collected',
            blind_first_pass=row['blind_first_pass'],ai_assisted=row['ai_assisted'],
            review_method=row['review_method'],source_review_status=row['source_review_status'],
            source_reviewer_role=row['source_reviewer_role'],
            submitted_via='human-confirmed-json-import',
            source_file_sha256=summary['source_file_sha256'])
        event={'revision':state['revision']+1,'case_id':row['case_id'],'entry':entry,
            'previous_hash':state['audit'][-1]['hash'] if state['audit'] else store.source_hash}
        event['hash']=hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest()
        state['audit'].append(event); state['entries'][row['case_id']]=entry
        state['revision']+=1
    # Protect against accidental concurrent edits while validation was in progress.
    if (digest(store.file) if store.file.exists() else None)!=before_ledger:
        raise RuntimeError('review ledger changed during import; no write')
    if digest(source.resolve())!=summary['source_file_sha256']:
        raise RuntimeError('human source JSON changed during import; no write')
    if additions:
        if store.file.exists():
            backup=store.directory/f'human_reviews.before-json-{before_ledger[:12]}.json'
            if not backup.exists():
                with backup.open('xb') as handle:
                    handle.write(store.file.read_bytes())
        atomic(store.file,state)
        store.state=state; store.export_csv_file()
        approved=sum(e['review_status']=='APPROVED' for e in state['entries'].values())
        atomic(store.directory/'review_progress.json',{'total':120,'approved':approved,
            'unresolved':sum(e['review_status']=='UNRESOLVED' for e in state['entries'].values()),
            'human_review_complete':approved==120,'training_approved':False,
            'source_independence_approved':False,'backend_context_mapping_approved':False,
            'updated_at':now})
    return {**summary,'write_performed':bool(additions),'new_reviews_imported':len(additions),
        'human_confirmation_still_required':False,'training_approved':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('check','apply'))
    parser.add_argument('source',type=Path)
    parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--confirm-human-review',action='store_true',
        help='Only after the human explicitly confirms these are their actual decisions')
    parser.add_argument('--ai-assisted',action='store_true',
        help='Preserve AI-assisted provenance; requires human confirmation for apply, never claims blind review')
    args=parser.parse_args()
    try:
        result=check(args.source,args.pack,args.ai_assisted)[2] if args.mode=='check' else apply(args.source,args.pack,args.confirm_human_review,args.ai_assisted)
        print(json.dumps(result,ensure_ascii=False))
    except (ValueError,RuntimeError) as exc:
        parser.exit(2,str(exc)+'\n')
