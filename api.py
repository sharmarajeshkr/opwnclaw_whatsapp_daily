"""
api.py
------
FastAPI application entrypoint for OpenClaw.

Run with:
    .\\venv\\Scripts\\uvicorn.exe api:app --reload --port 8000

Interactive API docs available at:
    http://localhost:8000/docs     (Swagger UI)
    http://localhost:8000/redoc   (ReDoc)
"""
from fastapi import FastAPI, Depends, HTTPException, status, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router
from src.core.env import get_api_secret_key

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    expected_key = get_api_secret_key()
    if expected_key and api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key",
        )
    return api_key

app = FastAPI(
    title="OpenClaw Bot API",
    description=(
        "REST API for managing OpenClaw WhatsApp bots. "
        "Register users, control bot processes, manage configs, and tail logs."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Allow requests only from expected local Streamlit hosts
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(router, dependencies=[Depends(verify_api_key)])
