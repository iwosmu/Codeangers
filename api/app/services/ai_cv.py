from ..envelope import ApiError
from ..schemas import CATEGORIES, LEVEL_SCALE, PersonProfile, Warning

# OWNER D  --  stage 1: a CV in, a skill profile out.
#
# Two rules that are not negotiable:
#   1. No PDF parser. Hand the PDF bytes to Gemini through gemini.generate_json(files=[...]).
#   2. Every skill carries a verbatim `evidence` quote from the CV. Drop any skill
#      that comes back without one -- that quote is the only defence against
#      invented skills, and the UI shows it on hover.
#
# Paste LEVEL_SCALE into the prompt verbatim so levels mean the same thing for
# every person. If the whole team fits in one call, score them all at once: one
# shared scale beats five independent ones.

RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["name", "skills", "prefers", "avoids"],
    "properties": {
        "name": {"type": "string"},
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["category", "label", "level", "evidence"],
                "properties": {
                    "category": {"type": "string", "enum": CATEGORIES},
                    "label": {"type": "string"},
                    "level": {"type": "integer", "minimum": 1, "maximum": 5},
                    "evidence": {"type": "string"},
                },
            },
        },
        "prefers": {"type": "array", "items": {"type": "string", "enum": CATEGORIES}},
        "avoids": {"type": "array", "items": {"type": "string", "enum": CATEGORIES}},
    },
}

PROMPT_HEADER = (
    "Extract a skill profile from this CV. Use only these categories: "
    + ", ".join(CATEGORIES)
    + ". Level scale: " + LEVEL_SCALE
    + " Every skill must include an `evidence` field quoting the CV verbatim. "
      "If you cannot quote the CV for a skill, do not list that skill."
)


async def parse_cv(*, name: str | None, text: str | None,
                   file_bytes: bytes | None) -> tuple[PersonProfile, list[Warning]]:
    raise ApiError(
        "internal",
        "parse_cv is not implemented yet. Run with MOCK_ONLY=true or send the header x-mock: 1.",
    )
