"""Run pinned backend pure policy OFFLINE, emit blind, UNSPLIT human review pack.

Synthetic scenarios, actual executed backend policy outputs. Never account logs,
exchange orders, independent incidents, human gold, or an approved training split.
"""
import argparse
from collections import Counter
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import socket
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/ml'))
from reviewed_learning import BOOLS, state_from_context

COMMIT='1c9cf359d522e2f67c77e13418b7127c21ef2e40'
SCENARIOS=(
    ('monitoring','Yalnızca piyasa izleniyor; yeni emir önerilmedi.',{'intent_requested':False}),
    ('preflight','Emir öncesi yerel kontroller için gerekli bağlam sağlandı.',{}),
    ('terminal','Önceki olayın sorguyla terminal olduğu doğrulandı; yeni emir yok.',{'intent_requested':False}),
    ('optional','Ek açıklama notu yok; gerekli kontrollerin verileri mevcut.',{'intent_requested':False}),
    ('account_missing','Bir emir öneriliyor; hesap durumu bilinmiyor.',{'account_known':False}),
    ('approval_missing','Bir emir öneriliyor; ayrı kullanıcı onayı henüz mevcut değil.',{'approval_available':False}),
    ('read_timeout','Submit çağrısı yapılmadı; önceki bilgi okuma isteği timeout oldu.',{'api_timeout':True}),
    ('disagreement','İki analiz kaynağı mevcut bağlam hakkında birbiriyle çelişiyor.',{'agents_disagree':True}),
    ('stale','Piyasa kaydının yaşı güncel veri sınırını aşıyor.',{'feed_age_seconds':40}),
    ('duplicate','Aynı istem daha önce kaydedilmiş; duplicate sinyali doğrulandı.',{'duplicate_intent':True}),
    ('unknown_submit','Submit sonrası yanıt alınamadı; emrin borsaya ulaşıp ulaşmadığı belirsiz.',{'unknown_order':True}),
    ('revoked','Güvenilir kontrol katmanı işlem yetkisinin geri alındığını bildirdi.',{'permission_revoked':True}),
)


def dump(path,obj):
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(snapshot,output):
    snapshot=snapshot.resolve()
    expected=ROOT.parent/'work/backend-review-1c9cf35/snapshot/backend'
    if snapshot!=expected.resolve():
        raise ValueError('only pinned pure-policy snapshot accepted')
    output=output.resolve()
    if not output.is_relative_to(ROOT/'data/reviewed_learning'):
        raise ValueError('output outside owned review directory')
    # Deny all network operations before loading the two dependency-free backend modules.
    def denied(*args,**kwargs):
        raise RuntimeError('Network forbidden in offline policy replay')
    socket.create_connection=denied
    socket.getaddrinfo=denied
    socket.socket.connect=denied
    socket.socket.connect_ex=denied
    sys.path.insert(0,str(snapshot))
    from aegis.models import Observation, Proposal, Classification
    from aegis.policy import check
    import aegis.policy as policy_module
    if Path(policy_module.__file__).resolve()!=snapshot/'aegis/policy.py':
        raise ValueError('wrong backend policy imported')
    # Prove outbound deny is active without attempting an external connection.
    try:
        socket.create_connection(('127.0.0.1',1))
    except RuntimeError:
        pass
    else:
        raise ValueError('offline guard inactive')
    output.mkdir(parents=True,exist_ok=False)
    now=datetime(2026,10,17,12,0,tzinfo=timezone.utc)
    cases=[]; evidence=[]; meta=[]
    for family,narrative,changes in SCENARIOS:
        for kind in ('market','limit','post_only','fok','ioc'):
            for side in ('buy','sell'):
                index=len(cases)
                quantity=str(Decimal('0.0001')+Decimal(index)*Decimal('0.00000001'))
                facts={'symbol':'BTC-USDT','site':'tr','source_mode':'MOCK',
                    'intent_requested':True,'feed_age_seconds':2,'quantity':quantity,
                    **{k:False for k in BOOLS},'account_known':True,'approval_available':True,**changes}
                # These are injected synthetic facts, NOT verified account facts.
                obs=Observation(symbol='BTC-USDT',observed_at=now-timedelta(seconds=facts['feed_age_seconds']),
                    price='50000',bid='49999',ask='50001',min_size='0.00001',lot_size='0.00000001',
                    tick_size='0.1',instrument_live=True,account_known=facts['account_known'],
                    quote_available='1000',base_available='0.1',exposure_quote='0')
                proposal=Proposal(symbol='BTC-USDT',action=side.upper() if facts['intent_requested'] else 'NO_TRADE',
                    quantity=quantity if facts['intent_requested'] else '0',
                    intent_id=f'OFFLINE{index}',summary='Offline synthetic policy replay; no order executor')
                # Stub CONTINUE classification probes the deterministic gate, NOT real LAYA inference.
                classification=Classification(label='CONTINUE',confidence=1,abstained=False,
                    model_version='EXPLICIT_TEST_STUB_NOT_LAYA',latency_ms=0)
                result=check(obs,classification,proposal,now=now,source_mode='MOCK',
                    approval_available=facts['approval_available'],unresolved=facts['unknown_order'],
                    duplicate=facts['duplicate_intent'])
                state,_=state_from_context(facts)
                case_id=hashlib.sha256(f'{COMMIT}:{index}:{state}'.encode()).hexdigest()[:20]
                # All cases remain UNSPLIT; semantic/source independence has NOT been approved.
                case={'case_id':case_id,'split':'UNASSIGNED','origin':'SYNTHETIC_DERIVED',
                    'backend_commit':COMMIT,'source_capture_group':'offline-policy-review-1c9cf35',
                    'source_event_group':family,'parent_scenario_group':family,'context':facts,
                    'review_context':{'order_type':kind,'side':side,'description':narrative,
                        'backend_approved':result.approved,'backend_reasons':result.reasons,
                        'backend_order_type_aware':False}}
                # No expected class or model prediction is emitted in this draft/reviewer pack.
                cases.append(case)
                mapped={'symbol','source_mode','feed_age_seconds','intent_requested','quantity',
                    'account_known','approval_available','unknown_order','duplicate_intent'}
                meta.append({'case_id':case_id,'scenario_family':family,'human_review_status':'PENDING',
                    'not_in_backend_policy':[k for k in facts if k not in mapped],
                    'all_operational_facts_injected':True,'independent_incident':False})
                evidence.append({'case_id':case_id,'backend_commit':COMMIT,'backend_policy_executed':True,
                    'context_sha256':hashlib.sha256(state.encode()).hexdigest(),
                    'backend_result':result.model_dump(mode='json'),
                    'laya_classification_is_stub':True,'order_type_is_fixture_metadata_only':True,
                    'network_allowed':False,'execution_component_loaded':False})
    dump(output/'draft_cases.json',cases)
    dump(output/'offline_evidence.json',evidence)
    dump(output/'provenance.json',meta)
    dump(output/'backend_ack.json',{'person1_approved':False,'commit':COMMIT,'reviewer_role':'',
        'trusted_context_mapping_approved':False,'network_disabled':True,'order_execution_disabled':True})
    manifest={'backend_commit':COMMIT,'cases':len(cases),'scenario_families':len(SCENARIOS),
        'orders_sent':0,'backend_calls_executed':len(evidence),'network_denial_verified':True,
        'human_review_complete':False,'independent_split_approved':False,
        'backend_context_mapping_approved':False,'origin':'SYNTHETIC_DERIVED_WITH_EXECUTED_OFFLINE_POLICY',
        'snapshot_hashes':{str(p.relative_to(snapshot)):digest(p) for p in snapshot.rglob('*.py')},
        'hashes':{p.name:digest(p) for p in output.iterdir() if p.is_file()}}
    dump(output/'review_manifest.json',manifest)
    print(json.dumps({k:manifest[k] for k in ('backend_commit','cases','scenario_families','orders_sent','backend_calls_executed','network_denial_verified')}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    build(args.snapshot,args.output)
