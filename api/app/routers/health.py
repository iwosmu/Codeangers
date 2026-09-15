from fastapi import APIRouter

from ..config import settings
from ..envelope import ok

router = APIRouter()


@router.get("/health")
async def health():
    s = settings()
    return ok({"model": {"extract": s.model_extract, "reason": s.model_reason},
               "mockMode": s.mock_only,
               "hasKey": bool(s.gemini_api_key),
               "commit": s.commit})
