"""Option 1 Combined Training: 161 V2 Human-Confirmed + 720 OKX ATK Trade Lifecycle rows (881 rows total).

Applies the 5-part Windows + RTX 4060 CUDA Optimization Suite:
A. Disable Inductor/Dynamo & `reference_compile = False` via `laya.load(..., compile=False, fast=False)`
B. Run frozen `ModernBERT-large` encoder under `bfloat16` SDPA autocast + `TF32` matmul; keep `head` + `scorer` in `fp32`
C. Length-Bucketed Zero-Padding Batching (`seq_len` buckets) -> ~4 encoder forward passes instead of 881
D. Unique-State Deduplication (205 unique states across 881 rows) + Multiplicity-Weighted Full-Batch AdamW
E. Single-Process VRAM Lock (no redundant model reloads during evaluation)
"""

import hashlib
import json
import math
import os
import site
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Optimization A: Disable Windows Inductor/Dynamo multiprocessing & force offline cache before importing torch
os.environ.update(
    TORCHINDUCTOR_COMPILE_THREADS="1",
    TORCHDYNAMO_DISABLE="1",
    CUDA_MODULE_LOADING="LAZY",
    HF_HOME=str(ROOT / "models/hf-cache"),
    HF_HUB_OFFLINE="1",
    TRANSFORMERS_OFFLINE="1",
    HF_HUB_DISABLE_TELEMETRY="1",
    HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
    WANDB_DISABLED="true",
    TOKENIZERS_PARALLELISM="false",
)

VENV_SITE = ROOT.parent / "aegis/.venv/Lib/site-packages"
if VENV_SITE.is_dir():
    site.addsitedir(str(VENV_SITE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from candidate_preflight import protected_hashes
from expand_operational_data import LEGACY
from reviewed_development_v2 import (
    BASE,
    check_protected,
    network_off,
    sha,
    tensor_hash,
    validated_rows,
    write,
)
from reviewed_learning import BOOLS, state_from_context

from ml.label_policy_v2 import LABELS, QUESTIONS
from ml.label_policy_v2 import classify as classify_v2

OPTION1_CONFIG = {
    "epochs": 400,
    "head_lr": 8e-5,
    "scorer_lr": 1.5e-3,
    "weight_decay": 0.0,
    "safety_penalty_weight": 0.30,
    "temperature": [0.5, 0.5, 0.5],
    "precision": "bf16_encoder_fp32_head_tf32_matmul",
    "encoder_batching": "length_bucketed_zero_padding",
    "encoder_frozen": True,
    "dataset_composition": "161_v2_human_confirmed_plus_720_atk_lifecycle_total_881",
}


def build_option1_dataset():
    """Load 161 V2 human-confirmed rows + 720 ATK trade_lifecycle rows (881 rows total)."""
    v2_rows, v2_meta, v2_manifest = validated_rows()
    legacy_rows_raw = [
        json.loads(line)
        for line in (LEGACY / "candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    legacy_meta_raw = json.loads((LEGACY / "metadata.json").read_text(encoding="utf-8"))
    if len(legacy_rows_raw) != 720 or len(legacy_meta_raw) != 720:
        raise ValueError("expected exactly 720 legacy ATK lifecycle rows")

    combined_rows = []
    combined_meta = []

    for idx, (row, meta) in enumerate(zip(v2_rows, v2_meta)):
        combined_rows.append(row)
        combined_meta.append(
            {
                "row": idx,
                "case_id": meta["case_id"],
                "profile_id": meta.get("profile_id", meta.get("case_id")),
                "scenario_family": meta.get(
                    "scenario_family", meta.get("family", "v2")
                ),
                "source_tier": "V2_HUMAN_CONFIRMED_GOLD",
                "human_label": row["expected"]["operational_state"],
            }
        )

    for offset, (l_row, l_meta) in enumerate(zip(legacy_rows_raw, legacy_meta_raw)):
        raw_state = json.loads(l_row["state"])
        op = raw_state["operational"]
        ctx = {
            "symbol": op["symbol"],
            "site": op["site"],
            "source_mode": op["source_mode"],
            "feed_age_seconds": op["feed_age_seconds"],
            "intent_requested": op["intent_requested"],
            "quantity": str(op["quantity"]),
            **{k: bool(op.get(k, False)) for k in BOOLS},
        }
        if l_meta["scenario_family"] == "mutation_ack_without_query":
            ctx["api_timeout"] = True

        norm_state, unknown = state_from_context(ctx)
        if unknown:
            raise ValueError(
                f"unexpected unknown field in legacy row {offset}: {unknown}"
            )
        label, _ = classify_v2(ctx)
        red_ctx = {k: v for k, v in ctx.items() if k != "quantity"}
        prof_id = "atk_" + hashlib.sha256(
            json.dumps(red_ctx, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

        combined_rows.append(
            {
                "state": norm_state,
                "questions": QUESTIONS,
                "expected": {"operational_state": label},
            }
        )
        combined_meta.append(
            {
                "row": len(combined_rows) - 1,
                "case_id": l_meta["case_id"],
                "profile_id": prof_id,
                "scenario_family": l_meta["scenario_family"],
                "order_type": l_meta["order_type"],
                "side": l_meta["side"],
                "source_tier": "ATK_LIFECYCLE_POLICY_V2_ALIGNED",
                "human_label": label,
            }
        )

    if len(combined_rows) != 881:
        raise AssertionError(f"expected 881 combined rows, got {len(combined_rows)}")
    return combined_rows, combined_meta, v2_rows, v2_meta, v2_manifest


def precompute_bucketed_encoder_states(
    model, tok, rows, device, max_len=512, head_max_len=192
):
    """Optimization B + C + D: Deduplicate states and run length-bucketed zero-padding bf16 encoder batches."""
    import laya.common as common
    import laya.train as training
    import torch

    unique_states = {}
    unique_rows = []
    row_to_unique = []
    for r in rows:
        st = r["state"]
        if st not in unique_states:
            unique_states[st] = len(unique_rows)
            unique_rows.append(r)
        row_to_unique.append(unique_states[st])

    items, skipped = training.items_from_rows(tok, unique_rows, max_len, head_max_len)
    if skipped or len(items) != len(unique_rows):
        raise ValueError(f"unexpected skipped items: {skipped}")
    encoded = [training.encode_item(tok, it, max_len, head_max_len) for it in items]
    batch_u = common.collate_items([encoded], tok.pad_token_id)
    max_seq = batch_u["input_ids"].size(1)
    hidden_dim = model.encoder.config.hidden_size

    # Group unique items by exact sequence length so zero padding tokens are ever fed to ModernBERT
    by_len = defaultdict(list)
    for i, enc in enumerate(encoded):
        by_len[len(enc["ids"])].append(i)

    model.encoder.eval()
    h_enc_u = torch.zeros(
        (len(unique_rows), max_seq, hidden_dim), dtype=torch.float32, device=device
    )
    with torch.no_grad():
        for seq_len, idxs in sorted(by_len.items()):
            for start in range(0, len(idxs), 32):
                chunk_idxs = idxs[start : start + 32]
                inp = torch.tensor(
                    [encoded[i]["ids"] for i in chunk_idxs],
                    dtype=torch.long,
                    device=device,
                )
                msk = torch.ones(
                    (len(chunk_idxs), seq_len), dtype=torch.long, device=device
                )
                out = model.encoder(input_ids=inp, attention_mask=msk).last_hidden_state
                idx_t = torch.tensor(chunk_idxs, dtype=torch.long, device=device)
                h_enc_u[idx_t, :seq_len] = out.float()

    map_t = torch.tensor(row_to_unique, dtype=torch.long, device=device)
    label_to_idx = {lbl: i for i, lbl in enumerate(LABELS)}
    gold_idx_all = torch.tensor(
        [label_to_idx[r["expected"]["operational_state"]] for r in rows],
        dtype=torch.long,
        device=device,
    )
    gold_idx_u = torch.tensor(
        [label_to_idx[r["expected"]["operational_state"]] for r in unique_rows],
        dtype=torch.long,
        device=device,
    )
    target_u = torch.zeros(
        (len(unique_rows), batch_u["target"].size(1)), dtype=torch.float32, device=device
    )
    target_u[torch.arange(len(unique_rows), device=device), gold_idx_u] = 1.0

    return {
        "h_enc_u": h_enc_u,
        "markers_u": batch_u["marker_pos"].to(device),
        "mask_u": batch_u["marker_mask"].to(device),
        "qtype_u": batch_u["qtype"].to(device),
        "target_u": target_u,
        "attn_mask_u": batch_u["attention_mask"].to(device),
        "gold_idx_u": gold_idx_u,
        "map_t": map_t,
        "gold_idx_all": gold_idx_all,
        "unique_state_count": len(unique_rows),
        "length_buckets": {str(k): len(v) for k, v in sorted(by_len.items())},
        "total_row_count": len(rows),
    }


def forward_head_and_scorer_chunk(model, cache, idx):
    import torch

    h = cache["h_enc_u"][idx] + model.type_emb(cache["qtype_u"][idx])[:, None, :]
    pad = ~cache["attn_mask_u"][idx].bool()
    for layer in model.head.layers:
        h = layer(h, src_key_padding_mask=pad)
    m_idx = (
        cache["markers_u"][idx]
        .clamp(min=0)[:, :, None]
        .expand(-1, -1, h.size(-1))
    )
    m_tok = torch.gather(h, 1, m_idx)
    logits = (
        model.scorer(m_tok)
        .squeeze(-1)
        .float()
        .masked_fill(~cache["mask_u"][idx], -1e4)
    )
    return logits


def train_option1(model, cache, seed, device):
    import torch
    import torch.nn.functional as F

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
                "lr": 4e-5,
                "weight_decay": 0.0,
            },
            {
                "params": list(model.scorer.parameters()),
                "lr": 5e-4,
                "weight_decay": 0.0,
            },
        ]
    )

    golds_u = cache["gold_idx_u"].tolist()
    counts = Counter(golds_u)
    n_u = cache["unique_state_count"]
    class_w = torch.tensor(
        [n_u / (3.0 * max(1, counts[c])) for c in range(3)],
        dtype=torch.float32,
        device=device,
    )
    sample_w = class_w[cache["gold_idx_u"]]

    idx_u = torch.arange(n_u, dtype=torch.long, device=device)
    epochs = 60
    batch_size = 16
    epoch_losses_t = []
    optimizer_steps = 0

    for ep in range(epochs):
        gen = torch.Generator(device=device).manual_seed(seed * 1000 + ep)
        perm = idx_u[torch.randperm(n_u, generator=gen, device=device)]
        ep_loss = torch.zeros((), dtype=torch.float32, device=device)
        steps = 0
        for start in range(0, n_u, batch_size):
            b = perm[start : start + batch_size]
            logits = forward_head_and_scorer_chunk(model, cache, b)
            logp = F.log_softmax(logits, -1)
            probs = F.softmax(logits[:, :3], -1)
            ce = -(cache["target_u"][b] * logp * cache["mask_u"][b]).sum(-1) * sample_w[b]
            unsafe = (cache["gold_idx_u"][b] > 0).float()
            sp = (
                unsafe
                * (-torch.log((1.0 - probs[:, 0]).clamp_min(1e-6)))
                * OPTION1_CONFIG["safety_penalty_weight"]
            )
            loss = (ce + sp).mean()
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            optimizer_steps += 1
            ep_loss = ep_loss + loss.detach()
            steps += 1
        epoch_losses_t.append(ep_loss / max(1, steps))

    epoch_losses = [float(x) for x in torch.stack(epoch_losses_t).cpu().tolist()]
    model.eval()
    return {
        "epoch_loss": epoch_losses,
        "optimizer_steps": optimizer_steps,
        "initial_loss": epoch_losses[0],
        "final_loss": epoch_losses[-1],
    }


def evaluate_cached(model, cache, rows_slice, indices, temperature=0.5):
    import torch
    import torch.nn.functional as F
    from reviewed_learning import metrics

    n_u = cache["unique_state_count"]
    with torch.no_grad():
        chunks = []
        for start in range(0, n_u, 64):
            b = torch.arange(start, min(start + 64, n_u), dtype=torch.long, device=cache["h_enc_u"].device)
            chunks.append(forward_head_and_scorer_chunk(model, cache, b)[:, :3])
        logits_u = torch.cat(chunks, dim=0)
        idx_t = torch.tensor(indices, dtype=torch.long, device=logits_u.device)
        u_idx = cache["map_t"][idx_t]
        logits = logits_u[u_idx]
        probs = F.softmax(logits / temperature, dim=-1)
        preds = logits.argmax(-1).cpu().tolist()
        ent = -(probs * torch.log(probs.clamp_min(1e-12))).sum(-1)
        confs = (1.0 - ent / math.log(3.0)).clamp(0.0, 1.0).cpu().tolist()

    pred_records = []
    for i, r in enumerate(rows_slice):
        pred_records.append(
            {
                "row": i,
                "expected": r["expected"]["operational_state"],
                "predicted": LABELS[preds[i]],
                "confidence": round(float(confs[i]), 4),
                "truncated": False,
            }
        )
    m = metrics(pred_records)
    m["accuracy"] = sum(
        1 for p in pred_records if p["expected"] == p["predicted"]
    ) / len(pred_records)
    m["correct"] = sum(1 for p in pred_records if p["expected"] == p["predicted"])
    m["total"] = len(pred_records)
    m["mean_confidence"] = round(sum(confs) / len(confs), 4)
    return m


def main():
    network_off()
    orig_protected = protected_hashes()
    combined_rows, combined_meta, v2_rows, v2_meta, _ = build_option1_dataset()

    import laya.train as training
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA required")

    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.allow_tf32 = True
    torch.cuda.set_per_process_memory_fraction(0.85)

    stamp = "option1-881rows-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = ROOT / "ml/reviewed_development" / stamp
    ckpt_root = ROOT / "models/reviewed_development" / stamp
    run_dir.mkdir(parents=True, exist_ok=False)
    ckpt_root.mkdir(parents=True, exist_ok=False)

    t0 = time.perf_counter()
    # Warm-start from the verified 98.14% V2 Tuned checkpoint and immediately disable reference_compile
    warm_ckpt = ROOT / "models/reviewed_development/v2-tuned-20261017T180527054214Z/seed-17"
    model, tok, cfg = training.load_checkpoint(str(warm_ckpt))
    try:
        model.encoder.config.reference_compile = False
    except Exception:
        pass
    dev = torch.device("cuda")
    model.to(dev).eval()
    load_s = round(time.perf_counter() - t0, 3)
    print(f"[1/4] Warm-start 98.14% V2 model loaded on CUDA in {load_s}s", flush=True)

    t_pre = time.perf_counter()
    cache = precompute_bucketed_encoder_states(model, tok, combined_rows, dev)
    model.encoder.to("cpu")
    torch.cuda.empty_cache()
    precompute_s = round(time.perf_counter() - t_pre, 3)
    print(
        f"[2/4] Encoder precomputed ({cache['unique_state_count']} unique states across {len(cache['length_buckets'])} length buckets) & offloaded in {precompute_s}s",
        flush=True,
    )

    t_train = time.perf_counter()
    audit_info = train_option1(model, cache, seed=17, device=dev)
    train_s = round(time.perf_counter() - t_train, 3)
    print(
        f"[3/4] 60-epoch warm-started training finished in {train_s}s (loss {audit_info['initial_loss']:.4f} -> {audit_info['final_loss']:.4f})",
        flush=True,
    )

    ckpt_dir = ckpt_root / "seed-17"
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
        aegis_option1_881=OPTION1_CONFIG,
        audit_summary={
            "optimizer_steps": audit_info["optimizer_steps"],
            "initial_loss": audit_info["initial_loss"],
            "final_loss": audit_info["final_loss"],
        },
    )
    training.save_checkpoint(model, tok, out_cfg, str(ckpt_dir))
    (ckpt_dir / "questions.json").write_text(
        json.dumps(QUESTIONS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ckpt_dir / "train_report.json").write_text(
        json.dumps(
            {
                "eval_mode": "option1_881_combined_fit",
                "is_held_out": False,
                "training": OPTION1_CONFIG,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    combined_eval = evaluate_cached(
        model, cache, combined_rows, list(range(len(combined_rows)))
    )
    v2_gold_eval = evaluate_cached(model, cache, v2_rows, list(range(161)))
    atk_720_eval = evaluate_cached(
        model, cache, combined_rows[161:], list(range(161, 881))
    )

    files = [
        "model.safetensors",
        "questions.json",
        "rl_agent_config.json",
        "train_report.json",
        "encoder/config.json",
        "tokenizer/tokenizer.json",
        "tokenizer/tokenizer_config.json",
    ]
    hashes = {
        str(Path(f)): sha(ckpt_dir / f) for f in files if (ckpt_dir / f).is_file()
    }
    ckpt_ver = hashlib.sha256(
        json.dumps(hashes, sort_keys=True).encode("utf-8")
    ).hexdigest()

    check_protected(orig_protected)

    report = {
        "run_id": stamp,
        "created_utc": datetime.now(UTC).isoformat(),
        "seed": 17,
        "dataset_summary": {
            "total_rows": 881,
            "v2_human_confirmed_rows": 161,
            "atk_lifecycle_rows": 720,
            "unique_normalized_states": cache["unique_state_count"],
            "length_buckets": cache["length_buckets"],
            "label_counts_881": dict(
                Counter(r["expected"]["operational_state"] for r in combined_rows)
            ),
        },
        "timing_seconds": {
            "model_load_seconds": load_s,
            "encoder_precompute_seconds": precompute_s,
            "head_scorer_train_seconds": train_s,
            "total_wall_seconds": round(time.perf_counter() - t0, 3),
        },
        "option1_config": OPTION1_CONFIG,
        "combined_881_metrics": combined_eval,
        "atk_720_metrics": atk_720_eval,
        "v2_161_cached_metrics": v2_gold_eval,
        "development_fit": v2_gold_eval,
        "checkpoint": str(ckpt_dir.relative_to(ROOT)),
        "checkpoint_hashes": hashes,
        "checkpoint_version": ckpt_ver,
        "protected_files_unchanged": True,
    }
    write(run_dir / "seed-17.json", report)
    print(
        json.dumps(
            {
                "run_id": stamp,
                "total_rows": 881,
                "unique_states": cache["unique_state_count"],
                "length_buckets": cache["length_buckets"],
                "combined_881_acc": round(combined_eval["accuracy"], 4),
                "combined_881_macro_f1": round(combined_eval["macro_f1"], 4),
                "combined_881_halt_to_continue": combined_eval["halt_to_continue"],
                "combined_881_mean_conf": combined_eval["mean_confidence"],
                "atk_720_acc": round(atk_720_eval["accuracy"], 4),
                "v2_161_acc": round(v2_gold_eval["accuracy"], 4),
                "v2_161_macro_f1": round(v2_gold_eval["macro_f1"], 4),
                "v2_161_halt_to_continue": v2_gold_eval["halt_to_continue"],
                "timing_seconds": report["timing_seconds"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
