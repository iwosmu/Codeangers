"""Application adapter for the standalone task_planner package.

Only the two session briefs cross this boundary. The existing envelope and
Gemini settings are used; no files, profiles, or graphs are persisted.
"""
import asyncio
import logging
import time
from dataclasses import asdict

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..config import settings
from ..envelope import ApiError, ok
from ..services.gemini import _client
from ..task_planner import PlannerConfig, PlanningError, TaskPlanner

router = APIRouter()


class FlowInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    project_md: str = Field(min_length=1, max_length=1_000_000)
    team_md: str = Field(min_length=1, max_length=1_000_000)
    team_size: int = Field(ge=2, le=8, strict=True)


async def read_flow_input(request: Request) -> FlowInput:
    if not request.headers.get("content-type", "").startswith("application/json"):
        raise ApiError("bad_input", "Send the two Markdown briefs and team_size as JSON.")
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > 8 * 1024 * 1024:
            raise ApiError("bad_input", "The planning request exceeds 8 MB. Shorten the source briefs.")
        content.extend(chunk)
    try:
        return FlowInput.model_validate_json(content)
    except ValidationError as exc:
        raise ApiError("bad_input", "Generate both non-empty briefs and supply the actual team size (2–8).") from exc


def generate_flow(body: FlowInput):
    # Own and close the client inside the worker, including when a browser leaves.
    client = _client()
    try:
        planner = TaskPlanner(client=client, config=PlannerConfig(model=settings().gemini_model, thinking_level="medium"))
        return planner.plan(body.project_md, body.team_md, body.team_size)
    finally:
        client.close()


@router.post("/task-graph")
async def create_task_flow(request: Request):
    started = time.perf_counter()
    body = await read_flow_input(request)
    try:
        result = await asyncio.to_thread(generate_flow, body)
    except ApiError:
        raise
    except PlanningError as exc:
        raise ApiError("model_invalid_json", "Gemini returned an incomplete or unreadable task graph. Please retry.", retryable=True) from exc
    except Exception as exc:
        logging.getLogger(__name__).warning("Task planner request failed (%s)", type(exc).__name__)
        if getattr(exc, "code", None) == 429:
            raise ApiError("rate_limited", "Gemini quota or rate limit reached. Wait a moment and retry.", retryable=True) from exc
        raise ApiError("model_failed", "Task planning failed or timed out. Retry, or shorten the briefs.", retryable=True) from exc
    if not result.ok:
        raise ApiError("plan_invalid", f"The graph did not pass dependency and capacity checks after {result.rounds} attempts. Refine the briefs or retry.", retryable=True)
    elapsed = round((time.perf_counter() - started) * 1000)
    validation = asdict(result.validation)
    validation.update(ok=True, summary=result.validation.summary())
    return ok({"graph": result.graph, "tasks": result.tasks, "team_size": result.team_size,
               "rounds": result.rounds, "validation": validation, "ms": elapsed},
              ms=elapsed, model=settings().gemini_model)
