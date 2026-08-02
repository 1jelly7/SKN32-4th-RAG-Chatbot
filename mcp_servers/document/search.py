"""사용자 ACL을 포함하려는 별도 Document MCP 공개 검색 스켈레톤."""

from app.core.security import UserContext
from mcp_servers.document.types import DocumentChunk


async def search_documents(
    query: str,
    user_context: UserContext,
    top_k: int = 5,
) -> list[DocumentChunk]:
    """Document MCP 공개 도구의 검색 흐름을 수행한다.

    사용자 범위를 검증한 뒤 retrieve로 충분한 후보를 얻고 ACL 필터를 적용하며, 필요하면
    top_k까지 자른다. 반환 항목은 chunk_id, document_id, title, content, score, updated_at,
    allowed_roles를 포함해야 하고, ACL 필터 전에 결과 수를 줄여 권한 문서가 누락되지 않게
    한다.
    """
    # TODO(contract clarification): 공식 Tool 입력에는 user_context가 정의돼 있지 않다.
    # 인증 context 전달·검증과 cache 격리 계약을 확정한 뒤 retrieve→ACL→top_k 순서를
    # 구현하며 비허용 후보 내용을 오류에도 노출하지 않는다.
    ...
