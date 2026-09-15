"""Assign one specific team to a validated task list with Gemini and order each member's work."""

from .assigner import AssignerConfig, AssignmentError, AssignResult, TaskAssigner
from .schema import (
    ASSIGNMENT_SCHEMA,
    Assignment,
    Member,
    Note,
    PersonAssignment,
    Task,
    TaskAssignment,
)
from .tasks import check_tasks, critical_path_hours, load_tasks
from .team import parse_members
from .validation import (
    Deadlock,
    IdleInterval,
    ValidationResult,
    simulate_schedule,
    validate_assignment,
)

__all__ = [
    "ASSIGNMENT_SCHEMA",
    "AssignResult",
    "AssignerConfig",
    "Assignment",
    "AssignmentError",
    "Deadlock",
    "IdleInterval",
    "Member",
    "Note",
    "PersonAssignment",
    "Task",
    "TaskAssignment",
    "TaskAssigner",
    "ValidationResult",
    "check_tasks",
    "critical_path_hours",
    "load_tasks",
    "parse_members",
    "simulate_schedule",
    "validate_assignment",
]
