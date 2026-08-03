"""캐시 우선 채팅 HTTP 오케스트레이션 경계.

검증된 요청으로 캐시를 먼저 조회하고 miss만 LangGraph에 전달한다. 이 모듈은 MCP,
LLM, MySQL, FAISS를 직접 호출하지 않으며 외부 Tool 예외를 비밀정보 없는 공개 오류
계약으로 변환한다.
"""

from __future__ import annotations

import hashlib
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.agent.state import GraphState
from app.auth.dependencies import CurrentUser
from app.cache.key import make_cache_key
from app.cache.service import lookup_cached_answer, write_answer_cache
from app.logging.performance import record_timing, start_timer
from app.mcp.client import (
    MCPMalformedPayloadError,
    MCPEvidenceInsufficientError,
    MCPInternalError,
    MCPForbiddenError,
    MCPInvalidInputError,
    MCPNoResultError,
    MCPQueryError,
    MCPTimeoutError,
)
from app.schemas.chat import ChatRequest, ChatResponse, ErrorResponse, Source, TableData

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


def _conversation_context_hash(session_id: str | None) -> str | None:
    """세션 원문을 노출하지 않는 결정적 캐시 격리 식별자를 만든다."""
    if session_id is None:
        return None
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def _tool_error_response(status_code: int, error_code: str, detail: str) -> JSONResponse:
    """외부 Tool 오류를 계약된 공개 메시지로 변환한다."""
    body = ErrorResponse(error_code=error_code, detail=detail)
    return JSONResponse(status_code=status_code, content=body.model_dump())


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, http_request: Request, user: CurrentUser) -> ChatResponse | JSONResponse:
    """캐시 조회, Graph 실행, 검증된 응답 저장 순서로 채팅 요청을 처리한다.

    캐시 hit는 즉시 반환해 Graph와 그 하위 LLM/MCP 호출을 모두 차단한다. miss에서만
    request별 state를 만들며, Tool 오류의 내부 메시지는 응답에 전달하지 않는다.
    """
    request_id = http_request.state.request_id
    timings = http_request.state.stage_timings
    state: GraphState = {
        "question": request.question,
        "session_id": request.session_id,
        "request_id": request_id,
        "conversation_context_hash": _conversation_context_hash(request.session_id),
        "user_context": user,
        "timings_ms": timings,
    }
    state.update(http_request.app.state.cache_key_context)
    cache_repository = http_request.app.state.dependencies.cache

    cache_started_ns = start_timer()
    cached_value = lookup_cached_answer(state, cache_repository)
    record_timing(timings, "cache_lookup", cache_started_ns)
    if cached_value is not None:
        logger.info(
            "request_id=%s cache=hit role=%s timings_ms=%s",
            request_id,
            user.get("role"),
            timings,
            extra={"event": "chat_performance"},
        )
        # 동일 freshness 입력의 hit는 외부 provider 호출을 금지하는 완전한 단락점이다.
        return ChatResponse(
            answer=cached_value.get("answer", ""),
            sources=[Source(**source) for source in cached_value.get("sources", [])],
            tables=[TableData(**table) for table in cached_value.get("tables", [])],
            cached=True,
            route=cached_value.get("route"),
            evidence_status=cached_value.get("evidence_status"),
            request_id=request_id,
        )

    try:
        graph_started_ns = start_timer()
        result_state = await http_request.app.state.graph.ainvoke(state)
    except MCPNoResultError:
        return _tool_error_response(404, "NO_RESULT", "조회 가능한 결과가 없습니다.")
    except MCPInvalidInputError:
        return _tool_error_response(400, "INVALID_INPUT", "조회 요청 형식이 올바르지 않습니다.")
    except MCPForbiddenError:
        return _tool_error_response(403, "FORBIDDEN", "요청한 데이터베이스에 접근할 권한이 없습니다.")
    except MCPEvidenceInsufficientError:
        return _tool_error_response(422, "EVIDENCE_INSUFFICIENT", "답변에 필요한 근거가 부족합니다.")
    except MCPTimeoutError:
        return _tool_error_response(504, "TIMEOUT", "조회 처리 시간이 초과되었습니다.")
    except MCPQueryError:
        return _tool_error_response(502, "QUERY_ERROR", "조회 서비스에서 오류가 발생했습니다.")
    except MCPInternalError:
        return _tool_error_response(502, "INTERNAL_ERROR", "조회 서비스 내부 오류가 발생했습니다.")
    except MCPMalformedPayloadError:
        return _tool_error_response(502, "INTERNAL_ERROR", "조회 서비스 응답을 처리할 수 없습니다.")
    except Exception:  # noqa: BLE001 - 경계 밖 오류의 상세를 노출하지 않는다.
        return _tool_error_response(500, "INTERNAL_ERROR", "답변 생성 중 오류가 발생했습니다.")
    finally:
        if "graph_started_ns" in locals():
            record_timing(timings, "graph_total", graph_started_ns)

    logger.info(
        "chat_completed request_id=%s route=%s labels=%s evidence_status=%s retrieval=%s",
        request_id,
        result_state.get("route"),
        result_state.get("query_labels", []),
        result_state.get("evidence_status"),
        result_state.get("retrieval_diagnostics", {}),
    )

    index_version = result_state.get("document_index_version")
    if index_version and index_version != http_request.app.state.cache_key_context.get("document_index_version"):
        http_request.app.state.cache_key_context["document_index_version"] = index_version
        result_state["cache_key"] = make_cache_key(result_state)
    cache_write_started_ns = start_timer()
    write_answer_cache(result_state, cache_repository)
    record_timing(timings, "cache_write", cache_write_started_ns)
    logger.info(
        "request_id=%s cache=miss role=%s route=%s timings_ms=%s",
        request_id,
        user.get("role"),
        result_state.get("route"),
        timings,
        extra={"event": "chat_performance"},
    )
    return ChatResponse(
        answer=result_state.get("answer", ""),
        sources=[Source(**source) for source in result_state.get("sources", [])],
        tables=[TableData(**table) for table in result_state.get("tables", [])],
        cached=False,
        route=result_state.get("route"),
        evidence_status=result_state.get("evidence_status"),
        request_id=request_id,
    )
