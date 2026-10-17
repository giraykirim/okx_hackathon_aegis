"""Offline integrity and reload check; not a held-out model evaluation."""
import hashlib
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ['HF_HOME'] = str(ROOT / 'models/hf-cache')
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

import laya
import torch

selected = ROOT / 'models/aegis_laya_selected'
record = json.loads((selected / 'selection.json').read_text(encoding='utf-8'))
for name, expected in record['hashes'].items():
    with (selected / name).open('rb') as handle:
        assert hashlib.file_digest(handle, 'sha256').hexdigest() == expected, name
assert hashlib.sha256(json.dumps(record['hashes'], sort_keys=True).encode()).hexdigest() == record['version']
dataset = json.loads((ROOT / 'data/manifest.json').read_text())
for name in ('train.jsonl', 'val.jsonl', 'test.jsonl', 'challenge.jsonl'):
    assert hashlib.sha256((ROOT / 'data' / name).read_bytes()).hexdigest() == dataset['hashes'][name]
row = json.loads((ROOT / 'data/train.jsonl').read_text(encoding='utf-8').splitlines()[0])
torch.cuda.reset_peak_memory_stats()
agent = laya.load(str(selected), device='cuda', compile=False, fast=False)
torch.cuda.synchronize()
start = time.perf_counter()
answer = agent.predict(row['state'], row['questions'])
torch.cuda.synchronize()
report = dict(status='PASS', offline_reload=True, hashes_match=True, dataset_hashes_unchanged=True,
              test_model_evaluation=False, selected=record['selected'], version=record['version'],
              latency_ms=(time.perf_counter() - start) * 1000,
              peak_allocated_mib=torch.cuda.max_memory_allocated() / 1024 ** 2,
              answer=answer, execution_authority=False, production_approved=False)
(ROOT / 'ml/runs/selected-offline.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, indent=2))
