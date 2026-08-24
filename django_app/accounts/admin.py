"""Django 관리자 화면의 사용자 관리 설정."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from django_app.accounts.models import User


@admin.register(User)
class AccountUserAdmin(UserAdmin):
    """애플리케이션 역할과 Django 관리자 권한을 별도 필드로 관리한다."""

    list_display = ("username", "display_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "display_name")
    fieldsets = UserAdmin.fieldsets + (
        (
            "Application access",
            {"fields": ("display_name", "role", "legacy_account_id")},
        ),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Application access", {"fields": ("display_name", "role")}),
    )
    readonly_fields = ("legacy_account_id",)
