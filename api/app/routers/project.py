from fastapi import APIRouter, Request

from ..config import settings
from ..envelope import Timer, fixture, ok, wants_mock
from ..schemas import ProjectModel, ProjectRequest
from ..services import cache
from ..services.ai_project import parse_project

router = APIRouter()


@router.post("/project")
async def create_project(body: ProjectRequest, request: Request):
    with Timer() as t:
        if wants_mock(request):
            return ok(fixture("project.mock.json"), ms=t.ms, mocked=True)

        k = cache.key("project", body.model_dump())
        hit = cache.get(k)
        if hit is not None:
            return ok(hit, ms=t.ms, model=settings().model_extract, cache_hit=True)

        project, warnings = await parse_project(body)
        cache.put(k, project.model_dump(by_alias=True))
    return ok(project, warnings, ms=t.ms, model=settings().model_extract)
