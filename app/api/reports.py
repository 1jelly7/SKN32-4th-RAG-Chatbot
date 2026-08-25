"""리포트(.docx) 생성 HTTP 경계.

템플릿 목록 조회와 실제 생성 두 엔드포인트만 노출한다. 조회·문서 조립 로직은
app/services/report_service.py, app/services/docx_builder.py에 있고, 이 모듈은
인증·권한 확인과 응답 형태(스트리밍 다운로드)만 책임진다. app/api/documents.py와
달리 디스크에 파일을 남기지 않는다 — docx_builder가 이미 메모리 안에서 bytes를
만들어 반환하므로 경로 관리가 필요 없다.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser
from app.auth.policy import require_database_access
from app.mcp.client import (
    MCPClientError,
    MCPEvidenceInsufficientError,
    MCPForbiddenError,
    MCPInternalError,
    MCPInvalidInputError,
    MCPMalformedPayloadError,
    MCPNoResultError,
    MCPQueryError,
    MCPTimeoutError,
)
from app.schemas.report import ReportGenerateRequest, ReportTemplateInfo
from app.services.report_service import generate_report
from app.services.report_templates import ReportTemplateSpec, get_template, list_templates

router = APIRouter(tags=["reports"])

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@router.get("/reports/templates", response_model=list[ReportTemplateInfo])
async def list_report_templates() -> list[ReportTemplateInfo]:
    """등록된 리포트 템플릿 목록을 반환한다."""
    return list_templates()


def _require_template(template_id: str) -> ReportTemplateSpec:
    try:
        return get_template(template_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail="등록되지 않은 리포트 템플릿입니다."
        ) from exc


def _require_template_access(user: dict[str, object], template: ReportTemplateSpec) -> None:
    """실제 조회를 시작하기 전에 템플릿이 쓰는 도메인 전부에 대한 권한을 미리 확인한다.

    이렇게 먼저 걸러내면, 권한이 없는 사용자가 요청했을 때 3개 섹션의 Text2SQL·DB
    조회를 전부 병렬로 시도했다가 뒤늦게 실패하는 낭비를 피할 수 있다. 그렇다고
    이 사전 확인이 app/mcp/client.py 안쪽의 require_database_access 강제를 대체하는
    것은 아니다 — 이중 방어다.
    """
    domains = {section["domain"] for section in template["sections"]}
    try:
        for domain in domains:
            require_database_access(user, f"{domain}_db")
    except PermissionError as exc:
        raise HTTPException(
            status_code=403, detail="요청한 데이터베이스에 접근할 권한이 없습니다."
        ) from exc


@router.post("/reports/generate")
async def generate_report_endpoint(
    body: ReportGenerateRequest, request: Request, user: CurrentUser
) -> StreamingResponse:
    """요청한 템플릿·기간으로 리포트를 만들어 .docx로 바로 스트리밍한다."""
    template = _require_template(body.template_id)
    _require_template_access(user, template)

    mcp = request.app.state.dependencies.mcp
    if mcp is None:
        raise HTTPException(status_code=503, detail="리포트 서비스를 사용할 수 없습니다.")

    try:
        docx_bytes = await generate_report(
            body.template_id,
            body.start_date,
            body.end_date,
            mcp,
            user_context=user,
        )
    except MCPInvalidInputError as exc:
        raise HTTPException(
            status_code=400, detail="조회 요청 형식이 올바르지 않습니다."
        ) from exc
    except MCPForbiddenError as exc:
        raise HTTPException(
            status_code=403, detail="요청한 데이터베이스에 접근할 권한이 없습니다."
        ) from exc
    except MCPNoResultError as exc:
        raise HTTPException(
            status_code=404, detail="조회 가능한 결과가 없습니다."
        ) from exc
    except MCPEvidenceInsufficientError as exc:
        raise HTTPException(
            status_code=422, detail="리포트를 만들기에 근거가 부족합니다."
        ) from exc
    except MCPTimeoutError as exc:
        raise HTTPException(
            status_code=504, detail="조회 처리 시간이 초과되었습니다."
        ) from exc
    except (MCPQueryError, MCPInternalError, MCPMalformedPayloadError) as exc:
        raise HTTPException(
            status_code=502, detail="리포트 조회 중 오류가 발생했습니다."
        ) from exc
    except MCPClientError as exc:
        raise HTTPException(
            status_code=502, detail="리포트 조회 중 오류가 발생했습니다."
        ) from exc
    except Exception as exc:  # noqa: BLE001 - 경계 밖 오류의 상세를 노출하지 않는다.
        raise HTTPException(
            status_code=500, detail="리포트 생성 중 오류가 발생했습니다."
        ) from exc

    filename = (
        f"{template['name']}_{body.start_date.isoformat()}_{body.end_date.isoformat()}.docx"
    )
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return StreamingResponse(
        iter([docx_bytes]),
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": disposition},
    )
