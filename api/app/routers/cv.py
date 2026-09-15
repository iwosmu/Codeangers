from fastapi import APIRouter, File, Form, Request, UploadFile

from ..config import settings
from ..envelope import ApiError, Timer, fixture, ok, wants_mock
from ..services.ai_cv import parse_cv

router = APIRouter()

MAX_BYTES = 10 * 1024 * 1024


@router.post("/cv")
async def create_profile(request: Request,
                         name: str | None = Form(default=None),
                         text: str | None = Form(default=None),
                         file: UploadFile | None = File(default=None)):
    # One CV per request. Five people means five parallel requests, so one bad
    # PDF cannot take the whole batch down.
    with Timer() as t:
        if wants_mock(request):
            people = fixture("people.mock.json")["people"]
            pick = next((p for p in people if name and p["name"].lower() == name.lower()), people[0])
            return ok(pick, ms=t.ms, mocked=True)

        if file is None and not text:
            raise ApiError("bad_input", "Send a PDF file or pasted CV text.")

        data = None
        if file is not None:
            data = await file.read()
            if len(data) > MAX_BYTES:
                raise ApiError("bad_input", "That CV is over 10 MB. Export it smaller and try again.")

        profile, warnings = await parse_cv(name=name, text=text, file_bytes=data)
    return ok(profile, warnings, ms=t.ms, model=settings().model_extract)
