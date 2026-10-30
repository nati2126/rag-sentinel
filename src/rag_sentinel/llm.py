"""Ollama client: schema-constrained JSON chat + embeddings.

Model output is always validated with Pydantic. Invalid output is retried once with the validation error,
then raised as LLMOutputError. It is never silently accepted.
"""

from __future__ import annotations

import json
import time
from typing import Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from rag_sentinel.log import get_logger

log = get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The LLM server is unreachable or returned an HTTP error."""


class LLMOutputError(LLMError):
    """The model returned output that does not match the requested schema."""


class LLM(Protocol):
    name: str

    def chat_json(self, system: str, user: str, schema: type[T]) -> T: ...


class OllamaLLM:
    def __init__(
        self,
        base_url: str,
        model: str,
        num_ctx: int = 8192,
        temperature: float = 0.0,
        timeout: float = 300,
        num_predict: int = 2048,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.name = model
        # num_predict stops runaway generations (a 7B model occasionally loops on a token)
        self.options = {"temperature": temperature, "num_ctx": num_ctx, "seed": 7, "num_predict": num_predict}
        self.client = httpx.Client(timeout=timeout)

    def _chat(self, messages: list[dict], schema: dict, options: dict | None = None) -> str:
        try:
            r = self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "format": schema,
                    "stream": False,
                    "options": options or self.options,
                },
            )
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMError(f"Ollama chat failed ({self.base_url}, model {self.model}): {exc}") from exc
        return r.json()["message"]["content"]

    def chat_json(self, system: str, user: str, schema: type[T]) -> T:
        # The retry is a fresh request with the validation error, another seed and a little temperature: at
        # temperature 0 the same prompt reproduces the same output, and echoing a degenerate output (a token
        # loop) back to the model tends to reinforce it.
        json_schema = schema.model_json_schema()
        last_error = ""
        for attempt in range(2):
            t0 = time.perf_counter()
            prompt, options = user, self.options
            if attempt:
                prompt = f"{user}\n\nA previous answer was invalid ({last_error[:300]}). Return valid JSON only."
                options = {**self.options, "seed": self.options["seed"] + 1, "temperature": 0.3}
            messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
            raw = self._chat(messages, json_schema, options)
            try:
                result = schema.model_validate_json(raw)
                log.debug("llm call", extra={"schema": schema.__name__, "ms": round((time.perf_counter() - t0) * 1000)})
                return result
            except ValidationError as exc:
                last_error = str(exc)
                log.warning(
                    "invalid llm output",
                    extra={"schema": schema.__name__, "attempt": attempt, "error": last_error[:300]},
                )
        raise LLMOutputError(f"{schema.__name__}: model output failed validation twice: {last_error[:500]}")

    def ping(self) -> bool:
        try:
            r = self.client.get(f"{self.base_url}/api/tags", timeout=5)
            names = {m["name"] for m in r.json().get("models", [])}
            return self.model in names
        except (httpx.HTTPError, json.JSONDecodeError, KeyError):
            return False
