"""Pydantic models for request/response validation."""
from datetime import datetime
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """POST /api/generate request body."""
    user_input: str = Field(..., min_length=1, max_length=5000, description="User's natural language description")
    duration: int = Field(..., ge=30, le=120, description="Desired audio duration in seconds")


class GenerateResponse(BaseModel):
    """Response after successful generation."""
    id: int
    user_input: str
    prompt_enhanced: str | None
    duration: int
    filename: str
    enhanced: bool
    created_at: str


class HistoryItem(BaseModel):
    """Single item in history list."""
    id: int
    created_at: str
    user_input: str
    duration: int
    filename: str
    enhanced: bool


class HistoryList(BaseModel):
    """GET /api/history response."""
    items: list[HistoryItem]


class ErrorResponse(BaseModel):
    """Standard error response."""
    detail: str
    error_code: str | None = None
