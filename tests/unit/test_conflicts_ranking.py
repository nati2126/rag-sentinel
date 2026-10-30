from datetime import date

from rag_sentinel.claims.normalize import normalize_value
from rag_sentinel.config import RankingWeights
from rag_sentinel.conflicts.detect import (
    CONTRADICTION,
    DIFFERENT_CONTEXT,
    HISTORICAL,
    INSUFFICIENT,
    OUTDATED,
    PENDING_CHANGE,
    ConflictDetector,
    context_relation,
    naive_value_conflicts,
)
from rag_sentinel.db import Claim, Document
from rag_sentinel.ingest.versioning import Lineage
from rag_sentinel.ranking import PRESETS, rank_evidence, standing
from rag_sentinel.retrieval.retriever import Hit

AS_OF = date(2026, 10, 1)


def doc(i, family=None, v=1, eff=None, auth=None, status="approved", sup=None):
    return Document(id=i, family_id=family or i, filename=f"{i}.md", title=i, content_type="md", sha256=i,
                    version_number=v, effective_date=eff, authority_level=auth, approval_status=status,
                    supersedes_id=sup, stored_path="")  # fmt: skip


def claim(i, d, value, subject="employee", key="annual_leave", qualifier=None):
    nv = normalize_value(value)
    return Claim(id=i, doc_id=d, chunk_id=f"ch-{i}", subject=subject, predicate=key, predicate_key=key, value=value,
                 value_kind=nv.kind, value_num=nv.num, value_unit=nv.unit, value_norm=nv.norm, qualifier=qualifier,
                 source_quote=f"{subject} {value}")  # fmt: skip


def detector(docs, claims, judge=None):
    dm = {d.id: d for d in docs}
    return ConflictDetector(dm, claims, Lineage(docs), AS_OF, RankingWeights(), 0.12, judge)


def kinds(findings):
    return {tuple(sorted((f.claim_a.doc_id, f.claim_b.doc_id))): f for f in findings}


def test_canonical_leave_scenario():
    docs = [
        doc("v1", "leave", 1, date(2026, 1, 15), 5),
        doc("v2", "leave", 2, date(2026, 6, 1), 5, sup="v1"),
        doc("handbook", eff=date(2025, 11, 1), auth=3),
        doc("faq", eff=date(2026, 2, 1), auth=2),
    ]
    claims = [claim("a", "v1", "20 days"), claim("b", "v2", "25 days"), claim("c", "handbook", "20 days"),
              claim("d", "faq", "10 days", subject="contractor")]  # fmt: skip
    f = kinds(detector(docs, claims).detect())
    assert f[("v1", "v2")].kind == HISTORICAL and f[("v1", "v2")].preferred_doc_id == "v2"
    out = f[("handbook", "v2")]
    assert out.kind == OUTDATED and out.confirmed and out.preferred_doc_id == "v2"
    assert ("handbook", "v1") not in f  # same value: agreement, not a finding
    assert all(f[k].kind == DIFFERENT_CONTEXT for k in f if "faq" in k)


def test_equal_authority_disagreement_is_unresolved_contradiction():
    docs = [doc("sec", eff=date(2026, 3, 1), auth=4), doc("ops", eff=date(2026, 4, 1), auth=4)]
    claims = [claim("a", "sec", "90 days", key="log_retention"), claim("b", "ops", "180 days", key="log_retention")]
    (only,) = detector(docs, claims).detect()
    assert only.kind == CONTRADICTION and only.preferred_doc_id is None


def test_newer_lower_authority_doc_is_contradiction_with_preferred_source():
    docs = [doc("policy", eff=date(2026, 1, 1), auth=5), doc("wiki", eff=date(2026, 8, 1), auth=1)]
    claims = [claim("a", "policy", "12 characters", key="pw"), claim("b", "wiki", "8 characters", key="pw")]
    (only,) = detector(docs, claims).detect()
    assert only.kind == CONTRADICTION and only.preferred_doc_id == "policy"


def test_older_lower_authority_doc_is_possibly_outdated():
    docs = [doc("policy", eff=date(2026, 5, 1), auth=5), doc("guide", eff=date(2025, 1, 1), auth=2)]
    claims = [claim("a", "policy", "$60", key="per_diem"), claim("b", "guide", "$45", key="per_diem")]
    (only,) = detector(docs, claims).detect()
    assert only.kind == OUTDATED and not only.confirmed


def test_draft_revision_is_pending_change_and_approved_version_preferred():
    docs = [doc("rw1", "remote", 1, date(2025, 9, 1), 5), doc("rw2", "remote", 2, date(2026, 9, 1), 5, status="draft"),
            doc("toolkit", eff=date(2026, 3, 1), auth=2)]  # fmt: skip
    claims = [claim("a", "rw1", "2 days", key="remote_days"), claim("b", "rw2", "4 days", key="remote_days"),
              claim("c", "toolkit", "2 days", key="remote_days")]  # fmt: skip
    f = kinds(detector(docs, claims).detect())
    assert f[("rw1", "rw2")].kind == PENDING_CHANGE and f[("rw1", "rw2")].preferred_doc_id == "rw1"
    assert f[("rw2", "toolkit")].kind == PENDING_CHANGE  # a draft disagreeing is not an actionable conflict


def test_already_superseded_document_needs_no_update():
    docs = [doc("old", "tls", 1, date(2019, 6, 1), 5), doc("new", "crypto", 1, date(2026, 3, 1), 5, sup="old"),
            doc("rfc", eff=date(2021, 3, 1), auth=4)]  # fmt: skip
    claims = [claim("a", "old", "TLS 1.0", key="min_tls"), claim("b", "rfc", "TLS 1.2", key="min_tls")]
    (only,) = detector(docs, claims).detect()
    assert only.kind == HISTORICAL


def test_ambiguous_context_without_judge_is_insufficient_and_with_judge_follows_verdict():
    docs = [doc("x", auth=4), doc("y", auth=4)]
    claims = [claim("a", "x", "5 days", qualifier="after 5 years of service"), claim("b", "y", "3 days")]
    (only,) = detector(docs, claims).detect()
    assert only.kind == INSUFFICIENT
    assert detector(docs, claims, judge=lambda a, b: "different_context").detect()[0].kind == DIFFERENT_CONTEXT
    assert detector(docs, claims, judge=lambda a, b: "equivalent").detect() == []


def test_context_relation():
    a, b = claim("a", "x", "1 day", subject="full-time employees"), claim("b", "y", "2 days", subject="employee")
    assert context_relation(a, b) == "same"
    assert context_relation(a, claim("c", "z", "1 day", subject="contractors")) == "different"


def test_naive_baseline_flags_every_value_difference():
    claims = [claim("a", "x", "20 days"), claim("b", "y", "10 days", subject="contractor")]
    assert len(naive_value_conflicts(claims)) == 1


def test_standing_and_ranking_not_newest_wins():
    approved = doc("approved", "rw", 1, date(2025, 9, 1), 5)
    draft = doc("draft", "rw", 2, date(2026, 9, 1), 5, status="draft")
    future = doc("future", "pd", 2, date(2027, 1, 1), 5)
    lin = Lineage([approved, draft, future])
    assert standing(approved, AS_OF, lin, RankingWeights()).status == "in_force"
    assert standing(draft, AS_OF, lin, RankingWeights()).status == "unapproved"
    assert standing(future, AS_OF, lin, RankingWeights()).status == "not_yet_effective"
    hits = [Hit("c-draft", "draft", "", None, relevance=0.9), Hit("c-ok", "approved", "", None, relevance=0.8)]
    docs = {d.id: d for d in (approved, draft, future)}
    ranked = rank_evidence(hits, docs, lin, AS_OF, RankingWeights())
    assert ranked[0].doc_id == "approved"
    assert "draft" in ranked[1].explanation
    naive = rank_evidence(hits, docs, lin, AS_OF, PRESETS["newest_wins"])
    assert naive[0].doc_id == "draft"


def test_historical_as_of_prefers_version_in_force_then():
    v1 = doc("v1", "leave", 1, date(2026, 1, 15), 5)
    v2 = doc("v2", "leave", 2, date(2026, 6, 1), 5, sup="v1")
    lin = Lineage([v1, v2])
    hits = [Hit("c2", "v2", "", None, relevance=0.9), Hit("c1", "v1", "", None, relevance=0.85)]
    docs = {"v1": v1, "v2": v2}
    assert rank_evidence(hits, docs, lin, AS_OF, RankingWeights())[0].doc_id == "v2"
    assert rank_evidence(hits, docs, lin, date(2026, 3, 1), RankingWeights())[0].doc_id == "v1"


def _broken_judge(a, b):
    from rag_sentinel.llm import LLMOutputError

    raise LLMOutputError("PairVerdict: model output failed validation twice")


def _disagreeing_judge(a, b):
    return "different_context"


def test_judge_failure_on_undecided_pair_is_recorded_for_review():
    docs = [doc("x", auth=4), doc("y", auth=4)]
    claims = [claim("a", "x", "5 days", qualifier="after 5 years of service"), claim("b", "y", "3 days")]
    (only,) = detector(docs, claims, judge=_broken_judge).detect()
    assert only.kind == INSUFFICIENT and only.detected_by == "llm_error"


def test_judge_failure_keeps_a_rule_finding():
    docs = [doc("x", auth=4), doc("y", auth=4)]
    claims = [claim("a", "x", "5 days"), claim("b", "y", "3 days")]
    (only,) = detector(docs, claims, judge=_broken_judge).detect()
    assert only.kind == CONTRADICTION and only.detected_by == "rule"


# -- arbitration regression tests: the LLM judge never erases a rule finding ----------------------------


def test_overlapping_population_rule_finding_survives_judge_disagreement():
    """'All employees: 20 days' (handbook) vs 'full-time employees: 25 days' (policy v2, supersedes v1)."""
    v1 = doc("v1", family="leave", v=1, eff=date(2026, 1, 1), auth=5)
    v2 = doc("v2", family="leave", v=2, eff=date(2026, 6, 1), auth=5, sup="v1")
    hb = doc("hb", eff=date(2025, 11, 1), auth=3)
    claims = [claim("c1", "v1", "20 days", subject="full-time employee"),
              claim("c2", "v2", "25 days", subject="full-time employee"),
              claim("c3", "hb", "20 days", subject="all employees")]  # fmt: skip
    found = kinds(detector([v1, v2, hb], claims, judge=_disagreeing_judge).detect())
    f = found[("hb", "v2")]
    assert f.kind == OUTDATED and f.confirmed
    assert f.judge_opinion == "different_context" and "kept for review" in f.explanation
    assert found[("v1", "v2")].kind == HISTORICAL


def test_judge_agreement_is_recorded():
    docs = [doc("x", auth=4), doc("y", auth=4)]
    claims = [claim("a", "x", "5 days"), claim("b", "y", "3 days")]
    (only,) = detector(docs, claims, judge=lambda a, b: "same_fact_conflict").detect()
    assert only.kind == CONTRADICTION and only.detected_by == "rule+llm" and only.judge_opinion is None


def test_rule_finding_without_judge_is_unchanged():
    docs = [doc("x", auth=4), doc("y", auth=4)]
    claims = [claim("a", "x", "5 days"), claim("b", "y", "3 days")]
    (with_judge,) = detector(docs, claims, judge=_disagreeing_judge).detect()
    (without,) = detector(docs, claims).detect()
    assert with_judge.kind == without.kind == CONTRADICTION


def test_supersession_is_historical_and_never_sent_to_the_judge():
    calls = []
    v1 = doc("v1", family="p", v=1, eff=date(2025, 1, 1), auth=4)
    v2 = doc("v2", family="p", v=2, eff=date(2026, 1, 1), auth=4, sup="v1")
    claims = [claim("a", "v1", "$250"), claim("b", "v2", "$320")]
    (only,) = detector([v1, v2], claims, judge=lambda a, b: calls.append(1) or "different_context").detect()
    assert only.kind == HISTORICAL and calls == []


def test_equivalent_values_across_units_are_not_conflicts():
    docs = [doc("x", auth=4), doc("y", auth=4)]
    claims = [claim("a", "x", "2 weeks"), claim("b", "y", "14 days")]
    assert detector(docs, claims, judge=_disagreeing_judge).detect() == []


def test_different_units_with_different_amounts_are_a_rule_finding():
    docs = [doc("x", auth=4), doc("y", auth=4)]
    claims = [claim("a", "x", "4 weeks"), claim("b", "y", "14 days")]
    (only,) = detector(docs, claims).detect()
    assert only.kind == CONTRADICTION


def test_scope_difference_is_left_to_the_judge():
    docs = [doc("x", auth=4), doc("y", auth=4)]
    claims = [claim("a", "x", "5 days", qualifier="international travel"), claim("b", "y", "3 days")]
    (only,) = detector(docs, claims, judge=_disagreeing_judge).detect()
    assert only.kind == DIFFERENT_CONTEXT and only.detected_by == "llm"


def test_document_with_several_values_for_one_attribute_is_left_to_the_judge():
    """'$500 needs a director, $10,000 the CFO' with the approver lost in extraction vs '$1,000 needs a director'."""
    docs = [doc("fin", auth=4), doc("proc", auth=4)]
    claims = [claim("a", "fin", "$500", subject="purchases", key="approval_amount"),
              claim("b", "fin", "$10,000", subject="purchases", key="approval_amount"),
              claim("c", "proc", "$1,000", subject="purchases", key="approval_amount")]  # fmt: skip
    verdicts = {frozenset({"a", "c"}): "same_fact_conflict", frozenset({"b", "c"}): "different_context"}
    found = detector(docs, claims, judge=lambda x, y: verdicts[frozenset({x.id, y.id})]).detect()
    by = {frozenset({f.claim_a.id, f.claim_b.id}): f for f in found}
    assert by[frozenset({"a", "c"})].kind == CONTRADICTION and by[frozenset({"a", "c"})].detected_by == "llm"
    assert by[frozenset({"b", "c"})].kind == DIFFERENT_CONTEXT
    (no_judge,) = {f.kind for f in detector(docs, claims).detect()}
    assert no_judge == INSUFFICIENT


def test_is_a_relations_make_subjects_comparable_but_siblings_stay_undecided():
    def c(subject):
        return claim("x", "d", "5 minutes", subject=subject)

    assert context_relation(c("laptops and desktops"), c("company device")) == "same"
    assert context_relation(c("company phones"), c("devices")) == "same"
    assert context_relation(c("laptops"), c("phones")) == "ambiguous"
    assert context_relation(c("laptops"), c("production databases")) == "different"
