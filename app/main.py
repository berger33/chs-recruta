from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .database import Base, engine
from .routers import auth, candidates, operations, users, vacancies

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

Base.metadata.create_all(bind=engine)
app = FastAPI(
    title="CHS Recruta API",
    version="2.0.0",
    description="Backend Python para recrutamento e seleção com RBAC, auditoria e PostgreSQL.",
)
app.include_router(auth.router)
app.include_router(candidates.router)
app.include_router(vacancies.router)
app.include_router(operations.router)
app.include_router(users.router)
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC / "index.html")
