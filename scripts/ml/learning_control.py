"""Quarantined label-encoding positive control. Not a trading model or gold dataset.

Uses the unmodified installed official LAYA CLI. In-process observation hooks are
restored after training and never edit the package. No backend or auth files read.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ml.label_policy import QUESTIONS, LABELS


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def frozen_files():
    paths = [ROOT/'data'/name for name in ('train.jsonl','val.jsonl','test.jsonl','challenge.jsonl')]
    paths += list((ROOT/'models/aegis_laya_selected').rglob('*'))
    paths += list((ROOT/'data/trade_lifecycle/20261017T103022Z').glob('*'))
    return {str(p.relative_to(ROOT)):sha(p) for p in sorted(paths) if p.is_file()}


def prepare(run):
    run.mkdir(parents=True, exist_ok=False)
    data = ROOT/'data/debug_learning'/run.name
    data.mkdir(parents=True, exist_ok=False)
    for split, per_class in (('train',16), ('diagnostic_val',4)):
        rows = [{'state':f'DEBUG_LABEL={label}; This is deliberately label-encoded debug input. '
                 f'Unrelated record {split}-{index}; no market, account or execution evidence is present.',
                 'questions':QUESTIONS, 'expected':{'operational_state':label}}
                for label in LABELS for index in range(per_class)]
        random.Random(17).shuffle(rows)
        (data/(split+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows), encoding='utf-8')
    write(data/'QUARANTINE.json', {'debug_only':True, 'deliberate_label_leakage':True,
        'real_task_training_allowed':False, 'human_gold':False, 'train_rows':48,'diagnostic_val_rows':12,
        'warning':'Never merge these rows, their checkpoints or metrics into operational training or final evaluation.'})
    write(run/'before.json', {'created_utc':datetime.now(timezone.utc).isoformat(),
        'protected_hashes':frozen_files(), 'debug_hashes':{p.name:sha(p) for p in data.iterdir()},
        'python':sys.version, 'execution_authority':False, 'production_approved':False})
    return data


def tensor_hash(parameter):
    return hashlib.sha256(parameter.detach().cpu().contiguous().view(-1).numpy().tobytes()).hexdigest()


def worker(run, epochs):
    os.environ.update(HF_HOME=str(ROOT/'models/hf-cache'),HF_HUB_OFFLINE='1',
        TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    import torch
    import laya
    import laya.train as training
    from laya.train_cli import main as official_cli
    if epochs not in (8,16):
        raise ValueError('only planned 8 epoch attempt and 16 epoch retry allowed')
    data = ROOT/'data/debug_learning'/run.name
    out = ROOT/'models/debug_learning'/run.name/f'epochs-{epochs}'
    if out.exists():
        raise ValueError('refusing to overwrite a checkpoint')
    audit = {'optimizer_steps':0,'gradient_samples':[], 'nonfinite_loss':False}
    original_train, original_step, original_loss = training.train_model, torch.optim.AdamW.step, training.soft_ce_loss

    def measured_loss(*args, **kwargs):
        loss = original_loss(*args, **kwargs)
        if not torch.isfinite(loss).item():
            audit['nonfinite_loss'] = True
            raise RuntimeError('nonfinite loss: experiment stopped')
        return loss

    def measured_step(optimizer, *args, **kwargs):
        audit['optimizer_steps'] += 1
        if audit['optimizer_steps'] <= 8 or audit['optimizer_steps'] % 64 == 0:
            gradients = [p.grad for group in optimizer.param_groups for p in group['params'] if p.grad is not None]
            norms = [float(g.detach().float().norm().item()) for g in gradients]
            audit['gradient_samples'].append({'step':audit['optimizer_steps'], 'tensors':len(norms),
                'norm_sum':sum(norms), 'finite':all(math.isfinite(n) for n in norms)})
        return original_step(optimizer,*args,**kwargs)

    def measured_train(model, *args, **kwargs):
        before_heads = {n:tensor_hash(p) for n,p in model.named_parameters() if not n.startswith('encoder.')}
        before_encoder = {n:tensor_hash(p) for n,p in model.named_parameters() if n.startswith('encoder.')}
        audit['head_parameter_tensors'] = len(before_heads)
        audit['encoder_parameter_tensors'] = len(before_encoder)
        history = original_train(model,*args,**kwargs)
        audit['encoder_frozen'] = all(not p.requires_grad for n,p in model.named_parameters() if n.startswith('encoder.'))
        audit['encoder_unchanged'] = all(tensor_hash(p)==before_encoder[n] for n,p in model.named_parameters() if n in before_encoder)
        audit['head_tensors_changed'] = sum(tensor_hash(p)!=before_heads[n] for n,p in model.named_parameters() if n in before_heads)
        audit['epoch_loss'] = history
        return history

    started = time.perf_counter()
    report = {'epochs':epochs,'seed':17,'laya':laya.__version__,'torch':torch.__version__,
        'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0), 'audit':audit,
        'gpu_total_mib':torch.cuda.get_device_properties(0).total_memory/1024**2,
        'real_task_success':False,'production_approved':False}
    torch.cuda.reset_peak_memory_stats()
    argv = ['--data',str(data/'train.jsonl'),'--eval',str(data/'diagnostic_val.jsonl'),
        '--base',str(ROOT/'models/aegis_laya_selected'),'--out',str(out), '--epochs',str(epochs),
        '--micro-batch','1','--grad-accum','1','--freeze-encoder','--loss','soft-ce',
        '--device','cuda','--seed','17']
    report['official_cli_args'] = argv
    try:
        training.train_model, torch.optim.AdamW.step, training.soft_ce_loss = measured_train, measured_step, measured_loss
        code = official_cli(argv)
        if code:
            raise RuntimeError('official training CLI failed')
        training.train_model, torch.optim.AdamW.step, training.soft_ce_loss = original_train, original_step, original_loss
        agent = laya.load(str(out),device='cuda',compile=False,fast=False)
        predictions = []
        for line in (data/'diagnostic_val.jsonl').read_text().splitlines():
            row = json.loads(line)
            answer = agent.predict(row['state'],row['questions'])
            predictions.append({'expected':row['expected']['operational_state'],
                'predicted':answer['answers']['operational_state']['choice'], 'usage':answer.get('usage',{})})
        report['reload_predictions'] = predictions
        report['confusion'] = {label:dict(Counter(p['predicted'] for p in predictions if p['expected']==label)) for label in LABELS}
        report['correct'] = sum(p['expected']==p['predicted'] for p in predictions)
        report['truncated_rows'] = sum(bool(p['usage'].get('truncated')) or bool(p['usage'].get('state_tokens_dropped',0)) for p in predictions)
        report['debug_pass'] = (report['correct']==12 and report['truncated_rows']==0
            and audit['encoder_frozen'] and audit['encoder_unchanged'] and audit['head_tensors_changed']>0
            and any(s['norm_sum']>0 for s in audit['gradient_samples']))
        report['checkpoint_hashes'] = {str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and 'checkpoint_latest' not in p.parts}
        report['official_report'] = json.loads((out/'train_report.json').read_text())
        report['status'] = 'PASS' if report['debug_pass'] else 'CONTROL_NOT_LEARNED'
    except Exception as exc:
        report.update(status='ERROR',debug_pass=False,error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        training.train_model, torch.optim.AdamW.step, training.soft_ce_loss = original_train, original_step, original_loss
        report.update(wall_seconds=time.perf_counter()-started,
            peak_allocated_mib=torch.cuda.max_memory_allocated()/1024**2,
            peak_reserved_mib=torch.cuda.max_memory_reserved()/1024**2)
        write(run/f'epochs-{epochs}.json',report)
        print(json.dumps({k:report.get(k) for k in ('status','correct','debug_pass','wall_seconds','peak_allocated_mib')}),flush=True)


def orchestrate():
    run = ROOT/'ml/debug_learning'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    prepare(run)
    attempts=[]
    for epochs in (8,16):
        with (run/f'epochs-{epochs}.log').open('w',encoding='utf-8') as console:
            proc = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'worker','--run',str(run),
                '--epochs',str(epochs)],stdout=console,stderr=subprocess.STDOUT)
            try:
                proc.wait(timeout=1200)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                write(run/f'epochs-{epochs}.timeout.json', {'timeout_seconds':1200,'child_stopped':True})
                break
        if proc.returncode:
            break  # OOM/nonfinite/config errors do not trigger repeated thrashing.
        report=json.loads((run/f'epochs-{epochs}.json').read_text())
        attempts.append({'epochs':epochs,'debug_pass':report['debug_pass'],'correct':report['correct']})
        print(json.dumps(attempts[-1]),flush=True)
        if report['debug_pass']:
            break
    before=json.loads((run/'before.json').read_text())['protected_hashes']
    unchanged=all((ROOT/n).exists() and sha(ROOT/n)==h for n,h in before.items())
    result={'run':str(run),'attempts':attempts,'protected_files_unchanged':unchanged,
        'control_passed':any(a['debug_pass'] for a in attempts),
        'outcome':'DATA/INTEGRATION BLOCKED' if any(a['debug_pass'] for a in attempts) else 'PIPELINE FAILURE',
        'backend_acknowledged':False,'human_review_complete':False,'real_task_training_started':False,
        'production_approved':False,'orders_sent':0}
    write(run/'result.json',result)
    print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('run','worker'))
    parser.add_argument('--run',type=Path)
    parser.add_argument('--epochs',type=int,choices=(8,16))
    args=parser.parse_args()
    if args.mode=='run':
        orchestrate()
    elif args.run and args.epochs:
        if not args.run.resolve().is_relative_to(ROOT/'ml/debug_learning'):
            raise ValueError('run outside owned debug directory')
        worker(args.run,args.epochs)
    else:
        parser.error('worker requires --run and --epochs')
