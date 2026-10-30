"""Answer check: does the draft answer the question that was asked, and is every statement in it backed?

A 7B generator given related evidence often answers a neighbouring question ("who is the DPO?" answered
with what the DPO does). Retrieval relevance cannot see this, so a separate, focused LLM call compares the
question, the draft and the cited passages. Its verdict feeds two verification rules:

  R9  the draft does not provide what the question asks for   -> INSUFFICIENT_EVIDENCE
  R10 the draft states something the cited passages do not    -> NEEDS_REVIEW

A negative verdict counts only when an independent second sample agrees. Results are cached by model,
prompt version, question, answer and cited text.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from pydantic import BaseModel, Field

from rag_sentinel.llm import LLM

PROMPT_VERSION = "answer-check-v3"

SYSTEM = "You check answers produced by a document question-answering system. Output JSON only."

TEMPLATE = """Question: {question}

Draft answer: {answer}

Cited evidence:
{evidence}

Fill the fields in order.

1. asked_for: in a few words, the information the question requests and the specific thing it is about.
2. draft_provides: in a few words, what the draft states about that specific thing, or "nothing".
3. answers_question: true if the draft states the requested information about that specific thing. The
   draft does not need to repeat the question's wording, dates or conditions, and an answer such as
   "only when X happens" or "no" counts as an answer.
   False when the draft gives a different kind of information (a description instead of a name, a general
   rule instead of a requested product), is about a different item than the one asked about, or answers a
   question about one specific situation with a general rule that never mentions that situation.
4. supported: true if every fact in the draft appears in the cited evidence (paraphrase is fine)."""


class AnswerCheck(BaseModel):
    asked_for: str = Field(max_length=200)  # required: forces the reasoning to come before the verdict
    draft_provides: str = Field(max_length=300)
    answers_question: bool
    supported: bool

    @property
    def missing(self) -> str:
        return "" if self.answers_question else f"{self.asked_for} (the draft gives {self.draft_provides})"


def make_answer_checker(llm: LLM, cache_get=None, cache_set=None) -> Callable[[str, str, list[dict]], AnswerCheck]:
    def check(question: str, answer: str, cited: list[dict]) -> AnswerCheck:
        evidence = "\n".join(f"[{e['label']}] {' '.join(e['text'].split())}" for e in cited)
        key = (
            "answer-check:"
            + hashlib.sha256(f"{llm.name}|{PROMPT_VERSION}|{question}|{answer}|{evidence}".encode()).hexdigest()
        )
        if cache_get and (hit := cache_get(key)) is not None:
            return AnswerCheck.model_validate(hit)
        prompt = TEMPLATE.format(question=question, answer=answer, evidence=evidence)
        res = llm.chat_json(SYSTEM, prompt, AnswerCheck)
        if not (res.answers_question and res.supported):
            # a negative verdict must be confirmed by an independent sample; one 'no' from a 7B model is noisy
            second = llm.chat_json(SYSTEM, prompt, AnswerCheck, sample=1)
            res = AnswerCheck(
                asked_for=res.asked_for or second.asked_for,
                draft_provides=res.draft_provides or second.draft_provides,
                answers_question=res.answers_question or second.answers_question,
                supported=res.supported or second.supported,
            )
        if cache_set:
            cache_set(key, res.model_dump())
        return res

    return check
