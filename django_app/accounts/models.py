"""Django가 단독 소유하는 사용자와 애플리케이션 역할 모델."""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """기존 계정 필드를 보존하면서 Django 권한 모델을 사용하는 사용자."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        HR = "hr", "HR"
        FINANCE = "finance", "Finance"

    username = models.CharField(
        max_length=128,
        unique=True,
        help_text="기존 계정과 호환되는 128자 이하의 고유 사용자명입니다.",
    )
    display_name = models.CharField(max_length=128)
    role = models.CharField(max_length=16, choices=Role.choices)
    legacy_account_id = models.PositiveBigIntegerField(
        null=True, blank=True, unique=True
    )
    REQUIRED_FIELDS = ["email", "display_name", "role"]

    class Meta:
        db_table = "accounts_user"
        indexes = [
            models.Index(fields=["role", "is_active"], name="idx_user_role_active")
        ]

    def __str__(self) -> str:
        return self.username
