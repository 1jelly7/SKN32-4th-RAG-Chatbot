"""사용자용 HTML 화면 view."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache


@never_cache
def index(request: HttpRequest) -> HttpResponse:
    """채팅 UI의 HTML shell을 반환한다.

    인증 복원과 실제 채팅 요청은 같은 origin의 인증·FastAPI API를 호출하는
    정적 JavaScript가 담당하며, view는 계정 DB나 업무 데이터에 접근하지 않는다.
    """
    return render(request, "web/index.html", {"active_tab": "chat"})


@never_cache
def dashboard(request: HttpRequest) -> HttpResponse:
    """이상탐지 대시보드 HTML shell을 반환한다.

    실제 대시보드 데이터·역할 기반 접근 제어는 클라이언트 JavaScript가 담당한다
    (index와 동일한 패턴). view는 계정 DB나 업무 데이터에 접근하지 않는다.
    """
    return render(request, "web/dashboard.html", {"active_tab": "dashboard"})
