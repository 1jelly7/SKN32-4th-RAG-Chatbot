from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api.chat import router as chat_router
from app.api.system import router as system_router

app = FastAPI(title="RAG MCP Chatbot")
app.include_router(chat_router, prefix="/api")
app.include_router(system_router, prefix="/api")
app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="web")
