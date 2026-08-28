from __future__ import annotations
import hmac,secrets
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from .config import get_settings
from .database import Base,engine
from . import advanced_models, identity_models, portal_models, time_payroll_models, workforce_models  # noqa: F401
from .routers import employee_portal, identity_security, integrations_billing, people_advanced, performance, recruiting_advanced, saas, time_payroll_advanced, workforce_advanced

ROOT=Path(__file__).resolve().parents[1]; STATIC=ROOT/"static"; settings=get_settings()
@asynccontextmanager
async def lifespan(app:FastAPI):
    if settings.auto_create_schema: Base.metadata.create_all(bind=engine)
    yield
app=FastAPI(title="CHS RH API",version="3.0.0",description="SaaS multiempresa para recrutamento e gestão de pessoas.",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=list(settings.allowed_origins),allow_credentials=True,allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],allow_headers=["Authorization","Content-Type","X-Request-ID","X-CSRF-Token","X-Session-Mode"])
@app.middleware("http")
async def request_context(request:Request,call_next):
    request.state.request_id=request.headers.get("x-request-id") or secrets.token_hex(16)
    csrf_exempt={"/api/auth/login","/api/auth/mfa/verify","/api/auth/password/forgot","/api/auth/password/reset"}
    has_cookie=bool(request.cookies.get(settings.session_cookie_name))
    uses_bearer=bool(request.headers.get("authorization"))
    if request.method not in {"GET","HEAD","OPTIONS"} and has_cookie and not uses_bearer and request.url.path not in csrf_exempt:
        cookie_token=request.cookies.get("chs_csrf",""); header_token=request.headers.get("x-csrf-token","")
        if not cookie_token or not hmac.compare_digest(cookie_token,header_token):
            response=JSONResponse(status_code=403,content={"detail":"Token CSRF inválido","request_id":request.state.request_id})
        else: response=await call_next(request)
    else: response=await call_next(request)
    response.headers["X-Request-ID"]=request.state.request_id
    response.headers["X-Content-Type-Options"]="nosniff"
    response.headers["X-Frame-Options"]="DENY"
    response.headers["Referrer-Policy"]="strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"]="camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"]="default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    if request.url.path.startswith(("/api/auth","/api/security")): response.headers["Cache-Control"]="no-store"
    if settings.is_production: response.headers["Strict-Transport-Security"]="max-age=31536000; includeSubDomains"
    return response
app.include_router(saas.router)
app.include_router(identity_security.router)
app.include_router(recruiting_advanced.router)
app.include_router(people_advanced.router)
app.include_router(performance.router)
app.include_router(integrations_billing.router)
app.include_router(employee_portal.router)
app.include_router(workforce_advanced.router)
app.include_router(time_payroll_advanced.router)
app.mount("/static",StaticFiles(directory=STATIC),name="static")
@app.get("/health")
def health(): return {"status":"ok","service":"chs-rh","version":"3.0.0"}
@app.get("/",include_in_schema=False)
def home(): return FileResponse(STATIC/"index.html")
