"""Evidence-gated answer generation: the LLM sees only labelled evidence and must cite labels."""

from __future__ import annotations

from pydantic import BaseModel, Field

SYSTEM = (
    "You answer questions about an organisation's documents strictly from the evidence provided. "
    "You never use outside knowledge and never invent sources. Output JSON only."
)


class GeneratedAnswer(BaseModel):
    answer: str = Field(max_length=3000)
    citations: list[str] = Field(default_factory=list, max_length=12)
    cannot_answer: bool
    reason: str = Field(default="", max_length=1000)


def evidence_block(label: str, ev: dict, include_metadata: bool) -> str:
    head = f"[{label}] {ev['title']}"
    if ev.get("version"):
        head += f" (version {ev['version']})"
    head += f" - {ev['filename']}" + (f", page {ev['page']}" if ev.get("page") else "")
    lines = [head]
    if include_metadata:
        meta = [
            f"effective {ev.get('effective_date') or 'unknown'}",
            f"approval: {ev.get('approval_status') or 'unknown'}",
            f"authority {ev.get('authority_level') or '?'}/5",
            f"status at as-of date: {ev.get('standing_status', 'unknown').replace('_', ' ')}",
        ]
        lines.append("    " + " | ".join(meta))
    lines.append('    """' + ev["text"].strip() + '"""')
    return "\n".join(lines)


def build_prompt(
    question: str,
    evidence: list[dict],
    include_metadata: bool,
    as_of: str,
    mode: str,
    conflict_notes: list[str] | None = None,
) -> str:
    blocks = "\n\n".join(evidence_block(e["label"], e, include_metadata) for e in evidence)
    rules = [
        "Answer using ONLY the evidence above.",
        "After every sentence, cite the evidence label(s) that support it, e.g. [E1] or [E1][E3].",
        "List every label you cited in `citations`.",
        "If the evidence does not contain the answer, set cannot_answer to true, leave citations empty, "
        "and explain what is missing in `reason`.",
        "Keep the answer short: 1 to 3 sentences.",
    ]
    if include_metadata:
        if mode == "current":
            rules.insert(1, f"Answer for what applies on {as_of}. Prefer evidence whose status is 'in force'. "
                            "Do not present superseded, draft or not-yet-effective values as current; you may "
                            "mention them as history or as an upcoming change.")  # fmt: skip
        else:
            rules.insert(1, f"The question is about the past: answer for what was in force on {as_of}, "
                            "using evidence whose status is 'in force' at that date.")  # fmt: skip
    notes = ""
    if conflict_notes:
        notes = "\nKnown conflicts between documents (from automated analysis):\n" + "\n".join(
            f"- {n}" for n in conflict_notes
        )
    rule_text = "\n".join(f"{i}. {r}" for i, r in enumerate(rules, 1))
    return f"Evidence:\n\n{blocks}\n{notes}\n\nQuestion: {question}\n\nRules:\n{rule_text}"
