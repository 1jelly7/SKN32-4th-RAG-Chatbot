"""FastAPI 애플리케이션 조립 경계.

라우터, 정적 UI, 주입된 LLM/MCP/cache 의존성과 LangGraph를 하나의 앱 수명주기에
연결한다. 실제 문서·업무 데이터 접근은 이 모듈이 수행하지 않으며, 캐시 miss 이후의
조회는 그래프에 주입된 MCP client가 담당한다.
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.auth import router as auth_router
from app.api.system import router as system_router
from app.agent.graph import build_graph
from app.agent.prompts import PROMPT_VERSION
from app.core.dependencies import AppDependencies

WEB_DIR = Path(__file__).resolve().parent / "web"
UI_CACHE_HEADERS = {"Cache-Control": "no-store"}
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
    if dependencies is None:
        from app.core.config import get_settings
        settings = get_settings()
        app_dependencies.auth_secret = settings.auth_secret_key
        app_dependencies.auth_expire_minutes = settings.auth_access_token_expire_minutes
        app_dependencies.auth_cookie_secure = settings.auth_cookie_secure

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """앱 시작 시 주입된 logging만 구성하고 provider 수명주기는 변경하지 않는다."""
        app_dependencies.configure_logging()
        yield

    application = FastAPI(title="RAG MCP Chatbot", lifespan=lifespan)
    application.state.dependencies = app_dependencies
    application.state.auth_service = app_dependencies.auth_service
    application.state.auth_secret = app_dependencies.auth_secret
    application.state.auth_expire_minutes = app_dependencies.auth_expire_minutes or 60
    application.state.auth_cookie_secure = bool(app_dependencies.auth_cookie_secure)
    application.state.graph = build_graph(app_dependencies.mcp, app_dependencies.llm)
    application.state.cache_key_context = dict(CACHE_KEY_CONTEXT)
    application.include_router(chat_router, prefix="/api")
    application.include_router(auth_router, prefix="/api")
    application.include_router(system_router, prefix="/api")

    # /api 이후에 등록해야 /api/* 요청이 정적 파일 라우트와 충돌하지 않습니다.
    application.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @application.get("/")
    def index() -> FileResponse:
        """번들된 채팅 UI의 진입 HTML을 반환한다."""
        return FileResponse(WEB_DIR / "index.html", headers=UI_CACHE_HEADERS)

    @application.get("/chat.js")
    def chat_js() -> FileResponse:
        """별도 정적 경로를 기대하는 UI를 위해 채팅 스크립트를 반환한다."""
        return FileResponse(WEB_DIR / "chat.js", headers=UI_CACHE_HEADERS)

    @application.get("/style.css")
    def style_css() -> FileResponse:
        """별도 정적 경로를 기대하는 UI를 위해 스타일시트를 반환한다."""
        return FileResponse(WEB_DIR / "style.css", headers=UI_CACHE_HEADERS)

    return application


app = create_app()
