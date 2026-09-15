"""Deterministic Markdown. The model never controls document structure or HTML."""
import re
from ..brief_schemas import AREAS, AREA_LABELS, BriefInput, Claim, ProjectBrief, TeamBrief
from .brief_files import Source


def safe(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = re.sub(r"([\\`*_{}\[\]<>|])", r"\\\1", value)
    return re.sub(r"^(#{1,6}|[-+]|[0-9]+\.)(?= )", r"\\\1", value)


def bullets(items: list[str]) -> str:
    return "\n".join("- " + i for i in items) if items else "not stated"


def render_team(team: TeamBrief, request: BriefInput, sources: list[Source]) -> str:
    labels = {m.id: m.label or f"Member {i + 1}" for i, m in enumerate(request.members)}
    names = {m.id: m.cv_name.text if m.cv_name.text != "not stated" else labels[m.id] for m in team.members}
    source_labels = {s.id: s.label for s in sources}
    def refs(mid: str, ids: list[str]) -> str:
        return " ".join(f"[{safe(mid)}:{safe(e)}]" for e in ids)
    def claim(mid: str, c: Claim) -> str:
        return safe(c.text) + (" " + refs(mid, c.evidence_ids) if c.evidence_ids else "")
    lines = [f"# {safe(request.setup.name or 'Your team')} — team understanding", "",
             "Evidence-based suggestions for discussion. Coverage describes supplied CV evidence, not a person's ability or preference.", ""]
    for m in team.members:
        evidence = {e.id: e for e in m.evidence}
        def role(c):
            if c.text == "not stated":
                return "not stated"
            def excerpt(ref):
                quote = evidence[ref].quote
                if len(quote) > 320:
                    quote = quote[:320].rsplit(" ", 1)[0] + "…"
                return "“" + safe(quote) + "”"
            justification = "; ".join(excerpt(ref) for ref in c.evidence_ids[:2])
            return claim(m.id, c) + " — CV excerpt: " + justification + " Full passages appear in CV evidence below."
        lines += [f"## {safe(names[m.id])}", "", f"Member ID: {safe(m.id)}", "", f"CV name: {claim(m.id, m.cv_name)}", "",
                  "### Likely roles", "", bullets([role(c) for c in m.roles]), "",
                  "### Strengths", "", bullets([claim(m.id, c) for c in m.strengths]), "",
                  "### Gaps / unknowns", "", bullets([f"No evidence of {safe(g.area)} in the supplied CV — not stated. {safe(g.relevance)}" for g in m.gaps]), "",
                  "### Stack & tools", "", bullets([claim(m.id, c) for c in m.stack]), "",
                  "### Experience level", "", claim(m.id, m.experience), "",
                  "### Working-style signals", "", bullets([claim(m.id, c) for c in m.working_style]), "",
                  "### CV evidence", "", bullets([f"{refs(m.id, [e.id])} “{safe(e.quote)}” — {safe(source_labels[e.source_id])}, {safe(e.location)}" for e in m.evidence]), ""]
    cells = {m.id: {c.area: c for c in m.coverage} for m in team.members}
    lines += ["## Team overview", "", "### Coverage map", "",
              "●● = strong explicit evidence · ● = some explicit evidence · – = not stated / unconfirmed", "",
              "| Area | " + " | ".join(safe(names[m.id]) for m in team.members) + " |",
              "| --- | " + " | ".join("---" for _ in team.members) + " |"]
    gaps, overlaps, leads = [], [], []
    scores = {"none": 0, "some": 1, "strong": 2}
    symbols = {"none": "–", "some": "●", "strong": "●●"}
    for area in AREAS:
        values = [cells[m.id][area] for m in team.members]
        lines.append("| " + AREA_LABELS[area] + " | " + " | ".join(symbols[v.level] + (" " + refs(m.id, v.evidence_ids) if v.evidence_ids else "") for m, v in zip(team.members, values)) + " |")
        supported = [m for m in team.members if cells[m.id][area].level != "none"]
        def person(m):
            return safe(names[m.id]) + " " + refs(m.id, cells[m.id][area].evidence_ids)
        if not supported:
            gaps.append(f"{AREA_LABELS[area]}: not stated / unconfirmed across the supplied CVs. Confirm whether the project needs this area.")
        else:
            if len(supported) > 1:
                overlaps.append(f"{AREA_LABELS[area]}: " + "; ".join(person(m) for m in supported))
            best = max(scores[cells[m.id][area].level] for m in supported)
            candidates = [m for m in supported if scores[cells[m.id][area].level] == best]
            leads.append(f"{AREA_LABELS[area]}: " + "; ".join(person(m) for m in candidates) + " — candidate(s) to discuss based on CV coverage; interest and availability not stated.")
    if team._coverage_review_notes:
        lines += ["", "### Coverage checks to review", "", bullets([safe(n) for n in team._coverage_review_notes])]
    lines += ["", "### Team gaps", "", bullets(gaps), "", "### Overlaps", "", bullets(overlaps), "",
              "### Suggested natural leads", "", bullets(leads), "", "### Questions for the team", "", bullets([safe(q) for q in team.open_questions]), "",
              "## Source notes", "", bullets([safe(s.id) + ": " + safe(s.label) + (" — " + safe(s.notes) if s.notes else "") for s in sources]), "",
              "Text citations are checked against the supplied text. Quotes from PDFs and images are transcribed by Gemini; check them against the original CV before relying on them."]
    return "\n".join(lines) + "\n"


def render_project(project: ProjectBrief, request: BriefInput, sources: list[Source]) -> str:
    def statement(s):
        return safe(s.text) + (" " + " ".join(f"[{safe(i)}]" for i in s.source_ids) if s.source_ids else "")
    lines = [f"# {safe(request.setup.name or 'Your project')} — project understanding", ""]
    for title, value in [("One-liner", project.one_liner), ("Problem", project.problem), ("Target user", project.target_user),
                         ("Vision", project.vision), ("Value proposition", project.value_proposition)]:
        lines += [f"## {title}", "", statement(value), ""]
    lines += ["## Key deliverables", "", "### Must-have", "", bullets([statement(s) for s in project.must_have]), "",
              "### Nice-to-have", "", bullets([statement(s) for s in project.nice_to_have]), "",
              "## Constraints & context", "", bullets([statement(s) for s in project.constraints]), "",
              "## Success criteria", "", bullets([statement(s) for s in project.success_criteria]), "",
              "### Intended impact", "", statement(project.impact), "",
              "## Open questions", "", bullets([safe(q) for q in project.open_questions]), "",
              "## Source notes", ""]
    labels = {s.id: s for s in sources}
    lines += [bullets([f"[{safe(n.source_id)}] {safe(labels[n.source_id].label)}: {safe(n.contribution)}" + (" " + safe(labels[n.source_id].notes) if labels[n.source_id].notes else "") for n in project.source_notes]), "",
              "### Contradictions to resolve", "", bullets([statement(s) for s in project.contradictions]) if project.contradictions else "None identified in the supplied material.", ""]
    return "\n".join(lines)
