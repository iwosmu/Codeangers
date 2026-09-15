from collections import defaultdict

from ..schemas import Metrics, PersonProfile, Plan, ProjectModel, TaskGraph, Warning

# OWNER D  --  the referee. Pure, synchronous, no network.
#
# This is not a solver. It never fixes, ranks or reorders anything. It states what
# is wrong and hands the plan back. Its twin lives in web/src/lib/validate.ts and
# runs in the browser after every drag, so the two must agree.
#
# error -> blocks the plan and triggers one repair round
# warn  -> shown in the warnings panel, the user decides


def validate_plan(project: ProjectModel, people: list[PersonProfile],
                  graph: TaskGraph, plan: Plan) -> list[Warning]:
    out: list[Warning] = []
    tasks = {t.id: t for t in graph.tasks}
    person_ids = {p.id for p in people}
    section_ids = {s.id for s in project.sections}
    end_of: dict[str, int] = {}
    by_person: dict[str, list] = defaultdict(list)

    for a in plan.assignments:
        if a.task_id not in tasks:
            out.append(Warning(code="unknown_ref", severity="error", task_ids=[a.task_id],
                               message="Plan assigns task " + a.task_id + ", which is not in the graph."))
            continue
        if a.person_id not in person_ids:
            out.append(Warning(code="unknown_ref", severity="error", person_ids=[a.person_id],
                               message="Plan assigns work to " + a.person_id + ", who is not on the team."))
            continue
        end_of[a.task_id] = a.end_block
        by_person[a.person_id].append(a)

    # 1. one person, two tasks, same time
    for pid, items in by_person.items():
        items.sort(key=lambda x: x.start_block)
        for prev, cur in zip(items, items[1:]):
            if cur.start_block < prev.end_block:
                out.append(Warning(code="overlap", severity="error", person_ids=[pid],
                                   task_ids=[prev.task_id, cur.task_id],
                                   message=_name(people, pid) + " is on " + prev.task_id + " and "
                                           + cur.task_id + " at the same time."))

    # 2. a task that starts before something it depends on has finished
    for a in plan.assignments:
        t = tasks.get(a.task_id)
        if not t:
            continue
        for dep in t.depends_on:
            dep_end = end_of.get(dep)
            if dep_end is None:
                out.append(Warning(code="orphan_task", severity="error", task_ids=[dep],
                                   message="Task " + a.task_id + " depends on " + dep + ", which nobody is doing."))
            elif a.start_block < dep_end:
                out.append(Warning(code="dep_violation", severity="error", task_ids=[dep, a.task_id],
                                   message=a.task_id + " starts at block " + str(a.start_block) + " but "
                                           + dep + " is not done until " + str(dep_end) + "."))

    # 3. tasks nobody picked up
    for t in graph.tasks:
        if t.id not in end_of:
            out.append(Warning(code="orphan_task", severity="error", task_ids=[t.id],
                               message="Nobody is assigned to " + t.id + " (" + t.title + ")."))

    # 4. sections and people
    for p in people:
        sec = plan.section_of.get(p.id)
        if sec is None:
            out.append(Warning(code="unknown_ref", severity="error", person_ids=[p.id],
                               message=p.name + " has no section."))
        elif sec not in section_ids:
            out.append(Warning(code="unknown_ref", severity="error", person_ids=[p.id],
                               message=p.name + " is in unknown section " + sec + "."))
        if not by_person.get(p.id):
            out.append(Warning(code="idle_person", severity="warn", person_ids=[p.id],
                               message=p.name + " has no tasks at all."))

    # 5. horizon
    for pid, items in by_person.items():
        last = max((x.end_block for x in items), default=0)
        if last > project.horizon_blocks:
            out.append(Warning(code="over_horizon", severity="warn", person_ids=[pid],
                               message=_name(people, pid) + " is still working at block " + str(last)
                                       + ", past the horizon of " + str(project.horizon_blocks) + "."))
    return out


def metrics(project: ProjectModel, people: list[PersonProfile],
            graph: TaskGraph, plan: Plan) -> Metrics:
    # Derived from the model's own output, so the numbers are real.
    # parallelism = share of elapsed blocks in which every person has work.
    tasks = {t.id: t for t in graph.tasks}
    horizon = max((a.end_block for a in plan.assignments), default=0)
    if horizon == 0 or not people:
        return Metrics(parallelism_score=0.0, critical_path=[])

    busy = [[False] * horizon for _ in people]
    index = {p.id: i for i, p in enumerate(people)}
    for a in plan.assignments:
        i = index.get(a.person_id)
        if i is None:
            continue
        for b in range(max(0, a.start_block), min(horizon, a.end_block)):
            busy[i][b] = True
    full = sum(1 for b in range(horizon) if all(busy[i][b] for i in range(len(people))))

    # longest dependency chain by blocks
    memo: dict[str, tuple[int, list[str]]] = {}

    def longest(tid: str) -> tuple[int, list[str]]:
        if tid in memo:
            return memo[tid]
        t = tasks.get(tid)
        if not t:
            return 0, []
        best_len, best_path = 0, []
        for dep in t.depends_on:
            n, path = longest(dep)
            if n > best_len:
                best_len, best_path = n, path
        memo[tid] = (best_len + t.blocks, best_path + [tid])
        return memo[tid]

    chain: list[str] = []
    best = 0
    for t in graph.tasks:
        n, path = longest(t.id)
        if n > best:
            best, chain = n, path

    return Metrics(parallelism_score=round(full / horizon, 3), critical_path=chain)


def _name(people: list[PersonProfile], pid: str) -> str:
    for p in people:
        if p.id == pid:
            return p.name
    return pid
