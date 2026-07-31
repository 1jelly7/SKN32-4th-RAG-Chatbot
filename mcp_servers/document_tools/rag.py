from ingestion.types import RawDocument
from mcp_servers.document_tools.types import DocumentChunk


async def retrieve(
    query: str,
    documents: list[RawDocument],
    top_k: int,
) -> list[DocumentChunk]:
    """문서 DB 경로에서 읽은 문서만 대상으로 embedding 검색과 rerank를 수행한다.

    query/top_k와 문서 목록을 검증하고, embedding 모델·인덱스 차원·버전을 호환성
    검사한다. rerank는 후보의 원본 식별자와 score를 보존하고 내부 file_path는 응답에서
    제거한다.
    """
    ...
