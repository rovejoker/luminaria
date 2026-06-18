"""Pydantic models for request/response validation."""
import enum
from datetime import datetime
from pydantic import BaseModel, Field



SAMPLER_OPTIONS = (
    "pingpong",
    "euler",
    "rk4",
    "dpmpp",
)

class GenerateRequest(BaseModel):
    """POST /api/generate request body."""
    user_input: str = Field(..., min_length=1, max_length=5000, description="User's natural language description")
    duration: int = Field(..., ge=15, le=120, description="Desired audio duration in seconds")
    steps: int = Field(default=25, ge=10, le=100, description="Diffusion sampling steps")
    cfg_scale: float = Field(default=6.0, ge=1.0, le=15.0, description="Classifier-free guidance scale")
    seed: int = Field(default=-1, ge=-1, le=2**31-1, description="Random seed (-1 = random)")
    sampler: str = Field(default="pingpong", description="Diffusion sampler type")


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


class TaskStatus(str, enum.Enum):
    """Task status enum."""
    QUEUED = "queued"
    ENHANCING = "enhancing"
    GENERATING = "generating"
    CONVERTING = "converting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskInfo(BaseModel):
    """Task in the generation queue."""
    task_id: str
    status: TaskStatus
    user_input: str
    duration: int
    progress: int = 0
    message: str = ""
    position: int = 0
    created_at: str = ""
    result: GenerateResponse | None = None
    error: str | None = None
