"""The v1 contract: evidence-backed team profiles and a separate project brief."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProductSetup(StrictModel):
    name: str = Field(default="", max_length=200)
    context: str = Field(default="", max_length=4000)
    constraints: str = Field(default="", max_length=4000)


class MemberInput(StrictModel):
    id: str = Field(pattern=r"^m[1-8]$")
    label: str = Field(default="", max_length=120)
    text: str = Field(default="", max_length=60000)


class BriefInput(StrictModel):
    setup: ProductSetup
    members: list[MemberInput] = Field(min_length=2, max_length=8)
    project_text: str = Field(default="", max_length=60000)


class ProjectBriefInput(StrictModel):
    setup: ProductSetup
    project_text: str = Field(default="", max_length=60000)


Area = Literal["frontend", "backend", "database", "ml", "design", "devops", "research", "pitch"]
AREAS = ["frontend", "backend", "database", "ml", "design", "devops", "research", "pitch"]
AREA_LABELS = {"frontend": "Frontend", "backend": "Backend", "database": "Database / data", "ml": "AI / ML", "design": "Design / UX", "devops": "DevOps", "research": "Research / domain", "pitch": "Pitch / communication"}


class Evidence(StrictModel):
    id: str = Field(min_length=1, max_length=40)
    source_id: str = Field(min_length=1, max_length=100)
    source_part: str = Field(min_length=1, max_length=180, description="text for pasted/extracted text, otherwise the exact supplied asset location")
    location: str = Field(min_length=1, max_length=160)
    quote: str = Field(min_length=1, max_length=3000)


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=600)
    evidence_ids: list[str] = Field(max_length=50)


class Coverage(StrictModel):
    area: Area
    level: Literal["strong", "some", "none"]
    evidence_ids: list[str] = Field(max_length=50)


class Gap(StrictModel):
    area: str = Field(min_length=1, max_length=120)
    relevance: str = Field(min_length=1, max_length=300)


class MemberBrief(StrictModel):
    id: str
    cv_name: Claim
    evidence: list[Evidence] = Field(max_length=50)
    roles: list[Claim] = Field(max_length=3)
    strengths: list[Claim] = Field(max_length=5)
    gaps: list[Gap] = Field(min_length=2, max_length=4)
    stack: list[Claim] = Field(max_length=80)
    experience: Claim
    working_style: list[Claim] = Field(max_length=3)
    coverage: list[Coverage] = Field(min_length=8, max_length=8)


class TeamBrief(StrictModel):
    members: list[MemberBrief] = Field(min_length=2, max_length=8)
    open_questions: list[str] = Field(min_length=3, max_length=5)
    _coverage_review_notes: list[str] = PrivateAttr(default_factory=list)


class Statement(StrictModel):
    text: str = Field(min_length=1, max_length=1000)
    source_ids: list[str] = Field(max_length=8)


class SourceNote(StrictModel):
    source_id: str
    contribution: str = Field(min_length=1, max_length=700)


class ProjectBrief(StrictModel):
    one_liner: Statement
    problem: Statement
    target_user: Statement
    vision: Statement
    value_proposition: Statement
    must_have: list[Statement] = Field(max_length=8)
    nice_to_have: list[Statement] = Field(max_length=6)
    constraints: list[Statement] = Field(max_length=10)
    success_criteria: list[Statement] = Field(max_length=8)
    impact: Statement
    open_questions: list[str] = Field(min_length=3, max_length=16)
    source_notes: list[SourceNote] = Field(min_length=1, max_length=20)
    contradictions: list[Statement] = Field(max_length=8)


def gemini_schema(model: type[BaseModel]) -> dict:
    """Send a compact, dereferenced generation schema; enforce full bounds locally.

    The API can reject deeply constrained Pydantic schemas with a generic 400.
    Structure, required fields and enums stay constrained on the model side.
    String/list limits and extra-field rejection remain mandatory after generation.
    """
    full = model.model_json_schema()
    definitions = full.get("$defs", {})
    def expand(node):
        if isinstance(node, list):
            return [expand(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            return expand(definitions[node["$ref"].rsplit("/", 1)[-1]])
        result = {}
        for key in ("type", "properties", "required", "items", "enum", "description"):
            if key in node:
                result[key] = {k: expand(v) for k, v in node[key].items()} if key == "properties" else expand(node[key])
        # Keep limits visible without the constrained schema complexity rejected by
        # the API. Local validation still enforces them; nothing is truncated.
        bounds = [f"{label}: {node[key]}" for key, label in (
            ("minLength", "Minimum characters"), ("maxLength", "Maximum characters"),
            ("minItems", "Minimum items"), ("maxItems", "Maximum items"),
        ) if key in node]
        if bounds:
            result["description"] = ". ".join(filter(None, [result.get("description"), *bounds])) + "."
        return result
    return expand(full)
