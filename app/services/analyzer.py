"""Service layer: wires up the LLM (if configured) and runs the agent graph
over a batch of notifications."""
from __future__ import annotations

import logging
import os

from app.agents.notification_agent import build_graph
from app.models.notification import NotificationAnalysis

logger = logging.getLogger(__name__)

_GEMINI_MODEL = "gemini-2.0-flash"


def _make_llm():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set; running in fallback (no-AI) mode.")
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=_GEMINI_MODEL,
            google_api_key=api_key,
            temperature=0.2,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not initialize Gemini client: %s", exc)
        return None


class NotificationAnalyzer:
    """Thin wrapper that owns the compiled LangGraph app."""

    def __init__(self) -> None:
        self._llm = _make_llm()
        self._app = build_graph(self._llm)

    def analyze_one(self, raw_text: str) -> NotificationAnalysis:
        final_state = self._app.invoke({"raw_text": raw_text})
        return final_state["result"]

    def analyze_many(self, notifications: list[str]) -> list[NotificationAnalysis]:
        results: list[NotificationAnalysis] = []
        for line in notifications:
            line = line.strip()
            if not line:
                continue
            results.append(self.analyze_one(line))
        return results


# Singleton instance reused across requests (stateless w.r.t. notification data).
analyzer = NotificationAnalyzer()
