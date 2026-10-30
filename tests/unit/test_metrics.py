from evaluation import metrics as M

Q = {"expected": [["25"]], "stale": ["20"], "gold_evidence": [{"file": "v2.md", "contains": "25 days"}]}


def test_answer_matching_ignores_citation_labels():
    assert M.is_correct(Q, "Employees get 25 days. [E2]")
    assert not M.is_correct(Q, "Employees get 20 days. [E25]")
    assert M.is_stale(Q, "Employees get 20 days. [E1]")
    assert not M.is_stale(Q, "Now 25 days (previously 20). [E1]")


def test_unit_words_required_for_numeric_alternatives():
    q = {"expected": [["1 hour", "one hour"]], "stale": []}
    assert M.is_correct(q, "Within one hour.")
    assert not M.is_correct(q, "Within 1 business day.")


def test_retrieval_metrics():
    ranked = [("v1.md", "20 days"), ("v2.md", "Employees get 25  days.")]
    assert M.recall_at_k(Q, ranked) == 1.0
    assert M.mrr_at_k(Q, ranked) == 0.5
    assert M.recall_at_k({"gold_evidence": []}, ranked) is None


def test_prf_and_stats():
    assert M.prf(3, 1, 1) == {"precision": 0.75, "recall": 0.75, "f1": 0.75, "tp": 3, "fp": 1, "fn": 1}
    lo, hi = M.bootstrap_ci([1, 0, 1, 1, 0, 1, 1, 1])
    assert 0 <= lo <= 0.75 <= hi <= 1
    assert M.mcnemar_exact([0, 0, 0, 1], [1, 1, 1, 1]) == {"b01": 3, "b10": 0, "p_value": 0.25}
    d = M.paired_bootstrap_diff([0, 0, 1, 1], [1, 1, 1, 1])
    assert d["diff"] == 0.5


def test_conflict_pair_matching_is_order_free_and_value_aware():
    gold = [{"a": "faq.md", "a_value": "3 years", "b": "policy.pdf", "b_value": "4 years", "kind": "outdated"},
            {"a": "x.md", "a_value": "1", "b": "y.md", "b_value": "2", "kind": "historical"}]  # fmt: skip
    found = [
        {"a": "policy.pdf", "a_value": "every 4 years", "b": "faq.md", "b_value": "3 years", "kind": "outdated"},
        {"a": "policy.pdf", "a_value": "every 4 years", "b": "faq.md", "b_value": "3 years", "kind": "outdated"},
        {"a": "x.md", "a_value": "1", "b": "y.md", "b_value": "2", "kind": "outdated"},
    ]
    s = M.conflict_scores(found, gold)
    assert (s["tp"], s["fp"], s["fn"]) == (1, 1, 0)
    assert s["kind_accuracy_on_matched_gold_pairs"] == 0.5
