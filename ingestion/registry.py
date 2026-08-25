# -*- coding: utf-8 -*-
"""
문서 메타데이터 레지스트리 (MySQL, 옵션 B).

문서 "경로"는 여전히 ingestion/loaders.py가 data/raw/documents/를 직접 스캔해서
얻습니다. 이 모듈은 경로를 대신하지 않고, 파일명을 key로 제목 오버라이드/부서/
카테고리/허용 role(allowed_roles) 같은 "메타데이터"만 MySQL에서 읽고 씁니다.

app/core/config.Settings가 이미 read/write 계정을 분리해서 정의하고 있어서
(mysql_read_*는 조회 전용 chatbot_reader, mysql_write_*는 등록/갱신용 etl_writer)
이 모듈도 용도에 맞춰 연결을 나눕니다.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pymysql
import pymysql.cursors


@dataclass(frozen=True)
class DocumentMetadata:
    """document_registry 한 행을 표현하는 값 객체입니다."""

    filename: str
    title_override: str | None
    department: str | None
    category: str | None
    version_date: str | None
    allowed_roles: list[str]
    is_active: bool


def _parse_roles(raw: str | None) -> list[str]:
    """콤마로 구분된 role 문자열을 정규화된 리스트로 변환합니다.

    값이 비어 있거나 손상되어 있으면(예: 공백뿐인 문자열) "기본 거부" 원칙에 따라
    빈 리스트를 반환합니다 - 즉, 명시적으로 role을 등록하지 않은 문서는
    아무도 못 보는 쪽으로 안전하게 처리됩니다.
    """

    if not raw:
        return []

    roles = [role.strip() for role in raw.split(",") if role.strip()]
    return roles


class DocumentRegistry:
    """document_registry 테이블에 대한 읽기/쓰기 어댑터입니다."""

    def __init__(
        self,
        read_host: str,
        read_user: str,
        read_password: str,
        write_host: str,
        write_user: str,
        write_password: str,
        database: str,
    ) -> None:
        # 조회(ingestion 시 메타데이터 lookup)는 SELECT 권한만 있는 계정으로 연결합니다.
        self._read_conn_kwargs = dict(
            host=read_host,
            user=read_user,
            password=read_password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            charset="utf8mb4",
        )

        # 등록/갱신(register_documents.py)은 쓰기 권한이 있는 계정으로 연결합니다.
        self._write_conn_kwargs = dict(
            host=write_host,
            user=write_user,
            password=write_password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            charset="utf8mb4",
        )

    # ------------------------------------------------------------------
    # 스키마 준비 (database/schema.sql을 미리 실행했다면 사실 필요 없지만,
    # 스크립트 단독 실행 시에도 안전하게 동작하도록 존재 확인용으로 둡니다)
    # ------------------------------------------------------------------
    def ensure_schema(self) -> None:
        """document_registry 테이블이 없으면 생성합니다. (쓰기 계정 사용)"""

        connection = pymysql.connect(**self._write_conn_kwargs)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_registry (
                        id               BIGINT PRIMARY KEY AUTO_INCREMENT,
                        filename         VARCHAR(255) NOT NULL UNIQUE,
                        title_override   VARCHAR(255),
                        department       VARCHAR(100),
                        category         VARCHAR(100),
                        version_date     DATE,
                        allowed_roles    VARCHAR(255) NOT NULL DEFAULT 'user',
                        is_active        BOOLEAN DEFAULT TRUE,
                        updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                         ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
            connection.commit()
        finally:
            connection.close()

    # ------------------------------------------------------------------
    # 조회 (읽기 전용 계정)
    # ------------------------------------------------------------------
    def get_metadata(self, filename: str) -> DocumentMetadata | None:
        """파일명으로 메타데이터 1건을 조회합니다. 등록되어 있지 않으면 None을 반환합니다."""

        connection = pymysql.connect(**self._read_conn_kwargs)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT filename, title_override, department, category,
                           version_date, allowed_roles, is_active
                    FROM document_registry
                    WHERE filename = %s
                    """,
                    (filename,),
                )
                row = cursor.fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return DocumentMetadata(
            filename=row["filename"],
            title_override=row["title_override"],
            department=row["department"],
            category=row["category"],
            version_date=str(row["version_date"]) if row["version_date"] else None,
            allowed_roles=_parse_roles(row["allowed_roles"]),
            is_active=bool(row["is_active"]),
        )

    def list_all(self, active_only: bool = True) -> list[DocumentMetadata]:
        """등록된 문서 메타데이터 전체를 조회합니다."""

        connection = pymysql.connect(**self._read_conn_kwargs)
        try:
            with connection.cursor() as cursor:
                query = (
                    "SELECT filename, title_override, department, category, "
                    "version_date, allowed_roles, is_active FROM document_registry"
                )
                if active_only:
                    query += " WHERE is_active = TRUE"
                cursor.execute(query)
                rows = cursor.fetchall()
        finally:
            connection.close()

        return [
            DocumentMetadata(
                filename=row["filename"],
                title_override=row["title_override"],
                department=row["department"],
                category=row["category"],
                version_date=str(row["version_date"]) if row["version_date"] else None,
                allowed_roles=_parse_roles(row["allowed_roles"]),
                is_active=bool(row["is_active"]),
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # 등록/갱신 (쓰기 계정)
    # ------------------------------------------------------------------
    def upsert_metadata(
        self,
        filename: str,
        title_override: str | None = None,
        department: str | None = None,
        category: str | None = None,
        version_date: str | None = None,
        allowed_roles: list[str] | None = None,
        is_active: bool = True,
    ) -> None:
        """문서 1건의 메타데이터를 등록하거나 갱신합니다.

        allowed_roles를 생략하면 baseline role("user")만 부여해 전 직원 공개로 취급합니다.
        특정 role만 접근하게 하려면 allowed_roles=["hr", "purchase"]처럼 명시적으로 지정하세요.
        is_active는 기본적으로 True입니다 - 즉, 이미 비활성화(is_active=False)된 문서를
        다시 upsert하면 별도 지정이 없는 한 다시 활성화됩니다. 문서를 비활성화만 하고
        싶다면 upsert_metadata(filename, is_active=False, ...)처럼 명시적으로 호출하세요.
        """

        roles_value = ",".join(allowed_roles) if allowed_roles else "user"

        connection = pymysql.connect(**self._write_conn_kwargs)
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO document_registry
                        (filename, title_override, department, category, version_date,
                         allowed_roles, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        title_override = VALUES(title_override),
                        department = VALUES(department),
                        category = VALUES(category),
                        version_date = VALUES(version_date),
                        allowed_roles = VALUES(allowed_roles),
                        is_active = VALUES(is_active)
                    """,
                    (
                        filename,
                        title_override,
                        department,
                        category,
                        version_date,
                        roles_value,
                        is_active,
                    ),
                )
            connection.commit()
        finally:
            connection.close()


def build_registry_from_settings(settings: Any) -> DocumentRegistry:
    """app.core.config.Settings로부터 DocumentRegistry를 생성합니다."""

    return DocumentRegistry(
        read_host=settings.mysql_read_host,
        read_user=settings.mysql_read_user,
        read_password=settings.mysql_read_password,
        write_host=settings.mysql_write_host,
        write_user=settings.mysql_write_user,
        write_password=settings.mysql_write_password,
        database=settings.mysql_database,
    )
