from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """채팅 요청을 안전한 GraphState로 변환해 그래프 결과를 HTTP 응답으로 만든다.

    request의 question을 검증하고, 클라이언트가 준 user_context는 신뢰하지 않은 채
    security 계층에서 인증 주체 기반 컨텍스트로 재구성한다. request_id를 부여해
    graph.ainvoke에 전달하고, answer/sources/cached/route를 ChatResponse로 직렬화한다.
    내부 오류·시간 초과는 비밀정보 없이 API 오류로 매핑한다.
    """
    ...
