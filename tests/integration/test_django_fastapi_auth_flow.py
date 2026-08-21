"""Django 서버 세션에서 FastAPI 채팅까지 이어지는 인프로세스 인증 계약."""

from __future__ import annotations

from pathlib import Path

import httpx
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core.asgi import get_asgi_application
from django.test import Client as DjangoClient
from fastapi.testclient import TestClient as FastAPIClient

from app.agent.llm import FakeLLMPort
from app.auth.gateway import DjangoAuthenticationGateway
from app.cache.repository import MemoryCache
from app.core.dependencies import AppDependencies
from app.main import create_app
from django_app.accounts.models import User
from tests.integration.chat_fakes import build_fake_application, document_success, tool_success


def _django_login(username: str, password: str) -> str:
    client = DjangoClient(enforce_csrf_checks=True)
    csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]
    response = client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert response.status_code == 200
    return client.cookies[settings.SESSION_COOKIE_NAME].value


def _fastapi_client(
    session_key: str,
    *,
    fake_document_mcp: bool = False,
) -> tuple[FastAPIClient, DjangoAuthenticationGateway]:
    gateway = DjangoAuthenticationGateway(
        "http://testserver/internal/auth/introspect",
        settings.AUTH_INTROSPECTION_KEY,
        transport=httpx.ASGITransport(app=get_asgi_application()),
    )
    if fake_document_mcp:
        application, _, _ = build_fake_application({"search_documents": document_success()})
        application.state.dependencies.auth_gateway = gateway
    else:
        application = create_app(
            AppDependencies(
                llm=FakeLLMPort("fake answer"),
                cache=MemoryCache(),
                auth_gateway=gateway,
                configure_logging=lambda: None,
            )
        )
    client = FastAPIClient(application)
    client.cookies.set("chatbot_session", session_key)
    return client, gateway


def _fastapi_document_client(
    session_key: str,
    document_path: Path,
) -> tuple[FastAPIClient, DjangoAuthenticationGateway]:
    """Django 세션을 검증하며 문서 다운로드까지 제공하는 FastAPI fake 앱을 조립한다."""
    gateway = DjangoAuthenticationGateway(
        "http://testserver/internal/auth/introspect",
        settings.AUTH_INTROSPECTION_KEY,
        transport=httpx.ASGITransport(app=get_asgi_application()),
    )
    application, _, _ = build_fake_application(
        {
            "search_documents": document_success(),
            "resolve_document_download": tool_success(
                "document",
                [{"file_path": str(document_path), "file_name": document_path.name}],
            ),
        }
    )
    application.state.dependencies.auth_gateway = gateway
    client = FastAPIClient(application)
    client.cookies.set(settings.SESSION_COOKIE_NAME, session_key)
    return client, gateway


def test_django_login_session_reaches_fastapi_chat(transactional_db) -> None:
    User.objects.create_user(
        username="integration-admin",
        password="admin-password",
        display_name="Integration Admin",
        role="admin",
    )
    session_key = _django_login("integration-admin", "admin-password")
    client, _ = _fastapi_client(session_key, fake_document_mcp=True)

    with client:
        response = client.post("/api/chat", json={"question": "법인카드 규정을 알려줘"})

    assert response.status_code == 200
    assert response.json()["answer"] == "fake answer"


def test_django_session_reaches_fastapi_chat_and_document_download(
    transactional_db,
    tmp_path: Path,
) -> None:
    """같은 origin UI가 쓰는 세션 쿠키로 채팅과 문서 다운로드를 모두 보호한다."""
    User.objects.create_user(
        username="integration-document",
        password="document-password",
        display_name="Integration Document",
        role="admin",
    )
    document_path = tmp_path / "휴가_규정.pdf"
    document_path.write_bytes(b"fixture-pdf")
    session_key = _django_login("integration-document", "document-password")
    client, _ = _fastapi_document_client(session_key, document_path)

    with client:
        chat = client.post("/api/chat", json={"question": "휴가 규정을 알려줘"})
        download = client.get("/api/documents/download", params={"doc_id": "policy-001"})

    assert chat.status_code == 200
    assert chat.json()["answer"] == "fake answer"
    assert download.status_code == 200
    assert download.content == b"fixture-pdf"
    assert "filename*=UTF-8''" in download.headers["content-disposition"]
    assert "file_path" not in download.text


def test_local_gateway_routes_ui_auth_and_fastapi_api_paths() -> None:
    """공개 origin에서 인증은 Django, 채팅·문서는 FastAPI로 분리한다."""
    config = Path("deploy/nginx/local.conf").read_text(encoding="utf-8")

    assert "location ^~ /api/auth/" in config
    assert "location = /api/chat" in config
    assert "location ^~ /api/documents/" in config
    fallback_location = "        location ^~ /api/ {"
    assert config.index("location ^~ /api/auth/") < config.index(fallback_location)
    assert config.index("location = /api/chat") < config.index(fallback_location)
    assert config.index("location ^~ /api/documents/") < config.index(fallback_location)
    assert config.count("proxy_pass http://django_local;") >= 2
    assert config.count("proxy_pass http://fastapi_local;") >= 5


def test_role_inactivation_and_session_deletion_are_immediate(transactional_db) -> None:
    user = User.objects.create_user(
        username="integration-finance",
        password="finance-password",
        display_name="Integration Finance",
        role="finance",
    )
    session_key = _django_login("integration-finance", "finance-password")
    client, _ = _fastapi_client(session_key)

    with client:
        user.role = "hr"
        user.save(update_fields=["role"])
        forbidden = client.post("/api/chat", json={"question": "공급업체별 구매 지출"})

        user.is_active = False
        user.save(update_fields=["is_active"])
        inactive = client.post("/api/chat", json={"question": "안녕하세요"})

        user.is_active = True
        user.save(update_fields=["is_active"])
        Session.objects.filter(session_key=session_key).delete()
        expired = client.post("/api/chat", json={"question": "안녕하세요"})

    assert forbidden.status_code == 403
    assert inactive.status_code == 401
    assert expired.status_code == 401
