"""Structured, source-linked skill fit for the application assignment stage.

References are checked mechanically; whether a quotation supports a particular
skill remains a model judgement exposed for the team to review.
"""
from copy import deepcopy
from typing import Literal

from pydantic import Field, TypeAdapter, ValidationError

from ..brief_schemas import StrictModel, MemberBrief, gemini_schema
from .schema import ASSIGNMENT_SCHEMA


class Match(StrictModel):
    member_id: str
    match: Literal['direct', 'adjacent', 'unconfirmed']
    matched_skills: list[str] = Field(max_length=12)
    missing_skills: list[str] = Field(max_length=12)
    evidence_ids: list[str] = Field(max_length=12, description="Local evidence IDs from this member's CV only, e.g. e1. Cite relevant work, not their name or contact details.")
    reason: str = Field(min_length=1, max_length=700)
    learning_step: str = Field(max_length=500, description="For adjacent/unconfirmed: concrete first practice or check before taking the task. Empty for direct.")


class TaskFit(StrictModel):
    task_id: int = Field(strict=True, ge=1)
    required_skills: list[str] = Field(min_length=1, max_length=12, description="Concrete skills explicitly needed by the task. Reuse these exact strings in matched, missing and team_missing_skills.")
    team_missing_skills: list[str] = Field(max_length=12, description="Required skills with no direct CV evidence anywhere in the entire team, after comparing ALL members. No evidence is not proof of inability.")
    matches: list[Match] = Field(min_length=1, max_length=8, description="One assessment for every assigned member, identified by stable member_id. Direct = all required skills evidenced; adjacent = relevant transferable CV evidence with a learning gap; unconfirmed = no relevant evidence to rank learning fit.")


FIT_ASSIGNMENT_SCHEMA = deepcopy(ASSIGNMENT_SCHEMA)
FIT_ASSIGNMENT_SCHEMA['properties']['fit'] = {'type': 'array', 'items': gemini_schema(TaskFit), 'description': 'Every task exactly once, with skill gaps and the evidence for each assigned person.'}
FIT_ASSIGNMENT_SCHEMA['required'].append('fit')


def ground_explanations(assignment: dict, profiles: list[MemberBrief]) -> None:
    """Expose literal CV excerpts instead of unchecked narrative relationships.

    The model still proposes fit and learning gaps. Its free-form reason can
    accidentally claim a tool was used on a project when it was only listed
    elsewhere, so the returned explanation is rendered from validated refs.
    """
    members = {p.id: p for p in profiles}
    for fit in assignment['fit']:
        for match in fit['matches']:
            if match['match'] == 'unconfirmed':
                match['reason'] = 'Relevant experience is not stated in the supplied CV. Confirm this proposed owner with the team.'
                continue
            evidence = {e.id: e for e in members[match['member_id']].evidence}
            excerpts = []
            for ref in match['evidence_ids'][:2]:
                quote = ' '.join(evidence[ref].quote.split())
                if len(quote) > 230:
                    quote = quote[:230].rsplit(' ', 1)[0] + '…'
                excerpts.append(f'“{quote}”')
            lead = 'Direct match suggested from CV evidence: ' if match['match'] == 'direct' else 'Transferable experience suggested from CV evidence: '
            match['reason'] = lead + ' '.join(excerpts)


def validate_fit(assignment: dict, profiles: list[MemberBrief], tasks: list[dict]) -> list[str]:
    try:
        fits = TypeAdapter(list[TaskFit]).validate_python(assignment.get('fit'))
    except ValidationError:
        return ['fit must contain valid structured skill assessments for every task and assigned member']
    errors = []
    task_ids = {t['id'] for t in tasks}
    if len(fits) != len(task_ids) or {f.task_id for f in fits} != task_ids:
        errors.append('fit must contain every task exactly once')
    profiles_by_id = {p.id: p for p in profiles}
    # Exact explicit stack entries are a cheap contradiction check. Broader
    # semantic equivalence remains part of the model's evidence review.
    known_skills = {claim.text.casefold() for p in profiles for claim in p.stack
                    if claim.evidence_ids and set(claim.evidence_ids) <= {e.id for e in p.evidence}}
    for fit in fits:
        owners = {p['member_id'] for p in assignment['people'] if fit.task_id in p['task_ids']}
        if len(fit.matches) != len(owners) or {m.member_id for m in fit.matches} != owners:
            errors.append(f'task {fit.task_id}: fit matches must correspond exactly to assigned member IDs')
        required = set(fit.required_skills)
        if len(required) != len(fit.required_skills) or not all(s.strip() for s in required):
            errors.append(f'task {fit.task_id}: required skills must be nonempty and unique')
        gaps = set(fit.team_missing_skills)
        if any(skill.casefold() in known_skills for skill in gaps):
            errors.append(f'task {fit.task_id}: team_missing_skills contradicts an explicitly evidenced team stack entry')
        if not gaps <= required:
            errors.append(f'task {fit.task_id}: team gaps must be required skills')
        for match in fit.matches:
            p = profiles_by_id.get(match.member_id)
            if p is None:
                errors.append(f'task {fit.task_id}: unknown match member {match.member_id}')
                continue
            refs = {e.id for e in p.evidence}
            if not set(match.evidence_ids) <= refs:
                errors.append(f'task {fit.task_id}, {p.id}: evidence IDs must exist in that member CV')
            matched, missing = set(match.matched_skills), set(match.missing_skills)
            if matched & missing or matched | missing != required or not gaps <= missing:
                errors.append(f'task {fit.task_id}, {p.id}: partition required skills into evidenced and missing; team gaps must stay missing')
            if match.match == 'direct' and (missing or not match.evidence_ids or match.learning_step):
                errors.append(f'task {fit.task_id}, {p.id}: direct match requires CV evidence for all skills and no learning gap')
            if match.match == 'adjacent' and (not missing or not match.evidence_ids or not match.learning_step.strip()):
                errors.append(f'task {fit.task_id}, {p.id}: adjacent match needs transferable CV evidence, missing skills and a learning step')
            if match.match == 'unconfirmed' and (matched or match.evidence_ids or not match.learning_step.strip()):
                errors.append(f'task {fit.task_id}, {p.id}: unconfirmed fit cannot claim supported skills or transferable evidence; give a first check')
    return errors
