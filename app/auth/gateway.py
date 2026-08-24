"""Django가 소유한 세션을 FastAPI가 확인하는 서비스 경계."""

from __future__ import annotations

import re
from typing import Protocol, TypedDict, cast

import httpx

from shared.auth_policy import Role

_DJANGO_SESSION_KEY = re.compile(r"[A-Za-z0-9]{1,128}")
_OPAQUE_SESSION_ID = re.compile(r"[0-9a-f]{64}")


class AuthenticatedUser(TypedDict):
    """Django 인증 확인 응답에서 허용하는 최소 사용자 컨텍스트."""

    user_id: int
    username: str
    display_name: str
    role: Role
    session_id: str


class AuthenticationUnavailableError(RuntimeError):
    """Django 인증 서비스의 장애나 잘못된 응답을 나타낸다."""


class AuthenticationGateway(Protocol):
    """세션 쿠키를 계정 저장소 접근 없이 사용자 컨텍스트로 교환한다."""

    async def authenticate(self, session_token: str) -> AuthenticatedUser | None: ...


class DjangoAuthenticationGateway:
    """Django 내부 인증 확인 API만 호출하는 FastAPI용 HTTP 어댑터."""

    def __init__(
        self,
        url: str,
        introspection_key: str,
        timeout_seconds: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._url = url
        self._introspection_key = introspection_key
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
            transport=transport,
            trust_env=False,
        )

    async def authenticate(self, session_token: str) -> AuthenticatedUser | None:
        """Django 세션을 확인하고 비밀정보 없는 사용자 컨텍스트만 반환한다."""
        if len(self._introspection_key) < 32:
            raise AuthenticationUnavailableError("인증 확인 키가 구성되지 않았습니다.")
        if _DJANGO_SESSION_KEY.fullmatch(session_token) is None:
            return None
        try:
            response = await self._client.post(
                self._url,
                headers={
                    "Authorization": f"Bearer {self._introspection_key}",
                    "Cookie": f"chatbot_session={session_token}",
                },
            )
        except httpx.HTTPError as exc:
            raise AuthenticationUnavailableError(
                "인증 서비스에 연결할 수 없습니다."
            ) from exc

        if response.status_code == 401:
            return None
        if response.status_code == 403:
            raise AuthenticationUnavailableError(
                "인증 서비스 내부 호출 권한이 거부되었습니다."
            )
        if response.status_code != 200:
            raise AuthenticationUnavailableError(
                "인증 서비스가 요청을 처리하지 못했습니다."
            )

        try:
            payload = response.json()
            user_id = payload["user_id"]
            username = payload["username"]
            display_name = payload["display_name"]
            role = cast(Role, payload["role"])
            session_id = payload["session_id"]
            if (
                type(user_id) is not int
                or user_id < 1
                or not isinstance(username, str)
                or not username
                or len(username) > 128
                or not isinstance(display_name, str)
                or len(display_name) > 128
                or role not in ("admin", "hr", "finance")
                or not isinstance(session_id, str)
                or _OPAQUE_SESSION_ID.fullmatch(session_id) is None
            ):
                raise ValueError
            user = AuthenticatedUser(
                user_id=user_id,
                username=username,
                display_name=display_name,
                role=role,
                session_id=session_id,
            )
            return user
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationUnavailableError(
                "인증 서비스 응답 계약이 올바르지 않습니다."
            ) from exc

    async def aclose(self) -> None:
        """공유 HTTP 연결 풀을 애플리케이션 종료 시 정리한다."""
        await self._client.aclose()


class SettingsDjangoAuthenticationGateway:
    """운영 설정 읽기를 첫 보호 요청까지 지연하는 gateway."""

    def __init__(self) -> None:
        self._gateway: DjangoAuthenticationGateway | None = None

    def _get(self) -> DjangoAuthenticationGateway:
        if self._gateway is None:
            from app.core.config import get_settings

            settings = get_settings()
            self._gateway = DjangoAuthenticationGateway(
                settings.django_auth_introspection_url,
                settings.auth_introspection_key,
                settings.auth_introspection_timeout_seconds,
            )
        return self._gateway

    async def authenticate(self, session_token: str) -> AuthenticatedUser | None:
        """현재 설정에 구성된 Django 인증 gateway로 요청을 위임한다."""
        return await self._get().authenticate(session_token)

    async def aclose(self) -> None:
        """실제 gateway가 생성된 경우에만 연결 풀을 정리한다."""
        if self._gateway is not None:
            await self._gateway.aclose()
            self._gateway = None
