from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.agent.state import GraphState
from app.cache.service import lookup_cached_answer, write_answer_cache
from app.mcp.client import (
    MCPMalformedPayloadError,
    MCPNoResultError,
    MCPQueryError,
    MCPTimeoutError,
)
from app.schemas.chat import ChatRequest, ChatResponse, ErrorResponse, Source, TableData

router = APIRouter(tags=["chat"])


def _tool_error_response(status_code: int, error_code: str, detail: str) -> JSONResponse:
    """외부 Tool 오류를 계약된 공개 메시지로 변환한다."""
    body = ErrorResponse(error_code=error_code, detail=detail)
    return JSONResponse(status_code=status_code, content=body.model_dump())


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request) -> ChatResponse | JSONResponse:
    """캐시 조회, Graph 실행, 캐시 저장 순서로 채팅 요청을 처리한다."""
    request_id = str(uuid.uuid4())
    state: GraphState = {
        "question": request.question,
        "session_id": request.session_id,
        "request_id": request_id,
    }
    state.update(http_request.app.state.cache_key_context)
    cache_repository = http_request.app.state.dependencies.cache

    cached_value = lookup_cached_answer(state, cache_repository)
    if cached_value is not None:
        return ChatResponse(
            answer=cached_value.get("answer", ""),
            sources=[Source(**source) for source in cached_value.get("sources", [])],
            tables=[TableData(**table) for table in cached_value.get("tables", [])],
            cached=True,
            route=cached_value.get("route"),
            request_id=request_id,
        )

    try:
        result_state = await http_request.app.state.graph.ainvoke(state)
    except MCPNoResultError:
        return _tool_error_response(404, "NO_RESULT", "조회 가능한 결과가 없습니다.")
    except MCPTimeoutError:
        return _tool_error_response(504, "QUERY_ERROR", "조회 처리 시간이 초과되었습니다.")
    except MCPQueryError:
        return _tool_error_response(502, "QUERY_ERROR", "조회 서비스에서 오류가 발생했습니다.")
    except MCPMalformedPayloadError:
        return _tool_error_response(502, "INTERNAL_ERROR", "조회 서비스 응답을 처리할 수 없습니다.")
    except Exception:  # noqa: BLE001 - 경계 밖 오류의 상세를 노출하지 않는다.
        return _tool_error_response(500, "INTERNAL_ERROR", "답변 생성 중 오류가 발생했습니다.")

    write_answer_cache(result_state, cache_repository)
    return ChatResponse(
        answer=result_state.get("answer", ""),
        sources=[Source(**source) for source in result_state.get("sources", [])],
        tables=[TableData(**table) for table in result_state.get("tables", [])],
        cached=False,
        route=result_state.get("route"),
        request_id=request_id,
    )
