"""Django 관리자 화면의 사용자 관리 설정."""

from django.conf import settings
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.http import HttpRequest

from django_app.accounts.models import User


@admin.register(User)
class AccountUserAdmin(UserAdmin):
    """애플리케이션 역할과 Django 관리자 권한을 별도 필드로 관리한다."""

    list_display = ("username", "display_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("username", "display_name")
    fieldsets = UserAdmin.fieldsets + (
        ("Application access", {"fields": ("display_name", "role", "legacy_account_id")}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Application access", {"fields": ("display_name", "role")}),
    )
    readonly_fields = ("legacy_account_id",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        """롤백 관찰 중에는 legacy에 없는 신규 애플리케이션 계정을 만들지 않는다."""
        if settings.LEGACY_AUTH_ROLLBACK_WINDOW:
            return False
        return super().has_add_permission(request)

    def has_change_permission(self, request: HttpRequest, obj: User | None = None) -> bool:
        """롤백 관찰 중에는 legacy 계정과 Django 계정의 권한·비밀번호 분기를 막는다."""
        if (
            obj is not None
            and obj.legacy_account_id is not None
            and settings.LEGACY_AUTH_ROLLBACK_WINDOW
        ):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request: HttpRequest, obj: User | None = None) -> bool:
        """롤백 관찰 중에는 신규·legacy 계정의 삭제와 bulk delete를 차단한다."""
        if settings.LEGACY_AUTH_ROLLBACK_WINDOW and (
            obj is None or obj.legacy_account_id is not None
        ):
            return False
        return super().has_delete_permission(request, obj)
