"""A deterministic, seeded stand-in for the upstream LLM.

Edge Case A of the assignment permits swapping the underlying model as a
controlled variable. No hosted LLM API key is available in this environment, so
instead of DeepSeek we inject an in-process scripted chat model through the
*upstream repository's own* test seam (``trading_graph.create_tier_client``).

Compared with the upstream ``tests/test_graph_end_to_end.py::ScriptedModel``
fixture, this version adds:

* a seed that controls the final portfolio rating, so repeated trials are
  reproducible yet not byte-identical (a controlled stand-in for sampling
  variation, which the upstream README explicitly says exists);
* a call log recording node name, prompt size, tool calls, thread and timing
  for every LLM invocation. Those records are the raw measurements.

Nothing here edits the upstream source. Prompts, tool schemas, graph topology
and report parsing all come from the upstream repository unchanged.
"""

from __future__ import annotations

import random
import threading
import time
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from pydantic import Field

from tradingagents.agents import schemas

# Analysis dates are pinned to the past; see README "Setup notes".
TRADE_DATE = "2026-01-09"

# Same argument shim as the upstream end-to-end fixture: every bound tool is
# called exactly once with only the arguments its schema declares.
ARGS = {
    "symbol": "NVDA", "ticker": "NVDA", "curr_date": TRADE_DATE,
    "start_date": "2026-01-02", "end_date": TRADE_DATE,
    "indicator": "rsi", "topic": "Fed rate cut", "freq": "quarterly",
}

# The five legal ratings from tradingagents.agents.schemas.PortfolioRating.
RATINGS = ("Buy", "Overweight", "Hold", "Underweight", "Sell")
_DIRECTION = {"Buy": "BUY", "Overweight": "BUY", "Hold": "HOLD",
              "Underweight": "SELL", "Sell": "SELL"}

# Must contain the two labelled lines the upstream parsers look for.
TEXT_TEMPLATE = (
    "Report.\n\n"
    "The committee reviewed the analyst reports and the debate record.\n"
    "**Rating**: {rating}\n\n"
    "FINAL TRANSACTION PROPOSAL: **{action}**"
)


def _new_stats() -> dict[str, Any]:
    """One mutable dict shared across every ``bind_tools`` / ``model_copy``."""
    return {"calls": [], "tool_calls": [], "threads": set(), "prompt_chars": 0,
            "tool_invocations": 0}


class SeedScriptedModel(BaseChatModel):
    """Calls every bound tool once, then answers with a seeded final rating."""

    seed: int = 0
    structured: bool = False
    tools: tuple = ()
    stats: dict = Field(default_factory=_new_stats)

    @property
    def _llm_type(self) -> str:
        return "seed-scripted-stub-v1"

    @property
    def rating(self) -> str:
        """The final rating for this trial: fixed by the seed, not by the graph."""
        return RATINGS[self.seed % len(RATINGS)]

    @property
    def action(self) -> str:
        return _DIRECTION[self.rating]

    @property
    def text(self) -> str:
        return TEXT_TEMPLATE.format(rating=self.rating, action=self.action)

    def bind_tools(self, tools, **kwargs):
        return self.model_copy(update={"tools": tuple(tools)})

    def with_structured_output(self, schema, **kwargs):
        if not self.structured:
            raise NotImplementedError
        rating = self.rating

        def produce(_):
            self._count("structured-output", 0, False)
            if schema is schemas.ResearchPlan:
                return schemas.ResearchPlan(
                    recommendation=schemas.PortfolioRating(rating),
                    rationale="r", strategic_actions="a")
            if schema is schemas.TraderProposal:
                return schemas.TraderProposal(
                    action=schemas.TraderAction(self.action.title()), reasoning="r")
            if schema is schemas.PortfolioDecision:
                return schemas.PortfolioDecision(
                    rating=schemas.PortfolioRating(rating),
                    executive_summary="s", investment_thesis="s")
            if schema is schemas.SentimentReport:
                return schemas.SentimentReport(
                    overall_band=schemas.SentimentBand.NEUTRAL,
                    overall_score=5.0, confidence="low", narrative="n")
            raise KeyError(f"unexpected schema: {schema}")

        return RunnableLambda(produce)

    def _count(self, node, prompt_chars: int, had_tools: bool) -> None:
        now = time.perf_counter()
        self.stats["calls"].append({
            "i": len(self.stats["calls"]),
            "node": node,
            "prompt_chars": prompt_chars,
            "had_tools": had_tools,
            "thread": threading.current_thread().name,
            "ts": now,
        })
        self.stats["prompt_chars"] += prompt_chars
        self.stats["threads"].add(threading.current_thread().name)
        if had_tools:
            self.stats["tool_calls"].append(node)
        # A tiny, deterministic amount of work per call. We deliberately do NOT
        # sleep: absolute latency numbers would then be an artefact of the stub.
        # Wall-clock latency is still reported, with that caveat in the report.
        rng = random.Random(self.seed * 7919 + len(self.stats["calls"]))
        _ = rng.random()

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        node = None
        if run_manager is not None:
            node = (run_manager.metadata or {}).get("langgraph_node")
        prompt_chars = sum(len(str(getattr(m, "content", ""))) for m in messages)
        had_tools = bool(self.tools) and not isinstance(messages[-1], ToolMessage)
        self._count(node or "unknown", prompt_chars, had_tools)

        if had_tools:
            calls = [
                {"name": t.name, "id": f"call_{i}",
                 "args": {k: v for k, v in ARGS.items()
                          if k in t.tool_call_schema.model_json_schema()["properties"]}}
                for i, t in enumerate(self.tools)
            ]
            self.stats["tool_invocations"] += len(calls)
            message = AIMessage(content="", tool_calls=calls)
        else:
            message = AIMessage(content=self.text)
        return ChatResult(generations=[ChatGeneration(message=message)])


class _StubClient:
    """Duck-typed LLM client, matching what create_tier_client must return."""

    def __init__(self, model: SeedScriptedModel):
        self.model = model

    def get_llm(self):
        return self.model
