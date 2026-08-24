"""보호 API가 공통으로 사용하는 서버 측 사용자 컨텍스트 dependency다."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Cookie, Depends, HTTPException, Request, status

from app.auth.gateway import AuthenticationUnavailableError
from app.auth.policy import Role, allowed_databases

SESSION_COOKIE_NAME = "chatbot_session"


async def current_user(
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, object]:
    """HttpOnly Django 세션을 내부 API로 확인하고 401을 강제한다."""
    if session_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다."
        )
    try:
        payload = await request.app.state.dependencies.auth_gateway.authenticate(
            session_token
        )
    except AuthenticationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="인증 서비스를 사용할 수 없습니다.",
        ) from exc
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다."
        )
    try:
        role = cast(Role, payload["role"])
        user_id = payload["user_id"]
        username = payload["username"]
        display_name = payload["display_name"]
        session_id = payload["session_id"]
        if (
            role not in ("admin", "hr", "finance")
            or type(user_id) is not int
            or user_id < 1
            or not isinstance(username, str)
            or not username
            or not isinstance(display_name, str)
            or not isinstance(session_id, str)
            or not session_id
        ):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
        ) from None
    return {
        "user_id": user_id,
        "username": username,
        "display_name": display_name,
        "session_id": session_id,
        "role": role,
        "allowed_databases": allowed_databases(role),
    }


CurrentUser = Annotated[dict[str, object], Depends(current_user)]
