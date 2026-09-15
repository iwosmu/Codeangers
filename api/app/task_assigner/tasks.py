"""The task list: loading the task planner's output shapes and checking it is usable."""

from __future__ import annotations

from collections import deque
from typing import Any

from .schema import TASK_FIELDS, Task


def load_tasks(data: Any) -> list[Task]:
    """Normalise any of the task planner's output shapes to the flat task list.

    Accepts the flat list (``result.tasks``, ``--format tasks``), the
    ``{"nodes", "edges"}`` graph (``result.graph``, the planner CLI's default
    output), a ``{"tasks": [...]}`` wrapper, or the API envelope
    ``{"data": {...}}`` around either.
    """
    if isinstance(data, dict):
        if isinstance(data.get("data"), dict):
            return load_tasks(data["data"])
        if isinstance(data.get("tasks"), list):
            return [dict(t) for t in data["tasks"]]
        if isinstance(data.get("nodes"), list) and isinstance(data.get("edges"), list):
            return graph_to_tasks(data)
    if isinstance(data, list):
        return [dict(t) for t in data]
    raise ValueError('expected a task list, a {"nodes", "edges"} graph or a {"tasks": [...]} object')


def graph_to_tasks(graph: dict) -> list[Task]:
    """Nodes + edges -> flat tasks with ``prerequisites`` (edges run prerequisite -> task)."""
    prereqs: dict[Any, list] = {n["id"]: [] for n in graph["nodes"]}
    for e in graph["edges"]:
        if e["to"] not in prereqs:
            raise ValueError(f"edge {e['from']} -> {e['to']} points at an unknown node")
        if e["from"] not in prereqs[e["to"]]:
            prereqs[e["to"]].append(e["from"])
    return [
        {
            "id": n["id"],
            "name": n["label"],
            "description": n["title"],
            "group": n.get("group", "task"),
            "prerequisites": prereqs[n["id"]],
            "estimated_time_hours": n["estimated_time_hours"],
            "people_needed": n["people_needed"],
        }
        for n in graph["nodes"]
    ]


def check_tasks(tasks: list[Task]) -> None:
    """Raise ValueError unless the list can be scheduled.

    Fields present, ids unique positive integers, positive estimates and
    head-counts, prerequisites that resolve without self-loops, no cycle.
    """
    if not tasks:
        raise ValueError("the task list is empty")
    for i, t in enumerate(tasks):
        missing = [f for f in TASK_FIELDS if not isinstance(t, dict) or f not in t]
        if missing:
            raise ValueError(f"task #{i} is missing fields: {', '.join(missing)}")
        if not _is_int(t["id"]) or t["id"] < 1:
            raise ValueError(f"task #{i} has an invalid id {t['id']!r}; ids are integers >= 1")
        if not _is_int(t["estimated_time_hours"]) or t["estimated_time_hours"] < 1:
            raise ValueError(f"task {t['id']}: estimated_time_hours must be a positive integer")
        if not _is_int(t["people_needed"]) or t["people_needed"] < 1:
            raise ValueError(f"task {t['id']}: people_needed must be a positive integer")
        if not isinstance(t["prerequisites"], list) or not all(_is_int(p) for p in t["prerequisites"]):
            raise ValueError(f"task {t['id']}: prerequisites must be a list of integer ids")
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("task ids must be unique")
    known = set(ids)
    for t in tasks:
        for p in t["prerequisites"]:
            if p == t["id"]:
                raise ValueError(f"task {t['id']} lists itself as a prerequisite")
            if p not in known:
                raise ValueError(f"task {t['id']} has unknown prerequisite {p}")
    if topological_order(tasks) is None:
        raise ValueError("the task graph contains a cycle")


def topological_order(tasks: list[Task]) -> list[int] | None:
    """Kahn's algorithm; ``None`` when the graph has a cycle."""
    by_id = {t["id"]: t for t in tasks}
    dependents: dict[int, list[int]] = {i: [] for i in by_id}
    indeg: dict[int, int] = {}
    for t in tasks:
        prereqs = set(t["prerequisites"])
        indeg[t["id"]] = len(prereqs)
        for p in prereqs:
            dependents[p].append(t["id"])
    queue = deque(sorted(i for i, d in indeg.items() if d == 0))
    order: list[int] = []
    while queue:
        i = queue.popleft()
        order.append(i)
        for d in dependents[i]:
            indeg[d] -= 1
            if indeg[d] == 0:
                queue.append(d)
    return order if len(order) == len(by_id) else None


def critical_path_hours(tasks: list[Task]) -> int:
    """Length in hours of the longest prerequisite chain: the lower bound on the project."""
    order = topological_order(tasks)
    if order is None:
        raise ValueError("the task graph contains a cycle")
    by_id = {t["id"]: t for t in tasks}
    finish: dict[int, int] = {}
    for i in order:
        start = max((finish[p] for p in set(by_id[i]["prerequisites"])), default=0)
        finish[i] = start + by_id[i]["estimated_time_hours"]
    return max(finish.values(), default=0)


def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)
