"""Checks the JSON schema cannot express: id uniqueness, dependency integrity,
acyclicity, team capacity, and whole-team utilisation over a simulated schedule.

``validate_graph`` takes the PyVis-shaped ``{"nodes", "edges"}`` output and
delegates to ``validate``, which works on the flat task list where each task
carries a list of prerequisite ids.

``errors`` are hard violations of the planning constraints; ``warnings`` are
quality issues worth feeding back to the model but not worth rejecting the
plan for on their own.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field

from .graph import graph_to_tasks
from .schema import EDGE_FIELDS, NODE_FIELDS, TASK_FIELDS, Graph, Task


@dataclass
class IdleInterval:
    start: int
    end: int
    idle_people: int

    @property
    def idle_person_hours(self) -> int:
        return (self.end - self.start) * self.idle_people


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    makespan_hours: int = 0
    total_person_hours: int = 0
    idle_person_hours: int = 0
    idle_fraction: float = 0.0
    idle_intervals: list[IdleInterval] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "OK" if self.ok else f"{len(self.errors)} error(s)"
        return (
            f"{status}, {len(self.warnings)} warning(s); "
            f"makespan {self.makespan_hours} h, "
            f"{self.total_person_hours} person-hours of work, "
            f"{self.idle_person_hours} idle person-hours "
            f"({self.idle_fraction:.0%} of capacity)"
        )


def _label(t: Task) -> str:
    return f"task {t.get('id')!r} ({t.get('name')!r})"


def validate_graph(
    graph: Graph,
    team_size: int,
    *,
    max_task_hours: int = 40,
    max_idle_fraction: float = 0.25,
) -> ValidationResult:
    """Validate a ``{"nodes": [...], "edges": [...]}`` graph.

    Graph-level problems (bad shape, duplicate node ids, edges pointing at
    unknown nodes) are reported here; everything else is checked by
    ``validate`` on the converted task list.
    """
    r = ValidationResult()
    if not isinstance(graph, dict) or not isinstance(graph.get("nodes"), list) \
            or not isinstance(graph.get("edges"), list):
        r.errors.append('the response must be an object with "nodes" and "edges" arrays')
        return r
    nodes, edges = graph["nodes"], graph["edges"]

    for i, n in enumerate(nodes):
        missing = [f for f in NODE_FIELDS if not isinstance(n, dict) or f not in n]
        if missing:
            r.errors.append(f"node #{i} is missing fields: {', '.join(missing)}")
        elif not _is_int(n["id"]) or n["id"] < 1:
            r.errors.append(f"node #{i} has an invalid id {n['id']!r}; ids are integers >= 1")
    for i, n in enumerate(nodes):
        if not isinstance(n, dict) or any(f not in n for f in NODE_FIELDS):
            continue
        for field_name in ("label", "title", "group"):
            if not isinstance(n[field_name], str) or not n[field_name].strip():
                r.errors.append(f"node #{i}: {field_name} must be non-empty text")
        for field_name in ("estimated_time_hours", "people_needed"):
            if not _is_int(n[field_name]) or n[field_name] < 1:
                r.errors.append(f"node #{i}: {field_name} must be a positive integer")
    for i, e in enumerate(edges):
        missing = [f for f in EDGE_FIELDS if not isinstance(e, dict) or f not in e]
        if missing:
            r.errors.append(f"edge #{i} is missing fields: {', '.join(missing)}")
        elif not (_is_int(e["from"]) and _is_int(e["to"])):
            r.errors.append(f"edge #{i} endpoints must be integer node ids")
    if r.errors:
        return r

    for id_, n in Counter(n["id"] for n in nodes).items():
        if n > 1:
            r.errors.append(f"id {id_} is used by {n} nodes; ids must be unique")
    if r.errors:
        return r

    known = {n["id"] for n in nodes}
    seen_edges: set[tuple[int, int]] = set()
    for e in edges:
        pair = (e["from"], e["to"])
        for end in pair:
            if end not in known:
                r.errors.append(f"edge {pair[0]} -> {pair[1]} references unknown node id {end}")
        if pair in seen_edges:
            r.warnings.append(f"edge {pair[0]} -> {pair[1]} appears more than once")
        seen_edges.add(pair)
    if r.errors:
        return r

    inner = validate(
        graph_to_tasks(graph),
        team_size,
        max_task_hours=max_task_hours,
        max_idle_fraction=max_idle_fraction,
    )
    inner.warnings = r.warnings + inner.warnings
    return inner


def validate(
    tasks: list[Task],
    team_size: int,
    *,
    max_task_hours: int = 40,
    max_idle_fraction: float = 0.25,
) -> ValidationResult:
    """Validate a task list against a team of ``team_size`` people.

    The schedule simulation is skill-agnostic: it only checks head-count, so a
    plan can pass here and still over-allocate a skill. That check stays in
    the prompt.
    """
    r = ValidationResult()
    if team_size < 1:
        r.errors.append("team_size must be at least 1")
        return r
    if not tasks:
        r.errors.append("the task list is empty")
        return r

    # --- shape (belt and braces; the API schema should already guarantee it)
    for i, t in enumerate(tasks):
        missing = [f for f in TASK_FIELDS if f not in t]
        if missing:
            r.errors.append(f"task #{i} is missing fields: {', '.join(missing)}")
            continue
        if not _is_int(t["id"]) or t["id"] < 1:
            r.errors.append(f"task #{i} has an invalid id {t['id']!r}; ids are integers >= 1")
        if not isinstance(t["prerequisites"], list) or not all(
            _is_int(p) for p in t["prerequisites"]
        ):
            r.errors.append(f"{_label(t)}: prerequisites must be a list of integer ids")
    if r.errors:
        return r

    # --- id uniqueness (hard) and name uniqueness (soft)
    for id_, n in Counter(t["id"] for t in tasks).items():
        if n > 1:
            r.errors.append(f"id {id_} is used by {n} tasks; ids must be unique")
    for name, n in Counter(t["name"] for t in tasks).items():
        if n > 1:
            r.warnings.append(f"name {name!r} is used by {n} tasks; names should be unique")
    if r.errors:
        return r  # everything below is keyed by id

    ids = [t["id"] for t in tasks]
    if ids != list(range(1, len(tasks) + 1)):
        r.warnings.append("ids are not numbered 1..N in list order")

    # --- per-task fields
    known = set(ids)
    for t in tasks:
        if not isinstance(t["name"], str) or not t["name"].strip():
            r.errors.append(f"task {t['id']} has an empty name")
        if t["people_needed"] < 1:
            r.errors.append(f"{_label(t)}: people_needed must be at least 1")
        if t["people_needed"] > team_size:
            r.errors.append(
                f"{_label(t)} needs {t['people_needed']} people but the team has {team_size}"
            )
        if t["estimated_time_hours"] < 1:
            r.errors.append(f"{_label(t)}: estimated_time_hours must be at least 1")
        elif t["estimated_time_hours"] > max_task_hours:
            r.warnings.append(
                f"{_label(t)} is estimated at {t['estimated_time_hours']} h; "
                f"tasks above {max_task_hours} h should be split"
            )
        seen: set[int] = set()
        for p in t["prerequisites"]:
            if p == t["id"]:
                r.errors.append(f"{_label(t)} lists itself as a prerequisite")
            elif p not in known:
                r.errors.append(f"{_label(t)} has unknown prerequisite id {p}")
            elif p in seen:
                r.warnings.append(f"{_label(t)} lists prerequisite {p} twice")
            seen.add(p)
    if r.errors:
        return r  # graph checks below need a consistent list

    # --- graph: topological order / cycle detection
    by_id = {t["id"]: t for t in tasks}
    dependents: dict[int, list[int]] = {i: [] for i in by_id}
    for t in tasks:
        for p in t["prerequisites"]:
            dependents[p].append(t["id"])
    order = _topological_order(by_id, dependents)
    if order is None:
        stuck = _nodes_in_cycles(by_id, dependents)
        r.errors.append(
            "the dependency graph contains a cycle involving: "
            + ", ".join(_label(by_id[i]) for i in stuck)
        )
        return r

    # --- redundant transitive prerequisites
    ancestors: dict[int, set[int]] = {}
    for i in order:
        anc: set[int] = set()
        for p in by_id[i]["prerequisites"]:
            anc.add(p)
            anc |= ancestors[p]
        ancestors[i] = anc
    for t in tasks:
        prereqs = t["prerequisites"]
        for p in prereqs:
            if any(p in ancestors[q] for q in prereqs if q != p):
                r.warnings.append(
                    f"{_label(t)}: prerequisite {p} is already implied "
                    f"transitively and should be dropped"
                )

    # --- utilisation at the start
    root_people = sum(t["people_needed"] for t in tasks if not t["prerequisites"])
    if root_people < team_size:
        r.errors.append(
            f"tasks without prerequisites occupy only {root_people} of "
            f"{team_size} people at the start; add or widen initial tasks"
        )

    # --- utilisation over a simulated schedule
    makespan, intervals = simulate_schedule(tasks, team_size, order, dependents)
    r.makespan_hours = makespan
    r.total_person_hours = sum(
        t["estimated_time_hours"] * t["people_needed"] for t in tasks
    )
    r.idle_intervals = intervals
    r.idle_person_hours = sum(iv.idle_person_hours for iv in intervals)
    capacity = team_size * makespan
    r.idle_fraction = r.idle_person_hours / capacity if capacity else 0.0

    idle_msg = _describe_idle(intervals, team_size)
    if r.idle_fraction > max_idle_fraction:
        r.errors.append(
            f"the team is idle {r.idle_fraction:.0%} of the time over a "
            f"{makespan} h schedule (limit {max_idle_fraction:.0%}); {idle_msg}"
        )
    elif intervals:
        r.warnings.append(f"idle capacity: {idle_msg}")

    return r


def simulate_schedule(
    tasks: list[Task],
    team_size: int,
    order: list[int] | None = None,
    dependents: dict[int, list[int]] | None = None,
) -> tuple[int, list[IdleInterval]]:
    """Greedy list scheduling with ``team_size`` interchangeable workers.

    Ready tasks are started in order of longest remaining critical path while
    enough people are free. Returns the makespan in hours and the intervals
    during which some workers had nothing to do. Assumes an acyclic,
    consistent task list (run ``validate`` first if unsure).
    """
    by_id = {t["id"]: t for t in tasks}
    if dependents is None:
        dependents = {i: [] for i in by_id}
        for t in tasks:
            for p in t["prerequisites"]:
                dependents[p].append(t["id"])
    if order is None:
        order = _topological_order(by_id, dependents)
        if order is None:
            raise ValueError("task graph contains a cycle")

    # longest path (in hours) from each task to the end of the project
    critical: dict[int, int] = {}
    for i in reversed(order):
        tail = max((critical[d] for d in dependents[i]), default=0)
        critical[i] = by_id[i]["estimated_time_hours"] + tail

    remaining = {i: set(by_id[i]["prerequisites"]) for i in by_id}
    started: set[int] = set()
    running: list[tuple[int, int]] = []  # (end_time, id)
    free = team_size
    now = 0
    done = 0
    idle: list[IdleInterval] = []

    while done < len(tasks):
        ready = [i for i, req in remaining.items() if not req and i not in started]
        ready.sort(key=lambda i: (-critical[i], -by_id[i]["people_needed"], i))
        for i in ready:
            need = by_id[i]["people_needed"]
            if need <= free:
                free -= need
                started.add(i)
                running.append((now + by_id[i]["estimated_time_hours"], i))
        if not running:  # cannot happen on a validated DAG, but never spin
            raise ValueError("scheduler stalled; is the task list consistent?")

        next_time = min(end for end, _ in running)
        if free > 0:
            idle.append(IdleInterval(now, next_time, free))

        finished = [i for end, i in running if end == next_time]
        running = [(end, i) for end, i in running if end != next_time]
        for i in finished:
            done += 1
            free += by_id[i]["people_needed"]
            for d in dependents[i]:
                remaining[d].discard(i)
        now = next_time

    return now, _merge_idle(idle)


# ---------------------------------------------------------------- helpers

def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _topological_order(
    by_id: dict[int, Task], dependents: dict[int, list[int]]
) -> list[int] | None:
    indeg = {i: len(by_id[i]["prerequisites"]) for i in by_id}
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


def _nodes_in_cycles(
    by_id: dict[int, Task], dependents: dict[int, list[int]]
) -> list[int]:
    """Ids that never reach in-degree zero, i.e. sit on or behind a cycle."""
    indeg = {i: len(by_id[i]["prerequisites"]) for i in by_id}
    queue = deque(i for i, d in indeg.items() if d == 0)
    while queue:
        i = queue.popleft()
        for d in dependents[i]:
            indeg[d] -= 1
            if indeg[d] == 0:
                queue.append(d)
    return sorted(i for i, d in indeg.items() if d > 0)


def _merge_idle(intervals: list[IdleInterval]) -> list[IdleInterval]:
    merged: list[IdleInterval] = []
    for iv in intervals:
        if merged and merged[-1].end == iv.start and merged[-1].idle_people == iv.idle_people:
            merged[-1].end = iv.end
        else:
            merged.append(IdleInterval(iv.start, iv.end, iv.idle_people))
    return merged


def _describe_idle(intervals: list[IdleInterval], team_size: int) -> str:
    if not intervals:
        return "none"
    parts = [
        f"{iv.idle_people} of {team_size} idle during h {iv.start}-{iv.end}"
        for iv in intervals[:6]
    ]
    if len(intervals) > 6:
        parts.append(f"... and {len(intervals) - 6} more intervals")
    return "; ".join(parts)
