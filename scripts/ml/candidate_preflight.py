"""Read-only development-package audit; format acceptance is NOT training approval.

No final-test inputs, weights loading, training, credentials, backend or orders.
Repair is limited to BOM/blank-line transport cleanup into a NEW quarantine copy.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ml.label_policy import LABELS, QUESTIONS

PACK = "data/reviewed_learning/expanded-v2-20261017T120738Z"
DATASETS = (
    "data/train.jsonl",
    "data/atk_spot/20261017T102105Z/candidates.jsonl",
    "data/trade_lifecycle/20261017T103022Z/candidates.jsonl",
    "data/reviewed_learning/review-1c9cf35-v1/human_confirmed_unsplit_v1/candidates.jsonl",
    PACK + "/candidates.jsonl",
    PACK + "/human_confirmed_unsplit_v2-r169/candidates.jsonl",
)


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def nonfinite(value):
    raise ValueError("non-finite JSON number: " + value)


def finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        nonfinite(value)
    return result


def strict_json(text):
    return json.loads(
        text,
        object_pairs_hook=object_pairs,
        parse_constant=nonfinite,
        parse_float=finite_float,
    )


def parse_rows(raw, allow_transport_cleanup=False):
    text = raw.decode("utf-8")
    bom = text.startswith("\ufeff")
    lines = text.removeprefix("\ufeff").splitlines()
    blank_lines = sum(not line.strip() for line in lines)
    if (bom or blank_lines) and not allow_transport_cleanup:
        raise ValueError("BOM/blank lines require explicit new-copy transport repair")
    rows = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        row = strict_json(line)
        if not isinstance(row, dict) or set(row) != {"state", "questions", "expected"}:
            raise ValueError(
                f"row {number}: exact state/questions/expected schema required"
            )
        if not isinstance(row["state"], str) or not row["state"].strip():
            raise ValueError(f"row {number}: nonempty text state required")
        if "DEBUG_LABEL" in row["state"]:
            raise ValueError(f"row {number}: positive-control label leakage")
        if row["questions"] != QUESTIONS:
            raise ValueError(f"row {number}: question contract mismatch")
        expected = row["expected"]
        if (
            not isinstance(expected, dict)
            or set(expected) != {"operational_state"}
            or expected["operational_state"] not in LABELS
        ):
            raise ValueError(f"row {number}: invalid answer channel/label; no guessing")
        rows.append(row)
    if not rows:
        raise ValueError("empty dataset")
    return rows, {"bom_removed": bom, "blank_lines_removed": blank_lines}


def transport_repair(source, destination):
    """Never drop an invalid example, alter its state/label, overwrite, or create approval."""
    source, destination = source.resolve(), destination.resolve()
    if str(source.relative_to(ROOT)).replace("\\", "/") not in DATASETS:
        raise ValueError("only allowlisted development inputs may be repaired")
    if not destination.is_relative_to(ROOT / "data/qa_repairs"):
        raise ValueError("repair output must be a new quarantine copy")
    if destination == source or destination.exists():
        raise ValueError("repair cannot overwrite any existing file")
    raw = source.read_bytes()
    rows, changes = parse_rows(raw, allow_transport_cleanup=True)
    # Keep every nonblank line verbatim: even JSON field order/spacing is preserved.
    cleaned = (
        "\n".join(line for line in raw.decode("utf-8-sig").splitlines() if line.strip())
        + "\n"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(cleaned)
    assert parse_rows(destination.read_bytes())[0] == rows
    return {
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "copy_sha256": sha(destination),
        "rows_preserved": len(rows),
        "training_approved": False,
        "changes": changes,
    }


def assert_complete(summary, count):
    if (
        summary["rows_read"] != count
        or summary["valid_items"] != count
        or summary["skipped"]
    ):
        raise ValueError(
            "official dry-run skipped/changed item count; never silently accept"
        )


def token_summary(stats):
    return {
        "rows_truncated": sum(bool(s["truncated"]) for s in stats),
        "max_state_tokens": max(s["state_tokens"] for s in stats),
        "total_state_tokens_dropped": sum(s["state_tokens_dropped"] for s in stats),
    }


def protected_hashes():
    from reviewed_development import protected_hashes as previous

    hashes = previous()
    for relative in (PACK, "data/atk_spot/20261017T102105Z"):
        for path in (ROOT / relative).rglob("*"):
            if path.is_file() and path.suffix != ".pyc":
                hashes[str(path.relative_to(ROOT))] = sha(path)
    return hashes


def audit(output):
    """Official installed LAYA path, local tokenizer only, with network disabled."""
    os.environ.update(
        HF_HOME=str(ROOT / "models/hf-cache"),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
        HF_HUB_DISABLE_IMPLICIT_TOKEN="1",
    )
    from data_expansion_offline import block_network

    block_network()
    before = protected_hashes()
    from laya.common import build_sequence
    from laya.train import TrainConfig, dry_run, to_internal
    from reviewed_learning import state_from_context
    from transformers import AutoTokenizer

    base = ROOT / "models/aegis_laya_selected"
    tokenizer = AutoTokenizer.from_pretrained(
        str(base / "tokenizer"), local_files_only=True
    )
    config = TrainConfig(
        epochs=8,
        micro_batch=1,
        grad_accum=1,
        freeze_encoder=True,
        loss="soft-ce",
        seed=17,
    )
    results = []
    for relative in DATASETS:
        path = ROOT / relative
        item = {
            "path": relative,
            "sha256": sha(path),
            "training_approved": False,
            "final_test": False,
        }
        try:
            rows, _ = parse_rows(path.read_bytes())
            item["rows"] = len(rows)
            item["classes"] = dict(
                Counter(row["expected"]["operational_state"] for row in rows)
            )
            item["unique_exact_states"] = len({row["state"] for row in rows})
            summary = dry_run(str(path), str(base), config)
            assert_complete(summary, len(rows))
            # Inspect the real sequence builder with uncapped state IDs: not a character heuristic.
            stats, compatible = [], 0
            for row in rows:
                internal = to_internal(
                    "operational_state", row["questions"]["operational_state"]
                )
                _, _, truncation = build_sequence(
                    tokenizer,
                    row["state"],
                    internal,
                    max_len=summary["max_len"],
                    head_max_len=summary["head_max_len"],
                    return_truncation_stats=True,
                )
                stats.append(truncation)
                try:
                    parsed = strict_json(row["state"])
                    if set(parsed) != {"operational"}:
                        raise ValueError("not canonical runtime representation")
                    normalized, _ = state_from_context(parsed["operational"])
                    compatible += normalized == row["state"]
                except (ValueError, KeyError, TypeError, AttributeError):
                    pass
            item.update(
                official_dry_run="PASS",
                official_summary=summary,
                tokenizer=token_summary(stats),
                canonical_adapter_compatible_rows=compatible,
                note="Optimizer update count is theoretical; no optimizer/model was run.",
            )
            item["preflight"] = (
                "PASS"
                if not item["tokenizer"]["rows_truncated"]
                else "BLOCKED_TRUNCATION"
            )
        except (ValueError, KeyError, TypeError, OSError) as error:
            item.update(preflight="FAIL", error=str(error))
        results.append(item)
    after = protected_hashes()
    unchanged = before == after
    manifest = strict_json(
        (ROOT / PACK / "human_confirmed_unsplit_v2-r169/manifest.json").read_text()
    )
    report = {
        "created_at_utc": datetime.now(UTC).isoformat(),
        "laya_version": importlib.metadata.version("laya"),
        "packages": results,
        "row_sum_not_independent_events": sum(r.get("rows", 0) for r in results),
        "protected_files_unchanged": unchanged,
        "protected_file_count": len(before),
        "protected_sha256": before,
        "training_started": False,
        "model_inference": False,
        "final_test_evaluated": False,
        "orders_sent": False,
        "open_policy_differences": len(manifest["policy_disagreements_open"]),
        "human_review_counts": manifest["label_counts"],
        "outcome": "DATA/INTEGRATION BLOCKED",
    }
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    if not unchanged:
        raise RuntimeError("Protected dataset/model hashes changed; review required")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = audit(arguments.output)
    print(
        json.dumps(
            {
                "packages": [
                    {k: r[k] for k in ("path", "preflight")} for r in result["packages"]
                ],
                "protected_files_unchanged": result["protected_files_unchanged"],
            },
            indent=2,
        )
    )
