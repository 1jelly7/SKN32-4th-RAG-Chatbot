"""FastAPI와 Django 사이 내부 인증 확인 HTTP 계약."""

from __future__ import annotations

import httpx
import pytest

from app.auth.gateway import AuthenticationUnavailableError, DjangoAuthenticationGateway

INTROSPECTION_KEY = "test-introspection-key-that-is-at-least-32-bytes"
OPAQUE_SESSION_ID = "a" * 64


@pytest.mark.asyncio
async def test_gateway_forwards_only_internal_key_and_session_cookie() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == f"Bearer {INTROSPECTION_KEY}"
        assert request.headers["cookie"] == "chatbot_session=djangosession"
        return httpx.Response(
            200,
            json={
                "user_id": 7,
                "username": "finance",
                "display_name": "Finance User",
                "role": "finance",
                "session_id": OPAQUE_SESSION_ID,
            },
        )

    gateway = DjangoAuthenticationGateway(
        "http://django/internal/auth/introspect",
        INTROSPECTION_KEY,
        transport=httpx.MockTransport(handler),
    )
    user = await gateway.authenticate("djangosession")
    await gateway.aclose()

    assert user is not None
    assert user["user_id"] == 7
    assert user["role"] == "finance"


@pytest.mark.asyncio
async def test_gateway_maps_invalid_session_to_none() -> None:
    gateway = DjangoAuthenticationGateway(
        "http://django/internal/auth/introspect",
        INTROSPECTION_KEY,
        transport=httpx.MockTransport(lambda request: httpx.Response(401)),
    )
    assert await gateway.authenticate("invalidsession") is None
    await gateway.aclose()


@pytest.mark.asyncio
async def test_gateway_rejects_malformed_success_payload() -> None:
    gateway = DjangoAuthenticationGateway(
        "http://django/internal/auth/introspect",
        INTROSPECTION_KEY,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"role": "admin"})
        ),
    )
    with pytest.raises(AuthenticationUnavailableError):
        await gateway.authenticate("djangosession")
    await gateway.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"),
    [("user_id", True), ("role", "unknown"), ("session_id", "raw-session-key")],
)
async def test_gateway_rejects_wrong_success_field_types(
    field: str, value: object
) -> None:
    payload: dict[str, object] = {
        "user_id": 7,
        "username": "finance",
        "display_name": "Finance User",
        "role": "finance",
        "session_id": OPAQUE_SESSION_ID,
    }
    payload[field] = value
    gateway = DjangoAuthenticationGateway(
        "http://django/internal/auth/introspect",
        INTROSPECTION_KEY,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=payload)
        ),
    )
    with pytest.raises(AuthenticationUnavailableError):
        await gateway.authenticate("djangosession")
    await gateway.aclose()
