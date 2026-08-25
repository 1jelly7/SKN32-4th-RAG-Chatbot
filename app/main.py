"""FastAPI 애플리케이션 조립 경계.

라우터, 정적 UI, 주입된 LLM/MCP/cache 의존성과 LangGraph를 하나의 앱 수명주기에
연결한다. 실제 문서·업무 데이터 접근은 이 모듈이 수행하지 않으며, 캐시 miss 이후의
조회는 그래프에 주입된 MCP client가 담당한다.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, Response

from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.system import router as system_router
from app.agent.graph import build_graph
from app.agent.prompts import PROMPT_VERSION
from app.core.dependencies import AppDependencies
from app.logging.context import reset_request_id, set_request_id
from app.logging.performance import elapsed_ms, server_timing_header, start_timer

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

        await asyncio.to_thread(
            embed, ["서버 시작 시 임베딩 모델을 미리 로드하기 위한 예열 문장입니다."]
        )
        logger.info(
            "embedding_model_warmed_up", extra={"event": "embedding_model_warmed_up"}
        )
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
        app_dependencies.warmup_providers = True

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        """logging을 구성하고 선택된 운영 provider의 읽기 전용 캐시를 예열한다."""
        app_dependencies.configure_logging()
        warmup_tasks: list[asyncio.Task[None]] = []
        if app_dependencies.warmup_providers and app_dependencies.mcp is not None:

            async def warmup_providers() -> None:
                try:
                    await app_dependencies.mcp.warmup()
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "provider_warmup_failed error_type=%s",
                        type(exc).__name__,
                        extra={"event": "provider_warmup_failed"},
                    )

            warmup_tasks.append(asyncio.create_task(warmup_providers()))
        if app_dependencies.warmup_providers:
            warmup_tasks.append(asyncio.create_task(_warmup_embedding_model()))
        try:
            # SBERT 모델·FAISS 예열은 수 초에서 수십 초가 걸릴 수 있으므로 API가
            # 준비되기 전에 기다리지 않는다. 이 지점에서 먼저 yield해야 gateway가
            # startup 중인 FastAPI에 연결해 HTML 502를 받는 일이 없다.
            yield
        finally:
            for task in warmup_tasks:
                task.cancel()
            if warmup_tasks:
                await asyncio.gather(*warmup_tasks, return_exceptions=True)
            close_auth_gateway = getattr(app_dependencies.auth_gateway, "aclose", None)
            if close_auth_gateway is not None:
                await close_auth_gateway()

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
            response.headers["Server-Timing"] = server_timing_header(
                request.state.stage_timings
            )
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
    application.state.graph = build_graph(app_dependencies.mcp, app_dependencies.llm)
    application.state.cache_key_context = dict(CACHE_KEY_CONTEXT)

    application.include_router(chat_router, prefix="/api")
    application.include_router(documents_router, prefix="/api")
    application.include_router(system_router, prefix="/api")

    return application


app = create_app()
