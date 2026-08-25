"""
MCP Resource가 반환할 데이터를 정의합니다.
"""

# JSON 문자열 생성을 위해 json을 가져옵니다.
import json

# 서비스 Container를 가져옵니다.
from app.services.container import get_container

# 파일 목록 Tool을 가져옵니다.
from app.tools.file_tools import list_doc_files


# 실행 설정을 Resource 문자열로 반환합니다.
def runtime_config() -> str:
    """민감정보를 제외한 현재 실행 설정을 JSON으로 반환합니다."""

    # 공용 Container를 가져옵니다.
    container = get_container()

    # 사용자에게 공개해도 되는 설정만 딕셔너리로 구성합니다.
    data = {
        "app_name": container.settings.app_name,
        "embedding_backend": container.settings.embedding_backend,
        "vector_backend": container.settings.vector_backend,
        "qdrant_mode": container.settings.qdrant_mode,
        "mysql_enabled": container.settings.mysql_enabled,
        "openai_configured": bool(container.settings.openai_api_key),
    }

    # 한글을 유지하는 들여쓰기 JSON 문자열로 반환합니다.
    return json.dumps(data, ensure_ascii=False, indent=2)


# 문서 카탈로그를 Resource 문자열로 반환합니다.
def document_catalog() -> str:
    """docs 폴더에 있는 문서 목록을 JSON으로 반환합니다."""

    # docs 폴더의 파일 목록을 가져옵니다.
    files = list_doc_files(get_container().settings.docs_dir)

    # 파일 목록을 JSON 문자열로 변환하여 반환합니다.
    return json.dumps({"files": files}, ensure_ascii=False, indent=2)
