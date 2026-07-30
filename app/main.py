"""
FastAPI 애플리케이션의 실행 진입점입니다.
"""

# FastAPI 클래스를 가져옵니다.
from fastapi import FastAPI

# 정적 파일(임시 GUI)을 서빙하기 위해 FileResponse를 가져옵니다.
from fastapi.responses import FileResponse

# 프로젝트 API Router를 가져옵니다.
from app.routers.api import router

# 설정 객체를 가져옵니다.
from app.config.settings import get_settings

# 프로젝트 루트 기준 정적 파일 경로를 계산하기 위해 Path를 가져옵니다.
from pathlib import Path


# 캐시된 설정 객체를 가져옵니다.
settings = get_settings()

# FastAPI 애플리케이션 객체를 생성합니다.
app = FastAPI(
    title=settings.app_name,
    description="OpenAI GPT, MCP, FAISS/Qdrant, MySQL을 학습하는 RAG Assistant API",
    version="1.0.0",
)

# 프로젝트 REST API Router를 애플리케이션에 등록합니다.
app.include_router(router)

# 정적 GUI 파일 경로를 계산합니다.
STATIC_DIR = Path(__file__).resolve().parent / "static"


# 루트 URL에서 임시 테스트 GUI를 반환합니다.
@app.get("/")
def home():
    """간단한 채팅형 테스트 GUI(정적 HTML)를 반환합니다."""

    # static/index.html 파일을 그대로 응답으로 반환합니다.
    return FileResponse(STATIC_DIR / "index.html")


# 이 파일을 직접 실행했을 때 Uvicorn 서버를 시작합니다.
if __name__ == "__main__":
    # ASGI 서버 실행 모듈을 가져옵니다.
    import uvicorn

    # 문자열 import 방식으로 FastAPI 앱을 실행합니다.
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )
