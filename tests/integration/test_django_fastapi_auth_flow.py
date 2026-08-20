"""Django 서버 세션에서 FastAPI 채팅까지 이어지는 인프로세스 인증 계약."""

from __future__ import annotations

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
from tests.integration.chat_fakes import build_fake_application, document_success


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
