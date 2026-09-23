"""Pydantic models for the Notification Translator agent."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    ACTION_REQUIRED = "ACTION_REQUIRED"
    IMPORTANT = "IMPORTANT"
    INFORMATIONAL = "INFORMATIONAL"
    LOW_PRIORITY = "LOW_PRIORITY"
    IGNORE = "IGNORE"


class Urgency(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AnalyzeRequest(BaseModel):
    """Incoming request body for POST /api/analyze."""

    notifications: list[str] = Field(
        default_factory=list,
        description="Raw notification lines pasted by the user.",
    )


class NotificationAnalysis(BaseModel):
    """Structured, validated output the agent must produce for one notification."""

    source: str = Field(description="Application/source the notification came from.")
    original_text: str = Field(description="The raw notification text as given by the user.")
    category: Category
    urgency: Urgency
    requires_action: bool
    action: Optional[str] = Field(
        default=None, description="Recommended action the user should take, if any."
    )
    deadline: Optional[str] = Field(
        default=None, description="Deadline mentioned in the notification, if any."
    )
    summary: str = Field(description="Concise, human-readable summary of the notification.")
    reason: str = Field(description="Why this notification was classified this way.")


class AnalyzeResponse(BaseModel):
    """Response body for POST /api/analyze."""

    total: int
    results: list[NotificationAnalysis]


class HealthResponse(BaseModel):
    status: str = "ok"
