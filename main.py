"""
Ghana Emergency Health Grid (GEHG) — FastAPI Backend
Version: 1.0
Architecture: Serverless-First | Google Cloud Run | Firestore | Dual AI Engine (Claude/Gemini)
"""

import os
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

# 1. LOAD ENVIRONMENT VARIABLES FIRST
from dotenv import load_dotenv
load_dotenv()

# 2. NOW IMPORT DATABASE, API ROUTES, AND AI SERVICES
from database import db_service
from services.triage_claude import evaluate_symptoms as evaluate_with_claude
from services.triage_gemini import evaluate_symptoms as evaluate_with_gemini
from fastapi import FastAPI, HTTPException, status, Header  # Added Header
from fastapi.middleware.cors import CORSMiddleware
from services.maps import add_real_travel_times # Added Maps service
from models import (
    Hospital,
    TriageRequest,
    TriageResponse,
    CapacityUpdate,
    HospitalStatus,
    UrgencyLevel,
    HospitalRecommendation,
)

# ---------------------------------------------------------------------------
# Environment Configuration
# ---------------------------------------------------------------------------

APP_ENV            = os.getenv("APP_ENV", "development")
APP_VERSION        = os.getenv("APP_VERSION", "1.0.0")
ALLOWED_ORIGINS    = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

# The Master AI Toggle
ACTIVE_AI_PROVIDER = os.getenv("ACTIVE_AI_PROVIDER", "gemini").lower()

ANTHROPIC_API_KEY  = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
GOOGLE_MAPS_API_KEY= os.getenv("GOOGLE_MAPS_API_KEY")
FIREBASE_PROJECT_ID= os.getenv("FIREBASE_PROJECT_ID")
GOOGLE_CLOUD_REGION= os.getenv("GOOGLE_CLOUD_REGION", "us-central1")

# ---------------------------------------------------------------------------
# App Lifespan (startup / shutdown hooks)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup: validate critical env vars and attach the database service.
    Shutdown: gracefully release any open connections.
    """
    print(f"[GEHG] ✅ Starting in '{APP_ENV}' mode — v{APP_VERSION}")
    print(f"[GEHG] 🧠 Active AI Engine: {ACTIVE_AI_PROVIDER.upper()}")
    print(f"[GEHG] 🌍 Firebase project: {FIREBASE_PROJECT_ID or '(not set)'}")
    print(f"[GEHG] 🔒 CORS origins: {ALLOWED_ORIGINS}")

    # Attach the database service to the app state
    app.state.db = db_service
    print("[GEHG] 🗄️  Database service attached to application state.")

    yield

    print("[GEHG] 🛑 Shutting down gracefully.")

# ---------------------------------------------------------------------------
# FastAPI Initialisation 
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Ghana Emergency Health Grid API",
    description=(
        "Real-time emergency health logistics platform solving No-Bed Syndrome "
        "across Accra and Greater Ghana. Powered by Claude 3.5 Sonnet & Gemini 2.5 Flash."
    ),
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

# ---------------------------------------------------------------------------
# Root & Health-Check Routes
# ---------------------------------------------------------------------------

@app.get("/", tags=["System"], summary="API root — confirms the service is reachable")
def root():
    return {
        "service": "Ghana Emergency Health Grid",
        "version": APP_VERSION,
        "status": "operational",
        "docs": "/docs",
    }


@app.get("/health", tags=["System"], summary="Shallow health check")
def health_check():
    return {
        "status": "healthy",
        "environment": APP_ENV,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


@app.get("/health/deep", tags=["System"], summary="Deep health check")
def deep_health_check():
    checks = {
        "active_ai_engine": ACTIVE_AI_PROVIDER,
        "firestore":       "ok" if FIREBASE_PROJECT_ID else "not_configured",
        "anthropic_api":   "ok" if ANTHROPIC_API_KEY else "not_configured",
        "gemini_api":      "ok" if GEMINI_API_KEY else "not_configured",
        "google_maps_api": "ok" if GOOGLE_MAPS_API_KEY else "not_configured",
    }

    overall = "healthy" if checks["firestore"] == "ok" else "degraded"

    return {
        "status": overall,
        "environment": APP_ENV,
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }

# ---------------------------------------------------------------------------
# API v1 — Triage Service  (/api/v1/triage)
# ---------------------------------------------------------------------------

@app.post(
    "/api/v1/triage/evaluate",
    response_model=TriageResponse,
    status_code=status.HTTP_200_OK,
    tags=["Triage Engine"],
    summary="AI-powered emergency triage and hospital recommendation",
)
async def evaluate_triage(
    request: TriageRequest, 
    x_simulation_mode: bool = Header(False, alias="X-Simulation-Mode")
):
    """
    Workflow (see Architecture §4.1):
    1. Fetch `GREEN` / `YELLOW` hospital list from Firestore.
    2. Route the prompt to the active AI Engine (Claude or Gemini).
    """
    
    # 1. Fetch live hospital data safely inside the async route
    try:
        available_hospitals = await app.state.db.get_available_hospitals()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database connection failed: {str(e)}"
        )

    # If no hospitals are currently available
    if not available_hospitals:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No GREEN or YELLOW hospitals are currently available."
        )

# ------------------------------------------------------------------
    # Step 3 — Route request to the active AI Engine
    # ------------------------------------------------------------------
    if ACTIVE_AI_PROVIDER == "claude":
        triage_result = await evaluate_with_claude(
            symptom_text=request.symptom_text,
            available_hospitals=available_hospitals
        )
    else:
        # Defaults to Gemini if anything else is set
        triage_result = await evaluate_with_gemini(
            symptom_text=request.symptom_text,
            available_hospitals=available_hospitals
        )

    # ------------------------------------------------------------------
    # Step 4 — Calculate Real-Time ETAs via Google Maps
    # ------------------------------------------------------------------
    # Convert the GeoLocation object into a Google Maps compatible string
    origin_coords = f"{request.user_location.lat},{request.user_location.lng}"

    triage_result.recommendations = await add_real_travel_times(
        user_location=origin_coords, # Passing the formatted lat/lng string
        recommendations=triage_result.recommendations,
        simulation_mode=x_simulation_mode
    )

    return triage_result

# ---------------------------------------------------------------------------
# API v1 — Hospital Management Service  (/api/v1/hospital)
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/hospital",
    tags=["Hospital Management"],
    summary="List all hospitals (filtered by status)",
)
async def list_hospitals(status_filter: HospitalStatus | None = None):
    try:
        hospitals = await app.state.db.get_available_hospitals()
        if status_filter:
            hospitals = [h for h in hospitals if h.get("status") == status_filter.value]
        return {
            "count": len(hospitals),
            "filter_applied": status_filter,
            "hospitals": hospitals,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/hospital/{hospital_id}", tags=["Hospital Management"])
async def get_hospital(hospital_id: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"Firestore deep fetch pending. hospital_id={hospital_id}",
    )


@app.patch("/api/v1/hospital/{hospital_id}/capacity", tags=["Hospital Management"])
async def update_capacity(hospital_id: str, update: CapacityUpdate):
    return {
        "hospital_id": hospital_id,
        "acknowledged": True,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "note": "Stub — Firestore write pending.",
    }

# ---------------------------------------------------------------------------
# Dev entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=APP_ENV == "development",
        log_level="info",
    )