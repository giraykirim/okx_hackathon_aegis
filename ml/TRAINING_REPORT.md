# P2-02 local LAYA experiment — completed, no accuracy improvement

Actual device: NVIDIA RTX 4060 Laptop, nvidia-smi 8188 MiB VRAM, not an RTX 4070. Python 3.13.16, official LAYA 0.4.8, PyTorch 2.14.1+cu130 / CUDA 13.0. The existing GPU environment was reused unchanged. No Kaggle, driver change or system installation. Seed 17.

## Result and selected checkpoint

`models/aegis_laya_selected` is a loadable local **base** checkpoint, selected because head-only did not improve validation accuracy. It is NOT an AEGIS-trained success claim. The head-only and smoke artifacts remain available separately for inspection.

Upstream English checkpoint: convaiinnovations/laya, actual revision `7b928d828b7b0e022f929d9bd2e44165aa270148`.
Selected artifact version SHA-256: `f38a07fa01dbf242cc120da859b2cffa18eb8631b28db88d2e54e14876a15c3e`.
Per-file hashes: models/aegis_laya_selected/selection.json and ml/runs/select.json. Aggregate hash covers the sorted JSON mapping of checkpoint files (weights/config/encoder/tokenizer/question), excluding generated selection sidecars. Run verify_selected.py for independent integrity/offline checks.

The published base snapshot did not include a local encoder config. To make the selected base self-contained, only its matching encoder architecture config was copied from the official smoke export. The selected weights remain the original base weights; smoke/head weights are not substituted.

## Executed order and measurements

Installed `laya-train --help` was inspected and current official docs were read before running: https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md

| Run | Train accuracy (56) | VAL accuracy (12) | VAL HALT→CONTINUE | VAL median ms | Wall seconds | Peak allocated MiB | Peak reserved MiB |
|---|---:|---:|---:|---:|---:|---:|---:|
| Base | 28.57% | 66.67% | 3 / 4 | 34.06 | 106.65 | 2318.51 | 2520 |
| Smoke, one epoch | 28.57% | 66.67% | 3 / 4 | 31.27 | 17.98 | 2329.91 | 2516 |
| Head-only, four epochs | 28.57% | 66.67% | 3 / 4 | 32.06 | 27.68 | 2329.91 | 2516 |

Wall times are stage end-to-end, including loading, checkpoint saves and train/VAL measurements; base time includes initial download. Peak figures are PyTorch process allocations/reservations, not total system GPU usage. Latency is synchronized per-query wall time after a separately recorded warm-up, not a service/network benchmark. Per-query outputs, class confusion, first/warm-up outputs and timings are in ml/runs/{baseline,smoke,head}.json.

A. Real typed-choice base inference on CUDA passed. Train and VAL outputs recorded; no test or challenge inference.
B. Structural QA passed. Exact official dry-run `laya-train --data data/train.jsonl --base english --dry-run` accepted 56/56 items, skipped none. Its default four-epoch effective batch 64 budget was only four optimizer updates; that is the dry-run default, not our actual training configuration.
C. Smoke used 36 balanced rows from TRAIN (12/class), one epoch, freeze encoder, micro-batch 1, accumulation 4, soft-ce, CUDA. Official internal split: 33 optimizer-training + 3 calibration items. Nine scheduled update opportunities. Mean epoch loss 1.1210. Save/reload/inference passed; no OOM.
D. Head-only used all 56 train rows; official internal split 51 optimizer-training + 5 calibration items, four epochs, micro-batch 1, accumulation 4. 52 scheduled update opportunities. Mean epoch losses: 1.1396, 1.1151, 1.0873, 1.0807. These are scheduled budgets; GradScaler successful-step counts were not instrumented. Actual official saved settings and VAL report are in models/aegis_laya_head/train_report.json; console output in ml/runs/head-console.log. CUDA fp16 autocast/GradScaler and default head gradient checkpointing were used by the official training path.
E. Full encoder fine-tuning was not run. The candidate set is tiny/unreviewed, head-only produced no accuracy gain, and full AdamW state/gradients would substantially increase memory on an 8 GiB laptop. A bounded completed experiment and known base were retained instead of speculative training/OOM retries.

The independent VAL set was only scored, never used for gradient updates or temperature fitting. LAYA reported zero normalized train/calibration overlap with its 12 VAL items. Its internal 3/5-item calibration split is random within TRAIN and is not scenario-family-separated; calibration reliability must not be claimed. Internal calibration requires at least ten items, so calibration was explicitly NOT FITTED and temperature remained 1.0. Head VAL ECE changed 0.2300 → 0.2500, i.e. worsened. Base loader also warned about an unrelated 11+-option shipped temperature being clamped; our question has three options.

Predeclared selection rule in run_training.py: head must strictly improve VAL accuracy and not increase HALT→CONTINUE count. It did not, so base was selected. No repeated seed/hyperparameter search was performed. No test/challenge data were used for training, selection, calibration or inference. Their hashes remain fixed; structural QA is not model evaluation.

## Reproduce

From repo root, with the existing sibling GPU Python environment (all cache/artifacts stay under this repo's models):

```powershell
..\aegis\.venv\Scripts\laya-train.exe --help
..\aegis\.venv\Scripts\python.exe scripts/ml/run_training.py baseline
..\aegis\.venv\Scripts\python.exe scripts/ml/qa_dataset.py
..\aegis\.venv\Scripts\python.exe scripts/ml/run_training.py dry-run
..\aegis\.venv\Scripts\python.exe scripts/ml/run_training.py smoke
..\aegis\.venv\Scripts\python.exe scripts/ml/run_training.py head
..\aegis\.venv\Scripts\python.exe scripts/ml/run_training.py select
..\aegis\.venv\Scripts\python.exe scripts/ml/verify_selected.py
```

Training/select stages refuse to overwrite existing artifacts; for another experiment choose a new output version rather than deleting the reliable checkpoint.
The harness calls the installed official laya.train_cli.main with inspected CLI flags. Actual head command equivalent (HF_HOME=models/hf-cache):

```text
laya-train --data data/train.jsonl --base english --out models/aegis_laya_head --eval data/val.jsonl --epochs 4 --micro-batch 1 --grad-accum 4 --freeze-encoder --device cuda --loss soft-ce --seed 17
```

## Limitations / next blocker

All 92 original candidates still await genuine human review. The user's P2-02 instruction authorized an exploratory run; it does not turn them into human gold labels. Observed train/VAL scores measure this synthetic candidate policy only. The high HALT false-negative rate means the selected model MUST remain advisory with deterministic backend vetoes; production readiness is false. No service or backend integration was changed. Person 1 context mapping acknowledgment and real annotation review remain pending; P2-03 was not executed.

Large checkpoint/cache directories are ignored by models/.gitignore. Never push these binaries casually. No Hugging Face token was requested and no model was published. For return cleanup, back up desired results and remove only task-created models/hf-cache, aegis_laya_smoke, aegis_laya_head, aegis_laya_selected and P2 run reports after verifying no teammate work overlaps. The earlier Python environment is reused and outside this cleanup scope.
