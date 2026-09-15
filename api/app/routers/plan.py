from fastapi import APIRouter, Request

from ..config import settings
from ..envelope import Timer, fixture, ok, wants_mock
from ..schemas import Plan, PlanRequest
from ..services import cache
from ..services.ai_plan import generate_plan
from ..services.validate import metrics, validate_plan

router = APIRouter()


@router.post("/plan")
async def create_plan(body: PlanRequest, request: Request):
    # The only slow endpoint. The UI calls it on an explicit Re-plan click and
    # never on a drag -- a drag is a local edit plus web/src/lib/validate.ts.
    with Timer() as t:
        if wants_mock(request):
            raw = fixture("plan.mock.json")
            plan = Plan.model_validate(raw)
            plan.issues = validate_plan(body.project, body.people, body.graph, plan)
            plan.metrics = metrics(body.project, body.people, body.graph, plan)
            return ok(plan, ms=t.ms, mocked=True)

        k = cache.key("plan", body.project.model_dump(), [p.model_dump() for p in body.people],
                      body.graph.model_dump(), [l.model_dump() for l in body.locks])
        hit = cache.get(k)
        if hit is not None:
            return ok(hit, ms=t.ms, model=settings().model_reason, cache_hit=True)

        plan, warnings = await generate_plan(body.project, body.people, body.graph, body.locks)
        plan.issues = validate_plan(body.project, body.people, body.graph, plan)
        plan.metrics = metrics(body.project, body.people, body.graph, plan)
        cache.put(k, plan.model_dump(by_alias=True))
    return ok(plan, warnings, ms=t.ms, model=settings().model_reason)
