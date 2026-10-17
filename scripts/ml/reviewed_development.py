"""Offline, quarantined fit diagnostic on human-confirmed development data.

This deliberately does NOT bypass reviewed_learning.validate_bundle: it cannot
select, promote, deploy, or run the final test. All metrics are dependent fit
diagnostics, not estimates of generalization. No backend/auth/order imports.
"""

import argparse
import gc
import hashlib
import json
import math
import os
import socket
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adjudicate_stale_review import verify_ledger
from reviewed_learning import metrics, state_from_context

from ml.label_policy import LABELS, QUESTIONS, classify

PACK = ROOT / "data/reviewed_learning/review-1c9cf35-v1"
CONFIRMED = PACK / "human_confirmed_unsplit_v1"
BASE = ROOT / "models/aegis_laya_selected"
CONTROL = ROOT / "ml/debug_learning/20261017T104341Z/result.json"
EXPERIMENT = "reviewed_development"


def write(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def validated_rows(directory=CONFIRMED, pack=PACK):
    """Verify actual existing reviews without inventing splits or approvals."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["hashes"].items():
        if Path(name).name != name or sha(directory / name) != expected:
            raise ValueError("development bundle hash mismatch")
    ledger = json.loads((pack / "human_reviews.json").read_text(encoding="utf-8"))
    source_hash = sha(pack / "draft_cases.json")
    verify_ledger(ledger, source_hash)
    if manifest["ledger_sha256"] != sha(pack / "human_reviews.json"):
        raise ValueError("review ledger changed since development export")
    source = json.loads((pack / "draft_cases.json").read_text(encoding="utf-8"))
    by_id = {case["case_id"]: case for case in source}
    rows = [
        json.loads(line)
        for line in (directory / "candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    if len(rows) != 120 or len(metadata) != 120 or len(ledger["entries"]) != 120:
        raise ValueError("expected existing 120 confirmed cases")
    seen = set()
    for index, (row, item) in enumerate(zip(rows, metadata)):
        case_id = item["case_id"]
        if case_id in seen or case_id not in by_id or item["row"] != index:
            raise ValueError("case identity/row mismatch")
        seen.add(case_id)
        entry = ledger["entries"][case_id]
        context = by_id[case_id]["context"]
        normalized, unknown = state_from_context(context)
        if (
            set(row) != {"state", "questions", "expected"}
            or row["state"] != normalized
            or row["questions"] != QUESTIONS
            or unknown
        ):
            raise ValueError("training input/schema/source mismatch")
        label = row["expected"]["operational_state"]
        if (
            set(row["expected"]) != {"operational_state"}
            or label not in LABELS
            or label != entry["human_label"]
            or label != item["human_label"]
            or entry["review_status"] != "APPROVED"
            or not entry.get("rationale")
            or not entry.get("reviewer_role")
            or item["human_review_status"] != "APPROVED"
            or entry.get("review_method") != "AI_ASSISTED_HUMAN_CONFIRMED"
            or item.get("blind_first_pass") is not False
        ):
            raise ValueError("actual human review/provenance mismatch")
        if classify(context)[0] != label:
            raise ValueError("unresolved human/policy disagreement")
    if Counter(r["expected"]["operational_state"] for r in rows) != Counter(
        {c: 40 for c in LABELS}
    ):
        raise ValueError("unexpected confirmed label counts; do not rebalance labels")
    return rows, metadata, manifest


def dataset_audit(rows, metadata):
    signatures = Counter()
    signature_labels = {}
    for row in rows:
        context = json.loads(row["state"])["operational"]
        # Only remove quantity to expose trivial numeric variants, not to train.
        context.pop("quantity")
        signature = json.dumps(context, sort_keys=True)
        signatures[signature] += 1
        signature_labels.setdefault(signature, set()).add(
            row["expected"]["operational_state"]
        )
    return {
        "rows": len(rows),
        "label_counts": dict(Counter(r["expected"]["operational_state"] for r in rows)),
        "scenario_families": dict(
            Counter(m["parent_scenario_group"] for m in metadata)
        ),
        "source_capture_groups": sorted({m["source_capture_group"] for m in metadata}),
        "exact_unique_states": len({r["state"] for r in rows}),
        "unique_contexts_ignoring_only_quantity": len(signatures),
        "conflicting_contexts_ignoring_quantity": sum(
            len(v) > 1 for v in signature_labels.values()
        ),
        "quantity_shortcut_risk": True,
        "origins": dict(Counter(m["origin"] for m in metadata)),
        "ai_assisted": True,
        "independent_blind_review": False,
        "independent_validation_available": False,
        "independent_test_available": False,
        "order_type_and_side_in_model_input": False,
        "actual_exchange_order_traces": False,
    }


def protected_hashes():
    files = [
        ROOT / "data" / name
        for name in ("train.jsonl", "val.jsonl", "test.jsonl", "challenge.jsonl")
    ]
    files += list(BASE.rglob("*"))
    files += list(PACK.rglob("*"))
    files += list((ROOT / "data/trade_lifecycle/20261017T103022Z").glob("*"))
    # Live review server status is not a model/data input and may change separately.
    return {
        str(p.relative_to(ROOT)): sha(p)
        for p in sorted(files)
        if p.is_file() and p.name != "review_server.json"
    }


def check_protected(snapshot):
    changed = [
        name
        for name, expected in snapshot.items()
        if not (ROOT / name).is_file() or sha(ROOT / name) != expected
    ]
    if changed:
        raise ValueError("protected source/model changed: " + ", ".join(changed))


def network_off():
    os.environ.update(
        HF_HOME=str(ROOT / "models/hf-cache"),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        WANDB_DISABLED="true",
        TOKENIZERS_PARALLELISM="false",
    )

    def denied(*args, **kwargs):
        raise RuntimeError("network disabled for quarantined learning diagnostic")

    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    socket.create_connection = denied
    socket.getaddrinfo = denied


def fit_metrics(checkpoint, rows, metadata):
    import laya
    import torch

    agent = laya.load(str(checkpoint), device="cuda", compile=False, fast=False)
    predictions = []
    # Explicit warm-up is separate from steady-state timing.
    agent.predict(rows[0]["state"], rows[0]["questions"])
    torch.cuda.synchronize()
    for row, meta in zip(rows, metadata):
        start = time.perf_counter()
        answer = agent.predict(row["state"], row["questions"])
        torch.cuda.synchronize()
        usage = answer.get("usage", {})
        value = answer["answers"]["operational_state"]
        predictions.append(
            {
                "case_id": meta["case_id"],
                "family": meta["parent_scenario_group"],
                "expected": row["expected"]["operational_state"],
                "predicted": value.get("choice"),
                "probabilities": value.get("probabilities"),
                "truncated": bool(usage.get("truncated"))
                or bool(usage.get("state_tokens_dropped")),
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        )
    result = metrics(predictions)
    # Acceptance is defined only for genuinely independent VAL/test, never fit.
    result.pop("accepted", None)
    result.update(
        accuracy=sum(p["expected"] == p["predicted"] for p in predictions) / len(rows),
        correct=sum(p["expected"] == p["predicted"] for p in predictions),
        median_latency_ms=statistics.median(p["latency_ms"] for p in predictions),
        metric_scope="DEPENDENT_DEVELOPMENT_FIT_NOT_GENERALIZATION",
        independent_evaluation=False,
        promotion_eligible=False,
        confidence_validated=False,
        predictions=predictions,
    )
    del agent
    gc.collect()
    torch.cuda.empty_cache()
    return result


def official_args(data, out=None, seed=17, dry_run=False):
    args = [
        "--data",
        str(data),
        "--base",
        str(BASE),
        "--epochs",
        "8",
        "--micro-batch",
        "1",
        "--grad-accum",
        "1",
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


def tensor_hash(parameter):
    return hashlib.sha256(
        parameter.detach().cpu().contiguous().view(-1).numpy().tobytes()
    ).hexdigest()


def worker(run, stage):
    network_off()
    if not run.resolve().is_relative_to(ROOT / "ml" / EXPERIMENT):
        raise ValueError("run outside quarantine")
    rows, metadata, _ = validated_rows()
    before = json.loads((run / "before.json").read_text(encoding="utf-8"))
    check_protected(before["protected_hashes"])
    import laya
    import laya.train as training
    import torch
    from laya.train_cli import main as official_cli

    if not torch.cuda.is_available():
        raise RuntimeError("existing local CUDA is required; no fallback install")
    if stage == "dry-run":
        code = official_cli(official_args(CONFIRMED / "candidates.jsonl", dry_run=True))
        if code:
            raise RuntimeError("official dry-run failed")
        return
    if stage == "baseline":
        write(run / "baseline-fit.json", fit_metrics(BASE, rows, metadata))
        return
    seed = int(stage)
    if seed not in (17, 29):
        raise ValueError("only predeclared seeds are allowed")
    out = ROOT / "models" / EXPERIMENT / run.name / f"seed-{seed}"
    if out.exists():
        raise ValueError("refusing checkpoint overwrite")
    audit = {"optimizer_steps": 0, "gradient_samples": []}
    original_train, original_step, original_loss = (
        training.train_model,
        torch.optim.AdamW.step,
        training.soft_ce_loss,
    )

    def measured_loss(*args, **kwargs):
        loss = original_loss(*args, **kwargs)
        if not torch.isfinite(loss).item():
            raise RuntimeError("nonfinite loss; stop without retry")
        return loss

    def measured_step(optimizer, *args, **kwargs):
        audit["optimizer_steps"] += 1
        if audit["optimizer_steps"] <= 5 or audit["optimizer_steps"] % 128 == 0:
            norms = [
                float(p.grad.detach().float().norm())
                for group in optimizer.param_groups
                for p in group["params"]
                if p.grad is not None
            ]
            audit["gradient_samples"].append(
                {
                    "step": audit["optimizer_steps"],
                    "norm_sum": sum(norms),
                    "finite": all(math.isfinite(v) for v in norms),
                }
            )
        return original_step(optimizer, *args, **kwargs)

    def measured_train(model, *args, **kwargs):
        original = {n: tensor_hash(p) for n, p in model.named_parameters()}
        history = original_train(model, *args, **kwargs)
        encoder = [
            (n, p) for n, p in model.named_parameters() if n.startswith("encoder.")
        ]
        audit.update(
            epoch_loss=history,
            encoder_frozen=bool(encoder)
            and all(not p.requires_grad for _, p in encoder),
            encoder_unchanged=all(tensor_hash(p) == original[n] for n, p in encoder),
            head_tensors_changed=sum(
                tensor_hash(p) != original[n]
                for n, p in model.named_parameters()
                if not n.startswith("encoder.")
            ),
        )
        return history

    report = {
        "seed": seed,
        "laya": laya.__version__,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "official_cli_args": official_args(CONFIRMED / "candidates.jsonl", out, seed),
        "audit": audit,
        "status": "RUNNING",
        "checkpoint": str(out.relative_to(ROOT)),
        "independent_evaluation": False,
        "production_approved": False,
        "execution_authority": False,
        "promotion_eligible": False,
        "confidence_validated": False,
    }
    started = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    try:
        training.train_model, torch.optim.AdamW.step, training.soft_ce_loss = (
            measured_train,
            measured_step,
            measured_loss,
        )
        if official_cli(report["official_cli_args"]):
            raise RuntimeError("official training failed")
        training.train_model, torch.optim.AdamW.step, training.soft_ce_loss = (
            original_train,
            original_step,
            original_loss,
        )
        if (
            not audit["encoder_frozen"]
            or not audit["encoder_unchanged"]
            or audit["head_tensors_changed"] == 0
            or len(audit["epoch_loss"]) != 8
            or not all(math.isfinite(v) for v in audit["epoch_loss"])
        ):
            raise RuntimeError("head-only training audit failed")
        # Reload from disk, then answer the development inputs. NOT a held-out test.
        report["development_fit"] = fit_metrics(out, rows, metadata)
        report["official_report"] = json.loads(
            (out / "train_report.json").read_text(encoding="utf-8")
        )
        if report["official_report"].get("is_held_out"):
            raise RuntimeError("unexpected independent-evaluation claim")
        report["checkpoint_hashes"] = {
            str(p.relative_to(out)): sha(p)
            for p in out.rglob("*")
            if p.is_file() and "checkpoint_latest" not in p.parts
        }
        report["checkpoint_version"] = hashlib.sha256(
            json.dumps(report["checkpoint_hashes"], sort_keys=True).encode()
        ).hexdigest()
        check_protected(before["protected_hashes"])
        report["protected_files_unchanged"] = True
        report["status"] = "COMPLETED_DIAGNOSTIC_ONLY"
    except Exception as exc:
        report.update(
            status="FAILED_NO_RETRY", error_type=type(exc).__name__, error=str(exc)
        )
        raise
    finally:
        training.train_model, torch.optim.AdamW.step, training.soft_ce_loss = (
            original_train,
            original_step,
            original_loss,
        )
        report.update(
            wall_seconds=time.perf_counter() - started,
            peak_allocated_mib=torch.cuda.max_memory_allocated() / 1024**2,
            peak_reserved_mib=torch.cuda.max_memory_reserved() / 1024**2,
        )
        write(run / f"seed-{seed}.json", report)
        print(
            json.dumps(
                {
                    "seed": seed,
                    "status": report["status"],
                    "wall_seconds": report["wall_seconds"],
                }
            ),
            flush=True,
        )


def run_diagnostic(confirmed):
    if not confirmed:
        raise ValueError(
            "explicit user authorization for quarantined development training required"
        )
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
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run = ROOT / "ml" / EXPERIMENT / stamp
    run.mkdir(parents=True, exist_ok=False)
    before = {
        "created_utc": datetime.now(UTC).isoformat(),
        "protected_hashes": protected_hashes(),
        "dataset": dataset_audit(rows, metadata),
        "authorization": "User requested training, then stated: Person 1 bağlam onayı ve bağımsız veri onayını veriyorum",
        "authorization_scope_used": "Quarantined development-fit diagnostic only; not an independent-data attestation",
        "backend_mapping_verified": False,
        "independent_data_verified": False,
        "real_task_promotion_gates_unchanged": True,
    }
    write(run / "before.json", before)
    result = {
        "run": str(run.relative_to(ROOT)),
        "stages": [],
        "outcome": "DATA/INTEGRATION BLOCKED",
        "diagnostic_completed": False,
        "production_approved": False,
        "execution_authority": False,
        "selected_checkpoint_replaced": False,
        "final_test_opened": False,
        "confidence_validated": False,
        "orders_sent": 0,
    }
    try:
        for stage in ("dry-run", "baseline", "17", "29"):
            command = [
                sys.executable,
                "-u",
                str(Path(__file__).resolve()),
                "worker",
                "--run",
                str(run),
                "--stage",
                stage,
            ]
            with (run / f"{stage}.log").open("x", encoding="utf-8") as console:
                child = subprocess.Popen(
                    command, stdout=console, stderr=subprocess.STDOUT
                )
                try:
                    code = child.wait(timeout=1800)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                    raise RuntimeError(f"{stage} exceeded 30-minute limit; no retry")
            result["stages"].append(
                {"stage": stage, "exit_code": code, "command": command}
            )
            if code:
                raise RuntimeError(f"{stage} failed; no automatic retry")
            check_protected(before["protected_hashes"])
            print(
                json.dumps(
                    {"stage_completed": stage, "run": str(run.relative_to(ROOT))}
                ),
                flush=True,
            )
        result["diagnostic_completed"] = True
    except Exception as exc:
        result.update(diagnostic_error=str(exc), diagnostic_completed=False)
        raise
    finally:
        result["protected_files_unchanged"] = all(
            (ROOT / p).is_file() and sha(ROOT / p) == h
            for p, h in before["protected_hashes"].items()
        )
        write(run / "result.json", result)
        print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "worker", "audit"))
    parser.add_argument("--confirm-development-only", action="store_true")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--stage", choices=("dry-run", "baseline", "17", "29"))
    args = parser.parse_args()
    if args.mode == "audit":
        rows, metadata, _ = validated_rows()
        print(json.dumps(dataset_audit(rows, metadata), ensure_ascii=False, indent=2))
    elif args.mode == "run":
        run_diagnostic(args.confirm_development_only)
    elif args.run and args.stage:
        worker(args.run, args.stage)
    else:
        parser.error("worker needs --run and --stage")
