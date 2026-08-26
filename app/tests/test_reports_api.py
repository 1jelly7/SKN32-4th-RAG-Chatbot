"""app/api/reports.py(6단계) 인증·권한·응답 형태 계약 테스트.

app/tests/test_api.py와 동일한 DI/인증 대역 패턴(tests/auth_helpers)을 사용해,
실제 서버를 띄우지 않고 FastAPI 요청 경계만 검증한다.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.agent.llm import LLMClient
from app.auth.gateway import AuthenticatedUser
from app.core.dependencies import AppDependencies
from app.main import create_app
from app.mcp.client import MCPClient
from tests.auth_helpers import (
    FakeAuthenticationGateway,
    TEST_SESSION_TOKEN,
    authentication_dependencies,
    login,
)


class FakeLLMClient(LLMClient):
    """생성자에서 실제 OpenAI client를 만들지 않는 API 조립용 대역."""

    def __init__(self) -> None:
        pass


def _block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "label": "",
        "generated_sql": "SELECT 1",
        "rows": rows,
        "row_count": len(rows),
        "metadata": {},
    }


def _success(domain: str, data: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": "success",
        "domain": domain,
        "message": None,
        "data": data,
        "sources": [],
        "metadata": {},
    }


class _AlwaysSuccessPort:
    """질문 내용과 무관하게 sales 조회를 성공으로 응답하는 fake."""

    async def call_tool(self, tool_name: str, payload: dict[str, Any]) -> object:
        return _success("sales", [_block([{"total": 1000}])])


class _NeverCalledPort:
    """권한 확인이 MCP 호출 전에 막는지 검증할 때, 호출되면 바로 실패시킨다."""

    async def call_tool(self, tool_name: str, payload: dict[str, Any]) -> object:
        raise AssertionError("권한이 없는 요청은 MCP tool을 호출하면 안 된다.")


def _application(mcp: MCPClient, auth_gateway: FakeAuthenticationGateway) -> Any:
    dependencies = AppDependencies(
        llm=FakeLLMClient(),
        mcp=mcp,
        configure_logging=lambda: None,
        auth_gateway=auth_gateway,
    )
    return create_app(dependencies)


def test_list_report_templates_returns_registered_templates() -> None:
    application = _application(
        MCPClient(_NeverCalledPort()), FakeAuthenticationGateway()
    )
    with TestClient(application) as client:
        login(client)
        response = client.get("/api/reports/templates")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == ["sales_monthly"]


def test_generate_report_requires_authentication() -> None:
    application = _application(
        MCPClient(_NeverCalledPort()), FakeAuthenticationGateway()
    )
    with TestClient(application) as client:
        response = client.post(
            "/api/reports/generate",
            json={
                "template_id": "sales_monthly",
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
            },
        )

    assert response.status_code == 401


def test_generate_report_rejects_role_without_sales_access() -> None:
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
    application = _application(MCPClient(_NeverCalledPort()), gateway)

    with TestClient(application) as client:
        login(client)
        response = client.post(
            "/api/reports/generate",
            json={
                "template_id": "sales_monthly",
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
            },
        )

    assert response.status_code == 403


def test_generate_report_rejects_unknown_template() -> None:
    application = _application(
        MCPClient(_NeverCalledPort()), FakeAuthenticationGateway()
    )
    with TestClient(application) as client:
        login(client)
        response = client.post(
            "/api/reports/generate",
            json={
                "template_id": "no-such-template",
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
            },
        )

    assert response.status_code == 404


def test_generate_report_rejects_inverted_date_range() -> None:
    application = _application(
        MCPClient(_NeverCalledPort()), FakeAuthenticationGateway()
    )
    with TestClient(application) as client:
        login(client)
        response = client.post(
            "/api/reports/generate",
            json={
                "template_id": "sales_monthly",
                "start_date": "2026-03-31",
                "end_date": "2026-01-01",
            },
        )

    assert response.status_code == 422


def test_generate_report_streams_docx_with_download_headers() -> None:
    application = _application(MCPClient(_AlwaysSuccessPort()), FakeAuthenticationGateway())

    with TestClient(application) as client:
        login(client)
        response = client.post(
            "/api/reports/generate",
            json={
                "template_id": "sales_monthly",
                "start_date": "2026-01-01",
                "end_date": "2026-03-31",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment; filename*=UTF-8''")
    assert disposition.endswith(".docx")
    assert len(response.content) > 0
