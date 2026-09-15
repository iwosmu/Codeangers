"""In-memory adapter for task-assigner from origin/task-assigner (6c86e81)."""
import asyncio
import logging
import time
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import Field, ValidationError, model_validator

from ..brief_schemas import StrictModel, TeamBrief
from ..config import settings
from ..envelope import ApiError, ok
from ..services.gemini import _client
from ..task_assigner import TaskAssigner, AssignerConfig, AssignmentError, check_tasks

router = APIRouter()


class AssignmentTask(StrictModel):
    id: int = Field(strict=True, ge=1)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=6000)
    group: str = Field(default='task', max_length=100)
    prerequisites: list[Annotated[int, Field(strict=True, ge=1)]] = Field(max_length=50)
    estimated_time_hours: int = Field(strict=True, ge=1, le=1000)
    people_needed: int = Field(strict=True, ge=1, le=8)


class AssignmentInput(StrictModel):
    team: TeamBrief
    tasks: list[AssignmentTask] = Field(min_length=1, max_length=50)

    @model_validator(mode='after')
    def coherent(self):
        ids = [p.id for p in self.team.members]
        if len(set(ids)) != len(ids) or not set(ids) <= {f'm{i}' for i in range(1, 9)}:
            raise ValueError('Member IDs must be unique m1–m8.')
        for member in self.team.members:
            if len({e.id for e in member.evidence}) != len(member.evidence):
                raise ValueError('Evidence IDs must be unique within a member.')
        if any(t.people_needed > len(ids) for t in self.tasks):
            raise ValueError('A task requires more people than the team has.')
        check_tasks([t.model_dump() for t in self.tasks])
        return self


def generate_assignment(body: AssignmentInput):
    client = _client()
    try:
        assigner = TaskAssigner(client=client, config=AssignerConfig(
            model=settings().gemini_model, thinking_level='medium', max_fix_rounds=1,
            # Scarce expertise can make idle time unavoidable. Preserve skill truth
            # and report idle intervals as warnings rather than force a wrong match.
            max_idle_fraction=1.0))
        members = [{'id': m.id, 'name': m.cv_name.text if m.cv_name.text != 'not stated' else m.id} for m in body.team.members]
        return assigner.assign('Use the structured CV evidence and authoritative roster below.',
                               [t.model_dump() for t in body.tasks], members=members,
                               evidence_profiles=body.team.members)
    finally:
        client.close()


@router.post('/task-assignments')
async def create_assignments(request: Request):
    started = time.perf_counter()
    if not request.headers.get('content-type', '').startswith('application/json'):
        raise ApiError('bad_input', 'Send the team brief and tasks as JSON.')
    content = bytearray()
    async for chunk in request.stream():
        if len(content) + len(chunk) > 8 * 1024 * 1024:
            raise ApiError('bad_input', 'The assignment request exceeds 8 MB.')
        content.extend(chunk)
    try:
        body = AssignmentInput.model_validate_json(content)
    except ValidationError as exc:
        raise ApiError('bad_input', 'Supply a valid team brief and task graph for 2–8 people.') from exc
    try:
        result = await asyncio.to_thread(generate_assignment, body)
    except ApiError:
        raise
    except AssignmentError as exc:
        raise ApiError('model_invalid_json', 'Gemini returned an incomplete assignment. Please retry.', retryable=True) from exc
    except Exception as exc:
        logging.getLogger(__name__).warning('Task assignment failed (%s)', type(exc).__name__)
        if getattr(exc, 'code', None) == 429:
            raise ApiError('rate_limited', 'Gemini quota or rate limit reached. Wait a moment and retry.', retryable=True) from exc
        raise ApiError('model_failed', 'Assignment failed or timed out. The task graph is still available; retry assignment.', retryable=True) from exc
    if not result.ok:
        raise ApiError('plan_invalid', 'Assignments did not pass evidence-reference and schedule checks. Retry assignment or review owners manually.', retryable=True)
    elapsed = round((time.perf_counter() - started) * 1000)
    owners = {t['id']: [p['member_id'] for p in result.assignment['people'] if t['id'] in p['task_ids']] for t in result.tasks}
    validation = asdict(result.validation)
    validation.update(ok=True, summary=result.validation.summary())
    return ok({'assignment': result.assignment, 'owners': owners, 'validation': validation,
               'rounds': result.rounds, 'ms': elapsed}, ms=elapsed, model=settings().gemini_model)
