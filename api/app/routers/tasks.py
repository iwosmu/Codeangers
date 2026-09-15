from fastapi import APIRouter, Request

from ..config import settings
from ..envelope import Timer, fixture, ok, wants_mock
from ..schemas import TasksRequest
from ..services import cache
from ..services.ai_tasks import check_graph, generate_tasks

router = APIRouter()


@router.post("/tasks")
async def create_tasks(body: TasksRequest, request: Request):
    with Timer() as t:
        if wants_mock(request):
            return ok(fixture("graph.mock.json"), ms=t.ms, mocked=True)

        k = cache.key("tasks", body.project.model_dump())
        hit = cache.get(k)
        if hit is not None:
            return ok(hit, ms=t.ms, model=settings().model_reason, cache_hit=True)

        graph, warnings = await generate_tasks(body.project)
        warnings = warnings + check_graph(body.project, graph)
        cache.put(k, graph.model_dump(by_alias=True))
    return ok(graph, warnings, ms=t.ms, model=settings().model_reason)
