from __future__ import annotations

from mcp_servers.document_tools.types import DocumentPathRecord


class DocumentPathRepository:
    """내부 문서 DB에서 문서 본문이 아닌 파일 경로 메타데이터만 조회한다."""

    def __init__(self, host: str, user: str, password: str, database: str) -> None:
        """문서 DB 읽기 연결 설정을 보관하며 비밀번호를 로그에 남기지 않는다."""
        ...

    async def find_paths(self, query: str) -> list[DocumentPathRecord]:
        """질문과 연관된 문서의 식별자·제목·파일 경로·갱신 시각을 반환한다."""
        ...


async def lookup_document_paths(query: str) -> list[DocumentPathRecord]:
    """설정된 DocumentPathRepository를 이용해 내부 문서 파일 경로를 조회한다."""
    ...
