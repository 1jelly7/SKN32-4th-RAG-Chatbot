from __future__ import annotations

import pymysql
import pymysql.cursors

from app.core.config import get_settings
from mcp_servers.document_tools.types import DocumentPathRecord


class DocumentPathRepository:
    """내부 문서 DB에서 문서 본문이 아닌 파일 경로 메타데이터만 조회한다."""

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """문서 DB 읽기 연결 설정을 보관하며 비밀번호를 로그에 남기지 않는다."""
        # 연결은 매 호출마다 새로 여는 방식(단순하고 커넥션 누수 위험이 적음)입니다.
        # 이 kwargs 딕셔너리 자체를 로그로 출력하지 않도록 주의합니다.
        self._connection_kwargs = dict(
            host=host,
            user=user,
            password=password,
            database=database,
            cursorclass=pymysql.cursors.DictCursor,
            charset="utf8mb4",
        )

    async def find_paths(self, query: str) -> list[DocumentPathRecord]:
        """질문과 연관된 문서의 식별자·제목·파일 경로·갱신 시각을 반환한다.

        pymysql은 동기 클라이언트라, 이벤트 루프를 막지 않도록 실제 조회는
        스레드풀에서 실행합니다.

        지금 단계에서는 제목에 대한 단순 키워드 매칭으로 관련 문서를 좁히고,
        하나도 안 걸리면(질문이 아주 구체적이지 않은 경우가 많으므로) 활성 문서
        전체를 반환합니다 - 최종 순위는 뒤 단계인 FAISS 벡터 검색이 정하기 때문에,
        여기서는 "완전히 무관해 보이는 문서만 제외"하는 정도의 느슨한 필터면 충분합니다.
        """
        import asyncio

        return await asyncio.to_thread(self._find_paths_sync, query)

    def _find_paths_sync(self, query: str) -> list[DocumentPathRecord]:
        connection = pymysql.connect(**self._connection_kwargs)
        try:
            with connection.cursor() as cursor:
                keywords = [w for w in query.split() if len(w) >= 2]

                if keywords:
                    conditions = " OR ".join(["title LIKE %s"] * len(keywords))
                    params = [f"%{kw}%" for kw in keywords]
                    cursor.execute(
                        f"SELECT document_id, title, file_path, updated_at "
                        f"FROM document_paths WHERE is_active = TRUE AND ({conditions})",
                        params,
                    )
                    rows = cursor.fetchall()
                    if rows:
                        return [self._to_record(row) for row in rows]

                # 제목 키워드로 못 좁혔으면 활성 문서 전체를 반환합니다.
                cursor.execute(
                    "SELECT document_id, title, file_path, updated_at "
                    "FROM document_paths WHERE is_active = TRUE"
                )
                return [self._to_record(row) for row in cursor.fetchall()]
        finally:
            connection.close()

    @staticmethod
    def _to_record(row: dict) -> DocumentPathRecord:
        return {
            "document_id": row["document_id"],
            "title": row["title"],
            "file_path": row["file_path"],
            "updated_at": row["updated_at"].isoformat() if hasattr(row["updated_at"], "isoformat") else str(row["updated_at"]),
        }

    def ensure_schema(self) -> None:
        """document_paths 테이블이 없으면 생성한다. (database/document/schema.sql과 동일 내용)"""
        connection = pymysql.connect(**self._connection_kwargs)
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

    def upsert_path(self, document_id: str, title: str, file_path: str, updated_at: str) -> None:
        """문서 경로 1건을 등록하거나 갱신한다. (ingestion 배치가 사용)"""
        connection = pymysql.connect(**self._connection_kwargs)
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
