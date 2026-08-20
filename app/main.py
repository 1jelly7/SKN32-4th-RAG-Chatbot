"""FastAPI 애플리케이션 조립 경계.

라우터, 정적 UI, 주입된 LLM/MCP/cache 의존성과 LangGraph를 하나의 앱 수명주기에
연결한다. 실제 문서·업무 데이터 접근은 이 모듈이 수행하지 않으며, 캐시 miss 이후의
조회는 그래프에 주입된 MCP client가 담당한다.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.auth import router as auth_router
from app.api.system import router as system_router
from app.agent.graph import build_graph
from app.agent.prompts import PROMPT_VERSION
from app.core.dependencies import AppDependencies
from app.logging.context import reset_request_id, set_request_id
from app.logging.performance import elapsed_ms, server_timing_header, start_timer

WEB_DIR = Path(__file__).resolve().parent / "web"
UI_CACHE_HEADERS = {"Cache-Control": "no-store"}
CACHE_KEY_CONTEXT = {
    "document_index_version": "unknown",
    "database_freshness_bucket": "unknown",
    "prompt_version": PROMPT_VERSION,
    "model_id": "configured-model",
}
logger = logging.getLogger(__name__)


async def _warmup_embedding_model() -> None:
    """서버 기동 시 sbert 임베딩 모델을 미리 로드해, 첫 질문이 모델 로딩 비용을
    떠안지 않게 한다.
    """
    try:
        from app.core.config import get_settings

        settings = get_settings()
        if getattr(settings, "embedding_backend", "local") != "sbert":
            return

        import asyncio

        from ingestion.embedding import embed

        await asyncio.to_thread(embed, ["서버 시작 시 임베딩 모델을 미리 로드하기 위한 예열 문장입니다."])
        logger.info("embedding_model_warmed_up", extra={"event": "embedding_model_warmed_up"})
    except Exception as exc:  # noqa: BLE001 - 예열 실패로 API 전체 시작을 막지 않는다.
        logger.warning(
            "embedding_warmup_failed error_type=%s",
            type(exc).__name__,
            extra={"event": "embedding_warmup_failed"},
        )


def create_app(dependencies: AppDependencies | None = None) -> FastAPI:
    """설정·로깅·라우터·정적 UI를 일관되게 등록한 FastAPI 앱을 구성한다."""
    app_dependencies = dependencies or AppDependencies()
    if dependencies is None:
        from app.core.config import get_settings
        settings = get_settings()
        app_dependencies.auth_secret = settings.auth_secret_key
        app_dependencies.auth_expire_minutes = settings.auth_access_token_expire_minutes
        app_dependencies.auth_cookie_secure = settings.auth_cookie_secure
        app_dependencies.warmup_providers = True

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """logging을 구성하고 선택된 운영 provider의 읽기 전용 캐시를 예열한다."""
        app_dependencies.configure_logging()
        if app_dependencies.warmup_providers and app_dependencies.mcp is not None:
            try:
                await app_dependencies.mcp.warmup()
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "provider_warmup_failed error_type=%s",
                    type(exc).__name__,
                    extra={"event": "provider_warmup_failed"},
                )
        if app_dependencies.warmup_providers:
            await _warmup_embedding_model()
        yield

    application = FastAPI(title="RAG MCP Chatbot", lifespan=lifespan)

    @application.middleware("http")
    async def measure_http_request(
            request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started_ns = start_timer()
        request.state.request_id = str(uuid.uuid4())
        request.state.stage_timings = {}
        request_id_token = set_request_id(request.state.request_id)
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            total_ms = elapsed_ms(started_ns)
            request.state.stage_timings["app_total"] = total_ms
            response.headers["X-Request-ID"] = request.state.request_id
            response.headers["Server-Timing"] = server_timing_header(request.state.stage_timings)
            return response
        finally:
            logger.info(
                "request_id=%s method=%s path=%s status=%s elapsed_ms=%.3f",
                request.state.request_id,
                request.method,
                request.url.path,
                status_code,
                elapsed_ms(started_ns),
                extra={"event": "http_request_completed"},
            )
            reset_request_id(request_id_token)

    application.state.dependencies = app_dependencies
    application.state.auth_service = app_dependencies.auth_service
    application.state.auth_secret = app_dependencies.auth_secret
    application.state.auth_expire_minutes = app_dependencies.auth_expire_minutes or 60
    application.state.auth_cookie_secure = bool(app_dependencies.auth_cookie_secure)
    application.state.graph = build_graph(app_dependencies.mcp, app_dependencies.llm)
    application.state.cache_key_context = dict(CACHE_KEY_CONTEXT)

    application.include_router(chat_router, prefix="/api")
    application.include_router(documents_router, prefix="/api")
    application.include_router(auth_router, prefix="/api")
    application.include_router(system_router, prefix="/api")

    application.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @application.get("/")
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html", headers=UI_CACHE_HEADERS)

    @application.get("/chat.js")
    def chat_js() -> FileResponse:
        return FileResponse(WEB_DIR / "chat.js", headers=UI_CACHE_HEADERS)

    @application.get("/style.css")
    def style_css() -> FileResponse:
        return FileResponse(WEB_DIR / "style.css", headers=UI_CACHE_HEADERS)

    return application


app = create_app()