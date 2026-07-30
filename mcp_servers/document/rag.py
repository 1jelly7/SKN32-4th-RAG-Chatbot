from mcp_servers.document.types import DocumentChunk


async def retrieve(query: str, top_k: int) -> list[DocumentChunk]:
    """질문을 embedding해 FAISS 후보를 검색하고 필요 시 rerank한다.

    query/top_k를 검증하고, embedding 모델·인덱스 차원·버전을 호환성 검사한다. rerank는
    후보의 원본 식별자와 score를 보존하며 이 함수는 ACL 없이 최종 사용자 결과를 반환하지
    않는다.
    """
    ...
