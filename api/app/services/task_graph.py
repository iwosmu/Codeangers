"""Stage 2: project.md and team.md in, a validated dependency-ordered task graph out.

Runs ``app.task_planner`` against the two Markdown briefs. The planner validates the
model's graph (unique ids, edges that resolve, no self-loops or cycles, team capacity,
whole-team utilisation over a simulated schedule) and sends violations back to the
model for correction rounds. A graph that still fails is rejected here, never
returned. Nothing is cached or stored.
"""
import asyncio
from dataclasses import asdict

from ..config import settings
from ..envelope import ApiError
from ..task_planner import PlannerConfig, PlanningError, PlanResult, TaskPlanner
from .gemini import _client

ERRORS_IN_MESSAGE = 5


def build_planner() -> TaskPlanner:
    # Model name and key come from Settings, like every other Gemini call. The other
    # knobs keep the package defaults (see PlannerConfig).
    if not settings().gemini_api_key:
        raise ApiError("internal", "Add GEMINI_API_KEY to the repository's .env.local and restart the API.")
    return TaskPlanner(client=_client(), config=PlannerConfig(model=settings().gemini_model))


async def plan_task_graph(project_md: str, team_md: str, team_size: int | None) -> dict:
    planner = build_planner()
    try:
        # The planner is synchronous and one round can take minutes: keep the event loop free.
        result = await asyncio.to_thread(planner.plan, project_md, team_md, team_size)
    except PlanningError as exc:
        raise ApiError("model_invalid_json", f"Gemini returned an unusable task graph ({exc}). Please retry.",
                       retryable=True) from exc
    except ApiError:
        raise
    except Exception as exc:
        # Never echo vendor exceptions: they can contain document text or request metadata.
        code = getattr(exc, "code", None)
        if code == 429:
            raise ApiError("rate_limited", "Gemini quota or rate limit reached. Wait a moment and retry.", retryable=True) from exc
        if code in (401, 403):
            raise ApiError("model_failed", "Gemini rejected the API key or its permissions. Check the server configuration.") from exc
        if code == 404:
            raise ApiError("model_failed", "The configured Gemini model is unavailable for this API key. Check GEMINI_MODEL.") from exc
        raise ApiError("model_failed", "Gemini could not produce a task graph. Retry, or shorten the documents.", retryable=True) from exc

    if not result.ok:
        raise ApiError("plan_invalid", rejection_message(result), retryable=True)
    return serialize(result)


def rejection_message(result: PlanResult) -> str:
    errors = result.validation.errors
    shown = "; ".join(errors[:ERRORS_IN_MESSAGE])
    if len(errors) > ERRORS_IN_MESSAGE:
        shown += f"; and {len(errors) - ERRORS_IN_MESSAGE} more"
    return (f"The task graph still violates {len(errors)} constraint(s) after {result.rounds} attempt(s): "
            f"{shown}. Retry, or refine the documents.")


def serialize(result: PlanResult) -> dict:
    v = result.validation
    return {
        "graph": result.graph,
        "tasks": result.tasks,
        "team_size": result.team_size,
        "rounds": result.rounds,
        "validation": {
            "ok": v.ok,
            "summary": v.summary(),
            "errors": v.errors,
            "warnings": v.warnings,
            "makespan_hours": v.makespan_hours,
            "total_person_hours": v.total_person_hours,
            "idle_person_hours": v.idle_person_hours,
            "idle_fraction": v.idle_fraction,
            "idle_intervals": [asdict(interval) for interval in v.idle_intervals],
        },
    }
