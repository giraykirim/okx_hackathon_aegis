"""OFFLINE_BACKEND_TEST: synthetic fixtures; never exchange/ATK evidence."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from test_policy import inputs

from aegis.laya_context import CONTEXT_VERSION, TrustedSignals, build_shadow_context
from aegis.policy import check
from aegis.settings import Settings


def test_missing_signals_remain_null_and_ids_text_balances_are_not_features():
    obs, _, proposal, now = inputs()
    out = build_shadow_context(obs, proposal, settings=Settings(_env_file=None), now=now)
    facts = out["state"]["operational"]
    assert facts["permission_revoked"] is None and facts["approval_available"] is None
    assert facts["duplicate_intent"] is None and facts["unknown_order"] is None
    assert out["eligible_for_shadow_inference"] is False
    assert out["execution_authority"] is False and out["context_version"] == CONTEXT_VERSION
    assert set(facts) == {
        "symbol",
        "site",
        "source_mode",
        "feed_age_seconds",
        "intent_requested",
        "quantity",
        "account_known",
        "approval_available",
        "api_timeout",
        "agents_disagree",
        "unknown_order",
        "duplicate_intent",
        "permission_revoked",
        "injection_detected",
        "deployment_integrity_failure",
        "excess_exposure",
    }
    assert (
        not {"run_id", "correlation_id", "intent_id", "summary", "quote_available", "exposure_quote"}
        & facts.keys()
    )


@pytest.mark.parametrize(
    "statuses,unknown,unresolved",
    [
        ([], False, False),
        (["PENDING"], False, True),
        (["UNKNOWN"], True, True),
        (["VERIFIED"], False, False),
        (None, None, None),
    ],
)
def test_unresolved_ack_is_not_unknown_submission(statuses, unknown, unresolved):
    obs, _, proposal, now = inputs()
    out = build_shadow_context(
        obs, proposal, settings=Settings(_env_file=None), now=now, journal_statuses=statuses
    )
    assert out["state"]["operational"]["unknown_order"] is unknown
    assert out["unresolved_order"] is unresolved


def test_no_proposal_is_unknown_not_no_intent_and_future_age_preserved():
    obs, _, _, now = inputs()
    obs.observed_at = now + timedelta(seconds=10)
    out = build_shadow_context(obs, None, settings=Settings(_env_file=None), now=now)
    assert out["state"]["operational"]["intent_requested"] is None
    assert out["state"]["operational"]["quantity"] is None
    assert out["state"]["operational"]["feed_age_seconds"] == -10


def test_untrusted_extra_flags_or_string_booleans_are_rejected():
    with pytest.raises(ValidationError):
        TrustedSignals(permission_revoked="false")
    with pytest.raises(ValidationError):
        TrustedSignals(requester_context={"approval_available": True})


def test_all_twenty_preserved_human_cases_keep_execution_vetoes():
    contract = json.loads(
        (Path(__file__).resolve().parents[2] / "contracts/laya-trusted-context-v1.json").read_text()
    )
    assert len(contract["policy_groups"]) == 5
    assert sum(len(g["member_case_ids"]) for g in contract["policy_groups"]) == 20
    for group in contract["policy_groups"]:
        facts = group["context_without_quantity"]
        assert group["agreed_label"] == ("REVIEW" if facts["intent_requested"] else "CONTINUE")
        for _ in group["member_case_ids"]:
            obs, laya, proposal, now = inputs()
            obs.observed_at = now - timedelta(seconds=facts["feed_age_seconds"])
            if not facts["intent_requested"]:
                proposal.action = "NO_TRADE"
                proposal.quantity = 0
                assert facts["permission_revoked"] is None
            result = check(
                obs,
                laya,
                proposal,
                now=now,
                source_mode="MOCK",
                approval_available=facts["approval_available"],
                unresolved=False,
                duplicate=False,
            )
            assert not result.approved
            expected = (
                "no_trade_proposed"
                if not facts["intent_requested"]
                else "future_feed"
                if facts["feed_age_seconds"] < -2
                else "stale_feed"
            )
            assert expected in result.reasons
