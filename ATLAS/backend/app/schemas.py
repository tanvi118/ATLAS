"""Shared request/response models. Field names match docs/API_CONTRACT.md."""
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Priority = Literal["low", "medium", "high"]
Difficulty = Literal["easy", "medium", "hard"]
Status = Literal["pending", "in_progress", "completed"]
Intent = Literal[
    "chat", "create_task", "list_tasks", "update_task", "complete_task",
    "study_plan", "document_qa", "remember_preference", "use_memory",
]


# ---------- Tasks ----------
class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    deadline: datetime | None = None
    priority: Priority = "medium"
    difficulty: Difficulty = "medium"
    estimated_time_minutes: int | None = Field(default=None, gt=0, le=10080)

    @field_validator("subject")
    @classmethod
    def _blank_subject_is_none(cls, v):
        return v or None


class TaskUpdate(BaseModel):
    """Partial update: only the fields that are sent get changed."""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    deadline: datetime | None = None
    priority: Priority | None = None
    difficulty: Difficulty | None = None
    estimated_time_minutes: int | None = Field(default=None, gt=0, le=10080)
    status: Status | None = None

    @model_validator(mode="after")
    def _check_fields(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        for name in ("title", "priority", "difficulty", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"'{name}' cannot be null.")
        return self


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    subject: str | None = None
    deadline: datetime | None = None
    priority: Priority
    difficulty: Difficulty
    estimated_time_minutes: int | None = None
    status: Status
    created_at: datetime


class TaskListResponse(BaseModel):
    tasks: list[TaskResponse]


class TaskDeleteResponse(BaseModel):
    id: int
    deleted: bool = True


# ---------- Chat / documents ----------
class SourceResponse(BaseModel):
    document: str
    page: int | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=100)

    def resolved_session_id(self) -> str:
        return self.session_id or str(uuid.uuid4())


class ChatResponse(BaseModel):
    reply: str
    intent: Intent
    tasks_created: list[TaskResponse] = []
    sources: list[SourceResponse] = []
    session_id: str


class AgentResult(BaseModel):
    """What the agent returns to the chat endpoint (no session_id yet)."""
    reply: str
    intent: Intent
    tasks_created: list[TaskResponse] = []
    sources: list[SourceResponse] = []


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    indexed: bool          # True only if the RAG module really ingested the file
    chunks: int | None = None
    message: str


class DocumentQueryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=2000)
    document_id: str | None = Field(default=None, max_length=64)
    session_id: str | None = Field(default=None, max_length=100)


class DocumentQueryResponse(BaseModel):
    reply: str
    intent: Literal["document_qa"] = "document_qa"
    sources: list[SourceResponse] = []
    session_id: str
