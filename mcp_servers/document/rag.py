"""ACL 적용 전 문서 후보를 얻기 위한 별도 RAG 스켈레톤."""

from mcp_servers.document.types import DocumentChunk


async def retrieve(query: str, top_k: int) -> list[DocumentChunk]:
    """질문을 embedding해 FAISS 후보를 검색하고 필요 시 rerank한다.

    query/top_k를 검증하고, embedding 모델·인덱스 차원·버전을 호환성 검사한다. rerank는
    후보의 원본 식별자와 score를 보존하며 이 함수는 ACL 없이 최종 사용자 결과를 반환하지
    않는다.
    """
    # TODO(implementation): 확정된 embedding/index version 계약으로 ACL 필터에 충분한
    # 후보를 검색한다. 빈 질문, 잘못된 top_k, 차원·버전 불일치 회귀가 완료 조건이다.
    ...
