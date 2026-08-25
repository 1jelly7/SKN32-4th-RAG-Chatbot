"""문서 출처 카드에서 원본 파일을 안전하게 내려받는 HTTP 경계다."""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.auth.dependencies import CurrentUser
from app.mcp.client import MCPClientError, MCPForbiddenError, MCPNoResultError

router = APIRouter(tags=["documents"])


@router.get("/documents/download")
async def download_document(
    doc_id: str, request: Request, user: CurrentUser
) -> FileResponse:
    """출처 카드의 문서 ID로만 원본 파일을 다운로드한다.

    직접 파일 경로를 받지 않는다. Document MCP가 활성 문서 매핑과 권한을 검증한 뒤
    같은 프로세스에서만 경로를 전달하며, 파일 경로는 HTTP 응답 본문에 노출하지 않는다.
    """
    try:
        mcp = request.app.state.dependencies.mcp
        if mcp is None:
            raise MCPClientError(
                "resolve_document_download", "문서 서비스가 구성되지 않았습니다."
            )
        path = await mcp.resolve_document_download(doc_id, user)
    except MCPNoResultError as exc:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.") from exc
    except MCPForbiddenError as exc:
        raise HTTPException(
            status_code=403, detail="문서 다운로드 권한이 없습니다."
        ) from exc
    except MCPClientError as exc:
        raise HTTPException(
            status_code=502, detail="문서 다운로드를 준비할 수 없습니다."
        ) from exc

    filename = path.name
    disposition = f"attachment; filename*=UTF-8''{quote(filename)}"
    return FileResponse(
        path=path,
        filename=filename,
        media_type="application/octet-stream",
        headers={"Content-Disposition": disposition},
    )
