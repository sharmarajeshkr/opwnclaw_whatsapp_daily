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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router

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

# Allow requests from Streamlit (localhost:8501) and any local tools
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
