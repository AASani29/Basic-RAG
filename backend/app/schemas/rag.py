"""Request/response shapes for the RAG endpoints."""

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    filename: str
    chunk_count: int


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SourceChunk(BaseModel):
    filename: str
    chunk_index: int
    # Full chunk text, not a pre-truncated snippet — truncating for display is
    # a UI concern (CSS line-clamp, "show more"), and the frontend can't
    # recover text the API already cut off.
    content: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
