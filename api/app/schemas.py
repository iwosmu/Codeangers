from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# SHARED CONTRACT. The twin of web/src/types.ts.
# Edit both in one commit and announce it out loud.

Category = Literal["backend", "frontend", "ml", "data", "design", "devops", "domain", "pitch"]
CATEGORIES: list[str] = ["backend", "frontend", "ml", "data", "design", "devops", "domain", "pitch"]

# Pasted verbatim into every prompt that produces a level, so A, B, C and D all mean the same thing.
LEVEL_SCALE = (
    "1 = has heard of it. "
    "2 = coursework or a tutorial project. "
    "3 = shipped something real, with help. "
    "4 = shipped something real, alone. "
    "5 = others come to them with questions about it."
)


class Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True,
                              alias_generator=lambda s: s.split("_")[0] + "".join(w.capitalize() for w in s.split("_")[1:]))


class Section(Camel):
    id: str
    name: str
    description: str
    needs: list[Category] = []          # ordered, most important first
    min_people: int = 1
    max_people: int = 3


class ProjectModel(Camel):
    goal: str
    deliverables: list[str] = []
    stack: list[str] = []
    sections: list[Section] = []
    horizon_blocks: int = 48            # 30-minute blocks


class Skill(Camel):
    category: Category
    label: str
    level: int = Field(ge=1, le=5)
    evidence: str = ""                  # verbatim quote. Empty means drop the skill.


class PersonProfile(Camel):
    id: str
    name: str
    skills: list[Skill] = []
    prefers: list[Category] = []
    avoids: list[Category] = []
    source: Literal["cv", "manual"] = "cv"


class Task(Camel):
    id: str
    title: str
    section_id: str
    blocks: Literal[1, 2, 4]
    kind: Literal["contract", "impl", "integration"]
    depends_on: list[str] = []


class TaskGraph(Camel):
    tasks: list[Task] = []


class Assignment(Camel):
    task_id: str
    person_id: str
    start_block: int
    end_block: int                      # exclusive
    locked: bool = False


class Warning(Camel):
    code: str
    message: str
    severity: Literal["info", "warn", "error"] = "warn"
    task_ids: list[str] = []
    person_ids: list[str] = []


class Metrics(Camel):
    parallelism_score: float = 0.0
    critical_path: list[str] = []


class Plan(Camel):
    section_of: dict[str, str] = {}     # personId -> sectionId
    assignments: list[Assignment] = []
    rationale: dict[str, str] = {}      # personId -> one sentence
    risks: list[Warning] = []           # written by the model
    issues: list[Warning] = []          # written by the validator, never by the model
    metrics: Metrics | None = None      # derived from the plan, optional


# ---- request bodies -------------------------------------------------

class ProjectRequest(Camel):
    brief: str
    horizon_hours: int = 24
    team_size: int = 5


class TasksRequest(Camel):
    project: ProjectModel


class PlanRequest(Camel):
    project: ProjectModel
    people: list[PersonProfile]
    graph: TaskGraph
    locks: list[Assignment] = []
