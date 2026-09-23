"""LangGraph workflow that turns a raw notification string into a validated
NotificationAnalysis object.

Graph:

START -> normalize -> understand_intent -> determine_attention ->
determine_urgency -> extract_action_deadline -> generate_explanation ->
validate_output -> END

The LLM is only called once per notification (in `understand_intent`) with a
prompt that already asks for the full structured shape; the remaining nodes
are kept as explicit, separate steps (per the required workflow) that inspect
and refine the parsed data rather than re-calling the model, so the graph is
cheap while still visibly following the required stages.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional, TypedDict

from langgraph.graph import StateGraph, START, END
from pydantic import ValidationError

from app.models.notification import Category, NotificationAnalysis, Urgency
from app.prompts.notification_prompt import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    raw_text: str
    normalized_text: str
    source: str
    llm_raw_output: str
    parsed: dict
    error: Optional[str]
    result: NotificationAnalysis


def _split_source(text: str) -> tuple[str, str]:
    """Best-effort split of 'Source: message' into (source, message)."""
    match = re.match(r"^\s*([A-Za-z0-9 _.'-]{1,30}):\s*(.+)$", text)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return "Unknown", text.strip()


def _fallback_analysis(source: str, text: str, reason: str) -> dict:
    """Deterministic, safe fallback used if the LLM is unavailable or returns
    something we cannot parse. Keeps the app usable without ever crashing."""
    return {
        "source": source,
        "category": Category.INFORMATIONAL.value,
        "urgency": Urgency.LOW.value,
        "requires_action": False,
        "action": None,
        "deadline": None,
        "summary": text[:200],
        "reason": reason,
    }


def build_graph(llm):
    """Build the LangGraph workflow. `llm` is a LangChain chat model instance,
    or None to force fallback (heuristic) mode."""

    def normalize(state: AgentState) -> AgentState:
        text = state["raw_text"].strip()
        source, message = _split_source(text)
        return {**state, "normalized_text": message, "source": source}

    def understand_intent(state: AgentState) -> AgentState:
        if llm is None:
            return {**state, "llm_raw_output": ""}
        prompt = USER_PROMPT_TEMPLATE.format(notification=state["raw_text"])
        try:
            response = llm.invoke(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
            )
            content = response.content if hasattr(response, "content") else str(response)
            return {**state, "llm_raw_output": content}
        except Exception as exc:  # noqa: BLE001 - agent must degrade gracefully
            logger.warning("LLM call failed: %s", exc)
            return {**state, "llm_raw_output": "", "error": str(exc)}

    def determine_attention(state: AgentState) -> AgentState:
        raw = state.get("llm_raw_output", "")
        if not raw:
            parsed = _fallback_analysis(
                state["source"], state["normalized_text"], "AI unavailable; defaulted to informational."
            )
            return {**state, "parsed": parsed}
        cleaned = raw.strip()
        cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except json.JSONDecodeError:
                    parsed = _fallback_analysis(
                        state["source"], state["normalized_text"], "Could not parse AI response."
                    )
            else:
                parsed = _fallback_analysis(
                    state["source"], state["normalized_text"], "Could not parse AI response."
                )
        return {**state, "parsed": parsed}

    def determine_urgency(state: AgentState) -> AgentState:
        parsed = dict(state["parsed"])
        if parsed.get("urgency") not in (u.value for u in Urgency):
            parsed["urgency"] = Urgency.LOW.value
        if parsed.get("category") not in (c.value for c in Category):
            parsed["category"] = Category.INFORMATIONAL.value
        return {**state, "parsed": parsed}

    def extract_action_deadline(state: AgentState) -> AgentState:
        parsed = dict(state["parsed"])
        parsed.setdefault("action", None)
        parsed.setdefault("deadline", None)
        parsed["requires_action"] = bool(parsed.get("requires_action", False))
        return {**state, "parsed": parsed}

    def generate_explanation(state: AgentState) -> AgentState:
        parsed = dict(state["parsed"])
        parsed.setdefault("summary", state["normalized_text"][:200])
        parsed.setdefault("reason", "No additional reasoning provided.")
        parsed["source"] = parsed.get("source") or state["source"]
        parsed["original_text"] = state["raw_text"]
        return {**state, "parsed": parsed}

    def validate_output(state: AgentState) -> AgentState:
        try:
            result = NotificationAnalysis(**state["parsed"])
        except ValidationError as exc:
            logger.warning("Validation failed, using safe fallback: %s", exc)
            fallback = _fallback_analysis(
                state["source"], state["normalized_text"], "AI output failed validation."
            )
            fallback["original_text"] = state["raw_text"]
            result = NotificationAnalysis(**fallback)
        return {**state, "result": result}

    graph = StateGraph(AgentState)
    graph.add_node("normalize", normalize)
    graph.add_node("understand_intent", understand_intent)
    graph.add_node("determine_attention", determine_attention)
    graph.add_node("determine_urgency", determine_urgency)
    graph.add_node("extract_action_deadline", extract_action_deadline)
    graph.add_node("generate_explanation", generate_explanation)
    graph.add_node("validate_output", validate_output)

    graph.add_edge(START, "normalize")
    graph.add_edge("normalize", "understand_intent")
    graph.add_edge("understand_intent", "determine_attention")
    graph.add_edge("determine_attention", "determine_urgency")
    graph.add_edge("determine_urgency", "extract_action_deadline")
    graph.add_edge("extract_action_deadline", "generate_explanation")
    graph.add_edge("generate_explanation", "validate_output")
    graph.add_edge("validate_output", END)

    return graph.compile()
