"""Checks the JSON schema cannot express, plus a simulation of the execution rules.

Errors are hard violations: the two views disagree, a task has the wrong number
of members, a member or task is unknown or missing, the member lists deadlock,
or the team is idle more than ``max_idle_fraction`` of the project. Warnings are
quality issues worth sending back to the model: idle stretches while work was
ready, a project longer than its critical path, names that differ from the
document.

Skills are not checked here. Whether a member has evidence for a task's skills
is judged by the model from the team document (prompt rules 3-6); the notes it
returns are passed through untouched.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .schema import Assignment, Member, Task
from .tasks import critical_path_hours


class Deadlock(ValueError):
    """The member lists can never be executed to completion."""


@dataclass
class IdleInterval:
    member_id: str
    start: int
    end: int
    # Unstarted tasks whose prerequisites were finished when the wait began.
    ready_tasks: list[int] = field(default_factory=list)

    @property
    def hours(self) -> int:
        return self.end - self.start


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    makespan_hours: int = 0
    critical_path_hours: int = 0
    total_person_hours: int = 0
    idle_person_hours: int = 0
    idle_fraction: float = 0.0
    idle_intervals: list[IdleInterval] = field(default_factory=list)
    schedule: dict[int, tuple[int, int]] = field(default_factory=dict)  # task id -> (start, end)

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "OK" if self.ok else f"{len(self.errors)} error(s)"
        return (
            f"{status}, {len(self.warnings)} warning(s); project {self.makespan_hours} h "
            f"(critical path {self.critical_path_hours} h), "
            f"{self.total_person_hours} person-hours of work, "
            f"{self.idle_person_hours} idle person-hours ({self.idle_fraction:.0%} of capacity)"
        )


def validate_assignment(
    assignment: Assignment,
    tasks: list[Task],
    members: list[Member],
    *,
    max_idle_fraction: float = 0.25,
) -> ValidationResult:
    """Validate the model's assignment against the task list and the team.

    ``tasks`` must have passed ``check_tasks``. The per-member lists are the
    source of truth; the tasks view has to agree with them.
    """
    r = ValidationResult()
    if not isinstance(assignment, dict) or not all(
        isinstance(assignment.get(k), list) for k in ("tasks", "people", "notes")
    ):
        r.errors.append('the response must be an object with "tasks", "people" and "notes" arrays')
        return r
    for i, p in enumerate(assignment["people"]):
        if (
            not isinstance(p, dict)
            or not isinstance(p.get("member_id"), str)
            or not isinstance(p.get("name"), str)
            or not isinstance(p.get("task_ids"), list)
            or not all(_is_int(t) for t in p["task_ids"])
        ):
            r.errors.append(f"people entry #{i} must have member_id, name and a list of integer task_ids")
    for i, t in enumerate(assignment["tasks"]):
        if (
            not isinstance(t, dict)
            or not _is_int(t.get("task_id"))
            or not isinstance(t.get("task_name"), str)
            or not isinstance(t.get("assigned_to"), list)
            or not all(isinstance(n, str) for n in t["assigned_to"])
        ):
            r.errors.append(f"tasks entry #{i} must have task_id, task_name and a list of member names in assigned_to")
    for i, n in enumerate(assignment["notes"]):
        if (
            not isinstance(n, dict)
            or not _is_int(n.get("task_id"))
            or not isinstance(n.get("name"), str)
            or not isinstance(n.get("note"), str)
        ):
            r.errors.append(f"notes entry #{i} must have task_id, name and note")
    if r.errors:
        return r

    by_id = {t["id"]: t for t in tasks}
    name_of = {m["id"]: m["name"] for m in members}

    # --- per-member lists: the source of truth
    lists: dict[str, list[int]] = {}
    for p in assignment["people"]:
        mid = p["member_id"]
        if mid not in name_of:
            r.errors.append(f"people: unknown member id {mid!r} ({p['name']!r})")
            continue
        if mid in lists:
            r.errors.append(f"people: member {mid} appears more than once")
            continue
        if p["name"] != name_of[mid]:
            r.warnings.append(
                f"people: {mid} is named {p['name']!r} but the team document says {name_of[mid]!r}"
            )
        seen: set[int] = set()
        for t in p["task_ids"]:
            if t not in by_id:
                r.errors.append(f"people: {mid} lists unknown task id {t}")
            elif t in seen:
                r.errors.append(f"people: {mid} lists task {t} more than once")
            seen.add(t)
        lists[mid] = list(p["task_ids"])
    for mid, name in name_of.items():
        if mid not in lists:
            r.errors.append(
                f"people: member {mid} ({name}) is missing; every member must appear, "
                f"with an empty list if they have no task"
            )
    if r.errors:
        return r

    owners: dict[int, list[str]] = {i: [] for i in by_id}
    for mid, ids in lists.items():
        for t in ids:
            owners[t].append(mid)
    for t in tasks:
        n = len(owners[t["id"]])
        if n != t["people_needed"]:
            r.errors.append(
                f"task {t['id']} ({t['name']!r}) needs {t['people_needed']} member(s) but "
                f"appears in {n} list(s): {', '.join(owners[t['id']]) or 'none'}"
            )

    # --- the tasks view must agree with the lists
    counts = Counter(t["task_id"] for t in assignment["tasks"])
    for tid, n in counts.items():
        if tid not in by_id:
            r.errors.append(f"tasks: unknown task id {tid}")
        elif n > 1:
            r.errors.append(f"tasks: task {tid} appears {n} times; list every task once")
    for t in tasks:
        if t["id"] not in counts:
            r.errors.append(f"tasks: task {t['id']} ({t['name']!r}) is missing from the tasks view")
    for entry in assignment["tasks"]:
        t = by_id.get(entry["task_id"])
        if t is None:
            continue
        if entry["task_name"] != t["name"]:
            r.warnings.append(
                f"tasks: task {t['id']} is called {entry['task_name']!r} but the task list says {t['name']!r}"
            )
        expected = Counter(name_of[m] for m in owners[t["id"]])
        given = Counter(entry["assigned_to"])
        if given != expected:
            r.errors.append(
                f"task {t['id']}: the tasks view assigns {sorted(given.elements())} but the "
                f"member lists give {sorted(expected.elements())}; the two views must agree"
            )
    if r.errors:
        return r

    # --- notes refer to real tasks and members
    names = set(name_of.values())
    for n in assignment["notes"]:
        if n["task_id"] and n["task_id"] not in by_id:
            r.warnings.append(f"notes: unknown task id {n['task_id']}")
        if n["name"] not in names:
            r.warnings.append(f"notes: unknown member name {n['name']!r}")

    # --- simulate the execution rules
    try:
        schedule, idle = simulate_schedule(lists, tasks)
    except Deadlock as exc:
        r.errors.append(str(exc))
        return r
    r.schedule = schedule
    r.makespan_hours = max((end for _, end in schedule.values()), default=0)
    r.critical_path_hours = critical_path_hours(tasks)
    r.total_person_hours = sum(t["estimated_time_hours"] * t["people_needed"] for t in tasks)
    r.idle_intervals = idle
    r.idle_person_hours = sum(iv.hours for iv in idle)
    capacity = len(members) * r.makespan_hours
    r.idle_fraction = r.idle_person_hours / capacity if capacity else 0.0

    described = _describe_idle(idle, name_of)
    if r.idle_fraction > max_idle_fraction:
        r.errors.append(
            f"the team is idle {r.idle_fraction:.0%} of the time over a {r.makespan_hours} h "
            f"project (limit {max_idle_fraction:.0%}); {described}"
        )
    elif idle:
        r.warnings.append(f"idle capacity: {described}")
    if r.makespan_hours > r.critical_path_hours:
        r.warnings.append(
            f"the project takes {r.makespan_hours} h but its critical path is "
            f"{r.critical_path_hours} h; look for a task that waits for a busy member"
        )
    return r


def simulate_schedule(
    lists: dict[str, list[int]], tasks: list[Task]
) -> tuple[dict[int, tuple[int, int]], list[IdleInterval]]:
    """Execute the per-member lists under the prompt's rules.

    Each member works through their list in order. A task starts as soon as all
    its prerequisites have finished and every member assigned to it has reached
    it in their list and is free; it then runs for ``estimated_time_hours``.
    Returns ``{task id: (start, end)}`` and the intervals in which members had
    nothing to do. Raises ``Deadlock`` when the lists can never complete.
    Assumes every task appears in exactly ``people_needed`` lists and the task
    list passed ``check_tasks``.
    """
    by_id = {t["id"]: t for t in tasks}
    owners: dict[int, list[str]] = {i: [] for i in by_id}
    for mid, ids in lists.items():
        for t in ids:
            owners[t].append(mid)
    pointer = {mid: 0 for mid in lists}
    free_at = {mid: 0 for mid in lists}
    schedule: dict[int, tuple[int, int]] = {}
    unstarted = set(by_id)
    now = 0

    while unstarted:
        started_any = True
        while started_any:
            started_any = False
            for tid in sorted(unstarted):
                task = by_id[tid]
                prereqs_done = all(
                    p in schedule and schedule[p][1] <= now for p in set(task["prerequisites"])
                )
                owners_ready = owners[tid] and all(
                    pointer[m] < len(lists[m]) and lists[m][pointer[m]] == tid and free_at[m] <= now
                    for m in owners[tid]
                )
                if prereqs_done and owners_ready:
                    end = now + task["estimated_time_hours"]
                    schedule[tid] = (now, end)
                    for m in owners[tid]:
                        free_at[m] = end
                        pointer[m] += 1
                    unstarted.discard(tid)
                    started_any = True
        if not unstarted:
            break
        future = [end for _, end in schedule.values() if end > now]
        if not future:
            raise Deadlock(_explain_deadlock(now, lists, pointer, owners, by_id, schedule))
        now = min(future)

    makespan = max((end for _, end in schedule.values()), default=0)
    idle: list[IdleInterval] = []
    for mid, ids in lists.items():
        prev_end = 0
        for tid in ids:
            start, end = schedule[tid]
            if start > prev_end:
                idle.append(IdleInterval(mid, prev_end, start, _ready_at(prev_end, schedule, by_id)))
            prev_end = end
        if prev_end < makespan:
            idle.append(IdleInterval(mid, prev_end, makespan, _ready_at(prev_end, schedule, by_id)))
    idle.sort(key=lambda iv: (iv.start, iv.member_id))
    return schedule, idle


# ---------------------------------------------------------------- helpers

def _is_int(x: object) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _ready_at(moment: int, schedule: dict[int, tuple[int, int]], by_id: dict[int, Task]) -> list[int]:
    """Tasks not yet started at ``moment`` whose prerequisites were finished by then."""
    return sorted(
        tid
        for tid, (start, _) in schedule.items()
        if start > moment
        and all(schedule[p][1] <= moment for p in set(by_id[tid]["prerequisites"]))
    )


def _explain_deadlock(now, lists, pointer, owners, by_id, schedule) -> str:
    reasons = []
    for mid, ids in lists.items():
        if pointer[mid] >= len(ids):
            continue
        tid = ids[pointer[mid]]
        unfinished = [
            p for p in sorted(set(by_id[tid]["prerequisites"]))
            if p not in schedule or schedule[p][1] > now
        ]
        elsewhere = [
            o for o in owners[tid]
            if o != mid and (pointer[o] >= len(lists[o]) or lists[o][pointer[o]] != tid)
        ]
        why = []
        if unfinished:
            why.append("prerequisite(s) " + ", ".join(map(str, unfinished)) + " not finished")
        if elsewhere:
            why.append("co-assignee(s) " + ", ".join(elsewhere) + " not at that task")
        reasons.append(f"{mid} waits for task {tid}" + (f" ({'; '.join(why)})" if why else ""))
    return (
        f"the member lists cannot be executed: at hour {now} nothing can start - "
        + "; ".join(reasons)
    )


def _describe_idle(intervals: list[IdleInterval], name_of: dict[str, str]) -> str:
    if not intervals:
        return "none"
    parts = []
    for iv in intervals[:6]:
        text = f"{name_of[iv.member_id]} ({iv.member_id}) idle h {iv.start}-{iv.end}"
        if iv.ready_tasks:
            text += f" while task(s) {', '.join(map(str, iv.ready_tasks))} were ready"
        parts.append(text)
    if len(intervals) > 6:
        parts.append(f"... and {len(intervals) - 6} more intervals")
    return "; ".join(parts)
