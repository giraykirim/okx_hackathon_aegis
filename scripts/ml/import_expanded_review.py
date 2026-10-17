"""V2-specific AI-assisted human confirmation, explicit eight-case adjudication.

Never calls the legacy 120-row importer, changes production policy, creates a split,
trains a model, reads credentials, or grants trading authority.
"""

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adjudicate_stale_review import verify_ledger
from expand_operational_data import VERSION_V2, qa, suggested_label
from human_review_app import ReviewStore, atomic, digest
from reviewed_learning import LABELS, state_from_context

from ml.label_policy import QUESTIONS, classify

PACK_NAME = "expanded-v2-20261017T120738Z"
ADJUDICATION_ID = "USER_V2_FUTURE_TOLERANCE_CONTINUE_20261017"


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def read_json(path):
    def invalid_number(value):
        raise ValueError("nonstandard JSON numeric constant")

    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=unique_keys,
        parse_constant=invalid_number,
    )


def checked_store(directory):
    directory = directory.resolve()
    if (
        directory.parent != ROOT / "data/reviewed_learning"
        or directory.name != PACK_NAME
    ):
        raise ValueError("only the exact new V2 review pack is accepted")
    qa(directory)
    manifest = read_json(directory / "review_manifest.json")
    if manifest.get("version") != VERSION_V2 or manifest.get("cases") != 161:
        raise ValueError("V2 source version/count mismatch")
    store = ReviewStore(directory)
    if store.file.exists():
        verify_ledger(store.state, store.source_hash)
    return store


def check(source, directory):
    source = source.resolve()
    if not source.is_relative_to(ROOT.parent / "outputs"):
        raise ValueError("review source must be an explicitly archived task output")
    store = checked_store(directory)
    original = read_json(store.directory / "human_review_BLIND.json")
    document = read_json(source)
    if not isinstance(document, dict) or set(document) - set(original) - {"aciklama"}:
        raise ValueError("unsupported review document fields")
    for key, expected in original.items():
        if key != "ornekler" and canonical(document.get(key)) != canonical(expected):
            raise ValueError("review source header or decision instructions changed")
    returned = document.get("ornekler")
    if not isinstance(returned, list) or len(returned) != 161:
        raise ValueError("all 161 original examples required")
    reference = {row["case_id"]: row for row in original["ornekler"]}
    seen = set()
    entries = []
    for row in returned:
        if not isinstance(row, dict) or set(row) != {
            "ornek_no",
            "case_id",
            "senaryo",
            "olgular",
            "insan_incelemesi",
        }:
            raise ValueError("case fields changed or model-answer field added")
        case_id = row["case_id"]
        if not isinstance(case_id, str) or case_id not in reference or case_id in seen:
            raise ValueError("missing, duplicate, or unknown case ID")
        seen.add(case_id)
        expected = reference[case_id]
        if any(
            canonical(row[key]) != canonical(expected[key])
            for key in ("ornek_no", "senaryo", "olgular")
        ):
            raise ValueError("case facts, identity or description changed")
        review = row["insan_incelemesi"]
        if not isinstance(review, dict) or set(review) != {
            "karar",
            "gerekce",
            "inceleyen_rolu",
            "durum",
        }:
            raise ValueError("review schema mismatch")
        if review["karar"] not in LABELS or review["durum"] not in (
            "AI_SUGGESTED",
            "APPROVED",
        ):
            raise ValueError(
                "all 161 final human decisions required; no pending/unresolved import"
            )
        if (
            not isinstance(review["gerekce"], str)
            or not 10 <= len(review["gerekce"].strip()) <= 2000
        ):
            raise ValueError("actual 10..2000 character rationale required")
        if (
            not isinstance(review["inceleyen_rolu"], str)
            or not 2 <= len(review["inceleyen_rolu"].strip()) <= 80
        ):
            raise ValueError("source reviewer role missing")
        entries.append(
            {
                "case_id": case_id,
                "human_label": review["karar"],
                "rationale": review["gerekce"].strip(),
                "source_review_status": review["durum"],
                "source_reviewer_role": review["inceleyen_rolu"].strip(),
            }
        )
    return (
        store,
        entries,
        {
            "examples": 161,
            "source_file_sha256": digest(source),
            "source_dataset_sha256": store.source_hash,
            "facts_match": True,
            "unique_case_ids": len(seen),
            "source_label_counts": dict(
                Counter(entry["human_label"] for entry in entries)
            ),
            "source_review_status_counts": dict(
                Counter(entry["source_review_status"] for entry in entries)
            ),
            "ai_assisted": True,
            "blind_first_pass": False,
            "write_performed": False,
            "training_approved": False,
            "execution_authority": False,
        },
    )


@contextmanager
def write_lock(directory):
    directory = directory.resolve()
    if (
        directory.parent != ROOT / "data/reviewed_learning"
        or directory.name != PACK_NAME
    ):
        raise ValueError("write lock outside exact V2 review directory")
    # Leave unrelated legacy review UI running. Only a server for THIS pack blocks.
    if (directory / "review_server.json").exists():
        raise ValueError(
            "V2 pack has a review-server record; verify it stopped before import"
        )
    lock = directory / "review_import.lock"
    with lock.open("x", encoding="utf-8") as handle:
        handle.write(datetime.now(UTC).isoformat())
    try:
        yield
    finally:
        lock.unlink()


def append_event(state, case_id, entry, source_hash):
    event = {
        "revision": state["revision"] + 1,
        "case_id": case_id,
        "entry": entry,
        "previous_hash": state["audit"][-1]["hash"] if state["audit"] else source_hash,
    }
    event["hash"] = hashlib.sha256(
        json.dumps(event, sort_keys=True).encode()
    ).hexdigest()
    state["audit"].append(event)
    state["entries"][case_id] = entry
    state["revision"] += 1


def audit_rows(store, state):
    disagreements = []
    metadata = {
        row["case_id"]: row for row in read_json(store.directory / "metadata.json")
    }
    positive_profiles = defaultdict(set)
    for case in store.cases:
        case_id = case["case_id"]
        entry = state["entries"].get(case_id)
        if entry is None:
            raise ValueError("all cases must have actual human-confirmed decisions")
        if (
            entry["review_status"] != "APPROVED"
            or entry.get("ai_assisted") is not True
            or entry.get("blind_first_pass") is not False
            or entry.get("review_method") != "AI_ASSISTED_HUMAN_CONFIRMED"
        ):
            raise ValueError("false review/blind provenance")
        candidate, reasons = suggested_label(case["context"])
        legacy, _ = classify(case["context"])
        if entry["human_label"] != candidate:
            disagreements.append(
                {
                    "case_id": case_id,
                    "human_label": entry["human_label"],
                    "candidate_label": candidate,
                    "legacy_policy_label": legacy,
                    "reference_kind": "DEPLOYED_POLICY_DIFFERENCE"
                    if candidate == legacy
                    else "PROPOSED_CANDIDATE_RULE_DIFFERENCE",
                    "context": case["context"],
                    "candidate_reasons": reasons,
                    "human_rationale": entry["rationale"],
                    "status": "OPEN_USER_PRESERVED_OR_PENDING",
                }
            )
        if metadata[case_id]["valid_quantity_crossed_profile"]:
            positive_profiles[metadata[case_id]["profile_id"]].add(entry["human_label"])
    return disagreements, sum(len(labels) > 1 for labels in positive_profiles.values())


def progress(store, state):
    disagreements, quantity_conflicts = audit_rows(store, state)
    return {
        "total": 161,
        "approved": len(state["entries"]),
        "unresolved": 0,
        "human_review_complete": len(state["entries"]) == 161,
        "label_counts": dict(
            Counter(e["human_label"] for e in state["entries"].values())
        ),
        "ai_assisted": True,
        "blind_first_pass": False,
        "policy_disagreements_open": len(disagreements),
        "positive_quantity_profile_inconsistencies": quantity_conflicts,
        "training_approved": False,
        "source_independence_approved": False,
        "backend_context_mapping_approved": False,
        "updated_at": datetime.now(UTC).isoformat(),
    }


def commit_state(store, state, expected_ledger_hash):
    verify_ledger(state, store.source_hash)
    current = digest(store.file) if store.file.exists() else None
    if current != expected_ledger_hash:
        raise RuntimeError("concurrent ledger change; refusing overwrite")
    if digest(store.directory / "draft_cases.json") != store.source_hash:
        raise RuntimeError("source dataset changed during import")
    if expected_ledger_hash is not None:
        backup = (
            store.directory
            / f"human_reviews.before-v2-{expected_ledger_hash[:12]}.json"
        )
        if not backup.exists():
            with backup.open("xb") as handle:
                handle.write(store.file.read_bytes())
    atomic(store.file, state)
    store.state = state
    store.export_csv_file()
    atomic(store.directory / "review_progress.json", progress(store, state))


def apply(source, directory, confirmed=False):
    if not confirmed:
        raise ValueError("explicit human final-decision attestation required")
    with write_lock(directory):
        store, rows, summary = check(source, directory)
        before_hash = digest(store.file) if store.file.exists() else None
        state = json.loads(json.dumps(store.state))
        additions = []
        for row in rows:
            previous = state["entries"].get(row["case_id"])
            if previous is not None:
                # Repeat import never erases an explicit later adjudication.
                if (
                    previous.get("source_file_sha256") != summary["source_file_sha256"]
                    or previous.get("source_human_label") != row["human_label"]
                    or previous.get("source_rationale") != row["rationale"]
                ):
                    raise ValueError("conflicting existing review; no overwrite")
                continue
            additions.append(row)
        if digest(source) != summary["source_file_sha256"]:
            raise RuntimeError("returned source file changed during check")
        now = datetime.now(UTC).isoformat()
        for row in additions:
            entry = {
                **{key: value for key, value in row.items() if key != "case_id"},
                "review_status": "APPROVED",
                "reviewer_role": "User-confirmed final reviewer; AI analysis assistance",
                "source_human_label": row["human_label"],
                "source_rationale": row["rationale"],
                "source_file_sha256": summary["source_file_sha256"],
                "submitted_via": "explicit-user-confirmed-v2-json-import",
                "review_method": "AI_ASSISTED_HUMAN_CONFIRMED",
                "ai_assisted": True,
                "blind_first_pass": False,
                "reviewed_at_utc": now,
                "submitted_at_utc": now,
                "review_time_source": "Import confirmation time; original human reading time was not collected",
                "human_attestation": "User explicitly stated AI assistance and that final decisions were personally theirs",
            }
            append_event(state, row["case_id"], entry, store.source_hash)
        if additions:
            commit_state(store, state, before_hash)
        return {
            **summary,
            "new_reviews_imported": len(additions),
            "write_performed": bool(additions),
            **progress(store, state),
            "ledger_revision": state["revision"],
            "ledger_sha256": digest(store.file),
        }


def adjudicate_clock(directory, confirmed=False):
    if not confirmed:
        raise ValueError("explicit user eight-case clock adjudication required")
    with write_lock(directory):
        store = checked_store(directory)
        state = json.loads(json.dumps(store.state))
        verify_ledger(state, store.source_hash)
        selected = [
            case
            for case in store.cases
            if case["context"]["feed_age_seconds"] in (-2, -1.9)
            and suggested_label(case["context"])[0] == "CONTINUE"
        ]
        if len(selected) != 8 or len(state["entries"]) != 161:
            raise ValueError("expected all 161 reviews and exact eight tolerance cases")
        before_hash = digest(store.file)
        directives = {
            "dataset_sha256": store.source_hash,
            "time_outside_tolerance": "User explicitly preserved REVIEW; deployed policy disagreement remains open",
            "clock_inside_tolerance": "User explicitly changed only these eight REVIEW labels to CONTINUE",
            "no_intent_unknown_permission": "User explicitly preserved CONTINUE; proposed candidate rule remains open",
            "production_policy_changed": False,
            "training_approved": False,
        }
        directives_path = directory / "user_policy_resolution.json"
        if directives_path.exists() and read_json(directives_path) != directives:
            raise ValueError("existing policy-resolution record conflicts")
        changed = []
        for case in selected:
            old = state["entries"][case["case_id"]]
            if (
                old.get("adjudication_id") == ADJUDICATION_ID
                and old["human_label"] == "CONTINUE"
            ):
                continue
            if old["human_label"] != "REVIEW":
                raise ValueError(
                    "unexpected prior clock label; needs separate adjudication"
                )
            entry = {
                **old,
                "human_label": "CONTINUE",
                "prior_rationale": old["rationale"],
                "rationale": "Kullanıcının açık kararı: mevcut −2 saniyelik tolerans korunsun. −2/−1,9 saniye ve diğer bağlam sağlıklı; CONTINUE yalnız izlemeye izin verir, emir onayı değildir.",
                "adjudication_id": ADJUDICATION_ID,
                "adjudication_source": "Explicit user reply: Mevcut toleransı koru; bu 8 kararı CONTINUE olarak düzelt",
                "adjudicated_at_utc": datetime.now(UTC).isoformat(),
            }
            append_event(state, case["case_id"], entry, store.source_hash)
            changed.append(case["case_id"])
        if changed:
            commit_state(store, state, before_hash)
        if not directives_path.exists():
            atomic(directives_path, directives)
        return {
            "changed_case_ids": changed,
            "labels_changed": len(changed),
            "ledger_revision": state["revision"],
            **progress(store, state),
        }


def freeze(directory):
    store = checked_store(directory)
    verify_ledger(store.state, store.source_hash)
    disagreements, quantity_conflicts = audit_rows(store, store.state)
    revision = store.state["revision"]
    output = directory / f"human_confirmed_unsplit_v2-r{revision}"
    if output.exists():
        raise ValueError("refusing to overwrite an existing frozen review bundle")
    output.mkdir(exist_ok=False)
    source_meta = {
        row["case_id"]: row for row in read_json(directory / "metadata.json")
    }
    rows, metadata = [], []
    for case in store.cases:
        entry = store.state["entries"][case["case_id"]]
        normalized, _ = state_from_context(case["context"])
        rows.append(
            {
                "state": normalized,
                "questions": QUESTIONS,
                "expected": {"operational_state": entry["human_label"]},
            }
        )
        original = source_meta[case["case_id"]]
        metadata.append(
            {
                "row": len(rows) - 1,
                "case_id": case["case_id"],
                "split": "UNASSIGNED",
                "origin": original["origin"],
                "source_capture_group": original["source_capture_group"],
                "profile_id": original["profile_id"],
                "parent_sources": original["sources"],
                "matching_offline_trace_ids": original["matching_offline_trace_ids"],
                "human_label": entry["human_label"],
                "human_review_status": "APPROVED",
                "ai_assisted": True,
                "blind_first_pass": False,
                "review_method": entry["review_method"],
                "reviewed_at_utc": entry["reviewed_at_utc"],
                "reviewer_role": entry["reviewer_role"],
                "rationale": entry["rationale"],
                "adjudication_id": entry.get("adjudication_id"),
            }
        )
    (output / "candidates.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    atomic(output / "metadata.json", metadata)
    hashes = {path.name: digest(path) for path in output.iterdir() if path.is_file()}
    source_hashes = {
        entry["source_file_sha256"] for entry in store.state["entries"].values()
    }
    if len(source_hashes) != 1:
        raise ValueError("mixed human source files require separate audit")
    changed = [
        case_id
        for case_id, entry in store.state["entries"].items()
        if entry["human_label"] != entry["source_human_label"]
    ]
    report = {
        "outcome": "DATA/INTEGRATION BLOCKED",
        "human_reviews": 161,
        "label_counts": dict(
            Counter(entry["human_label"] for entry in store.state["entries"].values())
        ),
        "ledger_chain_valid": True,
        "ledger_revision": revision,
        "ledger_sha256": digest(store.file),
        "source_file_sha256": next(iter(source_hashes)),
        "source_dataset_sha256": store.source_hash,
        "ai_assisted": True,
        "blind_review": False,
        "user_adjudicated_case_ids": changed,
        "labels_changed_from_user_file": len(changed),
        "unmodified_label_count": 161 - len(changed),
        "policy_disagreements_open": disagreements,
        "positive_quantity_profile_inconsistencies": quantity_conflicts,
        "source_independence_approved": False,
        "person1_runtime_mapping_verified": False,
        "training_approved": False,
        "training_started": False,
        "split_created": False,
        "production_approved": False,
        "execution_authority": False,
        "dataset_scope": "AI-assisted human-confirmed UNSPLIT development labels; policy differences open; not final-test gold",
        "hashes": hashes,
    }
    atomic(output / "manifest.json", report)
    return output, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("check", "apply", "adjudicate-clock", "freeze")
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--confirm-human-final-decisions", action="store_true")
    parser.add_argument("--confirm-user-eight-clock-corrections", action="store_true")
    args = parser.parse_args()
    if args.mode == "check":
        result = check(args.source, args.pack)[2]
    elif args.mode == "apply":
        result = apply(args.source, args.pack, args.confirm_human_final_decisions)
    elif args.mode == "adjudicate-clock":
        result = adjudicate_clock(args.pack, args.confirm_user_eight_clock_corrections)
    else:
        bundle, report = freeze(args.pack)
        result = {
            "frozen_bundle": str(bundle),
            "label_counts": report["label_counts"],
            "open_policy_differences": len(report["policy_disagreements_open"]),
            "ledger_revision": report["ledger_revision"],
            "training_approved": False,
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
