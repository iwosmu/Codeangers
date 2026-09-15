import json
import time
from pathlib import Path
from typing import Any, Literal

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import FIXTURES, settings

ErrorCode = Literal[
    "bad_input",           # 400 our validation rejected the request
    "model_invalid_json",  # 502 model returned unparseable output
    "model_failed",        # 502 model call errored
    "plan_invalid",        # 422 validator rejected the plan and the repair round failed
    "rate_limited",        # 429 free-tier quota, retryable
    "internal",            # 500
]

STATUS = {
    "bad_input": 400,
    "model_invalid_json": 502,
    "model_failed": 502,
    "plan_invalid": 422,
    "rate_limited": 429,
    "internal": 500,
}


class ApiError(Exception):
    # Raise this anywhere. Never return a bare dict with an error string in it.
    def __init__(self, code: ErrorCode, message: str, retryable: bool = False):
        self.code, self.message, self.retryable = code, message, retryable
        super().__init__(message)


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=STATUS[exc.code],
        content={"ok": False, "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable}},
    )


async def unhandled_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": {"code": "internal", "message": str(exc) or "Something broke.", "retryable": False}},
    )


class Timer:
    # Readable both inside and after the with-block.
    def __enter__(self):
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *_):
        return False

    @property
    def ms(self) -> int:
        return int((time.perf_counter() - self.t0) * 1000)


def ok(data: Any, warnings: list | None = None, *, ms: int = 0,
       model: str | None = None, mocked: bool = False, cache_hit: bool = False) -> dict:
    payload = data.model_dump(by_alias=True) if hasattr(data, "model_dump") else data
    return {
        "ok": True,
        "data": payload,
        "warnings": [w.model_dump(by_alias=True) if hasattr(w, "model_dump") else w for w in (warnings or [])],
        "meta": {"ms": ms, "model": model, "mocked": mocked, "cacheHit": cache_hit},
    }


def wants_mock(request: Request) -> bool:
    return settings().mock_only or request.headers.get("x-mock") == "1"


def fixture(name: str) -> Any:
    path: Path = FIXTURES / name
    if not path.exists():
        raise ApiError("internal", "Missing fixture " + name + ". Commit it before anything else.")
    return json.loads(path.read_text(encoding="utf-8"))
