"""MCP server exposing RAG Sentinel's read-only verification tools.

Run over stdio (what desktop and IDE MCP clients launch):
    python -m rag_sentinel.mcp --data-dir data/demo
Run over HTTP (Streamable HTTP at http://127.0.0.1:8765/mcp):
    python -m rag_sentinel.mcp --data-dir data/demo --transport http --port 8765

The embedded vector store locks its folder, so do not point the API and this server at the same data
directory at the same time.
"""

from __future__ import annotations

import argparse
import importlib.metadata
from collections.abc import Callable
from typing import Annotated, Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import Field

from rag_sentinel.llm import LLMError
from rag_sentinel.mcp.tools import SentinelTools, ToolInputError

INSTRUCTIONS = """\
RAG Sentinel answers questions from a versioned document collection and checks every answer against the
evidence. Answers carry a status:
- VERIFIED: supported by cited sources that are approved and in force at the as-of date.
- NEEDS_REVIEW: an answer exists but a rule found a problem (outdated source, unresolved contradiction,
  values not in the cited text). Treat it as unconfirmed and report the reasons.
- INSUFFICIENT_EVIDENCE: no reliable answer. Do not guess one.
Documents have a standing at the as-of date: in_force, superseded, not_yet_effective, unapproved, withdrawn.
Dates are YYYY-MM-DD. Omit as_of to use the server's reference date. Use filenames from list_documents
when a tool asks for a document."""

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

try:
    VERSION = importlib.metadata.version("rag-sentinel")
except importlib.metadata.PackageNotFoundError:  # running from a source tree without installing
    VERSION = "0.0.0"


def _call(fn: Callable[..., dict[str, Any]], *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Expected failures become tool errors with a readable message (others are reported as crashes)."""
    try:
        return fn(*args, **kwargs)
    except ToolInputError as exc:
        raise ToolError(str(exc)) from exc
    except LLMError as exc:
        raise ToolError(f"The local model server is unavailable: {exc}") from exc


AsOf = Annotated[
    str | None,
    Field(description="Reference date YYYY-MM-DD for 'in force' decisions; omit for the server default."),
]


def build_server(tools: SentinelTools) -> MCPServer:
    server = MCPServer(name="rag-sentinel", title="RAG Sentinel", version=VERSION, instructions=INSTRUCTIONS)

    @server.tool(annotations=READ_ONLY)
    def search_documents(
        query: Annotated[str, Field(min_length=2, max_length=500, description="What to look for.")],
        as_of: AsOf = None,
        top_k: Annotated[int, Field(ge=1, le=10, description="Number of passages (max 10).")] = 5,
    ) -> dict[str, Any]:
        """Find passages relevant to a query, ranked by relevance, authority and whether the source is in
        force at the as-of date. Each result shows its document, version and standing. No answer is
        generated; use ask_verified for a checked answer."""
        return _call(tools.search_documents, query, as_of, top_k)

    @server.tool(annotations=READ_ONLY)
    def ask_verified(
        question: Annotated[str, Field(min_length=3, max_length=1000, description="A question about the documents.")],
        as_of: AsOf = None,
    ) -> dict[str, Any]:
        """Answer a question from the documents and verify the answer. Returns the status (VERIFIED,
        NEEDS_REVIEW or INSUFFICIENT_EVIDENCE), the answer, cited sources with their standing, and the
        reasons for the status. Questions about a past date ("in March 2025") are answered for that date."""
        return _call(tools.ask_verified, question, as_of)

    @server.tool(annotations=READ_ONLY)
    def check_statement(
        statement: Annotated[str, Field(min_length=3, max_length=1000, description="A factual statement to check.")],
        as_of: AsOf = None,
    ) -> dict[str, Any]:
        """Check a statement against the documents. For every number in the statement it lists the
        sources whose sentence states it (with standing and the sentence) and gives a finding: current
        (an in-force source states it), outdated (only superseded sources, or in-force sources flagged as
        the outdated side of a conflict or as still using a value a newer version changed; the flag names
        the preferred document and its value), disputed (only in an unresolved contradiction) or not_found.
        It also returns the verified answer with the correct value."""
        return _call(tools.check_statement, statement, as_of)

    @server.tool(annotations=READ_ONLY)
    def list_documents(
        as_of: AsOf = None,
        family: Annotated[str | None, Field(description="Only documents whose family contains this text.")] = None,
    ) -> dict[str, Any]:
        """List the documents with their version, effective date, authority (1-5), approval status and
        standing at the as-of date (in_force, superseded, ...), including what superseded them."""
        return _call(tools.list_documents, as_of, family)

    @server.tool(annotations=READ_ONLY)
    def get_document_versions(
        document: Annotated[str, Field(description="Filename, document id, or a unique part of the filename.")],
        as_of: AsOf = None,
    ) -> dict[str, Any]:
        """Show every version of a document with its standing, the values this version changed compared
        with the previous one, and other documents that still state the old values."""
        return _call(tools.get_document_versions, document, as_of)

    @server.tool(annotations=READ_ONLY)
    def list_conflicts(
        kind: Annotated[
            str | None,
            Field(
                description="contradiction, outdated, historical, pending_change, different_context, "
                "complementary or insufficient_evidence. Omit for contradiction + outdated."
            ),
        ] = None,  # fmt: skip
        status: Annotated[str | None, Field(description="open, resolved or dismissed; omit for all.")] = "open",
        document: Annotated[str | None, Field(description="Only conflicts involving this document.")] = None,
        limit: Annotated[int, Field(ge=1, le=100)] = 20,
    ) -> dict[str, Any]:
        """List detected conflicts between documents: the attribute, both values and documents, which
        document is preferred, and why. By default only open contradictions and outdated statements."""
        return _call(tools.list_conflicts, kind, status, document, actionable_only=True, limit=limit)

    return server


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m rag_sentinel.mcp", description="RAG Sentinel MCP server")
    ap.add_argument("--data-dir", help="knowledge base folder (default: SENTINEL_DATA_DIR or data/kb)")
    ap.add_argument("--transport", choices=["stdio", "http"], default="stdio")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)

    from rag_sentinel.config import Settings
    from rag_sentinel.kb import KnowledgeBase
    from rag_sentinel.log import setup_logging

    settings = Settings(**({"data_dir": args.data_dir} if args.data_dir else {}))
    tools = SentinelTools(lambda: KnowledgeBase.from_settings(settings))
    server = build_server(tools)
    setup_logging(settings.log_level)  # JSON logs on stderr; stdout belongs to the stdio transport
    try:
        if args.transport == "stdio":
            server.run("stdio")
        else:
            server.run("streamable-http", host=args.host, port=args.port)
    finally:
        tools.close()
