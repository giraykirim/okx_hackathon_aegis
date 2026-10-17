"""Fail-closed review/source gates and bounded shadow-only learning workflow.

All input bundles are manually supplied under data/reviewed_learning. No API,
backend subprocess, credential discovery, git merge, or real/demo execution.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from ml.label_policy import QUESTIONS, LABELS

# Explicitly supplied trusted facts; missing facts remain unknown rather than false.
BOOLS = ('account_known','approval_available','api_timeout','agents_disagree','unknown_order',
         'duplicate_intent','permission_revoked','injection_detected','deployment_integrity_failure','excess_exposure')
FIELDS = {'symbol','source_mode','site','feed_age_seconds','intent_requested','quantity',*BOOLS}
ORIGINS = {'REAL_PUBLIC_CAPTURE','OFFLINE_BACKEND_TEST','SYNTHETIC_DERIVED'}
SPLITS = {'train':60,'val':30,'test':30}
ACK_FIELDS = {'person1_approved','commit','reviewer_role','trusted_context_mapping_approved',
              'network_disabled','order_execution_disabled'}


def write(path,obj):
    path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle,'sha256').hexdigest()


def state_from_context(context):
    """Shared proposed representation, not a deployed backend adapter.

    Unknown safety facts force caller abstention; this helper does not grant orders.
    Only allowlisted values enter the model. Identifiers/tool text are not accepted.
    """
    if context.keys()!=FIELDS:
        raise ValueError('trusted context fields must match explicit allowlist')
    if context['symbol']!='BTC-USDT' or context['source_mode'] not in ('MOCK','MARKET_ONLY','OKX_DEMO') or context['site']!='tr':
        raise ValueError('unsupported model context')
    if type(context['intent_requested']) is not bool:
        raise ValueError('explicit intent required')
    for key in BOOLS:
        if context[key] is not None and type(context[key]) is not bool:
            raise ValueError('invalid boolean context')
    age=context['feed_age_seconds']
    if age is not None and (type(age) not in (int,float) or not math.isfinite(age)):
        raise ValueError('invalid feed age')
    if not isinstance(context['quantity'],(str,int,float)) or isinstance(context['quantity'],bool):
        raise ValueError('quantity must be a scalar')
    # Invalid quantities are meaningful HALT examples but arbitrary text is not.
    if not re.fullmatch(r'[+\-0-9.eE]+|NaN|Infinity|-Infinity',str(context['quantity'])):
        raise ValueError('quantity outside sterile numeric allowlist')
    unknown=[key for key in BOOLS if context[key] is None]
    if age is None:
        unknown.append('feed_age_seconds')
    return json.dumps({'operational':context},sort_keys=True,separators=(',',':')), unknown


def metrics(predictions):
    confusion={label:{p:0 for p in LABELS} for label in LABELS}
    invalid=truncated=0
    for row in predictions:
        if row['predicted'] not in LABELS:
            invalid+=1
            continue
        confusion[row['expected']][row['predicted']]+=1
        truncated+=bool(row.get('truncated'))
    f1=[]
    for label in LABELS:
        tp=confusion[label][label]
        fp=sum(confusion[other][label] for other in LABELS if other!=label)
        fn=sum(confusion[label][other] for other in LABELS if other!=label)
        f1.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    count_c=sum(confusion['CONTINUE'].values())
    result={'confusion':confusion, 'macro_f1':sum(f1)/3,
        'halt_to_continue':confusion['HALT']['CONTINUE'],
        'review_to_continue':confusion['REVIEW']['CONTINUE'],
        'continue_recall':confusion['CONTINUE']['CONTINUE']/count_c if count_c else 0,
        'invalid_outputs':invalid,'truncated_rows':truncated}
    result['accepted']=(len(predictions)>0 and all(sum(confusion[c].values())>0 for c in LABELS)
        and result['halt_to_continue']==0 and result['review_to_continue']==0
        and result['continue_recall']>=.8 and result['macro_f1']>=.8 and not invalid and not truncated)
    return result


def validate_bundle(directory, control):
    if not directory.resolve().is_relative_to(ROOT/'data/reviewed_learning'):
        raise ValueError('bundle outside quarantine-approved location')
    result=json.loads(control.read_text())
    if not result.get('control_passed') or not result.get('protected_files_unchanged'):
        raise ValueError('positive control or integrity gate not passed')
    if not control.resolve().is_relative_to(ROOT/'ml/debug_learning'):
        raise ValueError('control must be from quarantined local experiment')
    frozen=json.loads((control.parent/'before.json').read_text())['protected_hashes']
    for name,h in frozen.items():
        if not (ROOT/name).resolve().is_relative_to(ROOT) or sha(ROOT/name)!=h:
            raise ValueError('protected source/model changed since positive control')
    manifest=json.loads((directory/'manifest.json').read_text())
    if manifest.get('policy_disagreements_open') or manifest.get('policy_disagreements'):
        raise ValueError('open policy disagreements must be adjudicated before training')
    for flag in ('training_approved','source_independence_approved','approved_training_split'):
        if flag in manifest and manifest[flag] is not True:
            raise ValueError(f'explicit approval required: {flag}')
    ack=manifest['backend_ack']
    if (set(ack)!=ACK_FIELDS or ack.get('person1_approved') is not True or not re.fullmatch('[0-9a-f]{40}',ack.get('commit',''))
        or not ack.get('reviewer_role') or ack.get('trusted_context_mapping_approved') is not True
        or ack.get('network_disabled') is not True or ack.get('order_execution_disabled') is not True):
        raise ValueError('backend commit/context/offline safety acknowledgment required')
    required_files={*(s+'.jsonl' for s in SPLITS),'metadata.json','traces.json'}
    if not required_files<=manifest.get('hashes',{}).keys():
        raise ValueError('bundle hash coverage incomplete')
    for name,h in manifest['hashes'].items():
        if Path(name).name!=name or sha(directory/name)!=h:
            raise ValueError('bundle integrity mismatch')
    metadata=json.loads((directory/'metadata.json').read_text())
    traces=json.loads((directory/'traces.json').read_text())
    trace_fields={'origin','backend_commit','source_capture_group','source_event_group','parent_scenario_group','context'}
    if any(set(t)!=trace_fields for t in traces):
        raise ValueError('trace evidence must be sanitized to allowlist')
    evidence={hashlib.sha256(json.dumps(t,sort_keys=True,separators=(',',':')).encode()).hexdigest():t for t in traces}
    if len(metadata)!=120:
        raise ValueError('exactly 120 individually reviewed rows required')
    all_states=set()
    no_intent_split={}
    group_split={}
    bundles={}
    for split,count in SPLITS.items():
        rows=[json.loads(line) for line in (directory/(split+'.jsonl')).read_text().splitlines()]
        meta=[m for m in metadata if m['split']==split]
        if len(rows)!=count or len(meta)!=count:
            raise ValueError('split counts do not match 60/30/30')
        if Counter(r['expected']['operational_state'] for r in rows)!=Counter({c:count//3 for c in LABELS}):
            raise ValueError('each split must balance all three classes')
        for index,(row,m) in enumerate(zip(rows,meta)):
            if set(row)!={'state','questions','expected'} or set(row['expected'])!={'operational_state'}:
                raise ValueError('unexpected row fields or answer channel')
            if m.get('row')!=index or row['questions']!=QUESTIONS:
                raise ValueError('metadata row/question mismatch')
            if m.get('human_review_status')!='APPROVED' or m.get('human_label')!=row['expected']['operational_state']:
                raise ValueError('unreviewed or unadjudicated target')
            if not m.get('reviewer_role') or not m.get('rationale'):
                raise ValueError('actual human review evidence required')
            if 'ai_assisted' in m and type(m['ai_assisted']) is not bool:
                raise ValueError('AI assistance flag must be a boolean')
            if m.get('blind_first_pass') is True and (m.get('ai_assisted') is True or m.get('review_method')=='AI_ASSISTED_HUMAN_CONFIRMED'):
                raise ValueError('AI-assisted review cannot claim a blind first pass')
            if m.get('blind_first_pass') is not True:
                if split!='train' or m.get('review_method')!='AI_ASSISTED_HUMAN_CONFIRMED' or m.get('ai_assisted') is not True:
                    raise ValueError('independent blind review required for validation/test; train needs explicit AI-assistance provenance')
            when=datetime.fromisoformat(m.get('reviewed_at_utc',''))
            if when.tzinfo is None or when>datetime.now(timezone.utc):
                raise ValueError('invalid actual review timestamp')
            if m.get('origin') not in ORIGINS or m.get('backend_commit')!=ack['commit']:
                raise ValueError('source origin/commit mismatch')
            if not m.get('trace_hash') or not re.fullmatch('[0-9a-f]{64}',m['trace_hash']):
                raise ValueError('trace evidence hash required')
            if m.get('source_capture_group')=='20261017T102105Z' and split!='train':
                raise ValueError('old public capture belongs to development/train only')
            for key in ('source_capture_group','source_event_group','parent_scenario_group'):
                value=m.get(key)
                if not isinstance(value,str) or not value.strip():
                    raise ValueError('all provenance groups required')
                group=(key,value)
                if group in group_split and group_split[group]!=split:
                    raise ValueError('source/incident/paraphrase leakage across splits')
                group_split[group]=split
            parsed=json.loads(row['state'])
            if set(parsed)!={'operational'}:
                raise ValueError('only trusted normalized context accepted')
            normalized,_=state_from_context(parsed['operational'])
            if parsed['operational']['intent_requested'] is False:
                # With no requested order, quantity-only variants are not independent evidence.
                semantic=json.dumps({k:v for k,v in parsed['operational'].items() if k!='quantity'},sort_keys=True)
                if semantic in no_intent_split and no_intent_split[semantic]!=split:
                    raise ValueError('no-intent quantity sibling semantic leakage across splits')
                no_intent_split[semantic]=split
            if normalized!=row['state']:
                raise ValueError('training/inference serialization must be identical')
            trace=evidence.get(m['trace_hash'])
            if trace is None or trace.get('context')!=parsed['operational']:
                raise ValueError('trace evidence missing or context mismatch')
            for key in ('origin','backend_commit','source_capture_group','source_event_group','parent_scenario_group'):
                if trace.get(key)!=m.get(key):
                    raise ValueError('trace provenance mismatch')
            if normalized in all_states:
                raise ValueError('duplicate normalized state')
            all_states.add(normalized)
        bundles[split]=rows
    return manifest,bundles


def prepare_review(directory):
    """Only supplied draft traces; never invent data to reach 120 examples."""
    if not directory.resolve().is_relative_to(ROOT/'data/reviewed_learning'):
        raise ValueError('review directory outside owned location')
    cases=json.loads((directory/'draft_cases.json').read_text())
    if len(cases)!=120:
        raise ValueError('120 trace-backed draft cases required; no clone padding')
    seen=set()
    with (directory/'blind_review.csv').open('x',newline='',encoding='utf-8') as handle:
        fields=['case_id','state','human_label','review_status','reviewer_role','reviewed_at_utc','rationale']
        writer=csv.DictWriter(handle,fieldnames=fields)
        writer.writeheader()
        for case in cases:
            if case['case_id'] in seen:
                raise ValueError('duplicate review case')
            seen.add(case['case_id'])
            state,_=state_from_context(case['context'])
            # Candidate labels, oracle explanations and model outputs NEVER enter this view.
            writer.writerow({'case_id':case['case_id'],'state':state,'review_status':'PENDING'})


def export_review(directory):
    if not directory.resolve().is_relative_to(ROOT/'data/reviewed_learning'):
        raise ValueError('review directory outside owned location')
    cases=json.loads((directory/'draft_cases.json').read_text())
    with (directory/'blind_review.csv').open(newline='',encoding='utf-8') as handle:
        review=list(csv.DictReader(handle))
    ledger_path=directory/'human_reviews.json'
    ledger=json.loads(ledger_path.read_text(encoding='utf-8'))['entries'] if ledger_path.exists() else {}
    if len(cases)!=120 or len(review)!=120:
        raise ValueError('exactly 120 real reviews required')
    rows={s:[] for s in SPLITS}
    metadata=[]
    traces=[]
    for case,r in zip(cases,review):
        state,_=state_from_context(case['context'])
        if r['case_id']!=case['case_id'] or r['state']!=state:
            raise ValueError('blind review input changed')
        if r['review_status']!='APPROVED' or r['human_label'] not in LABELS:
            raise ValueError('pending/unresolved review; no export')
        if not r['reviewer_role'] or not r['rationale'] or not r['reviewed_at_utc']:
            raise ValueError('actual reviewer role/date/rationale required')
        split=case['split']
        if split not in SPLITS:
            raise ValueError('curator must preassign source-grouped split')
        trace={k:case[k] for k in ('origin','backend_commit','source_capture_group','source_event_group','parent_scenario_group','context')}
        traces.append(trace)
        m={k:case[k] for k in ('origin','backend_commit','source_capture_group','source_event_group','parent_scenario_group')}
        provenance=ledger.get(case['case_id'],{})
        if provenance and any(provenance.get(k)!=r[k] for k in ('human_label','review_status','reviewer_role','rationale')):
            raise ValueError('CSV and review ledger conflict')
        m.update(split=split,row=len(rows[split]),human_label=r['human_label'],human_review_status='APPROVED',
            reviewer_role=r['reviewer_role'],reviewed_at_utc=r['reviewed_at_utc'],rationale=r['rationale'],
            blind_first_pass=provenance.get('blind_first_pass',False),
            ai_assisted=provenance.get('ai_assisted',False),review_method=provenance.get('review_method','UNVERIFIED_MANUAL_CSV'),
            trace_hash=hashlib.sha256(json.dumps(trace,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        metadata.append(m)
        rows[split].append({'state':state,'questions':QUESTIONS,'expected':{'operational_state':r['human_label']}})
    for split,items in rows.items():
        if len(items)!=SPLITS[split] or Counter(i['expected']['operational_state'] for i in items)!=Counter({c:SPLITS[split]//3 for c in LABELS}):
            raise ValueError('reviewed split insufficient/balance changed; obtain genuinely new cases')
    ack=json.loads((directory/'backend_ack.json').read_text())
    if set(ack)!=ACK_FIELDS:
        raise ValueError('ack must contain only allowed non-secret fields')
    target=directory/'approved'
    target.mkdir(exist_ok=False)
    for split,items in rows.items():
        (target/(split+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in items),encoding='utf-8')
    write(target/'metadata.json',metadata)
    write(target/'traces.json',traces)
    write(target/'manifest.json',{'backend_ack':ack,'hashes':{p.name:sha(p) for p in target.iterdir()},
        'confidence_calibrated':False,'production_approved':False})
    return target


def evaluate(checkpoint,rows):
    import laya
    import torch
    agent=laya.load(str(checkpoint),device='cuda',compile=False,fast=False)
    outputs=[]
    for row in rows:
        normalized,unknown=state_from_context(json.loads(row['state'])['operational'])
        start=time.perf_counter()
        answer=agent.predict(normalized,row['questions'])
        torch.cuda.synchronize()
        usage=answer.get('usage',{})
        outputs.append({'expected':row['expected']['operational_state'],
            'predicted':answer['answers']['operational_state']['choice'],
            'unknown_context':unknown,'runtime_abstain':bool(unknown),
            'truncated':bool(usage.get('truncated')) or bool(usage.get('state_tokens_dropped')),
            'latency_ms':(time.perf_counter()-start)*1000})
    result=metrics(outputs)
    result['median_latency_ms']=statistics.median(p['latency_ms'] for p in outputs)
    result['predictions']=outputs
    return result


def train(directory,control):
    os.environ.update(HF_HOME=str(ROOT/'models/hf-cache'),HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    manifest,bundle=validate_bundle(directory,control)
    if (directory/'final-test-started.lock').exists():
        raise ValueError('final test already attempted; new training/selection blocked')
    # Atomic marker prevents inadvertent re-selection and a second final test.
    with (directory/'experiment-started.lock').open('x') as marker:
        marker.write(datetime.now(timezone.utc).isoformat())
    run=ROOT/'ml/reviewed_learning'/directory.name
    run.mkdir(parents=True,exist_ok=False)
    candidates=[]
    base=ROOT/'models/aegis_laya_selected'
    write(run/'base-val.json',evaluate(base,bundle['val']))
    for seed in (17,29):
        out=ROOT/'models/reviewed_learning'/directory.name/f'seed-{seed}'
        if out.exists():
            raise ValueError('existing experiment checkpoint')
        command=[sys.executable,str(Path(__file__).resolve()),'worker',str(directory),
            '--control',str(control),'--seed',str(seed),'--output',str(out)]
        with (run/f'seed-{seed}.log').open('w',encoding='utf-8') as console:
            child=subprocess.Popen(command,stdout=console,stderr=subprocess.STDOUT)
            try:
                child.wait(timeout=1800)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
                write(run/'result.json',{'outcome':'PIPELINE FAILURE','reason':'training timeout','production_approved':False})
                return
        if child.returncode:
            write(run/'result.json',{'outcome':'PIPELINE FAILURE','reason':'training failed; no OOM retries','production_approved':False})
            return
        console=(run/f'seed-{seed}.log').read_text()
        losses=re.findall(r'epoch \d+/\d+ mean loss (\S+)',console)
        if len(losses)!=8 or not all(math.isfinite(float(v)) for v in losses):
            raise ValueError('missing or nonfinite official epoch loss history')
        write(run/f'seed-{seed}-history.json',{'epoch_loss':[float(v) for v in losses],
            'command':command,'confidence_calibrated':False})
        val=evaluate(out,bundle['val'])
        write(run/f'seed-{seed}-val.json',val)
        if val['accepted']:
            candidates.append((out,val,seed))
    if not candidates:
        write(run/'result.json',{'outcome':'DATA/INTEGRATION BLOCKED',
            'reason':'No validation candidate passed; final test not evaluated','production_approved':False})
        return
    checkpoint,val,seed=min(candidates,key=lambda c:(c[1]['halt_to_continue'],c[1]['review_to_continue'],-c[1]['macro_f1'],c[2]))
    with (directory/'final-test-started.lock').open('x') as marker:
        marker.write(str(checkpoint))
    final=evaluate(checkpoint,bundle['test'])
    write(run/'final-test.json',final)
    hashes={str(p.relative_to(checkpoint)):sha(p) for p in checkpoint.rglob('*') if p.is_file() and 'checkpoint_latest' not in p.parts}
    write(run/'result.json',{'outcome':'SHADOW CANDIDATE' if final['accepted'] else 'DATA/INTEGRATION BLOCKED',
        'selected_checkpoint':str(checkpoint),'seed':seed,'hashes':hashes,'validation_accepted':True,
        'final_accepted':final['accepted'],'production_approved':False,'execution_authority':False,
        'confidence_calibrated':False,'existing_selected_checkpoint_replaced':False})


def worker(directory,control,seed,out):
    """Official CLI with nonfinite-loss stop; no edits to LAYA package or architecture."""
    if seed not in (17,29) or out is None or not out.resolve().is_relative_to(ROOT/'models/reviewed_learning') or out.exists():
        raise ValueError('unapproved worker seed/output')
    os.environ.update(HF_HOME=str(ROOT/'models/hf-cache'),HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    validate_bundle(directory,control)
    import torch
    import laya.train as training
    from laya.train_cli import main as official_cli
    original=training.soft_ce_loss
    def finite_loss(*args,**kwargs):
        loss=original(*args,**kwargs)
        if not torch.isfinite(loss).item():
            raise RuntimeError('nonfinite training loss; stop immediately')
        return loss
    started=time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    try:
        training.soft_ce_loss=finite_loss
        code=official_cli(['--data',str(directory/'train.jsonl'),'--eval',str(directory/'val.jsonl'),
            '--base',str(ROOT/'models/aegis_laya_selected'),'--out',str(out),'--epochs','8',
            '--micro-batch','1','--grad-accum','1','--freeze-encoder','--loss','soft-ce',
            '--device','cuda','--seed',str(seed)])
        if code:
            raise RuntimeError('official training failed; no retries')
    finally:
        training.soft_ce_loss=original
        if out.exists():
            write(out/'runtime.json',{'seed':seed,'gpu':torch.cuda.get_device_name(0),
                'torch':torch.__version__,'cuda':torch.version.cuda,
                'wall_seconds':time.perf_counter()-started,
                'peak_allocated_mib':torch.cuda.max_memory_allocated()/1024**2,
                'production_approved':False})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('prepare-review','export-review','validate','train','worker'))
    parser.add_argument('directory',type=Path)
    parser.add_argument('--control',type=Path)
    parser.add_argument('--seed',type=int,choices=(17,29))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.mode=='prepare-review':
        prepare_review(args.directory)
    elif args.mode=='export-review':
        print(export_review(args.directory))
    elif not args.control:
        parser.error('validate/train requires --control')
    elif args.mode=='train':
        train(args.directory,args.control)
    elif args.mode=='worker':
        worker(args.directory,args.control,args.seed,args.output)
    else:
        manifest,rows=validate_bundle(args.directory,args.control)
        print(json.dumps({'status':'PASS','counts':{s:len(r) for s,r in rows.items()},'backend_commit':manifest['backend_ack']['commit']}))
