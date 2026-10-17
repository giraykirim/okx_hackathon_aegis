"""Freeze AI-assisted human-confirmed UNSPLIT labels; audit without training.

No labels/splits/ACK invented. Verify source, ledger chain, history and policy.
"""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ml.label_policy import classify, QUESTIONS, VERSION
from adjudicate_stale_review import verify_ledger
from human_review_app import ReviewStore, digest


def main():
    pack=ROOT/'data/reviewed_learning/review-1c9cf35-v1'
    store=ReviewStore(pack)
    ledger=store.state
    verify_ledger(ledger,store.source_hash)
    assert len(ledger['entries'])==120
    source=ROOT.parent/'outputs/120-KARAR-AI-DESTEKLI-KAYNAK.json'
    source_hash=digest(source)
    assert source_hash=='fe77a64e2318afaddd428c1b8820797946bd39cb20fa6c8224c087cc053d4070'
    original=json.loads(source.read_text(encoding='utf-8-sig'))
    original_labels={r['case_id']:r['insan_incelemesi']['karar'] for r in original['ornekler']}
    rows=[]; meta=[]; conflicts=[]; changed=[]
    for case in store.cases:
        entry=ledger['entries'][case['case_id']]
        assert entry['review_status']=='APPROVED' and entry['ai_assisted'] is True and entry['blind_first_pass'] is False
        state=json.dumps({'operational':case['context']},sort_keys=True,separators=(',',':'))
        label=entry['human_label']; policy,reasons=classify(case['context'])
        if label!=policy: conflicts.append({'case_id':case['case_id'],'human':label,'policy':policy,'reasons':reasons})
        if label!=original_labels[case['case_id']]:
            assert case['source_event_group']=='stale' and entry['adjudication_id']=='USER_STALE40_HALT_20261017'
            changed.append(case['case_id'])
        rows.append({'state':state,'questions':QUESTIONS,'expected':{'operational_state':label}})
        meta.append({'row':len(rows)-1,'case_id':case['case_id'],'origin':case['origin'],
            'split':'UNASSIGNED','source_capture_group':case['source_capture_group'],
            'source_event_group':case['source_event_group'],'parent_scenario_group':case['parent_scenario_group'],
            'human_label':label,'human_review_status':'APPROVED','ai_assisted':True,'blind_first_pass':False,
            'review_method':'AI_ASSISTED_HUMAN_CONFIRMED','reviewer_role':entry['reviewer_role'],
            'reviewed_at_utc':entry['reviewed_at_utc'],'rationale':entry['rationale'],
            'adjudication_id':entry.get('adjudication_id'),'backend_commit':case['backend_commit']})
    assert len(changed)==10 and not conflicts
    counts=dict(Counter(r['expected']['operational_state'] for r in rows))
    assert set(counts.values())=={40}
    out=pack/'human_confirmed_unsplit_v1'
    out.mkdir(exist_ok=False)
    (out/'candidates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    (out/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    ack=json.loads((pack/'backend_ack.json').read_text(encoding='utf-8'))
    report={'created_utc':datetime.now(timezone.utc).isoformat(),'human_reviews':120,'label_counts':counts,
        'ai_assisted':True,'blind_review':False,'policy_version':VERSION,'policy_disagreements':conflicts,
        'user_adjudicated_stale_case_ids':changed,'ledger_chain_valid':True,'ledger_revision':ledger['revision'],
        'ledger_sha256':digest(store.file),'source_file_sha256':source_hash,
        'source_capture_groups':len({c['source_capture_group'] for c in store.cases}),
        'scenario_families':len({c['source_event_group'] for c in store.cases}),
        'approved_training_split':False,'final_test_independent':False,'final_test_blind_review':False,
        'person1_context_mapping_approved':ack['trusted_context_mapping_approved'],
        'training_started':False,'production_approved':False,'execution_authority':False,
        'remaining_blocks':['Single synthetic source batch; do not randomly split relatives across train/val/test',
            'All current reviews AI-assisted; independent blind validation/test still needed',
            'Person 1 trusted context mapping/runtime adapter not acknowledged or deployed'],
        'hashes':{p.name:digest(p) for p in out.iterdir()},
        'dataset_scope':'Human-confirmed development candidates; UNSPLIT, NOT gold final-test or training-approved bundle'}
    (out/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT.parent/'outputs/AEGIS-120-ONAY-DENETIMI.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    # New deliverable; preserve the pre-adjudication ledger copy and raw user source.
    (ROOT.parent/'outputs/AEGIS-120-ONAYLI-DUZELTILMIS.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('human_reviews','label_counts','ledger_chain_valid','ledger_revision','scenario_families','source_capture_groups','training_started')}))


if __name__=='__main__':
    main()
