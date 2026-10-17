"""Build review-pending, UNSPLIT candidates; never trains, promotes or approves.

Valid quantities are crossed with every profile, never assigned by target class.
Source relatives remain development-only. Candidate policy != human gold.
"""

import argparse
import hashlib
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from data_expansion_offline import (
    LIFECYCLE_SCENARIOS,
    block_network,
    gate_probes,
    lifecycle_replay,
    load_backend,
    snapshot_backend,
)
from reviewed_development import check_protected, protected_hashes, validated_rows
from reviewed_learning import BOOLS, state_from_context

from ml.label_policy import QUESTIONS, VERSION, classify

VERSION_V2 = "candidate-expansion-v2-NOT-DEPLOYED"
QUANTITIES = ("0.00005000", "0.00010000", "0.00015000", "0.00020000")
LEGACY = ROOT / "data/trade_lifecycle/20261017T103022Z"
SOURCES = [
    "https://github.com/okx/agent-trade-kit/blob/github-main/docs/modules/spot.md",
    "https://github.com/NandhaKishorM/laya/blob/main/docs/finetune.md",
]


def dump(path, value):
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def facts(**updates):
    context = {
        "symbol": "BTC-USDT",
        "site": "tr",
        "source_mode": "MOCK",
        "intent_requested": True,
        "feed_age_seconds": 2,
        "quantity": QUANTITIES[1],
        **{key: False for key in BOOLS},
        "account_known": True,
        "approval_available": True,
    }
    context.update(updates)
    return context


def suggested_label(context):
    """Proposed candidate rule only. Known HALT precedes unknown/abstention.

    No production policy edit. The legacy function defaults unknown flags false;
    this wrapper exposes that gap rather than silently teaching unknown=healthy.
    """
    _, unknown = state_from_context(context)
    label, reasons = classify(context)
    if label == "HALT":
        return label, reasons
    if unknown:
        return "REVIEW", ["proposed_required_context_unknown:" + key for key in unknown]
    return label, reasons


def coverage_specs():
    """Explicit contrasts, boundaries and combined faults. Not all trade combinations."""
    specs = []
    for age in (0, 14.9, 15, 15.1, 40):
        specs.append(
            (
                "freshness_boundary",
                f"Piyasa verisinin yaşı {age} saniye.",
                {"feed_age_seconds": age},
            )
        )
    for age in (-2.1, -2, -1.9):
        specs.append(
            (
                "future_boundary",
                f"Piyasa verisinin hesaplanan yaşı {age} saniye.",
                {"feed_age_seconds": age},
            )
        )
    specs.append(
        (
            "missing_time",
            "Piyasa kaydının zamanı bilinmiyor.",
            {"feed_age_seconds": None},
        )
    )
    descriptions = {
        "account_known": "Hesap bağlamının bilinirlik durumu",
        "approval_available": "Ayrı kullanıcı onayının mevcut olma durumu",
        "permission_revoked": "Güvenilir yetki katmanından geri alma sinyali",
        "unknown_order": "Gönderilmiş emrin sonucunun bilinmeme durumu",
        "duplicate_intent": "Yerel günlüğe göre tekrarlanan istem sinyali",
        "injection_detected": "Güvenilir katmanın injection tespit durumu",
        "deployment_integrity_failure": "Güvenilir bütünlük kontrolünün arıza durumu",
        "excess_exposure": "Güvenilir risk katmanından maruziyet aşımı sinyali",
        "api_timeout": "Submit yapılmadan önce bilgi okuma timeout durumu",
        "agents_disagree": "Analiz kaynaklarının çelişme durumu",
    }
    for field in BOOLS:
        for value in (False, True, None):
            specs.append(
                (
                    field,
                    descriptions[field]
                    + ": "
                    + {False: "hayır", True: "evet", None: "bilinmiyor"}[value],
                    {field: value},
                )
            )
    specs += [
        (
            "safe_no_trade",
            "Yeni emir yok; hesap ve işlem onayı mevcut değil.",
            {
                "intent_requested": False,
                "account_known": False,
                "approval_available": False,
            },
        ),
        (
            "unknown_no_trade",
            "Yeni emir yok; yetki geri alma sinyali bilinmiyor.",
            {"intent_requested": False, "permission_revoked": None},
        ),
        (
            "combined_faults",
            "Bilgi isteği timeout ve injection tespiti birlikte mevcut.",
            {"api_timeout": True, "injection_detected": True},
        ),
        (
            "combined_faults",
            "Onay eksik ve piyasa verisi 40 saniyelik.",
            {"approval_available": False, "feed_age_seconds": 40},
        ),
        (
            "combined_faults",
            "Yetki geri alınmış, hesap bağlamı bilinmiyor.",
            {"permission_revoked": True, "account_known": None},
        ),
        (
            "combined_faults",
            "Emir sonucu belirsiz ve aynı istem tekrarlanıyor.",
            {"unknown_order": True, "duplicate_intent": True},
        ),
        (
            "combined_faults",
            "Bütünlük arızası ve analiz kaynakları çelişkisi birlikte mevcut.",
            {"deployment_integrity_failure": True, "agents_disagree": True},
        ),
        (
            "combined_faults",
            "Maruziyet aşımı var; onay bilgisi bilinmiyor.",
            {"excess_exposure": True, "approval_available": None},
        ),
    ]
    for quantity in ("0", "-0.0001", "NaN", "Infinity", "-Infinity"):
        specs.append(
            (
                "invalid_numeric_quantity",
                "Emir miktarının sayısal geçerliliği kontrol ediliyor.",
                {"quantity": quantity},
            )
        )
    return specs


def signature(context):
    reduced = {key: value for key, value in context.items() if key != "quantity"}
    return json.dumps(reduced, sort_keys=True, separators=(",", ":"))


def inventory_legacy():
    rows = [
        json.loads(line)
        for line in (LEGACY / "candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    metadata = json.loads((LEGACY / "metadata.json").read_text(encoding="utf-8"))
    if len(rows) != 720 or len(metadata) != 720:
        raise ValueError("legacy candidate inventory changed")
    selected = {}
    eligible = 0
    for row, meta in zip(rows, metadata):
        if meta["order_type"] in ("market", "limit", "post_only", "fok", "ioc"):
            eligible += 1
            selected.setdefault(
                meta["scenario_family"],
                {
                    "case_id": meta["case_id"],
                    "family": meta["scenario_family"],
                    "source_capture_group": meta["source_capture_group"],
                    "candidate_label": row["expected"]["operational_state"],
                    "review_status": "PENDING",
                    "not_independent": True,
                    "actual_exchange_response": False,
                },
            )
    return {
        "legacy_rows": 720,
        "regular_spot_eligible_rows": eligible,
        "representatives": list(selected.values()),
        "automatic_human_approvals": 0,
        "included_as_new_independent_sources": False,
        "selection_note": "One representative per existing core family; no algo scope expansion or relabeling",
        "hashes": {
            name: digest(LEGACY / name)
            for name in ("candidates.jsonl", "metadata.json")
        },
    }


def build(output):
    output = output.resolve()
    if not output.is_relative_to(ROOT / "data/reviewed_learning") or output.exists():
        raise ValueError("new owned quarantine directory required; no overwrite")
    old_rows, old_meta, old_manifest = validated_rows()
    frozen = protected_hashes()
    block_network()
    output.mkdir(parents=True, exist_ok=False)
    dump(
        output / "before.json",
        {
            "protected_hashes": frozen,
            "original_review_ledger": old_manifest["ledger_sha256"],
        },
    )
    commit, snapshot, hashes = snapshot_backend(output)
    backend = load_backend(snapshot)
    profiles = {}

    def add(context, family, description, source, fixed_quantity=False):
        # Collapse semantic duplicates while retaining ALL source ancestry.
        key = signature(context) + (
            ":invalid:" + context["quantity"] if fixed_quantity else ""
        )
        if key not in profiles:
            profiles[key] = {
                "context": context,
                "family": family,
                "description": description,
                "sources": [],
                "fixed_quantity": fixed_quantity,
            }
        profiles[key]["sources"].append(source)

    for row, meta in zip(old_rows, old_meta):
        context = json.loads(row["state"])["operational"]
        add(
            context,
            meta["parent_scenario_group"],
            "Önceden incelenmiş bağlamın miktarı yeniden örneklenmiş türevi.",
            {
                "origin": "SYNTHETIC_DERIVED",
                "source_kind": "HUMAN_CONFIRMED_PARENT_NOT_REVIEW_OF_NEW_ROW",
                "source_capture_group": meta["source_capture_group"],
                "source_event_group": meta["source_event_group"],
                "parent_case_id": meta["case_id"],
                "parent_label": row["expected"]["operational_state"],
            },
        )
    for family, description, updates in coverage_specs():
        add(
            facts(**updates),
            family,
            description,
            {
                "origin": "SYNTHETIC_DERIVED",
                "source_kind": "AUTHORED_COVERAGE_SPEC",
                "source_capture_group": "authored-coverage-v2-single-family-batch",
                "source_event_group": family,
            },
            fixed_quantity="quantity" in updates,
        )

    offline_traces = []
    for scenario in LIFECYCLE_SCENARIOS:
        for quantity in QUANTITIES:
            trace = lifecycle_replay(backend, quantity, scenario)
            trace_id = hashlib.sha256(
                json.dumps(trace, sort_keys=True).encode()
            ).hexdigest()
            trace.update(trace_id=trace_id, backend_commit=commit)
            offline_traces.append(trace)
            add(
                facts(quantity=quantity, **trace["context_updates"]),
                scenario,
                "Offline günlük akışı: "
                + scenario.replace("_", " ")
                + ". Borsa olayları enjekte edilmiş fixture verisidir.",
                {
                    "origin": "OFFLINE_BACKEND_TEST",
                    "source_kind": "EXECUTED_PURE_STORE_AND_POLICY_WITH_FIXTURES",
                    "source_capture_group": "offline-backend-v2-single-harness",
                    "source_event_group": scenario,
                    "trace_id": trace_id,
                    "parent_quantity": quantity,
                },
            )

    cases, rows, metadata = [], [], []
    for profile in profiles.values():
        quantities = (
            (profile["context"]["quantity"],)
            if profile["fixed_quantity"]
            else QUANTITIES
        )
        parent_group = hashlib.sha256(
            signature(profile["context"]).encode()
        ).hexdigest()[:20]
        for quantity in quantities:
            context = dict(profile["context"], quantity=quantity)
            state, unknown = state_from_context(context)
            label, reasons = suggested_label(context)
            case_id = hashlib.sha256((VERSION_V2 + state).encode()).hexdigest()[:20]
            cases.append(
                {
                    "case_id": case_id,
                    "split": "UNASSIGNED",
                    "origin": "SYNTHETIC_DERIVED",
                    "backend_commit": commit,
                    "source_capture_group": "expanded-development-mixed-ancestry-v2",
                    "source_event_group": parent_group,
                    "parent_scenario_group": parent_group,
                    "context": context,
                    "review_context": {
                        "description": profile["description"],
                        "order_type": "not_encoded",
                        "side": "not_encoded",
                    },
                }
            )
            rows.append(
                {
                    "state": state,
                    "questions": QUESTIONS,
                    "expected": {"operational_state": label},
                }
            )
            metadata.append(
                {
                    "row": len(rows) - 1,
                    "case_id": case_id,
                    "profile_id": parent_group,
                    "scenario_family": profile["family"],
                    "split": "UNASSIGNED",
                    "origin": "SYNTHETIC_DERIVED",
                    "sources": profile["sources"],
                    "matching_offline_trace_ids": [
                        source["trace_id"]
                        for source in profile["sources"]
                        if source.get("parent_quantity") == quantity
                        and "trace_id" in source
                    ],
                    "source_capture_group": "expanded-development-mixed-ancestry-v2",
                    "human_review_status": "PENDING",
                    "blind_first_pass": None,
                    "ai_assisted_generation": True,
                    "human_label": None,
                    "suggested_label": label,
                    "suggestion_reasons": reasons,
                    "suggestion_policy": VERSION_V2,
                    "unknown_fields": unknown,
                    "valid_quantity_crossed_profile": not profile["fixed_quantity"],
                    "independent_incident": False,
                    "exchange_private_response": False,
                }
            )
    dump(output / "draft_cases.json", cases)
    dump(output / "metadata.json", metadata)
    dump(output / "offline_traces.json", offline_traces)
    dump(output / "diagnostic_only_backend_probes.json", gate_probes(backend))
    dump(output / "legacy_720_inventory.json", inventory_legacy())
    (output / "candidates.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    # Empty, label-free form. Randomized by an opaque, reproducible source hash.
    shuffled = list(cases)
    random.Random(digest(output / "draft_cases.json")).shuffle(shuffled)
    review = {
        "baslik": "AEGIS — yeni veri adayları / insan incelemesi",
        "ornek_sayisi": len(cases),
        "kaynak_sha256": digest(output / "draft_cases.json"),
        "backend_commit": commit,
        "dataset_version": VERSION_V2,
        "uyarilar": [
            "Tüm kararlar boş; eski onaylar bu yeni türevlere otomatik taşınmadı.",
            "Sentetik ve offline test türevleridir; bağımsız gerçek exchange olayları değildir.",
            "Miktar kardeşleri, kaynakları ve aynı olayın türevleri tek splitte kalmalıdır.",
            "CONTINUE izleme içindir; hiçbir karar emir göndermez.",
            "Aday etiket/model cevabı gizli. Emin değilsen karar=null bırak.",
            "Yeni satırların insan onayı ve bağımsız validation/test henüz yok.",
        ],
        "karar_kurali": {
            "CONTINUE": "İzleme/analiz devam edebilir; emir izni değildir.",
            "REVIEW": "Gerekli bilgi eksik/çelişkili; yeni işlem bloklu.",
            "HALT": "Yetki/yürütme/bütünlük sorunu; yeni işlem bloklu.",
        },
        "ornekler": [
            {
                "ornek_no": i + 1,
                "case_id": case["case_id"],
                "senaryo": case["review_context"]["description"],
                "olgular": case["context"],
                "insan_incelemesi": {
                    "karar": None,
                    "gerekce": "",
                    "inceleyen_rolu": "",
                    "durum": "PENDING",
                },
            }
            for i, case in enumerate(shuffled)
        ],
    }
    dump(output / "human_review_BLIND.json", review)
    dump(
        output / "backend_ack.json",
        {
            "person1_approved": False,
            "commit": commit,
            "reviewer_role": "",
            "trusted_context_mapping_approved": False,
            "network_disabled": True,
            "order_execution_disabled": True,
        },
    )
    manifest = {
        "version": VERSION_V2,
        "backend_commit": commit,
        "cases": len(cases),
        "created_utc": datetime.now(UTC).isoformat(),
        "snapshot_hashes": hashes,
        "hashes": {
            p.name: digest(p)
            for p in output.iterdir()
            if p.is_file() and p.name != "before.json"
        },
        "training_approved": False,
        "human_review_complete": False,
        "independent_split_approved": False,
        "backend_context_mapping_approved": False,
        "source_independence_claimed": False,
        "original_policy_unchanged": VERSION,
        "suggested_unknown_policy_not_deployed": True,
        "source_urls": SOURCES,
        "orders_sent": 0,
        "network_allowed": False,
        "backend_execution_scope": "Pure Store and policy only; no Agent, ATK, settings, provider or HTTP",
        "exhaustive_all_trades": False,
        "model_trained": False,
        "laya_inference_performed": False,
    }
    dump(output / "review_manifest.json", manifest)
    report = qa(output)
    check_protected(frozen)
    dump(output / "qa.json", report)
    print(
        json.dumps({"directory": str(output), **report}, ensure_ascii=False, indent=2)
    )


def qa(directory):
    manifest = json.loads(
        (directory / "review_manifest.json").read_text(encoding="utf-8")
    )
    if any(
        manifest.get(key)
        for key in (
            "training_approved",
            "source_independence_claimed",
            "human_review_complete",
            "independent_split_approved",
            "backend_context_mapping_approved",
        )
    ):
        raise ValueError("candidate bundle must not assert review/split independence")
    for name, expected in manifest["hashes"].items():
        if Path(name).name != name or digest(directory / name) != expected:
            raise ValueError("candidate file hash mismatch")
    for name, expected in manifest["snapshot_hashes"].items():
        if digest(directory / "backend_snapshot" / name) != expected:
            raise ValueError("pinned backend snapshot hash mismatch")
    rows = [
        json.loads(line)
        for line in (directory / "candidates.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    meta = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    cases = json.loads((directory / "draft_cases.json").read_text(encoding="utf-8"))
    review = json.loads(
        (directory / "human_review_BLIND.json").read_text(encoding="utf-8")
    )
    if not len(rows) == len(meta) == len(cases) == review["ornek_sayisi"]:
        raise ValueError("case count mismatch")
    if len({row["state"] for row in rows}) != len(rows):
        raise ValueError("semantic exact duplicates must be collapsed")
    by_id = {case["case_id"]: case for case in cases}
    valid_profiles = defaultdict(Counter)
    class_quantities = defaultdict(Counter)
    by_signature = defaultdict(set)
    unknown_counts = Counter()
    contrasts = Counter()
    for index, (row, item, case) in enumerate(zip(rows, meta, cases)):
        state, unknown = state_from_context(case["context"])
        if (
            row["state"] != state
            or row["questions"] != QUESTIONS
            or item["row"] != index
        ):
            raise ValueError("serializer/question/row mismatch")
        label = row["expected"]["operational_state"]
        if (
            item["case_id"] != case["case_id"]
            or item["split"] != "UNASSIGNED"
            or case["split"] != "UNASSIGNED"
            or item["origin"] != "SYNTHETIC_DERIVED"
        ):
            raise ValueError("candidate identity/provenance/split mismatch")
        if (
            label != suggested_label(case["context"])[0]
            or item["human_review_status"] != "PENDING"
            or item["human_label"] is not None
        ):
            raise ValueError("candidate target or review status mismatch")
        unknown_counts.update(unknown)
        for key in BOOLS:
            if case["context"][key] is True:
                contrasts[key] += 1
        if item["valid_quantity_crossed_profile"]:
            valid_profiles[item["profile_id"]][case["context"]["quantity"]] += 1
            class_quantities[label][case["context"]["quantity"]] += 1
        signature_key = signature(case["context"])
        if not item["valid_quantity_crossed_profile"]:
            signature_key += ":invalid:" + case["context"]["quantity"]
        by_signature[signature_key].add(label)
    if any(counter != Counter(QUANTITIES) for counter in valid_profiles.values()):
        raise ValueError("quantity profiles must use identical valid size pool")
    if any(
        len(set(counter.values())) != 1 or set(counter) != set(QUANTITIES)
        for counter in class_quantities.values()
    ):
        raise ValueError("valid quantity distribution must not encode class")
    if any(len(labels) != 1 for labels in by_signature.values()):
        raise ValueError("positive quantity mutation unexpectedly changed label")
    if len(by_id) != len(cases) or {r["case_id"] for r in review["ornekler"]} != set(
        by_id
    ):
        raise ValueError("blind review identifiers mismatch")
    for item in review["ornekler"]:
        if item["olgular"] != by_id[item["case_id"]]["context"] or set(item) != {
            "ornek_no",
            "case_id",
            "senaryo",
            "olgular",
            "insan_incelemesi",
        }:
            raise ValueError("blind review facts mismatch or hidden-field leak")
        if item["insan_incelemesi"] != {
            "karar": None,
            "gerekce": "",
            "inceleyen_rolu": "",
            "durum": "PENDING",
        }:
            raise ValueError("generated approval forbidden")
    frozen = json.loads((directory / "before.json").read_text(encoding="utf-8"))[
        "protected_hashes"
    ]
    check_protected(frozen)
    traces = json.loads((directory / "offline_traces.json").read_text(encoding="utf-8"))
    validate_traces(traces, manifest["backend_commit"])
    trace_by_id = {t["trace_id"]: t for t in traces}
    for item, case in zip(meta, cases):
        for trace_id in item["matching_offline_trace_ids"]:
            if (
                trace_id not in trace_by_id
                or trace_by_id[trace_id]["quantity"] != case["context"]["quantity"]
            ):
                raise ValueError("offline ancestry quantity mismatch")
    return {
        "status": "PASS",
        "rows": len(rows),
        "unique_exact_states": len(rows),
        "contexts_ignoring_valid_quantity": len(by_signature),
        "valid_size_profiles": len(valid_profiles),
        "invalid_numeric_rows": sum(
            not m["valid_quantity_crossed_profile"] for m in meta
        ),
        "candidate_class_counts": dict(
            Counter(row["expected"]["operational_state"] for row in rows)
        ),
        "valid_quantity_histogram_by_class": {
            label: dict(counter) for label, counter in class_quantities.items()
        },
        "true_boolean_coverage": dict(contrasts),
        "unknown_context_coverage": dict(unknown_counts),
        "offline_lifecycle_replays_executed": len(traces),
        "diagnostic_only_backend_probes": len(
            json.loads(
                (directory / "diagnostic_only_backend_probes.json").read_text(
                    encoding="utf-8"
                )
            )
        ),
        "human_approved": 0,
        "independent_incident_count_asserted": None,
        "source_independence_approved": False,
        "training_approved": False,
        "original_files_unchanged": True,
        "split_created": False,
        "execution_authority": False,
        "orders_sent": 0,
    }


def validate_traces(traces, commit):
    expected = {(scenario, q) for scenario in LIFECYCLE_SCENARIOS for q in QUANTITIES}
    if (
        len(traces) != len(expected)
        or {(t["scenario"], t["quantity"]) for t in traces} != expected
    ):
        raise ValueError("offline replay evidence incomplete")
    for trace in traces:
        unsigned = {
            k: v for k, v in trace.items() if k not in ("trace_id", "backend_commit")
        }
        if (
            hashlib.sha256(json.dumps(unsigned, sort_keys=True).encode()).hexdigest()
            != trace["trace_id"]
        ):
            raise ValueError("offline trace hash mismatch")
        if (
            trace["backend_commit"] != commit
            or trace["origin"] != "OFFLINE_BACKEND_TEST"
            or trace["execution_component_loaded"] is not False
            or trace["actual_exchange_receipt"] is not False
            or trace["laya_classification_is_stub"] is not True
            or trace["full_agent_reconciliation_test"] is not False
        ):
            raise ValueError("unsupported source/authenticity claim")
        for event in trace["events"]:
            if (
                event.get("fixture_venue_state") == "partially_filled"
                and event.get("fixture_order_type") == "fok"
            ):
                raise ValueError("FOK fixture cannot partially fill")


def dry_run(directory):
    qa(directory)
    block_network()
    os.environ.update(
        HF_HOME=str(ROOT / "models/hf-cache"),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        HF_HUB_DISABLE_TELEMETRY="1",
    )
    from laya.train_cli import main as official_cli

    code = official_cli(
        [
            "--data",
            str(directory / "candidates.jsonl"),
            "--base",
            str(ROOT / "models/aegis_laya_selected"),
            "--dry-run",
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
            "17",
        ]
    )
    if code:
        raise RuntimeError("official dry-run failed; no training attempted")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "qa", "dry-run"))
    parser.add_argument("--directory", type=Path)
    args = parser.parse_args()
    directory = args.directory or ROOT / "data/reviewed_learning" / (
        "expanded-v2-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    )
    directory = directory.resolve()
    if not directory.is_relative_to(ROOT / "data/reviewed_learning"):
        parser.error("directory outside owned review quarantine")
    if args.mode == "build":
        build(directory)
    elif args.mode == "qa":
        print(json.dumps(qa(directory), indent=2))
    else:
        dry_run(directory)
