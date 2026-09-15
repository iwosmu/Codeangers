"""Gemini calls: assign the team to the task list, validate, and ask for corrections.

Usage::

    from task_assigner import TaskAssigner

    assigner = TaskAssigner()                        # GEMINI_API_KEY from env
    result = assigner.assign(team_md, tasks)         # tasks: task planner output, any shape
    if result.ok:
        json.dump(result.assignment, open("assignment.json", "w"), indent=2)
    else:
        print(result.validation.errors)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

from ..brief_schemas import MemberBrief
from .fit import FIT_ASSIGNMENT_SCHEMA, validate_fit

from google import genai
from google.genai import types

from .prompts import SYSTEM_INSTRUCTION, build_fix_prompt, build_user_prompt
from .schema import ASSIGNMENT_SCHEMA, Assignment, Member, Task
from .tasks import check_tasks, load_tasks
from .team import parse_members
from .validation import ValidationResult, validate_assignment


class AssignmentError(RuntimeError):
    """The API returned something unusable (blocked, truncated, not JSON)."""


@dataclass
class AssignerConfig:
    model: str = "gemini-3.8-flash"
    # Gemini 3.x: thinking_level in {"low", "medium", "high"}. Scheduling is the
    # hard reasoning step of the pipeline, so it defaults to high.
    # Gemini 2.5: set thinking_level=None and use thinking_budget (-1 = dynamic).
    thinking_level: str | None = "high"
    thinking_budget: int | None = None
    # Counts thinking tokens too - keep it generous or the answer gets cut off.
    max_output_tokens: int = 32768
    # None = model default. Google advises keeping the default on Gemini 3.
    temperature: float | None = None
    # How many times validation feedback is sent back before giving up.
    max_fix_rounds: int = 2
    # Validation threshold (see validation.validate_assignment).
    max_idle_fraction: float = 0.25


@dataclass
class AssignResult:
    assignment: Assignment        # tasks/people/notes, plus structured fit in application mode
    validation: ValidationResult
    members: list[Member]         # the team the assignment was checked against
    tasks: list[Task]             # the flat task list the prompt was built from
    rounds: int
    history: list[ValidationResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.validation.ok


class TaskAssigner:
    def __init__(
        self,
        client: genai.Client | None = None,
        config: AssignerConfig | None = None,
    ) -> None:
        self.client = client or genai.Client()
        self.config = config or AssignerConfig()

    # ------------------------------------------------------------ public

    def assign(
        self,
        team_md: str,
        tasks: Any,
        members: list[Member] | None = None,
        evidence_profiles: list[MemberBrief] | None = None,
    ) -> AssignResult:
        """Assign, validate and (if needed) repair.

        ``tasks`` is the task planner's output in any of its shapes (flat list,
        graph, wrapper or API envelope). ``members`` overrides the members parsed
        from ``team_md`` when the document was not rendered by the brief pipeline.
        Raises ValueError for unusable input before any model call.
        """
        task_list = load_tasks(tasks)
        check_tasks(task_list)
        team = list(members) if members is not None else parse_members(team_md)
        if not team:
            raise ValueError(
                "no team members found: expected '## <name>' sections with 'Member ID: mN' "
                "lines in the team document, or pass members=[{'id': ..., 'name': ...}, ...]"
            )

        self.evidence_mode = evidence_profiles is not None
        prompt = build_user_prompt(team_md, task_list)
        if evidence_profiles is not None:
            prompt += "\nMember roster (authoritative IDs and names):\n" + json.dumps(team, ensure_ascii=False)
            prompt += "\nStructured CV evidence:\n" + json.dumps([p.model_dump(exclude={'github'}) for p in evidence_profiles], ensure_ascii=False)
        contents: list[types.Content] = [_user(prompt)]
        history: list[ValidationResult] = []
        assignment: Assignment = {"tasks": [], "people": [], "notes": []}
        result = ValidationResult(errors=["no attempt made"])

        for round_no in range(1, self.config.max_fix_rounds + 2):
            data, model_content = self._generate(contents)
            assignment = _as_assignment(data)
            result = validate_assignment(
                assignment, task_list, team, max_idle_fraction=self.config.max_idle_fraction
            )
            if result.ok and evidence_profiles is not None:
                result.errors.extend(validate_fit(assignment, evidence_profiles, task_list))
            history.append(result)
            if result.ok or round_no > self.config.max_fix_rounds:
                return AssignResult(assignment, result, team, task_list, round_no, history)

            # Feed the model's own turn back verbatim (keeps thought signatures)
            # followed by the list of problems.
            contents.append(model_content)
            contents.append(_user(build_fix_prompt(result.errors, result.warnings)))

        return AssignResult(assignment, result, team, task_list, self.config.max_fix_rounds + 1, history)

    # ----------------------------------------------------------- private

    def _generate(self, contents: list[types.Content]) -> tuple[Any, types.Content]:
        """One structured-output call. Returns (parsed JSON, model Content)."""
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION + ("\n\n" + (Path(__file__).resolve().parents[1] / "prompts" / "assignment_fit.md").read_text() if getattr(self, "evidence_mode", False) else ""),
            response_mime_type="application/json",
            response_json_schema=FIT_ASSIGNMENT_SCHEMA if getattr(self, "evidence_mode", False) else ASSIGNMENT_SCHEMA,
            http_options=types.HttpOptions(timeout=60000, retry_options=types.HttpRetryOptions(attempts=1)),
            thinking_config=self._thinking_config(),
            max_output_tokens=self.config.max_output_tokens,
            temperature=self.config.temperature,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        response = self.client.models.generate_content(
            model=self.config.model, contents=contents, config=cfg
        )

        if not response.candidates:
            raise AssignmentError(
                f"no candidates returned (prompt_feedback={response.prompt_feedback})"
            )
        candidate = response.candidates[0]
        if candidate.finish_reason == types.FinishReason.MAX_TOKENS:
            raise AssignmentError(
                "response truncated at max_output_tokens; raise it or lower thinking_level"
            )
        text = response.text
        if not text:
            raise AssignmentError(f"empty response (finish_reason={candidate.finish_reason})")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise AssignmentError(f"response is not valid JSON: {exc}") from exc
        if candidate.content is None:
            raise AssignmentError("candidate has no content")
        return data, candidate.content

    def _thinking_config(self) -> types.ThinkingConfig | None:
        if self.config.thinking_level:
            return types.ThinkingConfig(thinking_level=self.config.thinking_level)
        if self.config.thinking_budget is not None:
            return types.ThinkingConfig(thinking_budget=self.config.thinking_budget)
        return None


# ---------------------------------------------------------------- helpers

def _user(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part.from_text(text=text)])


def _as_assignment(data: Any) -> Assignment:
    if not isinstance(data, dict) or not all(k in data for k in ("tasks", "people", "notes")):
        raise AssignmentError('expected an object with "tasks", "people" and "notes"')
    return data
