from fastapi import FastAPI

from app.api.chat import router as chat_router
from app.api.system import router as system_router


def create_app() -> FastAPI:
    ...


app: FastAPI = FastAPI(title="RAG MCP Chatbot")
app.include_router(chat_router, prefix="/api")
app.include_router(system_router, prefix="/api")
