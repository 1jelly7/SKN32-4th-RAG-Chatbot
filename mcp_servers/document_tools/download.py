"""등록된 문서 ID를 다운로드 가능한 원본 파일로 안전하게 해석한다."""

from __future__ import annotations

from pathlib import Path

from mcp_servers.document_tools.document_db import lookup_document_path_by_id


async def resolve_document_download(document_id: str) -> Path | None:
    """문서 DB 화이트리스트의 활성 ID만 원본 파일로 해석한다.

    채팅 출처 카드에서 받은 ``document_id``에만 사용한다. 임의 파일 경로나
    디렉터리를 받지 않으며, 반환 경로는 같은 프로세스의 다운로드 응답 생성에만 쓴다.
    """
    record = await lookup_document_path_by_id(document_id)
    if record is None:
        return None
    path = Path(record["file_path"])
    if not path.is_file():
        return None
    return path.resolve()
