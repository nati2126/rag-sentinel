import numpy as np
import pytest

from rag_sentinel.claims.canonical import canonicalize
from rag_sentinel.claims.extract import ClaimList, extract_claims, locate_quote, to_claims, value_grounded
from rag_sentinel.claims.normalize import normalize_value, numbers_in, values_equivalent
from tests.fakes import ScriptedLLM


@pytest.mark.parametrize(
    "raw,kind,norm",
    [
        ("25 days", "quantity", "25 day"),
        ("twenty-five days", "quantity", "25 day"),
        ("25 working days", "quantity", "25 workday"),
        ("$60", "money", "60 usd"),
        ("60 USD per day", "money", "60 usd"),
        ("15%", "percent", "15%"),
        ("June 1, 2026", "date", "2026-06-01"),
        ("TLS 1.2 or higher", "text", "tls 1.2"),
        ("up to 2.5 days", "quantity", "2.5 day"),
        ("Required", "modal", "required"),
        ("not permitted", "modal", "prohibited"),
        ("12 characters", "quantity", "12 character"),
    ],
)
def test_normalize_value(raw, kind, norm):
    v = normalize_value(raw)
    assert (v.kind, v.norm) == (kind, norm)


def test_values_equivalent_rules():
    n = normalize_value
    assert values_equivalent(n("2 weeks"), n("14 days")) is True
    assert values_equivalent(n("24 hours"), n("1 day")) is True
    assert values_equivalent(n("20 days"), n("25 days")) is False
    assert values_equivalent(n("20 working days"), n("4 weeks")) is None  # not reliably comparable
    assert values_equivalent(n("$50"), n("€50")) is None
    assert values_equivalent(n("TLS 1.2"), n("TLS 1.3")) is False  # same named product, different version
    assert values_equivalent(n("containerd"), n("Docker Engine")) is None  # free text -> needs semantic judge
    assert values_equivalent(n("required"), n("optional")) is False


def test_numbers_in_handles_words():
    assert numbers_in("twenty-five days or $1,000") == {"25", "1000"}


def test_locate_quote_exact_and_near_exact():
    chunk = "Leave rules.\nFull-time employees receive 25 days of paid annual leave per year.\nOther text."
    assert locate_quote("full-time employees receive 25 days", chunk) is not None
    near = locate_quote("Full time employees receive 25 days of paid annual leave per year", chunk)
    assert near == "Full-time employees receive 25 days of paid annual leave per year."
    assert locate_quote("Employees receive 30 days of leave and a car", chunk) is None


def test_value_grounding():
    assert value_grounded("25 days", "Employees receive 25 days of leave.")
    assert not value_grounded("30 days", "Employees receive 25 days of leave.")
    assert value_grounded("required", "MFA is required for VPN access.")


def test_hallucinated_claims_are_rejected():
    raw = ClaimList.model_validate({"claims": [
        {"subject": "employee", "predicate": "Annual Leave", "value": "25 days", "source_quote": "Employees get 25 days.",
         "confidence": 0.9},
        {"subject": "employee", "predicate": "bonus", "value": "$5000", "source_quote": "Employees get a $5000 bonus.",
         "confidence": 0.9},
        {"subject": "employee", "predicate": "sick_leave", "value": "12 days", "source_quote": "Employees get 25 days.",
         "confidence": 0.9},
    ]})  # fmt: skip
    rep = to_claims(raw, "c1", "d1", "Intro. Employees get 25 days. End.", "test")
    assert [c.predicate for c in rep.accepted] == ["annual_leave"]
    assert {reason for _, reason in rep.rejected} == {
        "source_quote not found in passage",
        "value not stated in source_quote",
    }
    assert rep.accepted[0].value_norm == "25 day"


def test_extract_claims_uses_cache():
    llm = ScriptedLLM({"ClaimList": lambda s, u: {"claims": []}})
    store = {}
    extract_claims(llm, "c", "d", "T", "text", store.get, store.__setitem__)
    rep = extract_claims(llm, "c", "d", "T", "text", store.get, store.__setitem__)
    assert len(llm.calls) == 1 and rep.cached


def _label_embed(table):
    def embed(labels):
        return np.stack([np.asarray(table[lbl], dtype=np.float32) for lbl in labels])

    return embed


def test_canonicalize_merges_identical_and_judged_names():
    vecs = {"annual leave days": [1, 0, 0], "annual leave entitlement": [0.97, 0.243, 0],
            "annual leave carryover": [0.9, 0.0, 0.436], "meal per diem": [0, 0, 1]}  # fmt: skip
    preds = [
        "annual_leave_days",
        "annual_leave_days",
        "annual_leave_entitlement",
        "annual_leave_carryover",
        "meal_per_diem",
    ]

    def judge(a, b, qa, qb):
        return "carryover" not in (a + b)

    m = canonicalize(preds, {}, _label_embed(vecs), threshold=0.85, judge=judge)
    assert m["annual_leave_entitlement"] == "annual_leave_days"
    assert m["annual_leave_carryover"] == "annual_leave_carryover"
    assert m["meal_per_diem"] == "meal_per_diem"
    # Without a judge, only near-identical labels merge.
    m2 = canonicalize(preds, {}, _label_embed(vecs), threshold=0.85, judge=None)
    assert m2["annual_leave_entitlement"] == "annual_leave_days"  # cos 0.97
    assert m2["annual_leave_carryover"] == "annual_leave_carryover"
