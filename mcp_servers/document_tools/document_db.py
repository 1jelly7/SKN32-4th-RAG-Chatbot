"""내부 문서 DB에서 본문이 아닌 등록 파일 경로만 조회·관리한다."""

from __future__ import annotations

import pymysql
import pymysql.cursors

from app.core.config import get_settings
from app.core.db_pool import get_pool
from mcp_servers.document_tools.types import DocumentPathRecord


class DocumentPathRepository:
    """내부 문서 DB에서 문서 본문이 아닌 파일 경로 메타데이터만 조회한다."""

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """문서 DB 읽기 연결 풀을 준비한다.

        매 호출마다 새 TCP 연결을 열던 이전 방식은 문서 질문마다 핸드셰이크·인증
        왕복 비용이 그대로 지연시간에 쌓였다. 이제는 app.core.db_pool의 공유 풀에서
        연결을 빌려 쓰고 반납한다.
        """
        self._pool = get_pool(host, user, password, database, autocommit=False)

    async def find_paths(self, query: str) -> list[DocumentPathRecord]:
        """질문과 연관된 문서의 식별자·제목·파일 경로·갱신 시각을 반환한다.

        pymysql은 동기 클라이언트라, 이벤트 루프를 막지 않도록 실제 조회는
        스레드풀에서 실행합니다.

        이 저장소는 활성 문서 접근 허용 목록을 제공하고 의미적 관련성 판정은 FAISS에
        맡긴다. 질문 표현과 제목이 다를 수 있으므로 제목 LIKE 결과로 허용 목록을 좁히지
        않는다. 예를 들어 '겸직 규정'을 제목으로 선필터링하면 실제 근거인 '취업규칙'이
        제외되어 의미 검색이 복구할 수 없기 때문이다.
        """
        import asyncio

        return await asyncio.to_thread(self._find_paths_sync, query)

    async def find_path_by_document_id(
        self, document_id: str
    ) -> DocumentPathRecord | None:
        """활성 문서 ID만으로 다운로드용 화이트리스트 레코드를 찾는다."""
        import asyncio

        return await asyncio.to_thread(self._find_path_by_document_id_sync, document_id)

    def _find_paths_sync(self, query: str) -> list[DocumentPathRecord]:
        connection = self._pool.connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT document_id, title, file_path, updated_at "
                    "FROM document_paths WHERE is_active = TRUE"
                )
                return [self._to_record(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    def _find_path_by_document_id_sync(
        self, document_id: str
    ) -> DocumentPathRecord | None:
        connection = self._pool.connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT document_id, title, file_path, updated_at "
                    "FROM document_paths WHERE document_id = %s AND is_active = TRUE",
                    (document_id,),
                )
                row = cursor.fetchone()
                return self._to_record(row) if row is not None else None
        finally:
            connection.close()

    @staticmethod
    def _to_record(row: dict) -> DocumentPathRecord:
        return {
            "document_id": row["document_id"],
            "title": row["title"],
            "file_path": row["file_path"],
            "updated_at": (
                row["updated_at"].isoformat()
                if hasattr(row["updated_at"], "isoformat")
                else str(row["updated_at"])
            ),
        }

    def ensure_schema(self) -> None:
        """document_paths 테이블이 없으면 생성한다. (database/document/schema.sql과 동일 내용)"""
        connection = self._pool.connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS document_paths (
                        id BIGINT PRIMARY KEY AUTO_INCREMENT,
                        document_id VARCHAR(100) NOT NULL UNIQUE,
                        title VARCHAR(255) NOT NULL,
                        file_path VARCHAR(500) NOT NULL,
                        updated_at DATETIME NOT NULL,
                        is_active BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            connection.commit()
        finally:
            connection.close()

    def upsert_path(
        self, document_id: str, title: str, file_path: str, updated_at: str
    ) -> None:
        """문서 경로 1건을 등록하거나 갱신한다. (ingestion 배치가 사용)"""
        connection = self._pool.connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO document_paths (document_id, title, file_path, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        title = VALUES(title),
                        file_path = VALUES(file_path),
                        updated_at = VALUES(updated_at),
                        is_active = TRUE
                    """,
                    (document_id, title, file_path, updated_at),
                )
            connection.commit()
        finally:
            connection.close()


_default_repository: DocumentPathRepository | None = None


def _get_default_repository() -> DocumentPathRepository:
    global _default_repository
    if _default_repository is None:
        settings = get_settings()
        _default_repository = DocumentPathRepository(
            host=settings.document_db_host,
            user=settings.document_db_user,
            password=settings.document_db_password,
            database=settings.document_db_database,
        )
    return _default_repository


async def lookup_document_paths(query: str) -> list[DocumentPathRecord]:
    """설정된 DocumentPathRepository를 이용해 내부 문서 파일 경로를 조회한다."""
    return await _get_default_repository().find_paths(query)


async def lookup_document_path_by_id(document_id: str) -> DocumentPathRecord | None:
    """사용자 경로 입력 없이 활성 문서 ID의 등록 경로만 반환한다."""
    return await _get_default_repository().find_path_by_document_id(document_id)
