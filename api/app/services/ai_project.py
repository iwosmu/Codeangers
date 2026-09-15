from ..envelope import ApiError
from ..schemas import ProjectModel, ProjectRequest, Warning

# OWNER C  --  stage 0: free text in, ProjectModel out.
#
# The sections this produces are the spine of the whole product: tasks reference
# them, people are assigned to them, and the UI asks the user to confirm them
# before anything else runs. Generate 3 to 6, never more than there are people.
#
# Build it here, test it with:  python -m app.services.ai_project
# Do not import fastapi in this file. E mounts it.

RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["goal", "deliverables", "stack", "sections"],
    "properties": {
        "goal": {"type": "string"},
        "deliverables": {"type": "array", "items": {"type": "string"}},
        "stack": {"type": "array", "items": {"type": "string"}},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "name", "description", "needs", "minPeople", "maxPeople"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "needs": {"type": "array", "items": {"type": "string"}},
                    "minPeople": {"type": "integer"},
                    "maxPeople": {"type": "integer"},
                },
            },
        },
    },
}


async def parse_project(req: ProjectRequest) -> tuple[ProjectModel, list[Warning]]:
    raise ApiError(
        "internal",
        "parse_project is not implemented yet. Run with MOCK_ONLY=true or send the header x-mock: 1.",
    )
