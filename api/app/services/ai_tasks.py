from ..envelope import ApiError
from ..schemas import ProjectModel, TaskGraph, Warning

# OWNER D  --  stage 3a: a ProjectModel in, a task graph out.
#
# The model writes tasks and dependencies. Before returning, run the graph checks
# below. Cycles will happen -- this is not a risk, it is a certainty at 40 tasks.
# On errors: send the issues back once, ask for a corrected graph, and if the
# second attempt still fails raise plan_invalid. Never loop.

RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["tasks"],
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "sectionId", "blocks", "kind", "dependsOn"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "sectionId": {"type": "string"},
                    "blocks": {"type": "integer", "enum": [1, 2, 4]},
                    "kind": {"type": "string", "enum": ["contract", "impl", "integration"]},
                    "dependsOn": {"type": "array", "items": {"type": "string"}},
                },
            },
        }
    },
}


def check_graph(project: ProjectModel, graph: TaskGraph) -> list[Warning]:
    # Pure. No network. Returns errors that must be repaired and warnings that may stand.
    out: list[Warning] = []
    ids = {t.id for t in graph.tasks}
    section_ids = {s.id for s in project.sections}

    for t in graph.tasks:
        for dep in t.depends_on:
            if dep not in ids:
                out.append(Warning(code="dangling_dep", severity="error", task_ids=[t.id],
                                   message="Task " + t.id + " depends on " + dep + ", which does not exist."))
        if t.section_id not in section_ids:
            out.append(Warning(code="unknown_ref", severity="error", task_ids=[t.id],
                               message="Task " + t.id + " belongs to unknown section " + t.section_id + "."))

    # cycle detection, iterative DFS with colours
    colour: dict[str, int] = {t.id: 0 for t in graph.tasks}
    deps = {t.id: [d for d in t.depends_on if d in ids] for t in graph.tasks}
    for start in list(colour):
        if colour[start] != 0:
            continue
        stack = [(start, iter(deps[start]))]
        colour[start] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                colour[node] = 2
                stack.pop()
            elif colour[nxt] == 1:
                out.append(Warning(code="cycle", severity="error", task_ids=[node, nxt],
                                   message="Circular dependency between " + node + " and " + nxt + "."))
                colour[nxt] = 2
            elif colour[nxt] == 0:
                colour[nxt] = 1
                stack.append((nxt, iter(deps[nxt])))

    # a dependency that crosses a section boundary with no contract task in front of it
    by_id = {t.id: t for t in graph.tasks}
    for t in graph.tasks:
        for dep in t.depends_on:
            d = by_id.get(dep)
            if d and d.section_id != t.section_id and t.kind != "contract" and d.kind != "contract":
                out.append(Warning(code="missing_contract", severity="warn", task_ids=[dep, t.id],
                                   message="Cross-section dependency " + dep + " to " + t.id
                                           + " has no contract task in front of it, so both sides will block."))

    total = sum(t.blocks for t in graph.tasks)
    if total > project.horizon_blocks * 5:
        out.append(Warning(code="over_horizon", severity="warn",
                           message="Tasks total " + str(total) + " blocks, more than five people can fit in the horizon."))
    return out


async def generate_tasks(project: ProjectModel) -> tuple[TaskGraph, list[Warning]]:
    raise ApiError(
        "internal",
        "generate_tasks is not implemented yet. Run with MOCK_ONLY=true or send the header x-mock: 1.",
    )
