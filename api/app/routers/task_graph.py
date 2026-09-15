"""Stage 2: the two generated briefs in, a validated task graph out. No storage, no cache."""
import time

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import settings
from ..envelope import ApiError, ok
from ..services.task_graph import plan_task_graph

router = APIRouter()

MAX_DOCUMENT_CHARS = 1_000_000
MAX_REQUEST_BYTES = 8 * 1024 * 1024


class TaskGraphInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_md: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS)
    team_md: str = Field(min_length=1, max_length=MAX_DOCUMENT_CHARS)
    # Pass it when the caller knows it (the team brief was generated for a known number of
    # members); otherwise the planner counts the members with a small extra model call.
    team_size: int | None = Field(default=None, ge=1, le=50)


async def read_input(request: Request) -> TaskGraphInput:
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise ApiError("bad_input", "Send project_md and team_md as JSON.")
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > MAX_REQUEST_BYTES:
            raise ApiError("bad_input", "The documents are too large; the request must stay under 8 MB.")
        chunks.extend(chunk)
    try:
        body = TaskGraphInput.model_validate_json(bytes(chunks))
    except (ValidationError, ValueError) as exc:
        raise ApiError("bad_input", "Send non-empty project_md and team_md strings (at most "
                       f"{MAX_DOCUMENT_CHARS:,} characters each) and an optional team_size from 1 to 50.") from exc
    if not body.project_md.strip() or not body.team_md.strip():
        raise ApiError("bad_input", "Both documents must contain text. Generate project.md and team.md first.")
    return body


@router.post("/task-graph")
async def create_task_graph(request: Request):
    started = time.perf_counter()
    body = await read_input(request)
    data = await plan_task_graph(body.project_md, body.team_md, body.team_size)
    data["ms"] = round((time.perf_counter() - started) * 1000)
    return ok(data, ms=data["ms"], model=settings().gemini_model)
