"""Loopback-only blind human review. No model inference, orders or approval bypass.

Run: python scripts/ml/human_review_app.py <review-pack> --port 8768
Saved decisions are actual user submissions, never generator/model approvals.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import random
import threading

from reviewed_learning import state_from_context, LABELS

ROOT=Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path,value):
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)


class ReviewStore:
    def __init__(self,directory):
        self.directory=directory.resolve()
        if not self.directory.is_relative_to(ROOT/'data/reviewed_learning'):
            raise ValueError('only owned review packs accepted')
        manifest=json.loads((self.directory/'review_manifest.json').read_text(encoding='utf-8'))
        if digest(self.directory/'draft_cases.json')!=manifest['hashes']['draft_cases.json']:
            raise ValueError('draft manifest integrity mismatch')
        self.source_hash=digest(self.directory/'draft_cases.json')
        self.cases=json.loads((self.directory/'draft_cases.json').read_text(encoding='utf-8'))
        self.by_id={c['case_id']:c for c in self.cases}
        if len(self.by_id)!=len(self.cases):
            raise ValueError('duplicate opaque case IDs')
        for c in self.cases:
            state_from_context(c['context'])
        self.display_cases=list(self.cases)
        random.Random(self.source_hash).shuffle(self.display_cases)
        self.lock=threading.Lock()
        self.file=self.directory/'human_reviews.json'
        self.state={'dataset_sha256':self.source_hash,'revision':0,'entries':{},'audit':[]}
        if self.file.exists():
            self.state=json.loads(self.file.read_text(encoding='utf-8'))
            if self.state['dataset_sha256']!=self.source_hash:
                raise ValueError('saved review belongs to another dataset')
            if any(key not in self.by_id for key in self.state['entries']):
                raise ValueError('saved review references unknown cases')
        self.commit=manifest['backend_commit']

    def public(self):
        # Never serve draft source wholesale: it may contain curator/backend output labels.
        cases=[]
        for case in self.display_cases:
            details=case.get('review_context',{})
            cases.append({'case_id':case['case_id'],'context':case['context'],
                'description':details.get('description',''), 'order_type':details.get('order_type',''),
                'side':details.get('side','')})
        return {'dataset_sha256':self.source_hash,'cases':cases,'backend_commit':self.commit,
            'warning':'Sentetik offline testlerdir. 120 bağımsız gerçek olay değildir. Split ve backend bağlam onayı henüz yok.'}

    def reviews(self):
        with self.lock:
            return {'revision':self.state['revision'],'entries':dict(self.state['entries'])}

    def save(self,payload):
        required={'case_id','human_label','review_status','reviewer_role','rationale','revision'}
        if set(payload)!=required:
            raise ValueError('İstek alanları geçersiz; toplu onay desteklenmez.')
        case_id=payload['case_id']
        if case_id not in self.by_id:
            raise ValueError('Örnek bulunamadı.')
        status=payload['review_status']
        if status not in ('APPROVED','UNRESOLVED'):
            raise ValueError('Geçersiz inceleme durumu.')
        label=payload['human_label']
        if (status=='APPROVED' and label not in LABELS) or (status=='UNRESOLVED' and label!=''):
            raise ValueError('Geçersiz karar.')
        for key,minimum,maximum in (('reviewer_role',2,80),('rationale',10,2000)):
            if not isinstance(payload[key],str) or not minimum<=len(payload[key].strip())<=maximum:
                raise ValueError('Rol ve en az 10 karakter gerekçe gerekli; credential yazmayın.')
        with self.lock:
            if type(payload['revision']) is not int or payload['revision']!=self.state['revision']:
                raise RuntimeError('Başka sekmede kayıt değişti. Sayfayı yenileyin.')
            if digest(self.directory/'draft_cases.json')!=self.source_hash:
                raise RuntimeError('Kaynak değişti; kayıt durduruldu.')
            prior=self.state['entries'].get(case_id,{})
            # A later manual edit cannot erase prior AI assistance or create blind evidence.
            entry={**prior,**{k:payload[k].strip() if isinstance(payload[k],str) else payload[k]
                for k in ('human_label','review_status','reviewer_role','rationale')}}
            entry.update(reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
                blind_first_pass=prior.get('blind_first_pass',True) and not prior.get('ai_assisted',False),
                submitted_via='loopback-review-ui')
            revision=self.state['revision']+1
            event={'revision':revision,'case_id':case_id,'entry':entry,
                'previous_hash':self.state['audit'][-1]['hash'] if self.state['audit'] else self.source_hash}
            event['hash']=hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest()
            updated={**self.state,'revision':revision,'entries':{**self.state['entries'],case_id:entry},
                'audit':self.state['audit']+[event]}
            atomic(self.file,updated)
            self.state=updated
            approved=sum(e['review_status']=='APPROVED' for e in updated['entries'].values())
            atomic(self.directory/'review_progress.json',{'total':len(self.cases),'approved':approved,
                'unresolved':sum(e['review_status']=='UNRESOLVED' for e in updated['entries'].values()),
                'human_review_complete':approved==len(self.cases),'training_approved':False,
                'ai_assisted':any(e.get('ai_assisted',False) for e in updated['entries'].values()),
                'source_independence_approved':False,'backend_context_mapping_approved':False,
                'updated_at':entry['reviewed_at_utc']})
            # Same CSV contract as reviewed_learning.export_review; still blocked while split=UNASSIGNED.
            self.export_csv_file()
            return {'revision':revision,'entry':entry,'approved':approved,'total':len(self.cases)}

    def csv_text(self):
        buffer=io.StringIO(newline='')
        writer=csv.DictWriter(buffer,fieldnames=['case_id','state','human_label','review_status',
            'reviewer_role','reviewed_at_utc','rationale'])
        writer.writeheader()
        for case in self.cases:
            entry=self.state['entries'].get(case['case_id'],{})
            state,_=state_from_context(case['context'])
            writer.writerow({'case_id':case['case_id'],'state':state,'human_label':entry.get('human_label',''),
                'review_status':entry.get('review_status','PENDING'),'reviewer_role':entry.get('reviewer_role',''),
                'reviewed_at_utc':entry.get('reviewed_at_utc',''),'rationale':entry.get('rationale','')})
        return buffer.getvalue()

    def export_csv_file(self):
        path=self.directory/'blind_review.csv'
        tmp=path.with_suffix('.csv.tmp')
        tmp.write_text(self.csv_text(),encoding='utf-8',newline='')
        tmp.replace(path)


def create_server(store,port=8768):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass  # No request body, credentials or review text printed.

        def host_ok(self):
            return self.headers.get('Host')==f'127.0.0.1:{self.server.server_port}'

        def send(self,code,body,content_type='application/json; charset=utf-8'):
            if not isinstance(body,bytes):
                body=json.dumps(body,ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'none'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            if not self.host_ok():
                return self.send(403,{'error':'Host rejected'})
            if self.path=='/':
                return self.send(200,(Path(__file__).with_name('human_review_ui.html')).read_bytes(),'text/html; charset=utf-8')
            if self.path=='/api/cases':
                return self.send(200,store.public())
            if self.path=='/api/reviews':
                return self.send(200,store.reviews())
            return self.send(404,{'error':'Not found'})

        def do_POST(self):
            origin=f'http://127.0.0.1:{self.server.server_port}'
            if not self.host_ok() or self.headers.get('Origin')!=origin:
                return self.send(403,{'error':'Origin rejected'})
            if self.path!='/api/review' or self.headers.get('Content-Type')!='application/json':
                return self.send(400,{'error':'JSON review endpoint only'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=16384:
                    raise ValueError('İstek boyutu geçersiz.')
                payload=json.loads(self.rfile.read(length))
                self.send(200,store.save(payload))
            except (ValueError,TypeError,KeyError):
                self.send(400,{'error':'Karar, rol ve gerekçeyi kontrol edin. Toplu onay yok; en az 10 karakter gerekçe gerekli.'})
            except RuntimeError as exc:
                self.send(409,{'error':str(exc)})
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.daemon_threads=True
    return server


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--port',type=int,default=8768)
    args=parser.parse_args()
    store=ReviewStore(args.directory)
    server=create_server(store,args.port)
    atomic(args.directory/'review_server.json',{'pid':__import__('os').getpid(),
        'url':f'http://127.0.0.1:{server.server_port}','dataset_sha256':store.source_hash,
        'purpose':'Human review only; no model/order/auth endpoints'})
    print(f'Human review: http://127.0.0.1:{server.server_port}',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
