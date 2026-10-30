"""SQLite persistence (SQLModel). Holds documents, versions, chunks, claims, conflicts and history."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, Column, event
from sqlmodel import Field, Session, SQLModel, create_engine, select


def utcnow() -> datetime:
    return datetime.now(UTC)


class Document(SQLModel, table=True):
    """One stored file version. Versions are never overwritten; a changed file becomes a new row."""

    id: str = Field(primary_key=True)
    family_id: str = Field(index=True)
    filename: str = Field(index=True)
    title: str | None = None
    content_type: str
    sha256: str = Field(index=True)
    version_label: str | None = None
    version_number: int = 1
    created_date: date | None = None
    publication_date: date | None = None
    effective_date: date | None = None
    last_modified: date | None = None
    source_org: str | None = None
    authority_level: int | None = None  # 1 (informal note) .. 5 (official policy)
    approval_status: str = "unknown"  # approved | pending | draft | withdrawn | unknown
    supersedes_ref: str | None = None  # raw reference as provided (filename or document id)
    supersedes_id: str | None = Field(default=None, index=True)
    stored_path: str
    page_count: int | None = None
    char_count: int = 0
    metadata_sources: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    suggested_metadata: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    extraction_warnings: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    is_deleted: bool = False
    ingested_at: datetime = Field(default_factory=utcnow)


class Chunk(SQLModel, table=True):
    id: str = Field(primary_key=True)  # stable: hash(document sha256, page, char span)
    doc_id: str = Field(index=True, foreign_key="document.id")
    seq: int
    page: int | None = None
    start_char: int
    end_char: int
    text: str


class Claim(SQLModel, table=True):
    id: str = Field(primary_key=True)
    doc_id: str = Field(index=True)
    chunk_id: str = Field(index=True)
    subject: str
    predicate: str
    predicate_key: str = Field(default="", index=True)  # canonical predicate after clustering
    value: str
    value_kind: str  # quantity | money | percent | date | modal | text
    value_num: float | None = None
    value_unit: str | None = None
    value_norm: str  # canonical comparable string
    qualifier: str | None = None
    effective_date: date | None = None  # only if stated in the passage itself
    source_quote: str
    confidence: float = 0.5
    extractor: str = ""


class Conflict(SQLModel, table=True):
    id: str = Field(primary_key=True)
    predicate_key: str = Field(index=True)
    claim_a_id: str = Field(index=True)
    claim_b_id: str = Field(index=True)
    doc_a_id: str = Field(index=True)
    doc_b_id: str = Field(index=True)
    kind: str  # contradiction | outdated | historical | different_context | complementary | insufficient_evidence
    confirmed: bool = False
    preferred_doc_id: str | None = None
    margin: float | None = None
    explanation: str = ""
    detected_by: str = "rule"  # rule | llm
    status: str = "open"  # open | resolved | dismissed
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    detected_at: datetime = Field(default_factory=utcnow)


class DocumentEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    doc_id: str = Field(index=True)
    family_id: str = Field(index=True)
    event: str  # ingested | new_version | duplicate | superseded | metadata_updated | deleted | reindexed
    detail: str = ""
    at: datetime = Field(default_factory=utcnow)


class QueryRun(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    question: str
    pipeline: str
    status: str
    answer: str = ""
    latency_ms: float = 0.0
    result: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class CacheEntry(SQLModel, table=True):
    """Cache for expensive, deterministic LLM calls (claim extraction, pairwise judgements)."""

    key: str = Field(primary_key=True)
    value: Any = Field(sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow)


class Database:
    def __init__(self, path: Path | str):
        url = "sqlite://" if str(path) == ":memory:" else f"sqlite:///{Path(path).as_posix()}"
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        kwargs: dict[str, Any] = {"connect_args": {"check_same_thread": False}}
        if str(path) == ":memory:":
            from sqlalchemy.pool import StaticPool

            kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, **kwargs)

        @event.listens_for(self.engine, "connect")
        def _pragmas(dbapi_conn, _):  # noqa: ANN001
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

        SQLModel.metadata.create_all(self.engine)

    @contextmanager
    def session(self) -> Iterator[Session]:
        with Session(self.engine, expire_on_commit=False) as s:
            yield s

    # --- small cache helpers -------------------------------------------------
    def cache_get(self, key: str) -> Any | None:
        with self.session() as s:
            row = s.get(CacheEntry, key)
            return None if row is None else row.value

    def cache_set(self, key: str, value: Any) -> None:
        with self.session() as s:
            s.merge(CacheEntry(key=key, value=value))
            s.commit()

    def active_documents(self, s: Session) -> list[Document]:
        return list(s.exec(select(Document).where(Document.is_deleted == False)).all())  # noqa: E712
