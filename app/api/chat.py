from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """캐시 경계와 LangGraph를 순서대로 실행해 HTTP 응답을 만든다.

    request의 question을 검증해 GraphState를 생성한 뒤
    app.cache.service.lookup_cached_answer를 먼저 호출하고, miss일 때만 graph.ainvoke를
    실행한다. graph 완료 뒤 write_answer_cache를 호출하고 answer/sources/cached/route를
    ChatResponse로 직렬화한다. 내부 오류·시간 초과는 비밀정보 없이 API 오류로 매핑한다.
    """
    ...
