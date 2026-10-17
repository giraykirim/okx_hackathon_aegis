"""Prepare human review queue or export independently reviewed candidate labels.

Never fills in reviewer decisions, never trains, never updates selected model.
"""
import argparse
import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDS = ('row','case_id','candidate_label','human_label','review_status','reviewer_role','reviewed_at_utc','rationale')


def load(directory):
    directory = directory.resolve()
    if not directory.is_relative_to(ROOT/'data/trade_lifecycle'):
        raise ValueError('outside owned lifecycle directory')
    manifest = json.loads((directory/'manifest.json').read_text())
    for name, expected in manifest['hashes'].items():
        if hashlib.sha256((directory/name).read_bytes()).hexdigest() != expected:
            raise ValueError('candidate integrity mismatch '+name)
    rows = [json.loads(line) for line in (directory/'candidates.jsonl').read_text().splitlines()]
    meta = json.loads((directory/'metadata.json').read_text())
    return rows, meta


def main(mode, directory):
    rows, meta = load(directory)
    queue = directory/'human_review.csv'
    if mode == 'prepare':
        with queue.open('x', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader()
            for index,(row,m) in enumerate(zip(rows,meta)):
                writer.writerow({'row':index,'case_id':m['case_id'],
                    'candidate_label':row['expected']['operational_state'], 'review_status':'PENDING'})
        print('Prepared blank human review queue. No row approved.')
        return
    with queue.open(newline='', encoding='utf-8') as handle:
        review = list(csv.DictReader(handle))
    if len(review) != len(rows):
        raise ValueError('review row count mismatch')
    for index,(row,m,r) in enumerate(zip(rows,meta,review)):
        if r['row'] != str(index) or r['case_id'] != m['case_id']:
            raise ValueError('review identity mismatch')
        if r['review_status'] != 'APPROVED' or r['human_label'] not in ('CONTINUE','REVIEW','HALT'):
            raise ValueError(f'Row {index}: actual human review required; export blocked')
        if not r['rationale'].strip() or not r['reviewer_role'].strip():
            raise ValueError('review rationale/role required')
        reviewed_at = datetime.fromisoformat(r['reviewed_at_utc'])
        if reviewed_at.tzinfo is None:
            raise ValueError('review timestamp must include timezone')
        row['expected']['operational_state'] = r['human_label']
    with (directory/'reviewed_candidates.jsonl').open('x', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row)+'\n')
    print('Reviewed candidates exported. Still UNSPLIT: independent validation/calibration/test required before training.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('prepare','export'))
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    main(args.mode,args.directory)
