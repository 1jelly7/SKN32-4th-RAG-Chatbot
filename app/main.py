from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.system import router as system_router
from app.logging import configure_logging

WEB_DIR = Path(__file__).resolve().parent / "web"


def create_app() -> FastAPI:
    """설정·로깅·라우터·정적 UI를 일관되게 등록한 FastAPI 앱을 구성한다.

    startup/shutdown에서 공유 MCP/Redis 자원을 수명 관리하고, /api 라우터와 UI 경로의
    충돌을 방지한다. 생성 함수가 실제 앱 인스턴스와 동등하게 구성되어 테스트에서
    독립적으로 사용할 수 있어야 한다.
    """
    configure_logging()
    application = FastAPI(title="RAG MCP Chatbot")
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
