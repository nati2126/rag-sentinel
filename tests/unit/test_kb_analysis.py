from rag_sentinel.conflicts.detect import DIFFERENT_CONTEXT, HISTORICAL, OUTDATED


def test_ingestion_extracts_claims_and_detects_conflicts(kb, leave_corpus, tmp_path):
    kb.ingest_directory(leave_corpus)
    claims = kb.claims()
    assert len(claims) == 4
    assert all(c.source_quote in kb.lookup_chunks([c.chunk_id])[c.chunk_id][1] for c in claims)
    by_kind = {}
    for c in kb.conflicts():
        by_kind.setdefault(c.kind, []).append(c)
    assert len(by_kind[HISTORICAL]) == 1
    assert len(by_kind[OUTDATED]) == 1 and by_kind[OUTDATED][0].confirmed
    assert len(by_kind[DIFFERENT_CONTEXT]) == 3
    stats = kb.stats()
    assert stats["documents"] == 4 and stats["outdated_references"] == 1 and stats["superseded"] == 1


def test_affected_documents_after_policy_change(kb, leave_corpus):
    kb.ingest_directory(leave_corpus)
    v2 = next(d for d in kb.list_documents() if d.filename == "leave_policy_v2.md")
    rep = kb.affected_documents(v2.id)
    assert [(c.old_value, c.new_value) for c in rep.changes] == [("20 days", "25 days")]
    handbook = next(d for d in kb.list_documents() if d.filename == "employee_handbook.md")
    confirmed = [r for r in rep.references if r.confirmed]
    assert [r.doc_id for r in confirmed] == [handbook.id]


def test_resolution_is_kept_across_reanalysis(kb, leave_corpus):
    kb.ingest_directory(leave_corpus)
    c = next(c for c in kb.conflicts() if c.kind == OUTDATED)
    kb.resolve_conflict(c.id, "resolved", c.preferred_doc_id, "Handbook update scheduled")
    kb.refresh_analysis()
    again = next(x for x in kb.conflicts() if x.id == c.id)
    assert again.status == "resolved" and again.resolution_note == "Handbook update scheduled"
