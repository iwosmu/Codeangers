"""JSON schema enforced through ``response_json_schema`` and the matching types.

The model returns a vis.js / PyVis-shaped graph::

    {"nodes": [{"id": 1, "label": "...", "title": "...", "group": "backend",
                "estimated_time_hours": 8, "people_needed": 1}, ...],
     "edges": [{"from": 1, "to": 4}, ...]}

- ``id``/``label``/``title``/``group`` are vis.js node fields (title is the
  hover tooltip, group drives automatic colouring), so a node can be fed to
  PyVis directly: ``net.add_node(node["id"], **{k: v for k, v in node.items()
  if k != "id"})`` (PyVis names the first argument ``n_id``).
- ``estimated_time_hours`` and ``people_needed`` are extra node properties;
  vis.js keeps them on the node object and ignores them for rendering.
- An edge goes **from the prerequisite to the task that needs it**.

Field semantics live in the ``description`` strings - that is what the model
reads - so keep them in sync with ``validation.py`` and the prompt's numbered
constraints.
"""

from __future__ import annotations

from typing import TypedDict


class Node(TypedDict):
    id: int
    label: str
    title: str
    group: str
    estimated_time_hours: int
    people_needed: int


# "from" is a keyword, hence the functional form.
Edge = TypedDict("Edge", {"from": int, "to": int})


class Graph(TypedDict):
    nodes: list[Node]
    edges: list[Edge]


class _TaskRequired(TypedDict):
    id: int
    name: str
    description: str
    prerequisites: list[int]
    estimated_time_hours: int
    people_needed: int


class Task(_TaskRequired, total=False):
    """Flat per-task view used internally by the validator (see graph.py)."""

    group: str


NODE_FIELDS: tuple[str, ...] = (
    "id",
    "label",
    "title",
    "group",
    "estimated_time_hours",
    "people_needed",
)
EDGE_FIELDS: tuple[str, ...] = ("from", "to")
TASK_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "description",
    "prerequisites",
    "estimated_time_hours",
    "people_needed",
)

NODE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "id": {
            "type": "integer",
            "minimum": 1,
            "description": (
                "Unique task identifier. Number the tasks 1, 2, 3, ... in the "
                "order they are listed; edges reference these ids."
            ),
        },
        "label": {
            "type": "string",
            "description": (
                "Short, descriptive task name (at most 8 words), unique across "
                "the list. Shown on the node."
            ),
        },
        "title": {
            "type": "string",
            "description": (
                "Task description, 2-5 sentences: what is done, the concrete "
                "deliverable, and which skills it requires. Shown as the node's "
                "tooltip."
            ),
        },
        "group": {
            "type": "string",
            "description": (
                "One-word category of the work, e.g. setup, backend, frontend, "
                "database, devops, testing, docs, design. Use identical spelling "
                "for the same category across tasks; it drives node colouring."
            ),
        },
        "estimated_time_hours": {
            "type": "integer",
            "minimum": 1,
            "description": (
                "Wall-clock hours to complete the task with people_needed people "
                "working on it simultaneously."
            ),
        },
        "people_needed": {
            "type": "integer",
            "minimum": 1,
            "description": (
                "Number of team members working on this task at the same time. "
                "Never more than the team size."
            ),
        },
    },
    "required": list(NODE_FIELDS),
}

EDGE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "from": {
            "type": "integer",
            "minimum": 1,
            "description": "Id of the prerequisite task (the one that must finish first).",
        },
        "to": {
            "type": "integer",
            "minimum": 1,
            "description": "Id of the task that cannot start until 'from' is finished.",
        },
    },
    "required": list(EDGE_FIELDS),
}

GRAPH_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "nodes": {
            "type": "array",
            "description": (
                "One node per task; every task needed to fully deliver the "
                "project, in a sensible execution order."
            ),
            "items": NODE_SCHEMA,
        },
        "edges": {
            "type": "array",
            "description": (
                "One edge per direct dependency, from the prerequisite task to "
                "the task that needs it. No transitive edges, no cycles."
            ),
            "items": EDGE_SCHEMA,
        },
    },
    "required": ["nodes", "edges"],
}

TEAM_SIZE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "team_size": {
            "type": "integer",
            "minimum": 1,
            "description": "Number of distinct people on the team.",
        },
    },
    "required": ["team_size"],
}
