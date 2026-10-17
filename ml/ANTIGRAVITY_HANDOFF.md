# AEGIS — Codex → Antigravity / Claude Opus 5.5 handoff

Snapshot: 17 October 2026, approximately 16:34 TRT. Treat this as a dated handoff;
verify current facts before acting. User has roughly three hours remaining as of
the preceding readiness review. Communicate concisely in Turkish.

## Workspace and ownership

Existing repo (reuse, do NOT clone/copy over it):
`C:\Users\hackathon\Documents\Codex\2026-10-16\bu-bilgisayar-d-n-al-nm\okx_hackathon_aegis`

Remote: `https://github.com/giraykirim/okx_hackathon_aegis.git`.
Branch main; last verified local/remote commit:
`b949b19ef9fdf13cd38cb86b4e3963d5e4be609d`.
Last pull merged four team commits while preserving local ML commit `48716e1`;
normal non-force push succeeded. Tree was clean BEFORE this handoff file was added.
This handoff file is initially local/uncommitted; do not silently push unrelated changes.

Person 2 owns `ml/**`, `data/**`, `models/**`, `scripts/ml/**`.
Backend/frontend/web3 belong to teammates: read to diagnose, coordinate before edits.
Respect applicable AGENTS.md; preserve other people's dirty work. No automatic
pull/merge/reset/rebase/force-push. Show edited code/reports in the user's IDE.

## Borrowed-machine constraints — mandatory

Only Windows hackathon account. Do not inspect owner homes/browser profiles,
credential stores, .env, auth files, tokens, private keys, seed phrases or unrelated logs.
Never ask for or print credentials. No real/demo orders or private ATK account calls.
No driver/BIOS/update, WSL/Docker, Defender/firewall/registry/PATH/system changes.
No new dependencies unless truly needed; current environment works.
Maintain the existing Desktop/outputs HACKATHON-CHANGES and CLEANUP logs safely,
checking for concurrent changes before overwriting a copy. Never run cleanup now.
Do not import another app's auth/session/cache into Antigravity.

## Runtime and commands

Actual device: RTX 4060 Laptop, 8188 MiB VRAM, NOT RTX4070. RAM total ~15.29GiB;
last free RAM only ~2.34GiB while inference service ran. Disk free ~176GiB.

GPU Python, reused without installation:
`C:\Users\hackathon\Documents\Codex\2026-10-16\bu-bilgisayar-d-n-al-nm\aegis\.venv\Scripts\python.exe`

Git: `C:\Users\hackathon\AppData\Local\HackathonTools\git\cmd\git.exe`.
Ruff: repo `backend\.venv\Scripts\ruff.exe`.
Python3.13.16, LAYA0.4.8, torch2.14.1+cu130/CUDA13.0. Use local official CLI/help.

From repo root, safe regression command:
`..\aegis\.venv\Scripts\python.exe -m unittest discover -s scripts/ml -p test_*.py -q`

Latest completed check: **236/236 ML/offline tests PASS** after the merge.
Not a full new backend/frontend E2E pass. Six development packages passed official
dry-run with no skipped items or sequence truncation; dry-run is NOT model quality.

## Selected checkpoint / active service

`models/aegis_laya_selected` is still **BASE**, NOT a successful V2 fine-tune.
Version `f38a07fa01dbf242cc120da859b2cffa18eb8631b28db88d2e54e14876a15c3e`.
Weights/config/question hashes in its selection.json; preserve all originals.
Local weights/cache/checkpoints are intentionally Git-ignored, present on this PC.

Service is ALREADY RUNNING, no second instance needed:
- POST `http://192.168.2.60:8770/classify`, binds `0.0.0.0:8770`.
- GET `/healthz`.
- model_version `aegis-laya-base-f38a07fa01db`.
- Actual model Python PID at snapshot:23216. Revalidate PID; never blindly kill it.
- Code `scripts/ml/serve_selected.py`.
- Runtime/startup logs `ml/lan_inference/selected-20261017-v1/`.
- Stop helper `scripts/ml/stop_selected_service.ps1`; supports -WhatIf and confirmation,
  checks PID command/script/runtime binding. NOT executed by this handoff.

Real CUDA inference is verified for complete canonical operational input. Returned
choice/confidence come from actual `agent.predict`, not the deterministic label oracle.
Unsupported/missing/null context or legacy Observation -> REVIEW,confidence0,abstained=true.
Run/correlation metadata never enters model input. Full typed facts are caller assertions,
not proof of real account permission. Service is SHADOW ONLY and cannot send orders.
No auth/TLS; isolated trusted LAN only; no firewall change. Same-PC LAN-IP HTTP smoke
passed, but a different physical device has NOT been verified.

Model's sample confidence0.0065 is not calibrated trade permission. The service
automatically loading a newly trained candidate is NOT implemented: selected path
is fixed. Preserve base and plan separate shadow deployment/rollback after acceptance.

## Current training decision: NO-GO for validated fine-tuning / promotion

The technical learning pipeline works, but real-task gates are NOT satisfied:

1. **20 unresolved V2 policy differences**; user explicitly asked to preserve decisions.
2. **No actual Person1 trusted-context/architecture approval**; backend_ack false.
3. **No independent source-grouped, blind-reviewed VAL/final bundle**.

Do not edit flags or invent review/provenance to bypass these gates. Running training
successfully does not solve integration, labels or independence.

### Actual human-reviewed data (preserve)

V1: `data/reviewed_learning/review-1c9cf35-v1/human_confirmed_unsplit_v1`,120 rows,
C40/R40/H40. AI-assisted human-final decisions, not blind or independent final gold.
Old720 lifecycle:15families/one public capture, synthetic development candidates.

V2: `data/reviewed_learning/expanded-v2-20261017T120738Z/`.
Frozen approved-human development export: `human_confirmed_unsplit_v2-r169/`.
161 reviews, ledger revision169, SHA
`0bb717f012d071e57ffeebcd917843010ca90e89771f2d77f6b8fc0ec23c2dcf`.
Final C36/R76/H49. AI_ASSISTED_HUMAN_CONFIRMED; blind=false.
Only39valid-size profiles x4quantities +5invalid numeric cases =161 rows;
44quantity-stripped contexts are NOT44proven independent incidents.
40actual pure Store/policy offline fixture replays, NOT real ATK/exchange logs.
11diagnostic-only probes lack model-input fields; do not add them to training blindly.

User decisions (do NOT ask to silently undo/relabel):
-16 age>15 or age<-2 REVIEW decisions preserved vs legacy HALT, difference OPEN.
-8 age=-2/-1.9 REVIEW->CONTINUE explicitly corrected by user; already applied.
-4no-intent/unknown permission CONTINUE decisions preserved vs proposed REVIEW.
  Legacy policy also CONTINUE here: this is proposed-rule-only difference.
No other153 review entries changed during targeted adjudication.

### Five-group Person1 decision package

`ml/policy_alignment/v2-r169-step1/evidence.json` contains all20cases and40executed
offline pure policy.check calls (human/reference label stubs). All40blocked; this is
NOT model/ATK evidence and does not settle label semantics. Groups, four rows each:

| group_id | case | human / legacy / proposed |
|---|---|---|
|6035c658446bc766|age40 + approval false|REVIEW / HALT / HALT|
|b507903e784e923b|age-2.1|REVIEW / HALT / HALT|
|bd4f3224298b7c68|age15.1|REVIEW / HALT / HALT|
|c328abb0010e5796|age40 + approval true|REVIEW / HALT / HALT|
|cb09120331fb2593|no intent, permission_revoked null|CONTINUE / CONTINUE / REVIEW|

Person1 must give agreed semantics/reason/version, any implementation commit/test
evidence, and preserve stale/future/approval/unresolved/duplicate execution vetos.
No Person1 answer has been received at handoff. A blank/null template is NOT an ACK.

Existing classify is called BEFORE reason creates proposal. Approval/journal/duplicate
binding occurs later. Even newly pulled integrations still send Observation. Thus
intent/quantity/authorization facts cannot be invented in the earlier model input.
Person1 must choose observation-only scope or a coordinated post-proposal trusted
operational context stage; do not unilaterally change the frozen HTTP envelope.

16 context fields: symbol,site,source_mode,feed_age_seconds,intent_requested,quantity,
account_known,approval_available,api_timeout,agents_disagree,unknown_order,
duplicate_intent,permission_revoked,injection_detected,deployment_integrity_failure,
excess_exposure. Unknown remains null, not false. Unresolved is not always unknown order.

## Historical learning evidence — not new evaluation

Debug positive control: `ml/debug_learning/20261017T104341Z/result.json`,48train/12debugVAL,
deliberate DEBUG_LABEL input,12/12pass at8epochs/save-reload. NEVER mix with task data.

Quarantined V1 development run `ml/reviewed_development/20261017T114335800999Z`:
seed17=75/120, H->C10/R->C7; seed29=74/120,H->C0/R->C3. Not independent evaluation.
On valid-quantity-constant diagnostic seed29 changed28answers and H->C became10;
numeric shortcut risk remains. No candidate was promoted; selected remains base.

## Gates / next action

First read current repo status and this file; preserve work; inspect actual Person1
response if the user provides it. Summarize GO/NO-GO briefly, not another huge plan.
Do NOT start training merely because the handoff says 'continue'.

Real training requires existing `reviewed_learning.validate_bundle` to pass:
source-grouped60train/30VAL/30final,20/10/10perclass, real review/provenance and
backend ACK. All source/parent/paraphrase relatives stay in one split; different
ID/seed/time/quantity does not create independence. AI-assisted train may be truthful;
VAL/final need independent blind review. Missing evidence -> DATA/INTEGRATION BLOCKED.

If gates genuinely pass AND training is authorized, scheduled own-service stop and
RAM/VRAM recheck first. Official head-only/soft-ce/micro1/accum1/8epochs/seeds17,29,
max30min each; no full encoder, OOM thrashing or hyperparameter sweep. Select only VAL.
Acceptance: H->C0,R->C0,C recall>=.8,Macro-F1>=.8,invalid/truncated0. Final exactly once
only after VAL passes. Confidence is not a calibrated safety gate. Successful result
is SHADOW CANDIDATE, never automatic trade authority or production safety proof.

Do not sacrifice stable demo for speculative model improvement. Retain original
checkpoints/datasets/decisions and deterministic execution vetoes; no real/demo orders.
After actual changes run relevant tests, show files in IDE, update change/revert log.

## Additional human-facing files (outside repo, optional authorized access)

Workspace outputs directory:
`C:\Users\hackathon\Documents\Codex\2026-10-16\bu-bilgisayar-d-n-al-nm\outputs`
Read only specifically named artifacts if access is permitted; never scan the home:
AEGIS-SON-3-SAAT-KARAR-RAPORU.md, AEGIS-PERSON1-ILK-ADIM.md,
AEGIS-PERSON1-YANIT-SABLONU.json, AEGIS-LAYA-ORNEK-ISTEK.json,
AEGIS-LAYA-HTTP-SERVISI.md, HACKATHON-CHANGES.txt, HACKATHON-CLEANUP.md.
The essential facts are already in this handoff; credentials/session exports are neither
needed nor authorized. There is no automatic transfer of Codex conversation/auth history.
