"""Prepare a read-only policy adjudication handoff, never grant or fabricate ACK.

Runs only pinned pure policy.check with injected fixtures and classification stubs.
No Agent/settings/ATK, HTTP, real/demo orders, training, or review-ledger writes.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from candidate_preflight import protected_hashes, sha, strict_json
from data_expansion_offline import (
    NOW,
    block_network,
    load_backend,
    observation,
    snapshot_backend,
)
from expand_operational_data import suggested_label
from import_expanded_review import checked_store
from reviewed_learning import LABELS, ROOT, state_from_context

from ml.label_policy import VERSION, classify

PACK = ROOT / "data/reviewed_learning/expanded-v2-20261017T120738Z"


def group_differences(differences):
    """Group only quantity siblings; preserve full contexts/labels/IDs in members."""
    seen, groups = set(), {}
    for item in differences:
        case_id, context = item["case_id"], item["context"]
        if case_id in seen:
            raise ValueError("duplicate conflict case ID")
        seen.add(case_id)
        state_from_context(context)
        if item["human_label"] not in LABELS:
            raise ValueError("invalid human decision")
        legacy, _ = classify(context)
        candidate, _ = suggested_label(context)
        if (
            legacy != item["legacy_policy_label"]
            or candidate != item["candidate_label"]
        ):
            raise ValueError(
                "reference policy drift; new explicit adjudication required"
            )
        expected_kind = (
            "DEPLOYED_POLICY_DIFFERENCE"
            if item["human_label"] != legacy
            else "PROPOSED_CANDIDATE_RULE_DIFFERENCE"
        )
        if item["reference_kind"] != expected_kind or item["human_label"] == candidate:
            raise ValueError("conflict kind/reference mismatch")
        normalized = {key: value for key, value in context.items() if key != "quantity"}
        encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
        identifier = hashlib.sha256(encoded.encode()).hexdigest()[:16]
        group = groups.setdefault(
            encoded,
            {
                "group_id": identifier,
                "context_without_quantity": normalized,
                "human_label": item["human_label"],
                "legacy_policy_label": legacy,
                "candidate_label": candidate,
                "reference_kind": expected_kind,
                "members": [],
                "review_status": "PENDING_PERSON1_POLICY_DECISION",
                "resolution": None,
            },
        )
        if (group["human_label"], group["reference_kind"]) != (
            item["human_label"],
            expected_kind,
        ):
            raise ValueError("quantity siblings have inconsistent human decisions")
        group["members"].append(item)
    return sorted(groups.values(), key=lambda group: group["group_id"])


def gate_fixture(modules, context, label):
    """Real gate function, fixture-only context. NOT actual LAYA or authorization proof."""
    models, policy = modules["models"], modules["policy"]
    intent = context["intent_requested"]
    obs = observation(
        models, age=context["feed_age_seconds"], account_known=context["account_known"]
    )
    proposal = models.Proposal(
        action="BUY" if intent else "NO_TRADE",
        symbol=context["symbol"],
        quantity=context["quantity"] if intent else "0",
        intent_id="POLICY_ALIGNMENT_FIXTURE",
        summary="OFFLINE FIXTURE ONLY",
    )
    classification = models.Classification(
        label=label,
        confidence=1,
        abstained=False,
        model_version="POLICY_FIXTURE_NOT_LAYA",
        latency_ms=0,
    )
    result = policy.check(
        obs,
        classification,
        proposal,
        now=NOW,
        source_mode=context["source_mode"],
        approval_available=context["approval_available"],
        unresolved=False,
        duplicate=False,
    )
    return {
        "classification_stub_label": label,
        "classification_is_fixture": True,
        "proposed_action_fixture": proposal.action,
        "approved": result.approved,
        "reasons": result.reasons,
        "origin": "EXECUTED_OFFLINE_PURE_POLICY_TEST",
        "not_exchange_or_atk_trace": True,
    }


def context_mapping():
    """Source hints only, not a Person 1 mapping approval or a new HTTP contract."""
    rows = {
        "symbol": (
            "Observation.symbol",
            "EXISTS_IN_LEGACY_OBSERVATION",
            "backend/aegis/models.py",
        ),
        "feed_age_seconds": (
            "observed_at + timezone-aware server clock",
            "DERIVABLE_NOT_SENT_AS_AGE",
            "backend/aegis/models.py",
        ),
        "account_known": (
            "Observation.account_known; default false conflates unavailable with false",
            "PARTIAL_SEMANTICS",
            "backend/aegis/models.py",
        ),
        "source_mode": (
            "Agent mode / risk service MARKET_ONLY",
            "NOT_IN_LEGACY_ENVELOPE",
            "backend/aegis/agent.py",
        ),
        "site": (
            "Trusted deployment configuration; do not infer from requester text",
            "NOT_IN_LEGACY_ENVELOPE",
            "backend/aegis/integrations.py",
        ),
        "intent_requested": (
            "Caller/proposal stage; agent calls classify before reason creates proposal",
            "ORDER_OF_OPERATIONS_DECISION_REQUIRED",
            "backend/aegis/agent.py",
        ),
        "quantity": (
            "Trusted bound proposal; classifier is currently called before reasoning",
            "ORDER_OF_OPERATIONS_DECISION_REQUIRED",
            "backend/aegis/agent.py",
        ),
        "approval_available": (
            "Computed after model classification; independent approval required",
            "NOT_IN_LEGACY_ENVELOPE",
            "backend/aegis/agent.py",
        ),
        "unknown_order": (
            "Store + reconciliation; unresolved is not synonymous with unknown",
            "SEMANTIC_MAPPING_REQUIRED",
            "backend/aegis/store.py",
        ),
        "duplicate_intent": (
            "Store.duplicate with bound proposal.intent_id, after proposal",
            "NOT_IN_LEGACY_ENVELOPE",
            "backend/aegis/agent.py",
        ),
        "permission_revoked": (
            "Explicit trusted authorization source; stop_requested alone is not proof",
            "NO_EXPLICIT_MAPPING_VERIFIED",
            "backend/aegis/agent.py",
        ),
        "api_timeout": (
            "Distinguish pre-submit read from post-submit unknown outcome",
            "NO_EXPLICIT_MAPPING_VERIFIED",
            "backend/aegis/integrations.py",
        ),
        "agents_disagree": (
            "Trusted comparison signal, not text/model allegation",
            "NO_EXPLICIT_MAPPING_VERIFIED",
            "backend/aegis/integrations.py",
        ),
        "injection_detected": (
            "Trusted detector result; instructions alone are not detection evidence",
            "NO_EXPLICIT_MAPPING_VERIFIED",
            "backend/aegis/integrations.py",
        ),
        "deployment_integrity_failure": (
            "Independent integrity verification, not default false",
            "NO_EXPLICIT_MAPPING_VERIFIED",
            "backend/aegis/integrations.py",
        ),
        "excess_exposure": (
            "Trusted risk calculation exists in final gate, not as classifier boolean",
            "NOT_IN_LEGACY_ENVELOPE",
            "backend/aegis/policy.py",
        ),
    }
    return [
        {
            "field": key,
            "source_hint": value[0],
            "status": value[1],
            "source_file": value[2],
            "person1_approved": False,
            "approved_semantics": None,
            "evidence": [],
        }
        for key, value in rows.items()
    ]


def dump_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def prepare(run, output, response):
    if not run.resolve().is_relative_to(ROOT / "ml/policy_alignment"):
        raise ValueError("run must be in owned policy_alignment quarantine")
    if (
        output.resolve().parent != ROOT.parent / "outputs"
        or response.resolve().parent != ROOT.parent / "outputs"
    ):
        raise ValueError("deliverables must be in task outputs")
    if run.exists() or output.exists() or response.exists():
        raise ValueError("new run/output paths required; never overwrite")
    block_network()
    before = protected_hashes()
    store = checked_store(
        PACK
    )  # validates immutable source + actual review audit chain
    frozen = PACK / "human_confirmed_unsplit_v2-r169"
    manifest = strict_json((frozen / "manifest.json").read_text(encoding="utf-8"))
    if sha(store.file) != manifest["ledger_sha256"]:
        raise ValueError("review ledger changed after frozen export")
    for name, expected in manifest["hashes"].items():
        if Path(name).name != name or sha(frozen / name) != expected:
            raise ValueError("frozen bundle mismatch")
    cases = {row["case_id"]: row for row in store.cases}
    differences = manifest["policy_disagreements_open"]
    for item in differences:
        case = cases[item["case_id"]]
        review = store.state["entries"][item["case_id"]]
        if (
            case["context"] != item["context"]
            or review["human_label"] != item["human_label"]
        ):
            raise ValueError("human/source/conflict binding mismatch")
    groups = group_differences(differences)
    if (
        len(differences) != 20
        or len(groups) != 5
        or any(len(g["members"]) != 4 for g in groups)
    ):
        raise ValueError("expected original 20 conflicts / five quantity groups")
    run.mkdir(parents=True, exist_ok=False)
    commit, snapshot, snapshot_hashes = snapshot_backend(run)
    if commit != store.commit:
        raise ValueError("backend commit changed; new Person 1 review required")
    modules = load_backend(snapshot)
    proofs = []
    for group in groups:
        for item in group["members"]:
            results = [
                gate_fixture(modules, item["context"], label)
                for label in sorted(
                    {
                        item["human_label"],
                        item["legacy_policy_label"],
                        item["candidate_label"],
                    }
                )
            ]
            if any(row["approved"] for row in results):
                raise ValueError("unexpected fixture gate approval; stop handoff")
            proofs.append(
                {
                    "case_id": item["case_id"],
                    "group_id": group["group_id"],
                    "results": results,
                }
            )
    after = protected_hashes()
    if before != after:
        raise ValueError("protected input changed during audit")
    bindings = {
        "backend_commit": commit,
        "ledger_sha256": sha(store.file),
        "draft_cases_sha256": sha(PACK / "draft_cases.json"),
        "frozen_manifest_sha256": sha(frozen / "manifest.json"),
        "policy_version": VERSION,
        "policy_sha256": sha(ROOT / "ml/label_policy.py"),
        "candidate_rule_sha256": sha(ROOT / "scripts/ml/expand_operational_data.py"),
    }
    report = {
        "bindings": bindings,
        "status": "PENDING_PERSON1_POLICY_AND_CONTEXT_DECISION",
        "groups": groups,
        "cases": len(differences),
        "group_count": len(groups),
        "conflict_kinds": dict(Counter(row["reference_kind"] for row in differences)),
        "pure_backend_proofs": proofs,
        "gate_calls_executed": sum(len(p["results"]) for p in proofs),
        "all_fixture_calls_blocked": True,
        "snapshot_hashes": snapshot_hashes,
        "context_mapping_to_be_reviewed": context_mapping(),
        "human_decisions_changed": False,
        "person1_ack_changed": False,
        "training_approved": False,
        "source_independence_approved": False,
        "runtime_mapping_verified": False,
        "policy_deployed": False,
        "protected_files_unchanged": True,
        "protected_sha256": before,
        "limitations": [
            "Gate checks use constructed observations/classification stubs, not LAYA/exchange/ATK",
            "Policy blocks in these fixtures do not settle label semantics or unknown permission mapping",
            "No original ledger, candidate rule, backend contract, model or data split changed",
        ],
    }
    template = {
        "bindings": bindings,
        "status": "PENDING_NOT_AN_ACK",
        "reviewer_role": None,
        "reviewed_at_utc": None,
        "person1_approved": None,
        "reason": None,
        "instructions": "Choose agreed semantics per group; attach reviewed commit/evidence. No secrets. This template is not a valid training ACK.",
        "groups": [
            {
                "group_id": group["group_id"],
                "case_ids": [row["case_id"] for row in group["members"]],
                "agreed_label": None,
                "policy_revision_required": None,
                "policy_version_after_review": None,
                "reason": None,
                "execution_veto_preserved": None,
            }
            for group in groups
        ],
        "context_mapping": context_mapping(),
        "trusted_context_mapping_approved": None,
        "implementation_commit": None,
        "offline_test_evidence": [],
        "source_independence_approved": False,
        "training_approved": False,
    }
    dump_new(run / "evidence.json", report)
    dump_new(output, report)
    dump_new(response, template)
    return {
        "cases": len(differences),
        "groups": len(groups),
        "gate_calls_executed": report["gate_calls_executed"],
        "all_fixture_calls_blocked": True,
        "protected_files_unchanged": True,
        "status": report["status"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--response", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.run, args.output, args.response), indent=2))
