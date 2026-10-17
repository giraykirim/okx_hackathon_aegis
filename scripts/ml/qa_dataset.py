"""Structural/provenance QA, not model evaluation or human review."""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ml.label_policy import LABELS, QUESTIONS, classify


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def check(data):
    manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
    sources = json.loads((data / 'sources.json').read_text(encoding='utf-8'))
    with (data / 'metadata.csv').open(encoding='utf-8', newline='') as handle:
        metadata = list(csv.DictReader(handle))
    errors, warnings, counts = [], [], {}
    index = {(m['split'], int(m['line_number'])): m for m in metadata}
    if len(index) != len(metadata):
        errors.append('Duplicate metadata line mapping')
    states, families, incident_sources = {}, defaultdict(set), defaultdict(set)
    rows_seen = 0
    for split in ('train', 'val', 'test', 'challenge'):
        rows = [json.loads(line) for line in (data / f'{split}.jsonl').read_text(encoding='utf-8').splitlines()]
        counts[split] = dict(Counter(r['expected']['operational_state'] for r in rows))
        if split != 'challenge' and set(counts[split]) != set(LABELS):
            errors.append(f'Missing class in {split}')
        if split == 'challenge' and set(counts[split]) != {'HALT'}:
            errors.append('Challenge must target HALT false negatives')
        for number, row in enumerate(rows, 1):
            rows_seen += 1
            m = index.get((split, number))
            if not m:
                errors.append(f'Missing metadata {split}:{number}')
                continue
            if set(row) != {'state', 'questions', 'expected'} or row['questions'] != QUESTIONS:
                errors.append(f'Invalid official row shape {split}:{number}')
            if set(row['expected']) != {'operational_state'}:
                errors.append('Unexpected label channel')
            state = json.loads(row['state'])
            label = row['expected']['operational_state']
            if label not in LABELS or classify(state['operational'])[0] != label or m['label'] != label:
                errors.append(f'Policy mismatch {split}:{number}')
            h = canonical_hash(row['state'])
            if h in states:
                errors.append(f'Duplicate state {split}:{number}')
            states[h] = split
            if canonical_hash(row) != m['row_sha256'] or h != m['state_sha256']:
                errors.append('Row hash mismatch')
            families[m['group_id']].add(split)
            if m['scenario_family'] != m['group_id']:
                errors.append('Family/group mismatch')
            source = sources.get(m['source_id'])
            if source is None or source['url'] != m['source_url']:
                errors.append('Unsupported source mapping')
            if source and source['claim_type'] == 'SOURCE_DOCUMENTED':
                incident_sources[m['source_id']].add(split)
                if m['claim_type'] != 'SYNTHETIC_DERIVED':
                    errors.append('Incident fact falsely presented as gold example')
            if m['claim_type'] == 'OBSERVED_ATK_DERIVED_LABEL' and not m['evidence_sha256']:
                errors.append('Observed example lacks capture hash')
            if m['human_review_status'] != 'PENDING_HUMAN_REVIEW' or m['reviewer'] or m['reviewed_at']:
                errors.append('Unverified human review claim')
            if m['label_basis'] != 'AGENT_AUTHORED_POLICY_DERIVATION':
                errors.append('Unsupported label provenance')
            # Input contains no gold labels, local paths, contact IDs or recognizable secret material.
            if any(token in row['state'] for token in ('PENDING_HUMAN_REVIEW', '"expected"', 'C:\\', '@')):
                errors.append('Metadata/identifier leaked into state')
            if re.search(r'(?i)(api[_ -]?key|passphrase|private[_ -]?key)\s*[:=]\s*[a-z0-9]{12,}', row['state']):
                errors.append('Potential secret in state')
    if rows_seen != len(metadata):
        errors.append('Orphan metadata')
    if any(len(s) > 1 for s in families.values()) or any(len(s) > 1 for s in incident_sources.values()):
        errors.append('Cross-split family/source leakage')
    if any(counts[s] != manifest['counts'][s] for s in counts):
        errors.append('Distribution differs from manifest')
    for name, expected in manifest['hashes'].items():
        if hashlib.sha256((data / name).read_bytes()).hexdigest() != expected:
            errors.append(f'File hash mismatch: {name}')
    for path, field in ((ROOT / 'ml/label_policy.py', 'policy_sha256'),
                        (ROOT / 'scripts/ml/build_dataset.py', 'builder_sha256')):
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest[field]:
            errors.append(f'Version mismatch: {field}')
    if manifest['training_approved'] is not False:
        errors.append('Unreviewed candidate cannot be training-approved')
    warnings.extend([
        'All labels await genuine human review; no gold dataset or trained-model result is claimed.',
        'Synthetic templates have shared field vocabulary; family isolation is not semantic independence.',
        'Challenge recombines familiar hazards and is a stress test, not an independent external benchmark.',
        'Four local receipt-derived rows share one capture; they are not four independent incidents.',
        'Parallel FindAll unavailable; only two primary-source incidents researched.',
    ])
    groups = dict(Counter(next(iter(s)) for s in families.values() if len(s) == 1))
    return dict(structural_status='FAIL' if errors else 'PASS', training_approved=False,
                errors=errors, warnings=warnings, counts=counts, groups=groups,
                review_pending=len(metadata), test_model_evaluation='NOT_RUN')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=ROOT / 'data')
    parser.add_argument('--require-human-review', action='store_true')
    args = parser.parse_args()
    report = check(args.data)
    (args.data / 'qa_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if report['errors'] or (args.require_human_review and report['review_pending']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
