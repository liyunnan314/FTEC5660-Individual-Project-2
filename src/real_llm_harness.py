"""Instrumentation for the real-LLM follow-up experiment."""

from __future__ import annotations

import time

from langchain_core.callbacks import BaseCallbackHandler


def _usage_from_response(response) -> dict:
    """Token counts from whichever field the provider populated."""
    out = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    llm_output = getattr(response, "llm_output", None) or {}
    usage = llm_output.get("token_usage") or llm_output.get("usage") or {}
    if usage:
        out["input_tokens"] = int(usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0)
        out["output_tokens"] = int(usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0)
        out["total_tokens"] = int(
            usage.get("total_tokens") or out["input_tokens"] + out["output_tokens"]
        )
        return out

    # Newer LangChain exposes usage_metadata on the generated AIMessage.
    for gen_list in getattr(response, "generations", []) or []:
        for gen in gen_list:
            meta = getattr(getattr(gen, "message", None), "usage_metadata", None) or {}
            if meta:
                out["input_tokens"] += int(meta.get("input_tokens", 0) or 0)
                out["output_tokens"] += int(meta.get("output_tokens", 0) or 0)
                out["total_tokens"] += int(meta.get("total_tokens", 0) or 0)
    return out


class UsageHandler(BaseCallbackHandler):
    """Accumulates one pipeline run's LLM usage, cost proxies and errors."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.llm_calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_tokens = 0
        self.prompt_chars = 0
        self.llm_seconds = 0.0
        self.errors: list[str] = []
        self._started: dict = {}

    def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
        self.llm_calls += 1
        self._started[run_id] = time.perf_counter()
        try:
            self.prompt_chars += sum(len(p) for p in prompts if isinstance(p, str))
        except TypeError:
            pass

    def on_llm_end(self, response, *, run_id, **kwargs):
        usage = _usage_from_response(response)
        self.input_tokens += usage["input_tokens"]
        self.output_tokens += usage["output_tokens"]
        self.total_tokens += usage["total_tokens"]
        started = self._started.pop(run_id, None)
        if started is not None:
            self.llm_seconds += time.perf_counter() - started

    def on_llm_error(self, error, *, run_id, **kwargs):
        self.errors.append(str(error)[:300])
        self._started.pop(run_id, None)

    def snapshot(self) -> dict:
        return {
            "llm_calls": self.llm_calls,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "prompt_chars": self.prompt_chars,
            "llm_seconds": round(self.llm_seconds, 3),
            "llm_errors": len(self.errors),
            "error_samples": self.errors[:3],
        }
