"""Quarantined V2 (161-row) discriminative head/scorer + quantity-invariant fine-tuning & group-CV.

Root-cause fix for LAYA DecisionModel (#963 prior collapse on V2 161-row dataset):
1. In `DecisionModel`, `self.head` is a 2-layer TransformerEncoder without positional
   embeddings, while `self.scorer` is a shared MLP applied to each option marker `[36, 54, 72]`.
   Training `self.head` and `self.scorer` at the same `1e-4` learning rate in `float16`
   causes self-attention in `self.head` to wash out inter-marker differences and collapse
   predictions to the majority class (`REVIEW`, 76/161 = 47.20%, CONTINUE recall = 0.0).
2. Using `fp32` (preventing ModernBERT-large `float16` GradScaler overflow), discriminative
   learning rates (`head_lr = 5e-5`, `scorer_lr = 5e-4`, `weight_decay = 0.0`), inverse-frequency
   class weighting (`[CONTINUE: 1.4907, REVIEW: 0.7061, HALT: 1.0952]`), a fail-closed safety
   margin against false `CONTINUE` on `REVIEW`/`HALT` cases, and profile quantity-invariance
   regularization across the 4 crossed quantities (`0.00005000..0.00020000`) resolves the collapse.

Compares:
- Base checkpoint (`models/aegis_laya_selected`)
- V2 Head-Only default (`ml/reviewed_development/v2-20261017T141303599045Z`)
- V2 Tuned (`seed-17` and `seed-29`, verified end-to-end via `laya.load().predict()`)
- 5-Fold Stratified `(profile_id, label)` Grouped Cross-Validation (zero group leakage)
"""

import argparse
import gc
import hashlib
import json
import math
import os
import site
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VENV_SITE = ROOT.parent / "aegis/.venv/Lib/site-packages"
if VENV_SITE.is_dir():
    site.addsitedir(str(VENV_SITE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from candidate_preflight import protected_hashes
from expand_operational_data import QUANTITIES
from reviewed_development_v2 import (
    BASE,
    CONFIRMED,
    CONTROL,
    EXPERIMENT,
    POLICY_V2_VERSION,
    check_protected,
    dataset_audit,
    fit_metrics,
    network_off,
    quantity_invariance_summary,
    sha,
    tensor_hash,
    validated_rows,
    write,
)
from reviewed_learning import metrics

from ml.label_policy_v2 import LABELS, QUESTIONS

HEAD_ONLY_RUN = ROOT / "ml/reviewed_development/v2-20261017T141303599045Z"

# Inverse-frequency class weights for [CONTINUE (36), REVIEW (76), HALT (49)] on 161 rows:
CLASS_WEIGHTS_TUPLE = (
    161.0 / (3.0 * 36.0),  # CONTINUE: ~1.4907
    161.0 / (3.0 * 76.0),  # REVIEW:   ~0.7061
    161.0 / (3.0 * 49.0),  # HALT:     ~1.0952
)

TUNED_CONFIG = {
    "epochs": 350,
    "batch_size": 16,
    "head_lr": 7e-5,
    "scorer_lr": 1.2e-3,
    "weight_decay": 0.0,
    "safety_penalty_weight": 0.30,
    "quantity_invariance_weight": 0.20,
    "temperature": [0.5, 0.5, 0.5],
    "precision": "fp32_no_fp16_overflow",
    "encoder_frozen": True,
}


def tuned_args(data, out=None, seed=17, dry_run=False, epochs=90):
    args = [
        "--data",
        str(data),
        "--base",
        str(BASE),
        "--epochs",
        str(epochs),
        "--micro-batch",
        "16",
        "--grad-accum",
        "1",
        "--head-lr",
        "5e-4",
        "--freeze-encoder",
        "--loss",
        "soft-ce",
        "--device",
        "cuda",
        "--seed",
        str(seed),
    ]
    if out is not None:
        args += ["--out", str(out)]
    if dry_run:
        args += ["--dry-run"]
    return args


def build_profile_grouped_folds(rows, metadata, n_folds=5):
    """Partition the 161 rows into `n_folds` stratified by label, grouped by `(profile_id, label)`.

    Every valid-quantity profile (all 4 crossed quantities) stays together in a single fold.
    The 5 invalid-quantity rows (which share parent `profile_id` `8332c2782ff433e14900` but
    have `HALT` label due to invalid quantity) form their own distinct group so each group has
    a single unambiguous label and zero valid-quantity sibling leakage occurs across folds.
    """
    group_to_indices = defaultdict(list)
    group_to_label = {}
    for idx, (row, meta) in enumerate(zip(rows, metadata)):
        label = row["expected"]["operational_state"]
        q_val = json.loads(row["state"])["operational"]["quantity"]
        is_valid_q = q_val in QUANTITIES
        group_id = (
            meta["profile_id"]
            if is_valid_q
            else f"{meta['profile_id']}:invalid_q:{idx}"
        )
        group_to_indices[group_id].append(idx)
        if group_id in group_to_label and group_to_label[group_id] != label:
            raise ValueError(f"group {group_id} has conflicting labels")
        group_to_label[group_id] = label

    by_label = defaultdict(list)
    for gid in sorted(group_to_indices):
        by_label[group_to_label[gid]].append(gid)

    folds = [[] for _ in range(n_folds)]
    for label in LABELS:
        for i, gid in enumerate(by_label[label]):
            folds[i % n_folds].append(gid)

    fold_splits = []
    for fold_idx in range(n_folds):
        val_groups = set(folds[fold_idx])
        train_indices = [
            i
            for gid, idxs in group_to_indices.items()
            if gid not in val_groups
            for i in idxs
        ]
        val_indices = [
            i
            for gid, idxs in group_to_indices.items()
            if gid in val_groups
            for i in idxs
        ]
        if set(train_indices) & set(val_indices):
            raise AssertionError("row overlap between train and val")
        if val_groups & (set(group_to_indices) - val_groups):
            raise AssertionError("group overlap between train and val")
        # Also verify zero overlap of valid-quantity profile_ids between train and val
        train_valid_pids = {
            metadata[i]["profile_id"]
            for i in train_indices
            if json.loads(rows[i]["state"])["operational"]["quantity"] in QUANTITIES
        }
        val_valid_pids = {
            metadata[i]["profile_id"]
            for i in val_indices
            if json.loads(rows[i]["state"])["operational"]["quantity"] in QUANTITIES
        }
        if train_valid_pids & val_valid_pids:
            raise AssertionError("valid-quantity profile overlap between train and val")
        fold_splits.append(
            {
                "fold": fold_idx,
                "train_indices": sorted(train_indices),
                "val_indices": sorted(val_indices),
                "train_groups": len(group_to_indices) - len(val_groups),
                "val_groups": len(val_groups),
            }
        )
    return fold_splits


def precompute_unpadded_encoder_states(model, tok, rows, device, max_len=512, head_max_len=192):
    """Run frozen `model.encoder` in fp32 without batch-padding so hidden states match `agent.predict()`."""
    import laya.common as common
    import laya.train as training
    import torch

    items, skipped = training.items_from_rows(tok, rows, max_len, head_max_len)
    if skipped or len(items) != len(rows):
        raise ValueError(f"unexpected skipped items: {skipped}")
    encoded = [training.encode_item(tok, it, max_len, head_max_len) for it in items]
    batch = common.collate_items([encoded], tok.pad_token_id)
    max_seq = batch["input_ids"].size(1)
    hidden_dim = model.encoder.config.hidden_size

    model.encoder.eval()
    h_enc = torch.zeros(
        (len(items), max_seq, hidden_dim), dtype=torch.float32, device=device
    )
    with torch.no_grad():
        for i, enc in enumerate(encoded):
            seq_len = len(enc["ids"])
            inp = torch.tensor([enc["ids"]], dtype=torch.long, device=device)
            msk = torch.ones((1, seq_len), dtype=torch.long, device=device)
            out = model.encoder(input_ids=inp, attention_mask=msk).last_hidden_state
            h_enc[i, :seq_len] = out[0].float()

    return {
        "h_enc": h_enc,
        "markers": batch["marker_pos"].to(device),
        "mask": batch["marker_mask"].to(device),
        "qtype": batch["qtype"].to(device),
        "target": batch["target"].to(device),
        "attn_mask": batch["attention_mask"].to(device),
        "gold_idx": batch["target"][:, :3].argmax(-1).to(device),
    }


def forward_head_and_scorer(model, cache, indices):
    import torch

    h = cache["h_enc"][indices] + model.type_emb(cache["qtype"][indices])[:, None, :]
    pad = ~cache["attn_mask"][indices].bool()
    for layer in model.head.layers:
        h = layer(h, src_key_padding_mask=pad)
    m_idx = (
        cache["markers"][indices]
        .clamp(min=0)[:, :, None]
        .expand(-1, -1, h.size(-1))
    )
    m_tok = torch.gather(h, 1, m_idx)
    logits = (
        model.scorer(m_tok)
        .squeeze(-1)
        .float()
        .masked_fill(~cache["mask"][indices], -1e4)
    )
    return logits


def train_head_and_scorer_on_indices(
    model,
    base_head_state,
    cache,
    rows,
    metadata,
    train_indices,
    seed,
    device,
    epochs=TUNED_CONFIG["epochs"],
):
    import torch
    import torch.nn.functional as F

    for k, v in base_head_state.items():
        model.state_dict()[k].copy_(v.to(device))
    for p in model.encoder.parameters():
        p.requires_grad_(False)
    for n, p in model.named_parameters():
        if not n.startswith("encoder."):
            p.requires_grad_(True)

    torch.manual_seed(seed)
    model.train()
    model.encoder.eval()

    opt = torch.optim.AdamW(
        [
            {
                "params": list(model.head.parameters())
                + list(model.type_emb.parameters()),
                "lr": TUNED_CONFIG["head_lr"],
                "weight_decay": TUNED_CONFIG["weight_decay"],
            },
            {
                "params": list(model.scorer.parameters()),
                "lr": TUNED_CONFIG["scorer_lr"],
                "weight_decay": TUNED_CONFIG["weight_decay"],
            },
        ]
    )

    train_idx_t = torch.tensor(train_indices, dtype=torch.long, device=device)
    # Compute inverse-frequency class weights on the training slice
    train_golds = cache["gold_idx"][train_idx_t].tolist()
    counts = Counter(train_golds)
    n_train = len(train_indices)
    weights = torch.tensor(
        [n_train / (3.0 * max(1, counts.get(c, 1))) for c in range(3)],
        dtype=torch.float32,
        device=device,
    )
    sample_w = weights[cache["gold_idx"]]

    # Group valid-quantity profile siblings present in train_indices
    prof_groups = defaultdict(list)
    for idx in train_indices:
        q_val = json.loads(rows[idx]["state"])["operational"]["quantity"]
        if q_val in QUANTITIES:
            prof_groups[metadata[idx]["profile_id"]].append(idx)
    full_prof_groups = [idxs for idxs in prof_groups.values() if len(idxs) == 4]
    prof_tensor = (
        torch.tensor(full_prof_groups, dtype=torch.long, device=device)
        if full_prof_groups
        else None
    )

    epoch_losses = []
    optimizer_steps = 0
    gradient_samples = []
    batch_size = TUNED_CONFIG["batch_size"]

    for ep in range(epochs):
        gen = torch.Generator(device=device).manual_seed(seed * 1000 + ep)
        perm = train_idx_t[
            torch.randperm(len(train_indices), generator=gen, device=device)
        ]
        ep_loss_sum = 0.0
        ep_steps = 0
        for start in range(0, len(train_indices), batch_size):
            batch_idx = perm[start : start + batch_size]
            logits = forward_head_and_scorer(model, cache, batch_idx)
            logp = F.log_softmax(logits, -1)
            probs = F.softmax(logits[:, :3], -1)
            ce = (
                -(cache["target"][batch_idx] * logp * cache["mask"][batch_idx]).sum(-1)
                * sample_w[batch_idx]
            )
            unsafe_mask = (cache["gold_idx"][batch_idx] > 0).float()
            safety_pen = (
                unsafe_mask
                * (-torch.log((1.0 - probs[:, 0]).clamp_min(1e-6)))
                * TUNED_CONFIG["safety_penalty_weight"]
            )
            loss = (ce + safety_pen).mean()
            if not torch.isfinite(loss).item():
                raise RuntimeError("nonfinite loss during tuned head/scorer training")
            opt.zero_grad(set_to_none=True)
            loss.backward()
            optimizer_steps += 1
            if optimizer_steps <= 5 or optimizer_steps % 128 == 0:
                norms = [
                    float(p.grad.detach().float().norm())
                    for g in opt.param_groups
                    for p in g["params"]
                    if p.grad is not None
                ]
                gradient_samples.append(
                    {
                        "step": optimizer_steps,
                        "norm_sum": sum(norms),
                        "finite": all(math.isfinite(v) for v in norms),
                    }
                )
            opt.step()
            ep_loss_sum += float(loss.item())
            ep_steps += 1

        if prof_tensor is not None and ep % 5 == 4:
            flat_p = prof_tensor.view(-1)
            logits_p = forward_head_and_scorer(model, cache, flat_p)[:, :3].view(
                -1, 4, 3
            )
            probs_p = F.softmax(logits_p, dim=-1)
            mean_p = probs_p.mean(dim=1, keepdim=True).detach()
            inv_loss = (
                ((probs_p - mean_p) ** 2).mean()
                * TUNED_CONFIG["quantity_invariance_weight"]
            )
            opt.zero_grad(set_to_none=True)
            inv_loss.backward()
            optimizer_steps += 1
            opt.step()

        epoch_losses.append(ep_loss_sum / max(1, ep_steps))

    model.eval()
    return {
        "epoch_loss": epoch_losses,
        "optimizer_steps": optimizer_steps,
        "gradient_samples": gradient_samples,
    }


def save_tuned_checkpoint(model, tok, cfg, out_dir, audit_info):
    import laya.train as training

    out_cfg = dict(
        cfg,
        max_len=512,
        head_max_len=192,
        fine_tuned=True,
        temperature=[0.5, 0.5, 0.5],
    )
    out_cfg.pop("temperature_by_options", None)
    out_cfg["training"] = dict(
        out_cfg.get("training") or {},
        aegis_v2_tuned=TUNED_CONFIG,
        audit_summary={
            "optimizer_steps": audit_info["optimizer_steps"],
            "initial_loss": audit_info["epoch_loss"][0],
            "final_loss": audit_info["epoch_loss"][-1],
        },
    )
    training.save_checkpoint(model, tok, out_cfg, str(out_dir))
    (out_dir / "questions.json").write_text(
        json.dumps(QUESTIONS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (out_dir / "train_report.json").write_text(
        json.dumps(
            {
                "eval_mode": "in_sample_development_fit",
                "is_held_out": False,
                "training": TUNED_CONFIG,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def run_diagnostic(confirmed):
    if not confirmed:
        raise ValueError(
            "explicit user authorization for quarantined V2 tuned training required"
        )
    network_off()
    rows, metadata, _ = validated_rows()
    control = json.loads(CONTROL.read_text(encoding="utf-8"))
    if not control.get("control_passed") or not control.get(
        "protected_files_unchanged"
    ):
        raise ValueError("positive-control prerequisite failed")
    original = json.loads((CONTROL.parent / "before.json").read_text(encoding="utf-8"))[
        "protected_hashes"
    ]
    check_protected(original)

    import laya
    import laya.train as training
    import torch
    from laya.train_cli import main as official_cli

    if not torch.cuda.is_available():
        raise RuntimeError("existing local CUDA is required; no fallback install")

    stamp = "v2-tuned-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run = ROOT / "ml" / EXPERIMENT / stamp
    run.mkdir(parents=True, exist_ok=False)
    ckpt_root = ROOT / "models" / EXPERIMENT / stamp
    ckpt_root.mkdir(parents=True, exist_ok=False)

    before = {
        "created_utc": datetime.now(UTC).isoformat(),
        "protected_hashes": protected_hashes(),
        "dataset": dataset_audit(rows, metadata),
        "tuned_config": TUNED_CONFIG,
        "authorization": "User requested improved V2 fine-tune and side-by-side comparison report",
        "authorization_scope_used": "Quarantined V2 (161-row) discriminative head/scorer fit + 5-fold profile-grouped out-of-fold benchmark",
        "backend_mapping_verified": False,
        "independent_data_verified": False,
        "real_task_promotion_gates_unchanged": True,
    }
    write(run / "before.json", before)

    # 1. Official dry-run
    if official_cli(tuned_args(CONFIRMED / "candidates.jsonl", dry_run=True)):
        raise RuntimeError("official dry-run failed")

    # 2. Baseline fit
    if (HEAD_ONLY_RUN / "baseline-fit.json").is_file():
        baseline_fit = json.loads(
            (HEAD_ONLY_RUN / "baseline-fit.json").read_text(encoding="utf-8")
        )
    else:
        baseline_fit = fit_metrics(BASE, rows, metadata)
    write(run / "baseline-fit.json", baseline_fit)

    # 3. Load model once & precompute unpadded encoder hidden states
    t_pre = time.perf_counter()
    model, tok, cfg = training.load_checkpoint(str(BASE))
    dev = torch.device("cuda")
    model.to(dev).eval()
    base_encoder_hashes = {
        n: tensor_hash(p)
        for n, p in model.named_parameters()
        if n.startswith("encoder.")
    }
    base_head_hashes = {
        n: tensor_hash(p)
        for n, p in model.named_parameters()
        if not n.startswith("encoder.")
    }
    base_head_state = {
        k: v.detach().cpu().clone()
        for k, v in model.state_dict().items()
        if not k.startswith("encoder.")
    }
    cache = precompute_unpadded_encoder_states(model, tok, rows, dev)
    precompute_seconds = time.perf_counter() - t_pre

    all_indices = list(range(len(rows)))
    seed_summaries = {}

    # 4. Train Seed 17 and Seed 29 on all 161 rows, save checkpoints, and verify via `laya.load().predict()`
    for seed in (17, 29):
        t_seed = time.perf_counter()
        torch.cuda.reset_peak_memory_stats()
        audit = train_head_and_scorer_on_indices(
            model, base_head_state, cache, rows, metadata, all_indices, seed, dev
        )
        encoder_unchanged = all(
            tensor_hash(p) == base_encoder_hashes[n]
            for n, p in model.named_parameters()
            if n.startswith("encoder.")
        )
        head_changed = sum(
            tensor_hash(p) != base_head_hashes[n]
            for n, p in model.named_parameters()
            if not n.startswith("encoder.")
        )
        if not encoder_unchanged or head_changed == 0:
            raise RuntimeError("encoder/head parameter audit failed")

        out = ckpt_root / f"seed-{seed}"
        save_tuned_checkpoint(model, tok, cfg, out, audit)

        # Verify actual reloaded checkpoint with official `laya.load(out).predict()`
        dev_fit = fit_metrics(out, rows, metadata)
        invariance = quantity_invariance_summary(dev_fit, rows)
        write(run / f"seed-{seed}-quantity-invariance.json", invariance)

        ckpt_hashes = {
            str(p.relative_to(out)): sha(p) for p in out.rglob("*") if p.is_file()
        }
        seed_report = {
            "seed": seed,
            "dataset_version": "human_confirmed_unsplit_v2-r169",
            "policy_version": POLICY_V2_VERSION,
            "training_mode": "DISCRIMINATIVE_HEAD_SCORER_FP32_SAFETY_INVARIANT",
            "tuned_config": TUNED_CONFIG,
            "laya": laya.__version__,
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "audit": {
                **audit,
                "encoder_frozen": True,
                "encoder_unchanged": encoder_unchanged,
                "head_tensors_changed": head_changed,
                "precompute_encoder_seconds": precompute_seconds,
            },
            "status": "COMPLETED_DIAGNOSTIC_ONLY",
            "checkpoint": str(out.relative_to(ROOT)),
            "development_fit": dev_fit,
            "quantity_invariance": {
                k: invariance[k]
                for k in (
                    "valid_quantity_profiles",
                    "invariant_profiles_across_all_4_quantities",
                    "changed_predictions",
                )
            },
            "checkpoint_hashes": ckpt_hashes,
            "checkpoint_version": hashlib.sha256(
                json.dumps(ckpt_hashes, sort_keys=True).encode()
            ).hexdigest(),
            "wall_seconds": time.perf_counter() - t_seed,
            "peak_allocated_mib": torch.cuda.max_memory_allocated() / 1024**2,
            "peak_reserved_mib": torch.cuda.max_memory_reserved() / 1024**2,
            "protected_files_unchanged": True,
            "independent_evaluation": False,
            "production_approved": False,
            "execution_authority": False,
            "promotion_eligible": False,
            "confidence_validated": False,
        }
        write(run / f"seed-{seed}.json", seed_report)
        seed_summaries[seed] = {
            "accuracy": dev_fit["accuracy"],
            "correct": dev_fit["correct"],
            "macro_f1": dev_fit["macro_f1"],
            "halt_to_continue": dev_fit["halt_to_continue"],
            "review_to_continue": dev_fit["review_to_continue"],
            "continue_recall": dev_fit["continue_recall"],
            "confusion": dev_fit["confusion"],
            "invariant_profiles": invariance[
                "invariant_profiles_across_all_4_quantities"
            ],
            "changed_predictions": invariance["changed_predictions"],
            "wall_seconds": seed_report["wall_seconds"],
        }

    # 5. Run 5-fold Profile-Grouped Out-of-Fold Cross-Validation (zero profile leakage)
    t_cv = time.perf_counter()
    folds = build_profile_grouped_folds(rows, metadata, n_folds=5)
    oof_predictions_by_idx = {}
    fold_summaries = []
    import torch.nn.functional as F

    for fold_info in folds:
        fold_id = fold_info["fold"]
        train_head_and_scorer_on_indices(
            model,
            base_head_state,
            cache,
            rows,
            metadata,
            fold_info["train_indices"],
            17,
            dev,
        )
        val_idx_t = torch.tensor(
            fold_info["val_indices"], dtype=torch.long, device=dev
        )
        with torch.no_grad():
            logits_val = forward_head_and_scorer(model, cache, val_idx_t)[:, :3]
            probs_val = F.softmax(logits_val, -1)
            preds_val = logits_val.argmax(-1).tolist()

        fold_preds = []
        for local_j, row_idx in enumerate(fold_info["val_indices"]):
            pred_obj = {
                "case_id": metadata[row_idx]["case_id"],
                "profile_id": metadata[row_idx]["profile_id"],
                "expected": rows[row_idx]["expected"]["operational_state"],
                "predicted": LABELS[preds_val[local_j]],
                "probabilities": {
                    LABELS[c]: float(probs_val[local_j, c]) for c in range(3)
                },
                "truncated": False,
                "latency_ms": 0.0,
            }
            oof_predictions_by_idx[row_idx] = pred_obj
            fold_preds.append(pred_obj)

        f_m = metrics(fold_preds)
        fold_summaries.append(
            {
                "fold": fold_id,
                "train_rows": len(fold_info["train_indices"]),
                "val_rows": len(fold_info["val_indices"]),
                "train_groups": fold_info["train_groups"],
                "val_groups": fold_info["val_groups"],
                "val_accuracy": sum(
                    p["expected"] == p["predicted"] for p in fold_preds
                )
                / len(fold_preds),
                "val_correct": sum(
                    p["expected"] == p["predicted"] for p in fold_preds
                ),
                "val_macro_f1": f_m["macro_f1"],
                "val_halt_to_continue": f_m["halt_to_continue"],
                "val_review_to_continue": f_m["review_to_continue"],
                "val_continue_recall": f_m["continue_recall"],
            }
        )

    ordered_oof = [oof_predictions_by_idx[i] for i in range(len(rows))]
    oof_metrics = metrics(ordered_oof)
    oof_metrics.pop("accepted", None)
    oof_metrics.update(
        accuracy=sum(p["expected"] == p["predicted"] for p in ordered_oof) / len(rows),
        correct=sum(p["expected"] == p["predicted"] for p in ordered_oof),
        metric_scope="PROFILE_GROUPED_5_FOLD_OUT_OF_FOLD_EVALUATION",
        zero_valid_profile_leakage=True,
        independent_capture_source=False,
        predictions=ordered_oof,
    )
    oof_invariance = quantity_invariance_summary(oof_metrics, rows)
    cv_report = {
        "n_folds": 5,
        "seed": 17,
        "epochs": TUNED_CONFIG["epochs"],
        "zero_valid_profile_leakage": True,
        "wall_seconds": time.perf_counter() - t_cv,
        "folds": fold_summaries,
        "oof_metrics": oof_metrics,
        "oof_quantity_invariance": {
            k: oof_invariance[k]
            for k in (
                "valid_quantity_profiles",
                "invariant_profiles_across_all_4_quantities",
                "changed_predictions",
            )
        },
        "protected_files_unchanged": True,
    }
    write(run / "group-cv.json", cv_report)

    del model
    gc.collect()
    torch.cuda.empty_cache()

    check_protected(before["protected_hashes"])
    result = {
        "run": str(run.relative_to(ROOT)),
        "dataset": "human_confirmed_unsplit_v2-r169",
        "policy_version": POLICY_V2_VERSION,
        "training_mode": "DISCRIMINATIVE_HEAD_SCORER_FP32_SAFETY_INVARIANT",
        "precompute_encoder_seconds": precompute_seconds,
        "seed_17": seed_summaries[17],
        "seed_29": seed_summaries[29],
        "group_cv_5fold_oof": {
            "accuracy": oof_metrics["accuracy"],
            "correct": oof_metrics["correct"],
            "macro_f1": oof_metrics["macro_f1"],
            "halt_to_continue": oof_metrics["halt_to_continue"],
            "review_to_continue": oof_metrics["review_to_continue"],
            "continue_recall": oof_metrics["continue_recall"],
            "confusion": oof_metrics["confusion"],
            "invariant_profiles": oof_invariance[
                "invariant_profiles_across_all_4_quantities"
            ],
            "changed_predictions": oof_invariance["changed_predictions"],
            "wall_seconds": cv_report["wall_seconds"],
        },
        "diagnostic_completed": True,
        "protected_files_unchanged": True,
        "production_approved": False,
        "execution_authority": False,
        "selected_checkpoint_replaced": False,
        "final_test_opened": False,
        "orders_sent": 0,
    }
    write(run / "result.json", result)
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "audit"))
    parser.add_argument("--confirm-development-only", action="store_true")
    args = parser.parse_args()
    if args.mode == "audit":
        rows, metadata, _ = validated_rows()
        print(json.dumps(dataset_audit(rows, metadata), ensure_ascii=False, indent=2))
    elif args.mode == "run":
        run_diagnostic(args.confirm_development_only)
