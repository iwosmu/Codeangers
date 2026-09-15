"""Members of the team document rendered by the brief pipeline (``team.md``).

The renderer writes one ``## <name>`` section per member with a ``Member ID: mN``
line right below it, then a ``## Team overview`` section. Names are Markdown
escaped in the document; they are unescaped here so they match what the model
sees as the heading text.
"""

from __future__ import annotations

import re

from .schema import Member

HEADING = re.compile(r"^## (?P<name>.+?)\s*$", re.MULTILINE)
MEMBER_ID = re.compile(r"^Member ID: (?P<id>m\d+)\s*$", re.MULTILINE)
ESCAPED = re.compile(r"\\([\\`*_{}\[\]<>|#+.\-])")


def unescape(text: str) -> str:
    return ESCAPED.sub(r"\1", text).strip()


def parse_members(team_md: str) -> list[Member]:
    """Every ``## <name>`` section that carries a ``Member ID: mN`` line, in document order.

    Returns an empty list for a document without such sections; the caller
    decides whether that is an error.
    """
    members: list[Member] = []
    headings = list(HEADING.finditer(team_md))
    for i, heading in enumerate(headings):
        end = headings[i + 1].start() if i + 1 < len(headings) else len(team_md)
        section = team_md[heading.end():end]
        match = MEMBER_ID.search(section)
        if match:
            members.append({"id": match.group("id"), "name": unescape(heading.group("name"))})
    ids = [m["id"] for m in members]
    if len(ids) != len(set(ids)):
        raise ValueError("the team document uses the same Member ID for two members")
    return members
