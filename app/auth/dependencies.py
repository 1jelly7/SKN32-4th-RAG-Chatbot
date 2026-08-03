"""보호 API가 공통으로 사용하는 서버 측 사용자 컨텍스트 dependency다."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Cookie, Depends, HTTPException, Request, status

from app.auth.sessions import read_session
from app.auth.policy import Role

SESSION_COOKIE_NAME = "chatbot_session"


async def current_user(
    request: Request,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> dict[str, object]:
    """HttpOnly 쿠키에서만 검증된 사용자 컨텍스트를 복원하고 401을 강제한다."""
    secret = request.app.state.auth_secret
    payload = read_session(session_token, secret) if session_token else None
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다.")
    try:
        role = cast(Role, payload["role"])
        if role not in ("admin", "hr", "finance"):
            raise ValueError
        user_id = int(payload["user_id"])
        username, display_name = str(payload["username"]), str(payload["display_name"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="인증이 필요합니다.")
    from app.auth.policy import allowed_databases
    return {"user_id": user_id, "username": username, "display_name": display_name, "role": role,
            "allowed_databases": allowed_databases(role)}


CurrentUser = Annotated[dict[str, object], Depends(current_user)]
