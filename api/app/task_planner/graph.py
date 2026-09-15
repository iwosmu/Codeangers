"""Conversions between the PyVis-shaped graph and the flat task list, plus an
optional PyVis renderer.

``pyvis`` is imported lazily inside ``to_pyvis`` so the rest of the package
does not depend on it.
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any

from .schema import Graph, Task

if TYPE_CHECKING:  # pragma: no cover
    from pyvis.network import Network


def graph_to_tasks(graph: Graph) -> list[Task]:
    """Nodes + edges -> flat tasks with ``prerequisites`` lists.

    Assumes the graph passed ``validate_graph`` (unique ids, edges resolve).
    Duplicate edges collapse; order of prerequisites follows edge order.
    """
    prereqs: dict[int, list[int]] = {n["id"]: [] for n in graph["nodes"]}
    for e in graph["edges"]:
        if e["from"] not in prereqs[e["to"]]:
            prereqs[e["to"]].append(e["from"])
    tasks: list[Task] = []
    for n in graph["nodes"]:
        tasks.append(
            {
                "id": n["id"],
                "name": n["label"],
                "description": n["title"],
                "group": n["group"],
                "prerequisites": prereqs[n["id"]],
                "estimated_time_hours": n["estimated_time_hours"],
                "people_needed": n["people_needed"],
            }
        )
    return tasks


def tasks_to_graph(tasks: list[Task]) -> Graph:
    """Inverse of ``graph_to_tasks``; edges run prerequisite -> task."""
    nodes = [
        {
            "id": t["id"],
            "label": t["name"],
            "title": t["description"],
            "group": t.get("group", "task"),
            "estimated_time_hours": t["estimated_time_hours"],
            "people_needed": t["people_needed"],
        }
        for t in tasks
    ]
    edges = [{"from": p, "to": t["id"]} for t in tasks for p in t["prerequisites"]]
    return {"nodes": nodes, "edges": edges}


def levels(graph: Graph) -> dict[int, int]:
    """Depth of each node = length of the longest chain of prerequisites
    before it (roots are 0). Useful as vis.js ``level`` for hierarchical
    layouts. Requires an acyclic graph."""
    ids = [n["id"] for n in graph["nodes"]]
    indeg = {i: 0 for i in ids}
    out: dict[int, list[int]] = {i: [] for i in ids}
    for e in graph["edges"]:
        indeg[e["to"]] += 1
        out[e["from"]].append(e["to"])
    level = {i: 0 for i in ids}
    queue = deque(i for i in ids if indeg[i] == 0)
    seen = 0
    while queue:
        i = queue.popleft()
        seen += 1
        for d in out[i]:
            level[d] = max(level[d], level[i] + 1)
            indeg[d] -= 1
            if indeg[d] == 0:
                queue.append(d)
    if seen != len(ids):
        raise ValueError("graph contains a cycle")
    return level


def to_pyvis(
    graph: Graph,
    *,
    hierarchical: bool = True,
    height: str = "800px",
    width: str = "100%",
    **network_kwargs: Any,
) -> "Network":
    """Build a ``pyvis.network.Network`` from the graph.

    Nodes keep every field from the JSON; the tooltip gets the estimate and
    head-count appended. With ``hierarchical=True`` nodes are arranged
    left-to-right by dependency depth. Call ``.write_html(path)`` or
    ``.show(path)`` on the result.
    """
    from pyvis.network import Network  # optional dependency

    net = Network(height=height, width=width, directed=True, **network_kwargs)
    depth = levels(graph) if hierarchical else {}
    for n in graph["nodes"]:
        extra = {k: v for k, v in n.items() if k not in ("id", "label", "title")}
        tooltip = (
            f"{n['title']}\n\n"
            f"{n['estimated_time_hours']} h - {n['people_needed']} "
            f"{'person' if n['people_needed'] == 1 else 'people'}"
        )
        if hierarchical:
            extra["level"] = depth[n["id"]]
        net.add_node(n["id"], label=n["label"], title=tooltip, **extra)
    for e in graph["edges"]:
        net.add_edge(e["from"], e["to"])
    if hierarchical:
        # pyvis strips whitespace from this string, so keep values space-free.
        net.set_options(
            '{"layout":{"hierarchical":{"enabled":true,"direction":"LR",'
            '"sortMethod":"directed","levelSeparation":220,"nodeSpacing":140}},'
            '"physics":{"enabled":false},'
            '"edges":{"smooth":{"type":"cubicBezier","forceDirection":"horizontal"}}}'
        )
    return net
