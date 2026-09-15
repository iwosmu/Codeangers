"""Generate a dependency-ordered, team-aware task graph for a project with Gemini."""

from .graph import graph_to_tasks, levels, tasks_to_graph, to_pyvis
from .planner import PlannerConfig, PlanningError, PlanResult, TaskPlanner
from .schema import GRAPH_SCHEMA, Edge, Graph, Node, Task
from .validation import (
    IdleInterval,
    ValidationResult,
    simulate_schedule,
    validate,
    validate_graph,
)

__all__ = [
    "Edge",
    "GRAPH_SCHEMA",
    "Graph",
    "IdleInterval",
    "Node",
    "PlannerConfig",
    "PlanningError",
    "PlanResult",
    "Task",
    "TaskPlanner",
    "ValidationResult",
    "graph_to_tasks",
    "levels",
    "simulate_schedule",
    "tasks_to_graph",
    "to_pyvis",
    "validate",
    "validate_graph",
]
