"""JSON schema enforced through ``response_json_schema`` and the matching types.

The model returns the same assignment in two views, plus notes::

    {"tasks":  [{"task_id": 1, "task_name": "Set up repository", "assigned_to": ["Ala"]}, ...],
     "people": [{"member_id": "m1", "name": "Ala", "task_ids": [1, 4, 7, 10]}, ...],
     "notes":  [{"task_id": 5, "name": "Bartek", "note": "Needs React; nobody has evidence ..."}]}

- ``tasks``: every input task once, with the names of the members doing it.
- ``people``: every team member once, with their task ids in execution order.
- ``notes``: one entry per task assigned without evidence for a skill it needs
  (prompt rule 4) and one per rule that could not be met; ``task_id`` is 0 when
  a note is about a member rather than one task.

Field semantics live in the ``description`` strings - that is what the model
reads - so keep them in sync with ``validation.py`` and the prompt's numbered
constraints.
"""

from __future__ import annotations

from typing import TypedDict


class Member(TypedDict):
    id: str      # Member ID from the team document, e.g. "m1"
    name: str    # the member's heading in the team document


class _TaskRequired(TypedDict):
    id: int
    name: str
    description: str
    prerequisites: list[int]
    estimated_time_hours: int
    people_needed: int


class Task(_TaskRequired, total=False):
    """Flat task as produced by the task planner (``result.tasks``)."""

    group: str


class TaskAssignment(TypedDict):
    task_id: int
    task_name: str
    assigned_to: list[str]


class PersonAssignment(TypedDict):
    member_id: str
    name: str
    task_ids: list[int]


class Note(TypedDict):
    task_id: int
    name: str
    note: str


class Assignment(TypedDict):
    tasks: list[TaskAssignment]
    people: list[PersonAssignment]
    notes: list[Note]


TASK_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "description",
    "prerequisites",
    "estimated_time_hours",
    "people_needed",
)

TASK_VIEW_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "integer",
            "minimum": 1,
            "description": "Id of the task, exactly as given in the task list.",
        },
        "task_name": {
            "type": "string",
            "description": "Name of the task, exactly as given in the task list.",
        },
        "assigned_to": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Names of the members who do this task together: exactly people_needed "
                "distinct names, each spelled exactly as the member's heading in the "
                "team document."
            ),
        },
    },
    "required": ["task_id", "task_name", "assigned_to"],
}

PERSON_VIEW_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "member_id": {
            "type": "string",
            "description": "The Member ID from the team document, e.g. m1.",
        },
        "name": {
            "type": "string",
            "description": "The member's name exactly as in their heading in the team document.",
        },
        "task_ids": {
            "type": "array",
            "items": {"type": "integer", "minimum": 1},
            "description": (
                "Ids of this member's tasks in the order they do them, one after "
                "another. Empty when the member has no task."
            ),
        },
    },
    "required": ["member_id", "name", "task_ids"],
}

NOTE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "task_id": {
            "type": "integer",
            "minimum": 0,
            "description": (
                "Id of the task the note is about; 0 when the note is about a member "
                "rather than one task."
            ),
        },
        "name": {
            "type": "string",
            "description": (
                "Name of the member the note is about, exactly as in their heading in "
                "the team document."
            ),
        },
        "note": {
            "type": "string",
            "description": (
                "The missing skill, why this member is the closest fit and what they "
                "need to pick up before starting; or which rule could not be met and why."
            ),
        },
    },
    "required": ["task_id", "name", "note"],
}

ASSIGNMENT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "tasks": {
            "type": "array",
            "description": "One entry per task in the task list, every task exactly once, in id order.",
            "items": TASK_VIEW_SCHEMA,
        },
        "people": {
            "type": "array",
            "description": (
                "One entry per team member, every member exactly once, including "
                "members with no tasks, in the order of the team document."
            ),
            "items": PERSON_VIEW_SCHEMA,
        },
        "notes": {
            "type": "array",
            "description": (
                "One entry for every task assigned to a member without evidence for a "
                "skill it needs, and one for every rule that could not be met. Empty "
                "when every assignment is fully evidenced."
            ),
            "items": NOTE_SCHEMA,
        },
    },
    "required": ["tasks", "people", "notes"],
}
