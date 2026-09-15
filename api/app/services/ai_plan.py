from ..envelope import ApiError
from ..schemas import Assignment, PersonProfile, Plan, ProjectModel, TaskGraph, Warning

# OWNER C  --  stages 2 and 4 in one call. This is the product.
#
# There is no solver. The model assigns people to sections, schedules every task
# into blocks, and explains itself. app/services/validate.py then checks the result
# and, if it finds errors, you send them back once for a repair round.
#
# The six constraints below are checked by the validator afterwards, so they must
# appear in the prompt word for word. Constraint 4 is the one that produces
# parallel work -- without it the model returns a queue, not a plan.

CONSTRAINTS = [
    "1. Every person gets exactly one section. Every section gets at least minPeople.",
    "2. A person is never assigned two tasks that overlap in time.",
    "3. A task starts only after every task in its dependsOn has ended.",
    "4. Every dependency that crosses a section boundary gets a contract task inserted "
    "before it, scheduled early and known to both sides.",
    "5. No person's assigned blocks exceed horizonBlocks.",
    "6. Locked assignments are copied through unchanged, exactly as given.",
]

RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["sectionOf", "rationale", "assignments", "risks"],
    "properties": {
        "sectionOf": {"type": "object", "additionalProperties": {"type": "string"}},
        "rationale": {"type": "object", "additionalProperties": {"type": "string"}},
        "assignments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["taskId", "personId", "startBlock", "endBlock"],
                "properties": {
                    "taskId": {"type": "string"},
                    "personId": {"type": "string"},
                    "startBlock": {"type": "integer"},
                    "endBlock": {"type": "integer"},
                    "locked": {"type": "boolean"},
                },
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["code", "message", "severity"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "warn", "error"]},
                    "taskIds": {"type": "array", "items": {"type": "string"}},
                    "personIds": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


async def generate_plan(project: ProjectModel, people: list[PersonProfile],
                        graph: TaskGraph, locks: list[Assignment]) -> tuple[Plan, list[Warning]]:
    raise ApiError(
        "internal",
        "generate_plan is not implemented yet. Run with MOCK_ONLY=true or send the header x-mock: 1.",
    )
