"""Fail closed on bad attribution; native-media transcription still needs human review."""
import re
import unicodedata
from ..brief_schemas import AREAS, AREA_LABELS, BriefInput, ProjectBrief, TeamBrief
from ..envelope import ApiError
from .brief_files import Source


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


def invalid(message: str):
    raise ApiError("model_invalid_json", message, retryable=True)


def coverage_has_direct_signal(area: str, quotes: list[str]) -> bool:
    """Conservative support gates, not skill inference or an exhaustive taxonomy.

    These gates only remove unsupported scores. They never award experience,
    and every removed score is surfaced for human review with its original refs.
    """
    patterns = {
        'backend': r'\b(API|APIs|endpoints?|backend|back-end|server-side|microservices?|REST|GraphQL|gRPC|FastAPI|Django|Flask|PHP|Node\.?js|Express|NestJS|Spring|ASP\.NET|Rails|Laravel)\b',
        'devops': r'\b(deploy\w*|hosting|hosted|CI|CD|continuous integration|continuous delivery|Docker|Kubernetes|K8s|Terraform|Ansible|Vercel|Netlify|AWS|Azure|GCP|SLURM|GitHub Actions|GitLab CI|Jenkins)\b',
        'pitch': r'\b(teach\w*|taught|tutor\w*|trainer|present\w*|speaking|speaker|negotiat\w*|liaison|stakeholder|corporate relations|public speaking)\b',
    }
    if area not in patterns:
        return True
    for quote in quotes:
        if area == 'pitch':
            # Authorship and collective outputs do not identify the speaker.
            quote = re.sub(r'[^.!?]*(?:group outputs|team outputs|group presentation|team presentation|group presented|team presented|poster)[^.!?]*(?:[.!?]|$)', '', quote, flags=re.I)
        if re.search(patterns[area], quote, flags=re.I):
            return True
    return False


def validate_team(team: TeamBrief, request: BriefInput, sources: list[Source]) -> TeamBrief:
    team._coverage_review_notes = []
    expected = {m.id for m in request.members}
    if len(team.members) != len(expected) or {m.id for m in team.members} != expected:
        invalid("Gemini did not return exactly one profile for every team member. Please retry.")
    by_id = {s.id: s for s in sources}
    for member in team.members:
        evidence = {e.id: e for e in member.evidence}
        if len(evidence) != len(member.evidence):
            invalid("Gemini returned duplicate evidence identifiers. Please retry.")
        for item in member.evidence:
            source = by_id.get(item.source_id)
            if source is None or source.owner != member.id:
                invalid("A CV citation referred to the wrong member or an unknown source. Please retry.")
            # Verify text quotes against exactly that member's source. For native media,
            # require an actual supplied asset rather than letting an arbitrary location bypass validation.
            if item.source_part == "text":
                if not source.text or normalized(item.quote) not in normalized(source.text):
                    invalid("A quoted passage could not be found in its CV text. Please retry or inspect the original file.")
            elif item.source_part not in {a.location for a in source.assets if a.mime != "text/plain"}:
                invalid("A CV citation referred to a missing image or document part. Please retry.")
        claims = [member.github, member.cv_name, *member.roles, *member.strengths, *member.stack, member.experience, *member.working_style]
        for claim in claims:
            if claim.text == "not stated":
                if claim.evidence_ids:
                    invalid("An unknown personal detail carried a misleading citation.")
            elif not claim.evidence_ids or any(ref not in evidence for ref in claim.evidence_ids):
                invalid("A personal claim was missing valid CV evidence. Please retry.")
        if member.github.text != "not stated":
            username = member.github.text
            quotes = " ".join(evidence[ref].quote for ref in member.github.evidence_ids)
            # A personal profile URL, not an organization/project repository link.
            profile = r"(?<![\w./-])(?:https?://)?(?:www\.)?github\.com/" + re.escape(username) + r"/?(?=$|[\s),;<>])"
            if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", username) or not re.search(profile, quotes, re.I):
                invalid("A GitHub username was not supported by a personal profile URL in its CV citation.")
        # Names and individual tool labels must occur in their quoted CV evidence,
        # not merely attach an unrelated, otherwise valid quote to a new skill.
        for exact in [member.cv_name, *member.stack]:
            if exact.text != "not stated":
                quoted = " ".join(evidence[ref].quote for ref in exact.evidence_ids)
                if normalized(exact.text).casefold() not in normalized(quoted).casefold():
                    invalid("A name or tool label was not present in its cited CV evidence. Please retry.")
        if {c.area for c in member.coverage} != set(AREAS):
            invalid("The coverage map omitted or duplicated an area. Please retry.")
        for cell in member.coverage:
            if cell.level == "none" and cell.evidence_ids:
                invalid("An empty coverage cell unexpectedly cited positive evidence.")
            if cell.level != "none" and (not cell.evidence_ids or any(ref not in evidence for ref in cell.evidence_ids)):
                invalid("A coverage claim was missing CV evidence. Please retry.")
            if cell.level != "none" and not coverage_has_direct_signal(cell.area, [evidence[ref].quote for ref in cell.evidence_ids]):
                refs = ' '.join(f'[{member.id}:{ref}]' for ref in cell.evidence_ids)
                team._coverage_review_notes.append(f'{member.id} — {AREA_LABELS[cell.area]}: model score withheld because the cited passages did not contain a recognized direct signal for this area. Review {refs}; the capability remains unconfirmed, not disproven.')
                cell.level = "none"
                cell.evidence_ids = []
    team.members.sort(key=lambda m: [x.id for x in request.members].index(m.id))
    return team


def validate_project(project: ProjectBrief, sources: list[Source]) -> ProjectBrief:
    ids = {s.id for s in sources}
    if len(project.source_notes) != len(ids) or {n.source_id for n in project.source_notes} != ids:
        invalid("Gemini did not account for every project source. Please retry.")
    statements = [project.one_liner, project.problem, project.target_user, project.vision, project.value_proposition,
                  project.impact, *project.must_have, *project.nice_to_have, *project.constraints,
                  *project.success_criteria, *project.contradictions]
    for statement in statements:
        if statement.text == "not stated":
            if statement.source_ids:
                invalid("An unknown project detail carried a misleading citation.")
        elif not statement.source_ids or any(s not in ids for s in statement.source_ids):
            invalid("A project statement referenced missing source material. Please retry.")
    for contradiction in project.contradictions:
        if len(set(contradiction.source_ids)) < 2:
            # One source can contradict itself, so retain it if clearly cited; no automatic winner.
            if not contradiction.source_ids:
                invalid("A contradiction lacked a source.")
    return project
