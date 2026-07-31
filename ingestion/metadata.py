from typing import Any

from ingestion.types import DocumentChunk, RawDocument


def build_metadata(document: RawDocument) -> dict[str, Any]:
    """출처 경로, 제목, 갱신 시각, 문서 버전, ACL 후보를 포함한 표준 metadata를 만든다.

    사용자 입력값은 정규화하고, 실제 파일 변경 정보에 근거한 updated_at을 기록한다.
    문서 본문이나 불필요한 민감 필드는 metadata에 중복 저장하지 않는다.
    """
    ...


def apply_acl(chunk: DocumentChunk, allowed_roles: list[str]) -> DocumentChunk:
    """원본 chunk를 변형하지 않고 정규화한 allowed_roles를 metadata에 붙여 반환한다.

    빈 ACL의 의미(비공개 또는 공개)는 정책으로 명시하며, 역할 와일드카드로 의도치 않게
    권한이 확대되지 않도록 검증한다.
    """
    ...
