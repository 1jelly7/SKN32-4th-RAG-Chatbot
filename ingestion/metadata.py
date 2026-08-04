"""
RawDocument에 표준 metadata(출처 경로, 제목, 갱신 시각)를 붙입니다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingestion.types import RawDocument


def build_metadata(document: RawDocument) -> dict[str, Any]:
    """출처 경로, 제목, 갱신 시각, 문서 버전을 포함한 표준 metadata를 만든다.

    - title은 document에 이미 있으면 그대로 쓰고(양끝 공백만 정리), 없으면 파일명으로
      대체합니다.
    - updated_at은 실제 파일의 마지막 수정 시각(mtime)을 사용합니다 - 문서 DB가 알려준
      값이 아니라 파일 자체의 진짜 변경 시점을 기록해, 문서 DB 등록 시각과 실제 파일
      변경 시각이 어긋나는 경우에도 정확한 값을 유지합니다.
    - content, 원본 file_path 등 민감하거나 이미 다른 곳에 있는 필드는 중복 저장하지
      않습니다.
    """

    path = Path(document["path"])
    title = (document.get("title") or path.stem).strip()

    return {
        "document_id": document["document_id"],
        "title": title,
        "file_name": path.name,
        "updated_at": _resolve_updated_at(path),
    }


def _resolve_updated_at(path: Path) -> str:
    """파일의 실제 수정 시각을 ISO 8601 문자열로 반환한다.

    파일이 없어졌거나 접근할 수 없는 경우(예: 조회 시점과 인덱싱 시점 사이 삭제)에는
    현재 시각으로 대체해, 파이프라인이 예외로 죽지 않게 합니다.
    """
    try:
        mtime = path.stat().st_mtime
        return datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
    except OSError:
        return datetime.now(tz=timezone.utc).isoformat()
