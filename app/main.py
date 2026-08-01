from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.system import router as system_router
from app.agent.graph import build_graph
from app.agent.prompts import PROMPT_VERSION
from app.core.dependencies import AppDependencies

WEB_DIR = Path(__file__).resolve().parent / "web"
CACHE_KEY_CONTEXT = {
    "document_index_version": "unknown",
    "database_freshness_bucket": "unknown",
    "prompt_version": PROMPT_VERSION,
    "model_id": "configured-model",
}


def create_app(dependencies: AppDependencies | None = None) -> FastAPI:
    """설정·로깅·라우터·정적 UI를 일관되게 등록한 FastAPI 앱을 구성한다.

    lifespan에서 주입된 logging 설정을 적용하고, MCP·LLM·cache 대역은 앱 상태에
    보관한다. /api 라우터와 UI 경로의 충돌을 방지하며 생성 함수는 테스트에서 독립적으로
    사용할 수 있어야 한다.
    """
    app_dependencies = dependencies or AppDependencies()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        app_dependencies.configure_logging()
        yield

    application = FastAPI(title="RAG MCP Chatbot", lifespan=lifespan)
    application.state.dependencies = app_dependencies
    application.state.graph = build_graph(app_dependencies.mcp, app_dependencies.llm)
    application.state.cache_key_context = dict(CACHE_KEY_CONTEXT)
    application.include_router(chat_router, prefix="/api")
    application.include_router(system_router, prefix="/api")

    # /api 이후에 등록해야 /api/* 요청이 정적 파일 라우트와 충돌하지 않습니다.
    application.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @application.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @application.get("/chat.js")
    def chat_js() -> FileResponse:
        return FileResponse(WEB_DIR / "chat.js")

    @application.get("/style.css")
    def style_css() -> FileResponse:
        return FileResponse(WEB_DIR / "style.css")

    return application


app = create_app()
