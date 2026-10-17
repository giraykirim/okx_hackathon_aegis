# P2-01 actual status

PASS: actual NVIDIA and PyTorch CUDA detection; real GPU tensor multiplication; deterministic operational label proposal; official LAYA state/questions/expected JSONL; grouped 70/15/15 base split; 12 HALT challenge cases; metadata/source/capture/policy hashes; structural QA and official LAYA reader compatibility; regression tests for QA tampering, fake review, family leakage, numeric boundaries and HALT precedence.

Data: 80 base + 12 challenge = 92 candidates. Train C/R/H=12/12/32; validation 4/4/4; test 4/4/4; challenge 0/0/12. Declared family groups 14/3/3 plus one compound challenge group. Source incident derivations and all local capture rows stay together. No model has been trained or evaluated on these files.

Hardware: actual RTX 4060 Laptop, approximately 8 GiB (nvidia-smi 8188 MiB; PyTorch total allocation reports floor 8187 MiB), not RTX 4070. LAYA 0.4.8, PyTorch 2.14.1+cu130, Python 3.13.16 reused. ml/environment.json contains the actual timestamped measurements. No new installation, driver change or model download.

ACTION REQUIRED: genuine human review of all 92 candidates and Person 1 acknowledgment of the proposed context mapping/label policy. Training approval is false. The --require-human-review gate intentionally exits nonzero. No generated label is marked HUMAN_REVIEWED.

DEVIATION: Parallel FindAll was unavailable; two primary-source incidents were researched using official SEC and Cloudflare pages instead. No FindAll run is claimed. The requested manually reviewed source subset is not available yet. This is a candidate seed set, not full P2-01 acceptance.

NOT_TESTED: semantic near-duplicate audit, empirical generalization, checkpoint training/inference/calibration, held-out model metrics, LAN /classify integration. P2-02 and P2-03 instructions were not supplied and were not executed.

Changed/created only: ml/{label_policy.py,LABEL_POLICY.md,PERSON1-HANDOFF.md,environment.json,P2-01-STATUS.md,CHANGELOG.md}, data/{train.jsonl,val.jsonl,test.jsonl,challenge.jsonl,metadata.csv,sources.json,atk_public_sanitized.json,manifest.json,qa_report.json,DATASET_CARD.md}, scripts/ml/{build_dataset.py,qa_dataset.py,test_dataset.py,check_environment.py} and normal Python __pycache__ files in owned folders. Backend and web3 files were not modified.

Rerun structural checks from repository root with the existing GPU interpreter:
`..\aegis\.venv\Scripts\python.exe scripts/ml/qa_dataset.py`
`..\aegis\.venv\Scripts\python.exe scripts/ml/test_dataset.py`

Review LABEL_POLICY.md, DATASET_CARD.md and PERSON1-HANDOFF.md before starting any training. Do not tune against test/challenge labels or claim model performance from structural QA.
