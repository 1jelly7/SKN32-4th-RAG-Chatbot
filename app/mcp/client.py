"""MCP transport와 agent evidence 사이의 Host-side 정규화 경계.

허용된 세 Tool만 호출하고 timeout, malformed payload, 빈 결과, 질의 오류를 구분한다.
SQL을 생성·수정하거나 문서/DB 저장소에 직접 접근하지 않는다.
"""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from pydantic import ValidationError

from app.agent.state import DataDomain
from app.schemas.mcp import (
    DocumentChunk,
    DocumentSource,
    MCPDomain,
    ToolErrorEnvelope,
    ToolName,
    ToolSuccessEnvelope,
)


class AsyncMCPPort(Protocol):
    """MCP transport가 제공해야 하는 최소 비동기 Tool 호출 경계다."""

    async def call_tool(self, tool_name: ToolName, payload: dict[str, Any]) -> object:
        """Tool 이름과 JSON payload를 전송하고 원본 응답을 반환한다."""
        ...


@dataclass(frozen=True)
class MCPCall:
    """Fake MCP가 기록하는 한 번의 Tool 호출이다."""

    tool_name: ToolName
    payload: dict[str, Any]


class FakeMCPPort:
    """네트워크 없이 production call 계약과 호출 이력을 제공하는 MCP 대역이다.

    응답과 payload를 방어적으로 복사해 테스트 변형이 fixture를 오염시키지 않으며,
    예외 객체는 실제 transport 실패처럼 그대로 발생시킨다.
    """

    def __init__(self, responses: Mapping[ToolName, object]) -> None:
        self._responses = dict(responses)
        self.calls: list[MCPCall] = []

    async def call_tool(self, tool_name: ToolName, payload: dict[str, Any]) -> object:
        """호출을 기록하고 설정된 envelope 또는 예외를 결정적으로 재생한다."""
        self.calls.append(MCPCall(tool_name=tool_name, payload=deepcopy(payload)))
        response = self._responses.get(tool_name)
        if isinstance(response, BaseException):
            raise response
        return deepcopy(response)


class InProcessMCPPort:
    """현재 전환 단계의 MCP Tool을 같은 프로세스에서 호출하는 transport다.

    import와 외부 연결은 실제 호출 시점까지 지연한다. FastAPI/Agent가 문서 저장소나
    MySQL을 직접 접근하지 않도록 각 소유 Tool service만 dispatch한다.
    """

    async def call_tool(self, tool_name: ToolName, payload: dict[str, Any]) -> object:
        """허용된 Tool 이름만 각 MCP 소유 경계로 전달한다."""
        if tool_name in ("query_purchase", "query_sales"):
            from mcp_servers.data_tools.server import execute_data_tool

            return await execute_data_tool(
                tool_name, str(payload.get("question", "")), payload.get("user_context")
            )
        if tool_name == "search_documents":
            from app.auth.policy import require_database_access
            from mcp_servers.document_tools.search import (
                DocumentSearchUnavailableError,
                search_documents,
            )

            from mcp_servers.document_tools.rag import get_last_index_version
            from mcp_servers.document_tools.search import search_documents

            query = str(payload.get("query", ""))
            top_k = payload.get("top_k", 5)
            try:
                require_database_access(payload.get("user_context"), "document_db")
            except PermissionError:
                return {
                    "status": "error",
                    "domain": "document",
                    "message": "문서 데이터베이스에 접근할 권한이 없습니다.",
                    "error_code": "FORBIDDEN",
                    "data": [],
                    "sources": [],
                    "metadata": {},
                }
            if not query.strip() or not isinstance(top_k, int) or top_k <= 0:
                return {
                    "status": "error",
                    "domain": "document",
                    "message": "문서 검색 입력이 올바르지 않습니다.",
                    "error_code": "INVALID_INPUT",
                    "data": [],
                    "sources": [],
                    "metadata": {},
                }
            try:
                chunks = await search_documents(query, top_k)
            except DocumentSearchUnavailableError:
                return {
                    "status": "error",
                    "domain": "document",
                    "message": "문서 조회 서비스를 현재 사용할 수 없습니다.",
                    "error_code": "QUERY_ERROR",
                    "data": [],
                    "sources": [],
                    "metadata": {},
                }
            except (
                Exception
            ):  # noqa: BLE001 - 내부 상세를 Host 경계 밖으로 노출하지 않는다.
                return {
                    "status": "error",
                    "domain": "document",
                    "message": "문서 검색 중 오류가 발생했습니다.",
                    "error_code": "INTERNAL_ERROR",
                    "data": [],
                    "sources": [],
                    "metadata": {},
                }
            if not chunks:
                return {
                    "status": "error",
                    "domain": "document",
                    "message": "관련 문서가 없습니다.",
                    "error_code": "NO_RESULT",
                    "data": [],
                    "sources": [],
                    "metadata": {"result_count": 0},
                }
            return {
                "status": "success",
                "domain": "document",
                "message": None,
                "data": [
                    {"content": item["content"], "score": item["score"]}
                    for item in chunks
                ],
                "sources": [
                    {
                        "document_id": item["document_id"],
                        "title": item["title"],
                        "page": item.get("page"),
                        **(
                            {"file_name": item["file_name"]}
                            if item.get("file_name")
                            else {}
                        ),
                    }
                    for item in chunks
                ],
                "metadata": {
                    "result_count": len(chunks),
                    "index_version": get_last_index_version(),
                },
            }
        if tool_name == "resolve_document_download":
            from app.auth.policy import require_database_access
            from mcp_servers.document_tools.download import resolve_document_download

            document_id = str(payload.get("document_id", ""))
            try:
                require_database_access(payload.get("user_context"), "document_db")
            except PermissionError:
                return {
                    "status": "error",
                    "domain": "document",
                    "message": "문서 다운로드 권한이 없습니다.",
                    "error_code": "FORBIDDEN",
                    "data": [],
                    "sources": [],
                    "metadata": {},
                }
            path = await resolve_document_download(document_id)
            return {
                "status": "success",
                "domain": "document",
                "message": None,
                "data": (
                    []
                    if path is None
                    else [{"file_path": str(path), "file_name": path.name}]
                ),
                "sources": [],
                "metadata": {},
            }
        raise ValueError(f"지원하지 않는 MCP Tool입니다: {tool_name}")

    async def warmup(self) -> None:
        """요청 전에 허용 문서의 PDF 파싱 캐시와 FAISS 인덱스를 읽기 전용 예열한다."""
        from mcp_servers.document_tools.document_db import lookup_document_paths
        from mcp_servers.document_tools.file_loader import load_document_files
        from mcp_servers.document_tools.rag import warmup_retrieval

        records = await lookup_document_paths("")
        await asyncio.to_thread(load_document_files, records)
        await asyncio.to_thread(warmup_retrieval)


class MCPClientError(RuntimeError):
    """MCP 경계에서 분류된 오류의 공통 기반 예외다."""

    def __init__(self, tool_name: ToolName, message: str) -> None:
        super().__init__(message)
        self.tool_name = tool_name


class MCPMalformedPayloadError(MCPClientError):
    """Tool envelope 또는 내부 evidence 형식이 계약과 다를 때 발생한다."""


class MCPNoResultError(MCPClientError):
    """Tool이 정상 호출됐지만 결과가 없음을 명시했을 때 발생한다."""


class MCPQueryError(MCPClientError):
    """Tool이 질의 실행 오류를 반환하거나 transport가 실패했을 때 발생한다."""


class MCPInvalidInputError(MCPClientError):
    """Tool이 요청 payload를 처리할 수 없다고 명시했을 때 발생한다."""


class MCPForbiddenError(MCPClientError):
    """인증된 사용자에게도 허용되지 않은 DB 접근을 Tool이 거절했을 때 발생한다."""


class MCPEvidenceInsufficientError(MCPClientError):
    """Tool은 정상 동작했지만 답변에 필요한 근거가 부족할 때 발생한다."""


class MCPInternalError(MCPClientError):
    """Tool 내부 장애가 질의 오류와 구분돼야 할 때 발생한다."""


class MCPTimeoutError(MCPClientError):
    """Tool 호출이 설정된 시간 안에 끝나지 않았을 때 발생한다."""


class MCPClient:
    """세 MCP Tool만 호출하고 응답을 내부 evidence 형식으로 정규화하는 어댑터다."""

    def __init__(self, port: AsyncMCPPort, timeout_seconds: float = 10.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("MCP timeout_seconds는 0보다 커야 합니다.")
        self._port = port
        self._timeout_seconds = timeout_seconds

    async def warmup(self) -> None:
        """transport가 제공하는 선택적 읽기 전용 예열을 실행한다."""
        warmup = getattr(self._port, "warmup", None)
        if callable(warmup):
            await warmup()

    async def document_search(
        self, query: str, top_k: int, user_context: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """`search_documents` 성공 envelope를 문서 evidence 목록으로 정규화한다."""
        payload: dict[str, Any] = {"query": query, "top_k": top_k}
        if user_context is not None:
            payload["user_context"] = user_context
        envelope = await self._call_success("search_documents", payload, "document")
        evidence: list[dict[str, Any]] = []
        for index, item in enumerate(envelope.data):
            try:
                chunk = DocumentChunk.model_validate(item)
                source = DocumentSource.model_validate(envelope.sources[index])
            except (IndexError, ValidationError) as exc:
                raise MCPMalformedPayloadError(
                    "search_documents", "문서 evidence 형식이 올바르지 않습니다."
                ) from exc
            evidence.append(
                {
                    "type": "document",
                    "document_id": source.document_id,
                    "title": source.title,
                    **({"file_name": source.file_name} if source.file_name else {}),
                    "content": chunk.content,
                    "score": chunk.score,
                    "page": source.page,
                    "metadata": envelope.metadata,
                }
            )
        return evidence

    async def resolve_document_download(
        self,
        document_id: str,
        user_context: dict[str, Any],
    ) -> Path:
        """등록된 문서 ID를 다운로드용 원본 경로로 해석한다.

        출처 카드의 서버 발급 ID에만 사용하며, 임의 경로나 문서 검색 결과가
        아닌 ID를 파일 접근 수단으로 사용하지 않는다. 반환 경로는 HTTP 파일 응답에만 쓴다.
        """
        envelope = await self._call_success(
            "resolve_document_download",
            {"document_id": document_id, "user_context": user_context},
            "document",
        )
        item = envelope.data[0]
        file_path = item.get("file_path")
        if not isinstance(file_path, str):
            raise MCPMalformedPayloadError(
                "resolve_document_download", "다운로드 문서 형식이 올바르지 않습니다."
            )
        path = Path(file_path)
        if not path.is_file():
            raise MCPNoResultError(
                "resolve_document_download", "문서를 찾을 수 없습니다."
            )
        return path

    async def purchase_query(
        self, question: str, user_context: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """`query_purchase` 성공 envelope를 구매 database evidence로 정규화한다."""
        payload: dict[str, Any] = {"question": question}
        if user_context is not None:
            payload["user_context"] = user_context
        envelope = await self._call_success("query_purchase", payload, "purchase")
        return _database_evidence("purchase", envelope)

    async def sales_query(
        self, question: str, user_context: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """`query_sales` 성공 envelope를 판매 database evidence로 정규화한다."""
        payload: dict[str, Any] = {"question": question}
        if user_context is not None:
            payload["user_context"] = user_context
        envelope = await self._call_success("query_sales", payload, "sales")
        return _database_evidence("sales", envelope)

    async def data_query(
        self, domain: DataDomain, question: str
    ) -> list[dict[str, Any]]:
        """명시된 데이터 도메인의 Tool만 호출한다."""
        if domain == "purchase":
            return await self.purchase_query(question)
        if domain == "sales":
            return await self.sales_query(question)
        if domain == "both":
            purchase_evidence = await self.purchase_query(question)
            sales_evidence = await self.sales_query(question)
            return purchase_evidence + sales_evidence
        raise ValueError(f"지원하지 않는 데이터 도메인입니다: {domain}")

    async def _call_success(
        self,
        tool_name: ToolName,
        payload: dict[str, Any],
        expected_domain: MCPDomain,
    ) -> ToolSuccessEnvelope:
        """한 Tool 호출에 timeout과 envelope/domain/빈 결과 검증을 적용한다."""
        try:
            raw_response = await asyncio.wait_for(
                self._port.call_tool(tool_name, payload),
                timeout=self._timeout_seconds,
            )
        except asyncio.TimeoutError as exc:
            raise MCPTimeoutError(
                tool_name, "MCP Tool 호출 시간이 초과되었습니다."
            ) from exc
        except MCPClientError:
            raise
        except (
            Exception
        ) as exc:  # noqa: BLE001 - 외부 transport 오류를 경계 예외로 정규화
            raise MCPQueryError(tool_name, "MCP Tool 호출에 실패했습니다.") from exc

        envelope = _parse_envelope(tool_name, raw_response)
        if envelope.domain != expected_domain:
            raise MCPMalformedPayloadError(
                tool_name, "MCP Tool domain이 요청과 일치하지 않습니다."
            )
        if not envelope.data:
            raise MCPNoResultError(
                tool_name, "MCP Tool이 조회 결과를 반환하지 않았습니다."
            )
        return envelope


def _parse_envelope(tool_name: ToolName, raw_response: object) -> ToolSuccessEnvelope:
    """외부 MCP 응답을 success/error envelope로 구분해 검증한다."""
    if not isinstance(raw_response, dict):
        raise MCPMalformedPayloadError(tool_name, "MCP Tool 응답은 객체여야 합니다.")

    try:
        status = raw_response.get("status")
        if status == "success":
            return ToolSuccessEnvelope.model_validate(raw_response)
        if status == "error":
            error = ToolErrorEnvelope.model_validate(raw_response)
        else:
            raise MCPMalformedPayloadError(
                tool_name, "MCP Tool status가 올바르지 않습니다."
            )
    except ValidationError as exc:
        raise MCPMalformedPayloadError(
            tool_name, "MCP Tool envelope 형식이 올바르지 않습니다."
        ) from exc

    if error.error_code == "NO_RESULT":
        raise MCPNoResultError(tool_name, error.message)
    if error.error_code == "INVALID_INPUT":
        raise MCPInvalidInputError(tool_name, error.message)
    if error.error_code == "FORBIDDEN":
        raise MCPForbiddenError(tool_name, error.message)
    if error.error_code == "EVIDENCE_INSUFFICIENT":
        raise MCPEvidenceInsufficientError(tool_name, error.message)
    if error.error_code == "INTERNAL_ERROR":
        raise MCPInternalError(tool_name, error.message)
    raise MCPQueryError(tool_name, error.message)


def _database_evidence(
    domain: MCPDomain, envelope: ToolSuccessEnvelope
) -> list[dict[str, Any]]:
    """SQL을 변경하지 않고 Data MCP의 행과 metadata를 database evidence로 보존한다."""
    generated_sql = envelope.metadata.get("generated_sql", "")
    if not isinstance(generated_sql, str):
        raise MCPMalformedPayloadError(
            "query_purchase" if domain == "purchase" else "query_sales",
            "generated_sql 형식이 올바르지 않습니다.",
        )
    return [
        {
            "type": "database",
            "domain": domain,
            "generated_sql": generated_sql,
            "rows": envelope.data,
            "row_count": envelope.metadata.get("row_count", len(envelope.data)),
            "metadata": envelope.metadata,
        }
    ]
