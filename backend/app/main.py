from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os
import sys

# Ensure backend root is in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_root = os.path.dirname(current_dir)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

from app.core.config import settings
from app.db.init_db import init_db

# Import API routers
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.patients import router as patients_router
from app.api.records import router as records_router
from app.api.ehr import router as ehr_router
from app.api.identity import router as identity_router
from app.api.conflicts import router as conflicts_router
from app.api.emergency import router as emergency_router
from app.api.audit import router as audit_router
from app.api.stats import router as stats_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize tables and seed data
    init_db()
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Production-grade Emergency Medical Information Interoperability Gateway with Zero-Trust Authorization, Multi-EHR Adapters, Clinical Conflict Detection, and Source Traceability.",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to specific client domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers under /api
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(admin_router, prefix=settings.API_V1_STR)
app.include_router(patients_router, prefix=settings.API_V1_STR)
app.include_router(records_router, prefix=settings.API_V1_STR)
app.include_router(ehr_router, prefix=settings.API_V1_STR)
app.include_router(identity_router, prefix=settings.API_V1_STR)
app.include_router(conflicts_router, prefix=settings.API_V1_STR)
app.include_router(emergency_router, prefix=settings.API_V1_STR)
app.include_router(audit_router, prefix=settings.API_V1_STR)
app.include_router(stats_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["System Telemetry"])
def health_check():
    return {
        "status": "HEALTHY",
        "system": "HC-04 Emergency Gateway",
        "version": "2.0.0",
        "security": "Zero-Trust Enforcement Active"
    }

@app.get("/api", tags=["System Telemetry"])
def api_root():
    return {
        "message": "HC-04 Emergency Interoperability API Gateway",
        "docs": "/docs",
        "health": "/health"
    }

# Mount frontend directly at /
frontend_dist = os.path.join(backend_root, "..", "frontend", "dist")
frontend_dir = os.path.join(backend_root, "..", "frontend")

if os.path.isdir(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static_frontend")
elif os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static_frontend")

