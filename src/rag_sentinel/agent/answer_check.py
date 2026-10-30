"""Answer check: does the draft answer the question that was asked, and is every statement in it backed?

A 7B generator given related evidence often answers a neighbouring question ("who is the DPO?" answered
with what the DPO does). Retrieval relevance cannot see this, so a separate, focused LLM call compares the
question, the draft and the cited passages. Its verdict feeds two verification rules:

  R9  the draft does not provide what the question asks for   -> INSUFFICIENT_EVIDENCE
  R10 the draft states something the cited passages do not    -> NEEDS_REVIEW

Results are cached by model, prompt version, question, answer and cited text.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from pydantic import BaseModel, Field

from rag_sentinel.llm import LLM

PROMPT_VERSION = "answer-check-v1"

SYSTEM = "You check answers produced by a document question-answering system. Output JSON only."

TEMPLATE = """Question: {question}

Draft answer: {answer}

Cited evidence:
{evidence}

Decide two things.

1. answers_question: does the draft answer give the specific information the question asks for?
   It is false when the draft talks about a related topic but does not provide what was asked, for example:
   - the question asks WHO holds a role, and the draft only says what the role does;
   - the question asks about one kind of item (e.g. sick leave) and the draft gives another (e.g. annual leave);
   - the question asks WHETHER something is allowed or WHEN something happens, and the draft gives a
     different rule that does not settle it.
   A short or partial answer that does provide the asked information counts as true.

2. supported: is every factual statement in the draft stated in the cited evidence (paraphrase is fine)?

In `missing`, say briefly what the question asks for that the draft does not provide (empty if nothing)."""


class AnswerCheck(BaseModel):
    answers_question: bool
    supported: bool
    missing: str = Field(default="", max_length=400)


def make_answer_checker(llm: LLM, cache_get=None, cache_set=None) -> Callable[[str, str, list[dict]], AnswerCheck]:
    def check(question: str, answer: str, cited: list[dict]) -> AnswerCheck:
        evidence = "\n".join(f"[{e['label']}] {' '.join(e['text'].split())}" for e in cited)
        key = (
            "answer-check:"
            + hashlib.sha256(f"{llm.name}|{PROMPT_VERSION}|{question}|{answer}|{evidence}".encode()).hexdigest()
        )
        if cache_get and (hit := cache_get(key)) is not None:
            return AnswerCheck.model_validate(hit)
        res = llm.chat_json(SYSTEM, TEMPLATE.format(question=question, answer=answer, evidence=evidence), AnswerCheck)
        if cache_set:
            cache_set(key, res.model_dump())
        return res

    return check
