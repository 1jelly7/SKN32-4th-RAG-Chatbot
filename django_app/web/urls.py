"""사용자 웹 화면 URL."""

from __future__ import annotations

from django.urls import path

from django_app.web import views

app_name = "web"

urlpatterns = [
    path("", views.index, name="index"),
    path("dashboard/", views.dashboard, name="dashboard"),
]
