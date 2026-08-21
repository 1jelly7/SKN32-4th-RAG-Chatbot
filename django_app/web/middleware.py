"""Django 사용자 UI에만 적용하는 브라우저 보안 헤더."""

from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


class ContentSecurityPolicyMiddleware:
    """`web` namespace의 HTML 응답에 최소 권한 CSP를 추가한다.

    Django Admin은 별도 inline 자산 계약을 가지므로 이 UI 전용 정책의 대상에서 제외한다.
    style 속성은 채팅 입력창 높이를 동적으로 조절하는 기존 UI 동작 때문에 허용하되,
    스크립트·연결·frame의 출처는 same-origin으로 제한한다.
    """

    policy = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        resolver_match = getattr(request, "resolver_match", None)
        content_type = response.headers.get("Content-Type", "")
        if getattr(resolver_match, "namespace", None) == "web" and content_type.startswith("text/html"):
            response.headers["Content-Security-Policy"] = self.policy
        return response
