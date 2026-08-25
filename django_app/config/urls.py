"""인증 API, 내부 인증 확인 API와 관리자 화면 경로."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles import views as staticfiles_views
from django.urls import include, path, re_path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("django_app.accounts.urls")),
    path("internal/auth/", include("django_app.accounts.internal_urls")),
    path("", include("django_app.web.urls")),
]

if settings.SERVE_STATIC_FILES:
    urlpatterns += [
        re_path(
            r"^django-static/(?P<path>.*)$",
            staticfiles_views.serve,
            {"insecure": True},
            name="development-static",
        )
    ]
