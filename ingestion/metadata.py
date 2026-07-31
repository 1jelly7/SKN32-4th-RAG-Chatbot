from typing import Any

from ingestion.types import RawDocument


def build_metadata(document: RawDocument) -> dict[str, Any]:
    """출처 경로, 제목, 갱신 시각, 문서 버전을 포함한 표준 metadata를 만든다.

    사용자 입력값은 정규화하고, 실제 파일 변경 정보에 근거한 updated_at을 기록한다.
    문서 본문이나 불필요한 민감 필드는 metadata에 중복 저장하지 않는다.
    """
    ...
