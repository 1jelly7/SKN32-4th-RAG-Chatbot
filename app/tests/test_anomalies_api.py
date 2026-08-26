"""app/api/anomalies.py(4단계) 인증·권한·응답 스키마 계약 테스트.

app/tests/test_reports_api.py와 동일한 DI/인증 대역 패턴(tests/auth_helpers)을
사용한다. get_anomalies()는 실제 DB에 붙는 함수라, API 계층만 독립적으로 검증하기
위해 app.api.anomalies.get_anomalies를 monkeypatch로 대체한다(app/services/
anomaly_service.py 자체의 동작은 test_anomaly_service.py가 담당).

TEMP: app/api/anomalies.py를 지울 때 이 파일도 함께 지운다
(docs/team_share/09_anomaly_temp_dashboard_cleanup.md 참고).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.agent.llm import LLMClient
from app.api import anomalies as anomalies_module
from app.auth.gateway import AuthenticatedUser
from app.core.dependencies import AppDependencies
from app.main import create_app
from app.mcp.client import MCPClient
from tests.auth_helpers import FakeAuthenticationGateway, TEST_SESSION_TOKEN, login


class FakeLLMClient(LLMClient):
    """생성자에서 실제 OpenAI client를 만들지 않는 API 조립용 대역."""

    def __init__(self) -> None:
        pass


class NeverCalledPort:
    """이 테스트들은 MCP를 전혀 쓰지 않는 엔드포인트를 검증하므로, 호출되면 실패시킨다."""

    async def call_tool(self, tool_name: str, payload: dict[str, Any]) -> object:
        raise AssertionError("이 테스트에서는 MCP tool이 호출되면 안 된다.")


def _application(auth_gateway: FakeAuthenticationGateway) -> Any:
    dependencies = AppDependencies(
        llm=FakeLLMClient(),
        mcp=MCPClient(NeverCalledPort()),
        configure_logging=lambda: None,
        auth_gateway=auth_gateway,
    )
    return create_app(dependencies)


def test_list_anomalies_requires_authentication() -> None:
    application = _application(FakeAuthenticationGateway())
    with TestClient(application) as client:
        response = client.get("/api/anomalies")

    assert response.status_code == 401


def test_list_anomalies_rejects_role_without_domain_access() -> None:
    """hr 역할은 document_db만 허용돼 있어(shared/auth_policy.py) 여기서 걸러진다."""
    gateway = FakeAuthenticationGateway(
        {
            TEST_SESSION_TOKEN: AuthenticatedUser(
                user_id=2,
                username="hr1",
                display_name="HR",
                role="hr",
                session_id="s-hr",
            )
        }
    )
    application = _application(gateway)
    with TestClient(application) as client:
        login(client)
        response = client.get("/api/anomalies")

    assert response.status_code == 403


def test_list_anomalies_returns_rows_for_authorized_role(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_anomalies() -> list[dict[str, Any]]:
        return [
            {
                "domain": "sales",
                "type": "amount_outlier",
                "entity": "Amman Capital",
                "amount": 1699885.51,
                "detail": "SO-1 (2026-01-01)",
                "detected_at": "2026-08-25T00:00:00+00:00",
            }
        ]

    monkeypatch.setattr(anomalies_module, "get_anomalies", fake_get_anomalies)

    application = _application(FakeAuthenticationGateway())
    with TestClient(application) as client:
        login(client)
        response = client.get("/api/anomalies")

    assert response.status_code == 200
    assert response.json() == [
        {
            "domain": "sales",
            "type": "amount_outlier",
            "entity": "Amman Capital",
            "amount": 1699885.51,
            "detail": "SO-1 (2026-01-01)",
            "detected_at": "2026-08-25T00:00:00+00:00",
        }
    ]


def test_list_anomalies_returns_empty_list_when_nothing_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_get_anomalies() -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(anomalies_module, "get_anomalies", fake_get_anomalies)

    application = _application(FakeAuthenticationGateway())
    with TestClient(application) as client:
        login(client)
        response = client.get("/api/anomalies")

    assert response.status_code == 200
    assert response.json() == []


def test_list_anomalies_allows_finance_role(monkeypatch: pytest.MonkeyPatch) -> None:
    """finance는 sales_db/purchase_db 둘 다 허용돼 있어(shared/auth_policy.py) 통과해야 한다."""

    async def fake_get_anomalies() -> list[dict[str, Any]]:
        return []

    monkeypatch.setattr(anomalies_module, "get_anomalies", fake_get_anomalies)

    gateway = FakeAuthenticationGateway(
        {
            TEST_SESSION_TOKEN: AuthenticatedUser(
                user_id=3,
                username="fin1",
                display_name="Finance",
                role="finance",
                session_id="s-fin",
            )
        }
    )
    application = _application(gateway)
    with TestClient(application) as client:
        login(client)
        response = client.get("/api/anomalies")

    assert response.status_code == 200
