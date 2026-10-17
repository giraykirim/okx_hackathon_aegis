"""P2-02 bounded local experiment; official LAYA only, never reads test/challenge."""
import argparse
import gc
import hashlib
import json
import math
import os
import shutil
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ['HF_HOME'] = str(ROOT / 'models/hf-cache')
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
sys.path.insert(0, str(ROOT))
RUNS = ROOT / 'ml/runs'
RUNS.mkdir(parents=True, exist_ok=True)


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, default=str) + '\n', encoding='utf-8')


def rows(name):
    if name not in ('train', 'val', 'smoke_train'):
        raise ValueError('Test/challenge data is excluded from this experiment')
    return [json.loads(line) for line in (ROOT / f'data/{name}.jsonl').read_text(encoding='utf-8').splitlines()]


def load(path):
    import laya
    return laya.load(str(path), device='cuda', compile=False, fast=False)


def evaluate(agent, samples):
    import torch
    predictions, latency = [], []
    # Warm-up is recorded separately, not silently counted as steady latency.
    torch.cuda.synchronize()
    start = time.perf_counter()
    warm = agent.predict(samples[0]['state'], samples[0]['questions'])
    torch.cuda.synchronize()
    warm_ms = (time.perf_counter() - start) * 1000
    for row in samples:
        torch.cuda.synchronize()
        start = time.perf_counter()
        result = agent.predict(row['state'], row['questions'])
        torch.cuda.synchronize()
        ms = (time.perf_counter() - start) * 1000
        answer = result['answers']['operational_state']
        predictions.append(dict(expected=row['expected']['operational_state'], answer=answer,
                                latency_ms=ms))
        latency.append(ms)
    confusion = {label: dict(Counter(p['answer'].get('choice') for p in predictions if p['expected'] == label))
                 for label in ('CONTINUE', 'REVIEW', 'HALT')}
    n_halt = sum(p['expected'] == 'HALT' for p in predictions)
    halt_continue = sum(p['expected'] == 'HALT' and p['answer'].get('choice') == 'CONTINUE' for p in predictions)
    return dict(n=len(samples), accuracy=sum(p['answer'].get('choice') == p['expected'] for p in predictions) / len(samples),
                halt_to_continue_count=halt_continue, halt_denominator=n_halt,
                confusion=confusion, warmup_ms=warm_ms, warmup_answer=warm,
                median_latency_ms=statistics.median(latency), max_latency_ms=max(latency), predictions=predictions)


def main(stage):
    import torch
    import laya
    from laya.train_cli import main as official_cli
    from laya.train import resolve_checkpoint_dir
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA required for this local experiment')
    torch.manual_seed(17)
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    report = dict(stage=stage, seed=17, laya=laya.__version__, torch=torch.__version__, cuda=torch.version.cuda,
                  gpu=torch.cuda.get_device_name(0), human_review_pending=True, production_approved=False,
                  train_sha256=hashlib.sha256((ROOT / 'data/train.jsonl').read_bytes()).hexdigest(),
                  val_sha256=hashlib.sha256((ROOT / 'data/val.jsonl').read_bytes()).hexdigest())
    try:
        if stage == 'baseline':
            agent = load('convaiinnovations/laya')
            report['model_revision'] = agent.revision
            # A real typed-choice query followed by train/VAL baseline outputs; no held-out TEST use.
            report['train'] = evaluate(agent, rows('train'))
            report['val'] = evaluate(agent, rows('val'))
            report['base_dir'] = resolve_checkpoint_dir('english')
        elif stage == 'dry-run':
            argv = ['--data', str(ROOT / 'data/train.jsonl'), '--base', 'english', '--dry-run']
            report['official_command_args'] = argv
            code = official_cli(argv)
            if code:
                raise RuntimeError(f'Official CLI exited {code}')
        elif stage in ('smoke', 'head'):
            if stage == 'smoke':
                # 36 balanced rows from TRAIN only. VAL remains independent.
                samples = rows('train')
                subset = []
                for label in ('CONTINUE', 'REVIEW', 'HALT'):
                    subset += [r for r in samples if r['expected']['operational_state'] == label][:12]
                (ROOT / 'data/smoke_train.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in subset), encoding='utf-8')
            data = 'smoke_train' if stage == 'smoke' else 'train'
            out = ROOT / ('models/aegis_laya_smoke' if stage == 'smoke' else 'models/aegis_laya_head')
            if out.exists():
                raise RuntimeError('Refusing to overwrite an existing checkpoint')
            argv = ['--data', str(ROOT / f'data/{data}.jsonl'), '--base', 'english', '--out', str(out),
                    '--eval', str(ROOT / 'data/val.jsonl'), '--epochs', '1' if stage == 'smoke' else '4',
                    '--micro-batch', '1', '--grad-accum', '4', '--freeze-encoder', '--device', 'cuda',
                    '--loss', 'soft-ce', '--seed', '17']
            report['official_command_args'] = argv
            code = official_cli(argv)
            if code:
                raise RuntimeError(f'Official CLI exited {code}')
            gc.collect()
            torch.cuda.empty_cache()
            agent = load(out)
            report['reload_inference'] = evaluate(agent, rows('train')[:1])
            report['train'] = evaluate(agent, rows('train'))
            report['val'] = evaluate(agent, rows('val'))
            tr = json.loads((out / 'train_report.json').read_text(encoding='utf-8'))
            report['official_train_report'] = tr
            cfg = json.loads((out / 'rl_agent_config.json').read_text(encoding='utf-8'))
            report['saved_training_config'] = cfg['training']['laya_train']
            n_train = (36 if stage == 'smoke' else 56) - int((36 if stage == 'smoke' else 56) * 0.1)
            report['optimizer_updates_expected'] = (1 if stage == 'smoke' else 4) * math.ceil(n_train / 4)
        elif stage == 'select':
            base = json.loads((RUNS / 'baseline.json').read_text())
            head = json.loads((RUNS / 'head.json').read_text())
            b, h = base['val'], head['val']
            # Predeclared no-regression rule, VAL only: no more dangerous false negatives;
            # accuracy must improve, otherwise prefer the known base checkpoint.
            use_head = (h['halt_to_continue_count'] <= b['halt_to_continue_count'] and h['accuracy'] > b['accuracy'])
            src = ROOT / 'models/aegis_laya_head' if use_head else Path(base['base_dir'])
            dst = ROOT / 'models/aegis_laya_selected'
            if dst.exists():
                raise RuntimeError('Refusing to overwrite selected checkpoint')
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns('checkpoint_latest', '.cache', '*.lock'))
            if not (dst / 'encoder').exists():
                # Published base has all weights but no local encoder config. Reuse the
                # architecture config saved by the official smoke run, never its weights.
                shutil.copytree(ROOT / 'models/aegis_laya_smoke/encoder', dst / 'encoder')
            if not (dst / 'questions.json').exists():
                write(dst / 'questions.json', rows('train')[0]['questions'])
            hashes = {}
            for path in sorted(dst.rglob('*')):
                if path.is_file():
                    with path.open('rb') as handle:
                        hashes[str(path.relative_to(dst))] = hashlib.file_digest(handle, 'sha256').hexdigest()
            version = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
            report.update(selected='head' if use_head else 'base', selection_rule='VAL accuracy improvement and no HALT->CONTINUE regression',
                          version=version, hashes=hashes, test_used=False,
                          upstream_revision=base['model_revision'])
            write(dst / 'selection.json', report)
            agent = load(dst)
            report['selected_reload'] = evaluate(agent, rows('val')[:1])
        report['status'] = 'PASS'
    except Exception as exc:
        report['status'] = 'FAIL'
        report['error_type'] = type(exc).__name__
        report['error'] = str(exc)
        raise
    finally:
        report['wall_seconds'] = time.perf_counter() - started
        report['peak_allocated_mib'] = torch.cuda.max_memory_allocated() / 1024 ** 2
        report['peak_reserved_mib'] = torch.cuda.max_memory_reserved() / 1024 ** 2
        write(RUNS / f'{stage}.json', report)
        print(json.dumps({k: report.get(k) for k in ('stage', 'status', 'wall_seconds', 'peak_allocated_mib', 'selected', 'error')}, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['baseline', 'dry-run', 'smoke', 'head', 'select'])
    main(parser.parse_args().stage)
