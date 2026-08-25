"""공개 라우터에서 분리한 서비스 간 인증 확인 경로."""

from django.urls import path

from django_app.accounts import views

urlpatterns = [path("introspect", views.introspect, name="auth-introspect")]
