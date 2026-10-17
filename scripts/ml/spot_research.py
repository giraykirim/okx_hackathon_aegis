"""Public ATK -> research analytics -> LAYA shadow inference. Never executes orders.

Run with the existing GPU Python: spot_research.py collect, then infer <capture-dir>.
Raw history is NOT labelled training data. Candidate labels require human review.
"""
import argparse
from collections import Counter
import csv
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ml.label_policy import QUESTIONS, VERSION, classify

BARS = {'1m': 60, '5m': 300, '15m': 900, '1H': 3600, '4H': 14400}


def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def closed(rows, seconds):
    """Validate OHLCV and discard unfinished candles; never infer completion from wall time."""
    result = {}
    for row in rows:
        if len(row) != 9 or row[8] not in ('0', '1'):
            raise ValueError('invalid candle schema')
        stamp = int(row[0])
        o, h, low, c, volume = map(float, row[1:6])
        if not all(math.isfinite(v) for v in (o, h, low, c, volume)):
            raise ValueError('nonfinite candle')
        if min(o, h, low, c) <= 0 or volume < 0 or not low <= min(o, c) <= max(o, c) <= h:
            raise ValueError('invalid OHLCV')
        if stamp % (seconds * 1000):
            raise ValueError('unaligned candle')
        if stamp in result:
            raise ValueError('duplicate timestamp')
        if row[8] == '1':
            result[stamp] = c
    return dict(sorted(result.items()))


def returns(candles, seconds):
    keys = list(candles)
    return {b: math.log(candles[b] / candles[a]) for a, b in zip(keys, keys[1:])
            if b - a == seconds * 1000}


def correlation(x, y):
    if len(x) < 3 or statistics.pstdev(x) == 0 or statistics.pstdev(y) == 0:
        return None
    mx, my = statistics.mean(x), statistics.mean(y)
    return sum((a-mx)*(b-my) for a,b in zip(x,y)) / math.sqrt(
        sum((a-mx)**2 for a in x) * sum((b-my)**2 for b in y))


class PublicATK:
    def __init__(self, directory):
        self.directory = directory
        self.node = Path(os.environ['LOCALAPPDATA']) / 'HackathonTools/node/node-v24.22.0-win-x64/node.exe'
        self.cli = ROOT / 'backend/node_modules/@okx_ai/okx-trade-cli/dist/index.js'
        self.home = tempfile.TemporaryDirectory(prefix='aegis-public-spot-')
        self.env = {key: os.environ[key] for key in ('SystemRoot', 'WINDIR', 'TEMP', 'TMP', 'PATH') if key in os.environ}
        self.env.update(AEGIS_ATK_HOME=self.home.name, OKX_SITE='tr', OKX_TIMEOUT_MS='15000',
                        NO_COLOR='1', DO_NOT_TRACK='1')
        self.receipts = []
        dump(directory / 'tool-version.json', {'package': '@okx_ai/okx-trade-cli',
             'version': json.loads((self.cli.parents[1] / 'package.json').read_text())['version'],
             'credential_home': 'isolated temporary empty directory', 'site': 'tr',
             'market_environment': 'public live market data; no private endpoint or execution'})

    def get(self, name, *args):
        started = datetime.now(timezone.utc).isoformat()
        for attempt in range(3):
            tick = time.perf_counter()
            try:
                proc = subprocess.run([str(self.node), '--import', (ROOT / 'scripts/ml/atk_public_isolation.mjs').as_uri(),
                    str(self.cli), 'market', *args, '--site', 'tr', '--json'],
                    env=self.env, cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=25)
                if proc.returncode:
                    raise RuntimeError('public CLI failed')  # Never persist arbitrary stderr.
                obj = json.loads(proc.stdout)
                if not isinstance(obj, list) or not obj:
                    raise ValueError('expected nonempty public data list')
                dump(self.directory / (name + '.json'), obj)
                self.receipts.append({'file': name+'.json', 'command': ['market', *args, '--site', 'tr', '--json'],
                    'requested_at': started, 'received_at': datetime.now(timezone.utc).isoformat(),
                    'latency_ms': round((time.perf_counter()-tick)*1000, 2), 'attempts': attempt+1,
                    'sha256': sha(self.directory / (name+'.json')), 'success': True})
                time.sleep(.12)
                return obj
            except (subprocess.TimeoutExpired, RuntimeError, ValueError) as exc:
                if attempt == 2:
                    self.receipts.append({'file': name+'.json', 'requested_at': started,
                        'command': ['market', *args], 'success': False, 'error_type': type(exc).__name__})
                    return None
                time.sleep(1+attempt)


def collect():
    directory = ROOT / 'data/atk_spot' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory.mkdir(parents=True)
    api = PublicATK(directory)
    instruments = api.get('instruments', 'instruments', '--instType', 'SPOT')
    tickers = api.get('tickers', 'tickers', 'SPOT')
    if not instruments or not tickers:
        dump(directory/'receipts.json', api.receipts)
        raise RuntimeError('discovery failed; no fabricated fallback')
    eligible = {x['instId']: x for x in instruments if x.get('quoteCcy') == 'USDT' and x.get('state') == 'live'}
    eligible_tickers = {x['instId']: x for x in tickers if x['instId'] in eligible and float(x['last']) > 0}
    ranked = sorted(eligible_tickers, key=lambda k: float(eligible_tickers[k].get('volCcy24h', 0)), reverse=True)
    symbols = [s for s in ('BTC-USDT','ETH-USDT','SOL-USDT') if s in eligible_tickers]
    symbols += [s for s in ranked if s not in symbols][:10-len(symbols)]
    metrics, hourly, observations, qa = [], {}, [], []
    candle_count = trade_count = 0
    for symbol in symbols:
        print('Collecting', symbol, flush=True)
        book = api.get(symbol+'_book', 'orderbook', symbol, '--sz', '50')
        trades = api.get(symbol+'_trades', 'trades', symbol, '--limit', '100')
        trade_count += len(trades or [])
        row = {'symbol': symbol, 'volume_quote_24h': float(eligible_tickers[symbol].get('volCcy24h', 0)),
               'policy_supported': symbol == 'BTC-USDT', 'intervals': {}}
        if book:
            b = book[0]
            bid, ask = float(b['bids'][0][0]), float(b['asks'][0][0])
            if not 0 < bid <= ask:
                qa.append({'symbol': symbol, 'error': 'crossed_or_invalid_book'})
            else:
                mid = (bid+ask)/2
                row.update(spread_bps=(ask-bid)/mid*10000,
                    bid_depth_50_usdt=sum(float(x[0])*float(x[1]) for x in b['bids']),
                    ask_depth_50_usdt=sum(float(x[0])*float(x[1]) for x in b['asks']), book_timestamp_ms=int(b['ts']))
        for bar, seconds in BARS.items():
            candles = api.get(symbol+'_'+bar, 'candles', symbol, '--bar', bar, '--limit', '300')
            if not candles:
                continue
            candle_count += len(candles)
            try:
                prices = closed(candles, seconds)
                r = returns(prices, seconds)
                row['intervals'][bar] = {'raw': len(candles), 'closed': len(prices),
                    'contiguous_returns': len(r), 'missing_intervals':
                        ((max(prices)-min(prices))//(seconds*1000)+1-len(prices)) if prices else None,
                    'start_ms': min(prices) if prices else None, 'end_ms': max(prices) if prices else None,
                    'log_return_std_bps_per_bar': statistics.pstdev(r.values())*10000 if r else None,
                    'window_return_pct': (prices[max(prices)]/prices[min(prices)]-1)*100 if prices else None}
                if bar == '1H':
                    hourly[symbol] = r
            except ValueError as exc:
                qa.append({'symbol': symbol, 'bar': bar, 'error': str(exc)})
        metrics.append(row)
        observations.append({'symbol': symbol, 'observed_at': datetime.now(timezone.utc).isoformat(),
            'feed_age_seconds': (time.time()*1000-row['book_timestamp_ms'])/1000 if 'book_timestamp_ms' in row else None,
            'spread_bps': row.get('spread_bps'), 'book_valid': 'spread_bps' in row,
            'source_mode': 'MARKET_ONLY', 'site': 'tr', 'intent_requested': False})
        dump(directory/'receipts.json', api.receipts)  # Preserve evidence after each symbol.
    pairs = []
    for a,b in itertools.combinations(hourly, 2):
        common = sorted(hourly[a].keys() & hourly[b].keys())
        x,y = [hourly[a][t] for t in common], [hourly[b][t] for t in common]
        if len(common) < 3:
            continue
        pairs.append({'a': a, 'b': b, 'aligned_closed_1H_returns': len(common),
            'start_ms': common[0], 'end_ms': common[-1], 'correlation': correlation(x,y),
            'equal_weight_rebalanced_log_return_proxy_std_bps_1H': statistics.pstdev([(u+v)/2 for u,v in zip(x,y)])*10000,
            'log_return_difference_std_bps_1H': statistics.pstdev([u-v for u,v in zip(x,y)])*10000,
            'execution_signal': False})
    dump(directory/'analysis.json', {'metrics': metrics, 'pair_combinations': pairs,
        'method': 'Closed contiguous OHLCV only; equal timestamp alignment; log returns; population std. '
                  '50/50 log-return average is a descriptive proxy, NOT executable backtest. No fees/slippage/PnL forecasts.'})
    dump(directory/'observations.json', observations)
    manifest = {'status': 'PARTIAL' if qa or any(not r['success'] for r in api.receipts) else 'PASS',
        'symbols': symbols, 'candles_raw': candle_count, 'public_trades': trade_count,
        'pair_combinations': len(pairs), 'qa_errors': qa, 'human_review_status': 'PENDING_HUMAN_REVIEW',
        'selection_bias': 'current high quote-volume USDT listings; not survivorship-free',
        'training_split': 'UNASSIGNED; group entire capture together; purge overlapping historical windows before any split',
        'test_and_challenge_modified': False, 'orders_sent': 0,
        'hashes': {p.name: sha(p) for p in directory.glob('*.json')}}
    dump(directory/'manifest.json', manifest)
    api.home.cleanup()
    print(json.dumps({'capture': str(directory), **{k:manifest[k] for k in ('status','candles_raw','public_trades','pair_combinations')}}))


def infer(directory):
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    import laya
    import torch
    directory = directory.resolve()
    if not directory.is_relative_to(ROOT/'data/atk_spot'):
        raise ValueError('only owned spot captures accepted')
    manifest = json.loads((directory/'manifest.json').read_text())
    for name, expected in manifest['hashes'].items():
        if sha(directory/name) != expected:
            raise ValueError('capture integrity failure: '+name)
    selected = ROOT/'models/aegis_laya_selected'
    record = json.loads((selected/'selection.json').read_text())
    for name, expected in record['hashes'].items():
        if sha(selected/name) != expected:
            raise ValueError('model integrity failure')
    agent = laya.load(str(selected), device='cuda', compile=False, fast=False)
    results, candidates, metadata = [], [], []
    variants = {'captured_monitoring': {}, 'stale_feed': {'feed_age_seconds': 60},
        'agent_disagreement': {'agents_disagree': True}, 'unknown_order': {'unknown_order': True},
        'duplicate_intent': {'duplicate_intent': True}, 'revoked_permission': {'permission_revoked': True},
        'tool_injection': {'injection_detected': True}, 'api_timeout': {'api_timeout': True},
        'malformed_quantity': {'intent_requested': True, 'quantity': 'NaN'},
        'missing_timestamp': {'feed_age_seconds': None}, 'unauthorized_live': {'source_mode': 'LIVE'}}
    for observed in json.loads((directory/'observations.json').read_text()):
        for name, changes in variants.items():
            facts = {**observed, **changes}
            # Archived capture age is deliberately evaluated AS OF its observation, never presented as live.
            label, reasons = classify(facts)
            if not facts['book_valid']:
                label, reasons = 'HALT', ['invalid_or_missing_orderbook', *reasons]
            state = json.dumps({'as_of': observed['observed_at'], 'facts': facts}, sort_keys=True)
            torch.cuda.synchronize()
            start = time.perf_counter()
            answer = agent.predict(state, QUESTIONS)['answers']['operational_state']
            torch.cuda.synchronize()
            predicted = answer['choice']
            # Fail closed: neither model nor deterministic policy can grant execution.
            effective = 'HALT' if 'HALT' in (label,predicted) else ('REVIEW' if 'REVIEW' in (label,predicted) else 'CONTINUE')
            index = len(candidates)
            candidates.append({'state': state, 'questions': QUESTIONS, 'expected': {'operational_state': label}})
            metadata.append({'row': index, 'symbol': observed['symbol'], 'scenario_family': name,
                'origin': 'SOURCE_DOCUMENTED_PUBLIC_CAPTURE' if name == 'captured_monitoring' else 'SYNTHETIC_DERIVED',
                'label_source': VERSION, 'human_review_status': 'PENDING_HUMAN_REVIEW',
                'group_id': directory.name, 'source_sha256': manifest['hashes']['observations.json']})
            results.append({'symbol': observed['symbol'], 'scenario': name, 'policy_label': label,
                'policy_reasons': reasons, 'model_label': predicted, 'effective_monitoring_label': effective,
                'probabilities': answer.get('probabilities'), 'confidence': answer.get('confidence'),
                'confidence_calibrated': False, 'latency_ms': (time.perf_counter()-start)*1000,
                'execution_authority': False})
    (directory/'candidates.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in candidates), encoding='utf-8')
    dump(directory/'candidate_metadata.json', metadata)
    with (directory/'candidate_metadata.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metadata[0]))
        writer.writeheader()
        writer.writerows(metadata)
    report = {'model_version': record['version'], 'shadow_only': True, 'as_of_capture_not_live': True,
        'model_policy_disagreements': sum(r['policy_label'] != r['model_label'] for r in results),
        'dangerous_halt_to_continue': sum(r['policy_label']=='HALT' and r['model_label']=='CONTINUE' for r in results),
        'rows': results, 'production_approved': False, 'orders_sent': 0}
    dump(directory/'laya_shadow.json', report)
    counts = dict(Counter(r['expected']['operational_state'] for r in candidates))
    dump(directory/'candidate_qa.json', {'schema_rows': len(candidates), 'counts': counts,
        'unique_state_rows': len({r['state'] for r in candidates}), 'metadata_rows': len(metadata),
        'split': 'UNASSIGNED_SINGLE_CAPTURE_GROUP', 'human_review_complete': False,
        'test_contamination_prevented_by': 'No existing dataset changed; no training or split performed',
        'known_shortcut_risk': 'unsupported symbols dominate HALT; cannot infer model generalization',
        'source_urls': ['https://github.com/okx/agent-tradekit',
            'https://www.okx.com/docs-v5/en/#order-book-trading-market-data',
            'https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md']})
    analytics = json.loads((directory/'analysis.json').read_text())
    lines = ['# ATK + LAYA spot araştırması', '', f'Capture (UTC): {directory.name}', '',
        f"Gerçek ATK: {manifest['candles_raw']} ham mum, {manifest['public_trades']} public işlem, "
        f"{len(manifest['symbols'])} spot çift, {manifest['pair_combinations']} ikili kombinasyon. QA: {manifest['status']}.", '',
        '## Likidite ve oynaklık', '',
        '| Çift | Spread bps | 50 seviye bid / ask USDT | 1H std bps | Politika kapsamı |',
        '|---|---:|---:|---:|---|']
    for row in sorted(analytics['metrics'], key=lambda r:r.get('spread_bps', float('inf'))):
        vol = row['intervals'].get('1H', {}).get('log_return_std_bps_per_bar')
        lines.append(f"| {row['symbol']} | {row.get('spread_bps',0):.3f} | "
            f"{row.get('bid_depth_50_usdt',0):,.0f} / {row.get('ask_depth_50_usdt',0):,.0f} | "
            f"{vol:.2f} | {'BTC monitoring' if row['policy_supported'] else 'OUT OF SCOPE / HALT'} |" if vol is not None
            else f"| {row['symbol']} | Eksik veri | — | — | MANUAL REVIEW |")
    lines += ['', '## Saatlik eşleştirilmiş kombinasyonlar', '',
        'Aşağıda en düşük korelasyonlu 10 kombinasyon; 45 kombinasyonun tamamı analysis.json içinde.', '',
        '| A / B | Korelasyon | Eşleşen saat | 50/50 log-getiri proxy std (bps/saat) |',
        '|---|---:|---:|---:|']
    for row in sorted((r for r in analytics['pair_combinations'] if r['correlation'] is not None), key=lambda r:r['correlation'])[:10]:
        lines.append(f"| {row['a']} / {row['b']} | {row['correlation']:.4f} | {row['aligned_closed_1H_returns']} | "
            f"{row['equal_weight_rebalanced_log_return_proxy_std_bps_1H']:.2f} |")
    lines += ['', '## LAYA entegrasyonu ve sınırlar', '',
        f"Yerel CUDA shadow inference: {len(results)} senaryo. Politika/model uyuşmazlığı: "
        f"{report['model_policy_disagreements']}; tehlikeli HALT → CONTINUE: {report['dangerous_halt_to_continue']}.", '',
        f"Aday etiket sayıları: {counts}. Tamamı PENDING_HUMAN_REVIEW; gold etiket DEĞİL.", '',
        '- Model seçimi: mevcut base checkpoint; sürüm/hash: '+record['version']+'.',
        '- Deterministik veto ve modelin daha kısıtlayıcı kararı korunur. Hiçbiri işlem izni vermez.',
        '- Model güveni kalibre değil; üretim onayı yok. Bu tarama doğruluk testi veya benchmark değildir.',
        '- ETH/SOL ve diğer semboller mevcut BTC-only politikası dışında: otomatik trade kapsamına eklenmedi.',
        '- Anlık orderbook/ticker ölçümleri eşzamanlı değil; snapshotlar artık güncel sayılmaz.',
        '- 50 seviyelik derinlik sabit fiyat bandı değildir; çiftler arasında doğrudan karşılaştırmak yanıltabilir.',
        '- Korelasyon kısa, seçilim yanlı bir penceredir; stablecoin çiftleri de bulunabilir. Düşük korelasyon alım tavsiyesi değildir.',
        '- 50/50 log-getiri ortalaması sadece betimsel proxy: gerçek sepet, arbitraj, ücret/slippage veya kâr backtesti değildir.',
        '- Tarihsel mumlar fiyat/gelecek getiri etiketi olarak kullanılmadı. Açık mumlar analiz dışında.',
        '- Sentetik sorunlar gerçek incident diye sunulmaz. Her senaryo aynı capture grubunda tutulur.',
        '- Yeni veri train/val/test/challenge ile birleştirilmedi. Örtüşen zaman pencereleri purge edilmeden split yapılmamalı.',
        '- Backend/frontend değiştirilmedi. Bu, çalıştırılmış yerel ATK→LAYA araştırma hattıdır; backend servis entegrasyonu değildir.',
        '- Emir, private endpoint, credential okuma veya yeni paket kurulumu yok.', '',
        '## Tekrar çalıştırma', '', '```powershell',
        '# Mevcut CUDA Python ortamından:', 'python scripts/ml/spot_research.py collect',
        'python scripts/ml/spot_research.py infer data/atk_spot/<capture-id>', '```', '',
        '## Kaynaklar', '',
        '- https://github.com/okx/agent-tradekit',
        '- https://www.okx.com/docs-v5/en/#order-book-trading-market-data',
        '- https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md', '',
        'Cleanup: önce backup, sonra yalnızca bu capture ve scripts/ml/spot_research.py, '
        'test_spot_research.py, atk_public_isolation.mjs eklerini overlap kontrolüyle kaldır. '
        'Mevcut checkpoint, backend ve owner dosyalarına dokunma. System-wide değişiklik: NONE.', '']
    (directory/'SPOT_RESEARCH_REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    (directory/'DATASET_CARD.md').write_text(
        '# Public spot capture + operational candidates\n\n'
        f'Raw candle count: {manifest["candles_raw"]}. Candidate count: {len(candidates)}. Labels: {counts}.\n\n'
        'Only public live-market data. Private account data absent. Numeric market facts are captured evidence; '
        'policy outcomes are derived candidate labels, not human-reviewed gold. Synthetic perturbations are marked '
        'in candidate_metadata.csv. The capture is one unsplit provenance group. The existing held-out test and '
        'challenge datasets remain untouched. Human annotation, broader supported-symbol policy and independent '
        'time/source-group split review are required before training. Do not train directly on raw OHLCV as '
        'operational-state ground truth. Shadow model predictions must not become training labels.\n', encoding='utf-8')
    dump(directory/'derived_hashes.json', {p.name: sha(p) for p in directory.iterdir() if p.name in
        ('candidates.jsonl','candidate_metadata.json','candidate_metadata.csv','candidate_qa.json',
         'laya_shadow.json','SPOT_RESEARCH_REPORT.md','DATASET_CARD.md')})
    print(json.dumps({k:v for k,v in report.items() if k!='rows'}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['collect','infer'])
    parser.add_argument('capture', nargs='?', type=Path)
    args = parser.parse_args()
    if args.mode == 'collect':
        collect()
    elif args.capture:
        infer(args.capture)
    else:
        parser.error('infer requires capture path')
