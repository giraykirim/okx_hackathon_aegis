"""Execute pinned backend Models.classify through HTTPX mock transport.

This is actual backend client code + proposed ML adapter, not LAN/model proof.
No credentials/settings instantiation, network connection, order or backend edits.
"""
import asyncio
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ml.context_adapter import adapt_legacy


async def main():
    def denied(*args,**kwargs):
        raise RuntimeError('network forbidden in compatibility proof')
    socket.socket.connect=denied
    socket.socket.connect_ex=denied
    socket.create_connection=denied
    socket.getaddrinfo=denied
    snapshot=ROOT.parent/'work/backend-review-1c9cf35/snapshot/backend'
    sys.path.insert(0,str(snapshot))
    from aegis.integrations import Models
    from aegis.models import Observation
    import aegis.integrations as implementation
    if Path(implementation.__file__).resolve()!=snapshot/'aegis/integrations.py':
        raise ValueError('wrong backend integration loaded')
    import httpx
    now=datetime(2026,10,17,12,tzinfo=timezone.utc)
    seen=[]
    def handler(request):
        assert request.url.path=='/classify'
        assert 'authorization' not in request.headers
        payload=json.loads(request.content)
        mapped=adapt_legacy(payload,now=now)
        assert not mapped['eligible_for_shadow_inference']
        seen.append({'envelope_keys':sorted(payload),'missing_context':mapped['missing'],
            'reasons':mapped['reasons'],'run_ids_not_in_model_state':
                payload['run_id'] not in mapped['normalized_state'] and payload['correlation_id'] not in mapped['normalized_state']})
        return httpx.Response(200,json=mapped['fallback'])
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler),trust_env=False) as client:
        models=Models(SimpleNamespace(laya_url='http://offline-laya.invalid',laya_token=None),client=client)
        obs=Observation(symbol='BTC-USDT',observed_at='2026-10-17T11:59:58+00:00',price='50000',bid='49999',ask='50001',
            min_size='0.00001',lot_size='0.00000001',instrument_live=True,account_known=False)
        result=await models.classify(obs,'UNIT_RUN_DO_NOT_TRAIN','UNIT_CORRELATION_DO_NOT_TRAIN')
        assert result.label=='REVIEW' and result.abstained and result.confidence==0
        assert models.capabilities['LAYA'].status=='PASS'
    report={'status':'PASS','transport':'HTTPX_MOCK_TRANSPORT_NOT_LAN',
        'pinned_backend_commit':'1c9cf359d522e2f67c77e13418b7127c21ef2e40',
        'backend_integrations_sha256':hashlib.sha256(Path(implementation.__file__).read_bytes()).hexdigest(),
        'current_remote_commit_checked':'7d6b7e4d9b9daa068e02d50df3b57b3e28339315',
        'backend_integration_changed_between_commits':False,
        'client_response_validated':result.model_dump(mode='json'),'observations':seen,
        'real_network':False,'real_laya_inference':False,'deployed':False,
        'person1_context_mapping_approved':False,'execution_authority':False,
        'limitation':'Wire compatibility and safe abstention only. Trusted context adapter still requires Person 1 agreement and runtime integration.'}
    path=ROOT/'ml/runs/context-compat.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    asyncio.run(main())
