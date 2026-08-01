"""ACL 기반 별도 Document MCP의 미구현 FAISS 저장소 경계."""

from __future__ import annotations

from pathlib import Path

from mcp_servers.document.types import DocumentChunk, IndexMetadata


class FaissStore:
    """FAISS 인덱스와 chunk metadata를 함께 다루는 읽기 전용 저장소."""
    def __init__(self, index_path: Path) -> None:
        """인덱스 경로와 대응 metadata 경로를 보관하되 즉시 대용량 파일을 읽지 않는다."""
        # TODO(contract clarification): document_tools.FaissStore와 이 adapter 중 공식
        # 경계를 확정한 뒤 index/metadata 경로만 보관하도록 구현한다.
        ...

    def load(self) -> IndexMetadata:
        """FAISS 파일과 metadata 파일의 존재·버전·개수·차원을 검증해 메모리에 로드한다.

        둘 중 하나만 갱신된 불일치나 손상은 검색 결과로 숨기지 말고 안전하게 실패시킨다.
        """
        # TODO(implementation): 벡터/청크 수, 차원, 버전 일관성을 함께 검증하고 손상이나
        # 반쪽 갱신을 명시적 오류로 처리하는 fixture test를 추가한다.
        ...

    def search(self, vector: list[float], top_k: int) -> list[DocumentChunk]:
        """로드된 인덱스에서 top_k 후보를 거리/점수와 함께 반환한다.

        query vector 차원과 top_k 상한을 검증하고, 검색 결과의 index id를 metadata와 정확히
        매핑한다. 이 계층은 ACL을 결정하지 않으므로 호출자가 추가 후보를 확보해 필터링한다.
        """
        # TODO(implementation): load 선행·차원·top_k를 검증해 내부 경로 없는 후보를
        # 반환한다. ACL 적용은 호출자 책임이며 이 단계에서 사용자에게 노출하지 않는다.
        ...
