from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .envelope import ApiError, api_error_handler, unhandled_handler
from .routers import briefs, health

app = FastAPI(title="Team Work Splitter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, unhandled_handler)

for r in (health.router, briefs.router):
    app.include_router(r, prefix="/api")


@app.middleware("http")
async def private_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
