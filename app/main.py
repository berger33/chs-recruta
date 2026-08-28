from __future__ import annotations
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .config import get_settings
from .database import Base,engine
from . import advanced_models, portal_models, workforce_models  # noqa: F401 - register metadata
from .routers import employee_portal, integrations_billing, people_advanced, performance, recruiting_advanced, saas, workforce_advanced

ROOT=Path(__file__).resolve().parents[1]; STATIC=ROOT/"static"; settings=get_settings()
@asynccontextmanager
async def lifespan(app:FastAPI):
    if settings.auto_create_schema: Base.metadata.create_all(bind=engine)
    yield
app=FastAPI(title="CHS RH API",version="3.0.0",description="SaaS multiempresa para recrutamento e gestão de pessoas.",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=list(settings.allowed_origins),allow_credentials=False,allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type","X-Request-ID"])
@app.middleware("http")
async def request_context(request:Request,call_next):
    request.state.request_id=request.headers.get("x-request-id") or secrets.token_hex(16)
    response=await call_next(request)
    response.headers["X-Request-ID"]=request.state.request_id
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    return response
app.include_router(saas.router)
app.include_router(recruiting_advanced.router)
app.include_router(people_advanced.router)
app.include_router(performance.router)
app.include_router(integrations_billing.router)
app.include_router(employee_portal.router)
app.include_router(workforce_advanced.router)
app.mount("/static",StaticFiles(directory=STATIC),name="static")
@app.get("/health")
def health(): return {"status":"ok","service":"chs-rh","version":"3.0.0"}
@app.get("/",include_in_schema=False)
def home(): return FileResponse(STATIC/"index.html")
