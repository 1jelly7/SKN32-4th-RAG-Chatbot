<<<<<<< HEAD
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException

from app.agent.graph import get_graph
from app.agent.state import GraphState
from app.cache.service import lookup_cached_answer, write_answer_cache
from app.schemas.chat import ChatRequest, ChatResponse, Source
=======
from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """캐시 경계와 LangGraph를 순서대로 실행해 HTTP 응답을 만든다.

    request의 question을 검증해 GraphState를 생성한 뒤
    app.cache.service.lookup_cached_answer를 먼저 호출하고, miss일 때만 graph.ainvoke를
    실행한다. graph 완료 뒤 write_answer_cache를 호출하고 answer/sources/cached/route를
    ChatResponse로 직렬화한다. 내부 오류·시간 초과는 비밀정보 없이 API 오류로 매핑한다.
    """
<<<<<<< HEAD
    request_id = str(uuid.uuid4())

    state: GraphState = {
        "question": request.question,
        "session_id": request.session_id,
        "request_id": request_id,
    }

    # 1) 캐시 조회 (LangGraph 실행 전)
    cached_value = lookup_cached_answer(state)
    if cached_value is not None:
        return ChatResponse(
            answer=cached_value.get("answer", ""),
            sources=[Source(**s) for s in cached_value.get("sources", [])],
            cached=True,
            route=cached_value.get("route"),
            request_id=request_id,
        )

    # 2) 캐시 미스 -> LangGraph 실행
    try:
        graph = get_graph()
        result_state = await graph.ainvoke(state)
    except Exception as exc:  # noqa: BLE001 - 내부 오류는 비밀정보 없이 일반화해서 노출합니다.
        raise HTTPException(status_code=500, detail="답변 생성 중 오류가 발생했습니다.") from exc

    # 3) 캐시 저장 (재사용 가능한 응답만)
    write_answer_cache(result_state)

    sources = [
        Source(
            id=s.get("id", ""),
            title=s.get("title", ""),
            source_type=s.get("source_type", "unknown"),
            document_id=s.get("document_id"),
            score=s.get("score"),
        )
        for s in result_state.get("sources", [])
    ]

    return ChatResponse(
        answer=result_state.get("answer", ""),
        sources=sources,
        cached=False,
        route=result_state.get("route"),
        request_id=request_id,
    )
=======
    ...
>>>>>>> 2c10b076b3ac2d6eac31fb4a1f44ce787c5fd9e0
