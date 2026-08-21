"""Django 계정, legacy 비밀번호와 공개·내부 인증 API 계약."""

from __future__ import annotations

from importlib import import_module

import pytest
from django.contrib.admin.sites import AdminSite
from django.conf import settings
from django.test import Client, RequestFactory

from app.auth.passwords import hash_password
from django_app.accounts.admin import AccountUserAdmin
from django_app.accounts.models import User


def _csrf_client() -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    response = client.get("/api/auth/csrf")
    return client, response.json()["csrf_token"]


def _login(client: Client, csrf_token: str, username: str, password: str):
    return client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )


def test_login_me_introspect_logout_contract(db) -> None:
    User.objects.create_user(
        username="finance",
        password="finance-password",
        display_name="Finance User",
        role="finance",
    )
    client, csrf_token = _csrf_client()

    login = _login(client, csrf_token, "finance", "finance-password")
    assert login.status_code == 200
    assert login.json()["user"]["allowed_databases"] == ["document_db", "purchase_db", "sales_db"]
    assert "password" not in login.content.decode()
    session_cookie = login.cookies[settings.SESSION_COOKIE_NAME]
    assert session_cookie["httponly"] is True
    assert session_cookie["samesite"] == "Lax"
    assert bool(session_cookie["secure"]) is settings.SESSION_COOKIE_SECURE
    csrf_cookie = client.cookies["csrftoken"]
    assert csrf_cookie["samesite"] == "Lax"
    assert bool(csrf_cookie["secure"]) is settings.CSRF_COOKIE_SECURE
    previous_cookie = client.cookies[settings.SESSION_COOKIE_NAME].value
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert "no-cache" in me.headers["Cache-Control"]

    introspection = client.post(
        "/internal/auth/introspect",
        HTTP_AUTHORIZATION=f"Bearer {settings.AUTH_INTROSPECTION_KEY}",
    )
    assert introspection.status_code == 200
    assert len(introspection.json()["session_id"]) == 64
    assert settings.AUTH_INTROSPECTION_KEY not in introspection.content.decode()

    rotated_csrf_token = client.get("/api/auth/csrf").json()["csrf_token"]
    logout = client.post("/api/auth/logout", HTTP_X_CSRFTOKEN=rotated_csrf_token)
    assert logout.status_code == 204
    replay = Client()
    replay.cookies[settings.SESSION_COOKIE_NAME] = previous_cookie
    assert replay.post(
        "/internal/auth/introspect",
        HTTP_AUTHORIZATION=f"Bearer {settings.AUTH_INTROSPECTION_KEY}",
    ).status_code == 401


def test_login_requires_csrf_and_blocks_inactive_user(db) -> None:
    User.objects.create_user(
        username="disabled",
        password="disabled-password",
        display_name="Disabled",
        role="hr",
        is_active=False,
    )
    client = Client(enforce_csrf_checks=True)
    assert _login(client, "missing", "disabled", "disabled-password").status_code == 403
    client, csrf_token = _csrf_client()
    assert _login(client, csrf_token, "disabled", "disabled-password").status_code == 401


def test_legacy_scrypt_is_rehashed_after_successful_login(db) -> None:
    legacy_hash = hash_password("legacy-password")
    user = User.objects.create(
        username="legacy",
        password=legacy_hash,
        display_name="Legacy User",
        role="hr",
        is_active=True,
    )
    client, csrf_token = _csrf_client()

    assert _login(client, csrf_token, "legacy", "legacy-password").status_code == 200
    user.refresh_from_db()
    assert user.password.startswith("pbkdf2_sha256$")


def test_application_admin_role_does_not_grant_django_admin_access(db) -> None:
    user = User.objects.create_user(
        username="app-admin",
        password="admin-password",
        display_name="Application Admin",
        role="admin",
    )
    assert user.is_staff is False
    assert user.is_superuser is False


def test_introspection_rejects_wrong_internal_key(db) -> None:
    User.objects.create_user(
        username="hr",
        password="hr-password",
        display_name="HR User",
        role="hr",
    )
    client, csrf_token = _csrf_client()
    assert _login(client, csrf_token, "hr", "hr-password").status_code == 200
    assert client.post(
        "/internal/auth/introspect",
        HTTP_AUTHORIZATION="Bearer wrong-key",
    ).status_code == 403


def test_login_rejects_non_string_credentials(db) -> None:
    client, csrf_token = _csrf_client()
    response = client.post(
        "/api/auth/login",
        data={"username": 1, "password": ["not", "a", "string"]},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    assert response.status_code == 400


def test_custom_user_command_fields_and_legacy_hash_validation() -> None:
    assert User.REQUIRED_FIELDS == ["email", "display_name", "role"]
    assert settings.STATIC_URL == "/django-static/"
    assert settings.SESSION_SAVE_EVERY_REQUEST is False
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.CSRF_COOKIE_SAMESITE == "Lax"
    migration = import_module("django_app.accounts.migrations.0002_import_legacy_accounts")
    with pytest.raises(RuntimeError, match="Unsupported legacy password hash"):
        migration._validate_legacy_password_hash(
            "scrypt$999999$8$1$c2FsdA==$aGFzaA==$32",
            7,
        )


def test_admin_freezes_migrated_users_during_rollback_window() -> None:
    request = RequestFactory().get("/admin/accounts/user/")
    request.user = User(username="root", is_active=True, is_staff=True, is_superuser=True)
    migrated_user = User(username="legacy", legacy_account_id=7)
    model_admin = AccountUserAdmin(User, AdminSite())

    assert settings.LEGACY_AUTH_ROLLBACK_WINDOW is True
    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request, migrated_user) is False
    assert model_admin.has_delete_permission(request, migrated_user) is False
