"""
api.py
------
FastAPI application entrypoint for Interview.

Run with:
    .\\venv\\Scripts\\uvicorn.exe api:app --reload --port 8000

Interactive API docs:
    http://localhost:8000/docs     → Swagger UI (try every endpoint live)
    http://localhost:8000/redoc   → ReDoc (clean reference docs)

Authentication:
    Pass  X-API-Key: <your key>  header on every request.
    Set API_SECRET_KEY in .env — if unset, auth is disabled (dev mode).

Typical UI Integration Flow:
    1. POST /api/auth/register   → create account
    2. POST /api/users/{phone}/qr → start QR generation
    3. GET  /api/users/{phone}/qr/poll  → poll every 3s until state == "paired"
    4. GET  /api/users/{phone}/qr/image → render QR PNG in <img> tag
    5. POST /api/auth/login      → login, get role + paired status
    6. GET  /api/users/{phone}/config   → load settings for settings page
    7. PUT  /api/users/{phone}/config   → save settings
    8. GET  /api/users/{phone}/performance → render performance charts
"""
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import settings
from app.database.db import init_db

# Initialize database schema
init_db()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    expected_key = settings.API_SECRET_KEY
    # If no key configured → open (dev mode)
    if expected_key and api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key. Pass X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key

app = FastAPI(
    title="Interview Bot API",
    description=(
        "REST API for managing Interview WhatsApp AI Interview Coach bots.\n\n"
        "**Auth:** Pass `X-API-Key` header. Set `API_SECRET_KEY` in `.env`.\n\n"
        "**UI Flow:** Register → Trigger QR → Poll pairing → Login → Use features."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    contact={"name": "Interview", "url": "https://github.com/sharmarajeshkr/opwnclaw_whatsapp_daily"},
)

# CORS — open for any UI origin (React, Vue, Angular, mobile apps, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # restrict to specific domains in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(router, dependencies=[Depends(verify_api_key)])
