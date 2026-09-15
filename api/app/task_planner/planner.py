"""Gemini calls: generate a task list, validate it, and ask for corrections.

Usage::

    from app.task_planner import TaskPlanner

    planner = TaskPlanner()                       # GEMINI_API_KEY from env
    result = planner.plan(project_md, team_md)    # team size inferred
    if result.ok:
        json.dump(result.graph, open("tasks.json", "w"), indent=2)   # PyVis-shaped
        result.tasks                                                # flat view
    else:
        print(result.validation.errors)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from .prompts import (
    SYSTEM_INSTRUCTION,
    build_fix_prompt,
    build_team_size_prompt,
    build_user_prompt,
)
from .graph import graph_to_tasks
from .schema import GRAPH_SCHEMA, TEAM_SIZE_SCHEMA, Graph, Task
from .validation import ValidationResult, validate_graph


class PlanningError(RuntimeError):
    """The API returned something unusable (blocked, truncated, not JSON)."""


@dataclass
class PlannerConfig:
    model: str = "gemini-3.8-flash"
    # Gemini 3.x: thinking_level in {"low", "medium", "high"}.
    # Gemini 2.5: set thinking_level=None and use thinking_budget (-1 = dynamic).
    thinking_level: str | None = "high"
    thinking_budget: int | None = None
    # Counts thinking tokens too - keep it generous or the answer gets cut off.
    max_output_tokens: int = 32768
    # None = model default. Google advises keeping the default on Gemini 3.
    temperature: float | None = None
    # How many times validation feedback is sent back before giving up.
    max_fix_rounds: int = 2
    # Validation thresholds (see validation.validate).
    max_task_hours: int = 40
    max_idle_fraction: float = 0.25


@dataclass
class PlanResult:
    graph: Graph                 # {"nodes": [...], "edges": [...]} as returned
    tasks: list[Task]            # same data, flat, with prerequisite id lists
    validation: ValidationResult
    team_size: int
    rounds: int
    history: list[ValidationResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.validation.ok


class TaskPlanner:
    def __init__(
        self,
        client: genai.Client | None = None,
        config: PlannerConfig | None = None,
    ) -> None:
        self.client = client or genai.Client()
        self.config = config or PlannerConfig()

    # ------------------------------------------------------------ public

    def plan(
        self,
        project_md: str,
        team_md: str,
        team_size: int | None = None,
    ) -> PlanResult:
        """Generate, validate and (if needed) repair a task graph.

        ``team_size`` should come from whatever produced ``team_md`` when you
        have it; otherwise it is extracted with a small extra call.
        """
        if team_size is None:
            team_size = self.team_size(team_md)

        contents: list[types.Content] = [
            _user(build_user_prompt(project_md, team_md)),
        ]
        history: list[ValidationResult] = []
        graph: Graph = {"nodes": [], "edges": []}
        result = ValidationResult(errors=["no attempt made"])

        for round_no in range(1, self.config.max_fix_rounds + 2):
            data, model_content = self._generate(
                contents, GRAPH_SCHEMA, thinking_level=self.config.thinking_level
            )
            graph = _as_graph(data)
            result = validate_graph(
                graph,
                team_size,
                max_task_hours=self.config.max_task_hours,
                max_idle_fraction=self.config.max_idle_fraction,
            )
            history.append(result)
            if result.ok or round_no > self.config.max_fix_rounds:
                return _make_result(graph, result, team_size, round_no, history)

            # Feed the model's own turn back verbatim (keeps thought signatures)
            # followed by the list of problems.
            contents.append(model_content)
            contents.append(_user(build_fix_prompt(result.errors, result.warnings)))

        return _make_result(graph, result, team_size, self.config.max_fix_rounds + 1, history)

    def team_size(self, team_md: str) -> int:
        """Count team members with a cheap structured call."""
        data, _ = self._generate(
            [_user(build_team_size_prompt(team_md))],
            TEAM_SIZE_SCHEMA,
            thinking_level="low" if self.config.thinking_level else None,
            max_output_tokens=4096,
        )
        size = int(data["team_size"])
        if size < 1:
            raise PlanningError(f"could not determine team size (got {size})")
        return size

    # ----------------------------------------------------------- private

    def _generate(
        self,
        contents: list[types.Content],
        schema: dict,
        *,
        thinking_level: str | None,
        max_output_tokens: int | None = None,
    ) -> tuple[Any, types.Content]:
        """One structured-output call. Returns (parsed JSON, model Content)."""
        cfg = types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_json_schema=schema,
            thinking_config=self._thinking_config(thinking_level),
            max_output_tokens=max_output_tokens or self.config.max_output_tokens,
            temperature=self.config.temperature,
        )
        response = self.client.models.generate_content(
            model=self.config.model, contents=contents, config=cfg
        )

        if not response.candidates:
            raise PlanningError(
                f"no candidates returned (prompt_feedback={response.prompt_feedback})"
            )
        candidate = response.candidates[0]
        if candidate.finish_reason == types.FinishReason.MAX_TOKENS:
            raise PlanningError(
                "response truncated at max_output_tokens; raise it or lower "
                "thinking_level"
            )
        text = response.text
        if not text:
            raise PlanningError(
                f"empty response (finish_reason={candidate.finish_reason})"
            )
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise PlanningError(f"response is not valid JSON: {exc}") from exc
        if candidate.content is None:
            raise PlanningError("candidate has no content")
        return data, candidate.content

    def _thinking_config(self, level: str | None) -> types.ThinkingConfig | None:
        if level:
            return types.ThinkingConfig(thinking_level=level)
        if self.config.thinking_budget is not None:
            return types.ThinkingConfig(thinking_budget=self.config.thinking_budget)
        return None


# ---------------------------------------------------------------- helpers

def _user(text: str) -> types.Content:
    return types.Content(role="user", parts=[types.Part.from_text(text=text)])


def _as_graph(data: Any) -> Graph:
    if not isinstance(data, dict) or "nodes" not in data or "edges" not in data:
        raise PlanningError('expected an object with "nodes" and "edges"')
    return data


def _make_result(
    graph: Graph,
    result: ValidationResult,
    team_size: int,
    rounds: int,
    history: list[ValidationResult],
) -> PlanResult:
    # The flat view is only derivable from a structurally sound graph.
    tasks = graph_to_tasks(graph) if _convertible(graph) else []
    return PlanResult(graph, tasks, result, team_size, rounds, history)


def _convertible(graph: Graph) -> bool:
    try:
        ids = [n["id"] for n in graph["nodes"]]
        return len(ids) == len(set(ids)) and all(
            e["from"] in ids and e["to"] in ids for e in graph["edges"]
        )
    except (KeyError, TypeError):
        return False
