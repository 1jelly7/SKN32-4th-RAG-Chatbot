"""브라우저에 공개되는 인증 API 경로."""

from django.urls import path

from django_app.accounts import views

urlpatterns = [
    path("csrf", views.csrf_token, name="auth-csrf"),
    path("login", views.login, name="auth-login"),
    path("logout", views.logout, name="auth-logout"),
    path("me", views.me, name="auth-me"),
]
