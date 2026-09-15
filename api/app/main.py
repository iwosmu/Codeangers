from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .envelope import ApiError, api_error_handler, unhandled_handler
from .routers import cv, health, plan, project, tasks

app = FastAPI(title="Codeangers planner", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(Exception, unhandled_handler)

for r in (health.router, project.router, cv.router, tasks.router, plan.router):
    app.include_router(r, prefix="/api")
