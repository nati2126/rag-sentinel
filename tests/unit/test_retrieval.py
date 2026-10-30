from rag_sentinel.retrieval.bm25 import BM25Index, tokenize
from rag_sentinel.retrieval.fusion import reciprocal_rank_fusion
from rag_sentinel.retrieval.retriever import RetrievalConfig


def test_rrf_rewards_agreement():
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "c", "a"]], k=60)
    assert fused[0][0] == "b"
    assert abs(fused[0][1] - (1 / 62 + 1 / 61)) < 1e-12


def test_rrf_single_list_preserves_order():
    assert [i for i, _ in reciprocal_rank_fusion([["x", "y", "z"]])] == ["x", "y", "z"]


def test_bm25_keyword_match_and_tokenizer_keeps_versions():
    assert "1.2" in tokenize("Use TLS 1.2 or later")
    idx = BM25Index([("1", "TLS 1.2 is required"), ("2", "Annual leave is 25 days"), ("3", "Meal per diem")])
    assert idx.search("annual leave days", 2)[0][0] == "2"
    assert idx.search("zzzz", 5) == []


def test_hybrid_and_rerank_pipeline_keeps_scores(kb, leave_corpus):
    kb.ingest_directory(leave_corpus)
    dense = kb.retriever.retrieve("annual leave days", RetrievalConfig(mode="dense", rerank=False, final_k=5))
    hybrid = kb.retriever.retrieve("annual leave days", RetrievalConfig(mode="hybrid", rerank=False, final_k=5))
    reranked = kb.retriever.retrieve("annual leave days", RetrievalConfig(mode="hybrid", rerank=True, final_k=3))
    assert dense and all(h.dense_score is not None for h in dense)
    assert all(h.fused_score is not None for h in hybrid)
    assert any(h.bm25_rank is not None for h in hybrid)
    assert len(reranked) == 3 and all(h.rerank_score is not None for h in reranked)
    assert [h.rank for h in reranked] == [1, 2, 3]
    assert reranked[0].relevance >= reranked[-1].relevance
    assert all(0.0 <= h.relevance <= 1.0 for h in dense + hybrid + reranked)
