"""공개 인증 API와 FastAPI 전용 내부 세션 확인 API."""

from __future__ import annotations

import json
import secrets

from django.conf import settings
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from django_app.accounts.services import opaque_session_id, serialize_user


def _unauthorized() -> JsonResponse:
    return JsonResponse({"detail": "인증이 필요합니다."}, status=401)


@require_GET
@never_cache
@ensure_csrf_cookie
def csrf_token(request: HttpRequest) -> JsonResponse:
    """브라우저가 로그인·로그아웃 요청에 사용할 CSRF 토큰을 발급한다."""
    return JsonResponse({"csrf_token": get_token(request)})


@require_POST
@never_cache
def login(request: HttpRequest) -> JsonResponse:
    """활성 계정을 검증해 Django 서버 세션을 발급한다."""
    if len(request.body) > 4096:
        return JsonResponse({"detail": "로그인 요청 형식이 올바르지 않습니다."}, status=400)
    try:
        body = json.loads(request.body)
        username = body["username"]
        password = body["password"]
    except (json.JSONDecodeError, KeyError, TypeError, UnicodeDecodeError):
        return JsonResponse({"detail": "로그인 요청 형식이 올바르지 않습니다."}, status=400)
    if (
        not isinstance(username, str)
        or not isinstance(password, str)
        or not username
        or len(username) > 128
        or not password
        or len(password) > 256
    ):
        return JsonResponse({"detail": "로그인 요청 형식이 올바르지 않습니다."}, status=400)

    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse({"detail": "아이디 또는 비밀번호가 올바르지 않습니다."}, status=401)
    try:
        profile = serialize_user(user)
    except ValueError:
        return JsonResponse({"detail": "아이디 또는 비밀번호가 올바르지 않습니다."}, status=401)
    django_login(request, user)
    return JsonResponse({"user": profile})


@require_POST
@never_cache
def logout(request: HttpRequest) -> HttpResponse:
    """서버 세션을 폐기해 보관된 이전 쿠키의 재사용도 차단한다."""
    if not request.user.is_authenticated:
        return _unauthorized()
    django_logout(request)
    return HttpResponse(status=204)


@require_GET
@never_cache
@ensure_csrf_cookie
def me(request: HttpRequest) -> JsonResponse:
    """현재 활성 사용자의 공개 프로필을 반환한다."""
    if not request.user.is_authenticated or not request.user.is_active:
        return _unauthorized()
    try:
        return JsonResponse(serialize_user(request.user))
    except ValueError:
        return _unauthorized()


@csrf_exempt
@require_POST
@never_cache
def introspect(request: HttpRequest) -> JsonResponse:
    """내부 공유 키와 Django 세션을 모두 통과한 사용자 컨텍스트만 반환한다."""
    configured_key = settings.AUTH_INTROSPECTION_KEY
    supplied_header = request.headers.get("Authorization", "")
    supplied_key = supplied_header.removeprefix("Bearer ") if supplied_header.startswith("Bearer ") else ""
    if len(configured_key) < 32:
        return JsonResponse({"detail": "인증 서비스 설정이 준비되지 않았습니다."}, status=503)
    if not supplied_key or not secrets.compare_digest(supplied_key, configured_key):
        return JsonResponse({"detail": "허용되지 않은 내부 요청입니다."}, status=403)
    if not request.user.is_authenticated or not request.user.is_active:
        return _unauthorized()

    session_key = request.session.session_key
    if not session_key:
        return _unauthorized()
    try:
        profile = serialize_user(request.user)
    except ValueError:
        return _unauthorized()
    return JsonResponse(
        {
            **profile,
            "session_id": opaque_session_id(session_key, configured_key),
        }
    )


def csrf_failure(request: HttpRequest, reason: str = "") -> JsonResponse:
    """CSRF 검증 실패를 내부 사유 노출 없이 JSON 오류로 변환한다."""
    return JsonResponse({"detail": "요청 검증에 실패했습니다."}, status=403)
