"""
문서 DB가 알려준 경로(또는 디렉터리)에서 지원 형식의 문서만 읽어
RawDocument로 변환합니다.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from pypdf import PdfReader

from ingestion.types import RawDocument

SUPPORTED_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}


def _make_document_id(path: Path) -> str:
    """경로 문자열의 SHA-256 앞부분으로 안정적인 document_id를 만듭니다.

    같은 경로는 항상 같은 id를 만들어서, 재인덱싱해도 document_id가 바뀌지 않게 합니다.
    """
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()
    return f"doc-{digest[:16]}"


def load_documents(path: Path) -> list[RawDocument]:
    """문서 DB에서 확인한 파일 또는 디렉터리 경로의 지원 문서만 수집한다.

    경로를 정렬해 재현 가능한 순서를 만들고, 숨김/지원하지 않는 파일은 조용히
    건너뜁니다(개별 파일 오류는 로드 자체를 막지 않되, 어떤 파일이 실패했는지는
    호출자가 확인할 수 있도록 예외 메시지에 파일명을 포함합니다).
    임의 입력 경로나 문서 DB에 없는 경로는 이 함수 스스로 검증하지 않습니다 -
    호출자(예: document_db 조회 결과)가 이미 검증된 경로만 넘겨야 합니다.
    """

    if path.is_file():
        candidates = [path]
    else:
        # 디렉터리인 경우 하위 파일을 정렬해 재현 가능한 순서로 만듭니다.
        candidates = sorted(
            p for p in path.iterdir() if p.is_file() and not p.name.startswith(".")
        )

    documents: list[RawDocument] = []
    for candidate in candidates:
        suffix = candidate.suffix.casefold()
        if suffix not in SUPPORTED_SUFFIXES:
            continue

        if suffix == ".pdf":
            documents.append(load_pdf_with_docling_fallback(candidate))
        elif suffix in {".md", ".markdown"}:
            documents.append(load_markdown(candidate))
        else:
            documents.append(load_text(candidate))

    return documents


def load_pdf(path: Path) -> RawDocument:
    """PDF의 페이지 순서를 보존해 텍스트와 기본 출처 metadata를 RawDocument로 만든다."""

    reader = PdfReader(str(path))

    # 페이지 경계를 유지하기 위해 페이지 사이에 명시적인 구분자를 넣습니다.
    # (chunking 단계에서 페이지 번호를 복원할 때 이 구분자를 기준으로 나눕니다)
    page_texts = [page.extract_text() or "" for page in reader.pages]
    content = "\f".join(page_texts)  # \f(form feed)를 페이지 구분자로 사용

    return {
        "document_id": _make_document_id(path),
        "path": str(path),
        "title": path.stem,
        "content": content,
        "metadata": {"source_type": "pdf", "page_count": len(reader.pages)},
    }


def load_pdf_with_docling_fallback(path: Path) -> RawDocument:
    """설정에 따라 Docling(이미지 캡셔닝 포함)을 시도하고, 실패하면 pypdf로 폴백한다.

    Docling은 무거운 레이아웃 분석 모델을 내려받아야 하고, 이미지 캡셔닝은
    OpenAI API 호출이 필요해 실패 지점이 여러 곳이다(모델 다운로드 실패,
    네트워크 문제, API 키 미설정 등). 재인덱싱 전체가 이미지 한 장 때문에
    멈추면 안 되므로, 실패하면 조용히 기존 pypdf 경로(load_pdf)로 대체한다 -
    텍스트만 있고 이미지 캡션은 없는 결과가 되지만, 최소한 인덱싱 자체는 된다.
    """
    from app.core.config import get_settings

    settings = get_settings()
    if not getattr(settings, "enable_docling_captioning", False):
        return load_pdf(path)

    try:
        return load_pdf_docling(path)
    except Exception as exc:  # noqa: BLE001 - 재인덱싱 전체를 막지 않기 위한 의도적 폴백
        import logging

        logging.getLogger(__name__).warning(
            "docling_load_failed path=%s error_type=%s - pypdf로 폴백합니다.",
            path,
            type(exc).__name__,
        )
        return load_pdf(path)


def load_pdf_docling(path: Path) -> RawDocument:
    """Docling으로 PDF를 파싱하고, 이미지는 OpenAI 모델로 캡션을 달아 해당
    페이지 텍스트 안에 끼워넣는다.

    load_pdf()와 동일하게 \\f(form feed)로 페이지를 구분한 content를 반환하므로,
    chunking.py는 전혀 수정할 필요가 없다 - 이미지 캡션도 그냥 검색 가능한
    일반 텍스트처럼 청킹·임베딩된다.
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        PictureDescriptionApiOptions,
    )
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import PictureItem

    from app.core.config import get_settings

    settings = get_settings()

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_picture_description = True
    # Docling은 기본적으로 외부 API 호출을 전부 차단한다(오프라인/보안 기본값).
    # OpenAI 비전 API로 캡셔닝을 하려면 이 플래그로 명시적으로 허용해야 한다 -
    # 이게 없으면 OperationNotAllowed 예외가 발생한다.
    pipeline_options.enable_remote_services = True
    picture_description_options = PictureDescriptionApiOptions(
        url="https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        params={"model": settings.openai_model, "max_tokens": 200},
        prompt="이 이미지에 어떤 정보가 담겨 있는지 한국어로 2~3문장으로 설명해줘.",
        timeout=60,
        # picture_area_threshold는 Docling 기본값(페이지 면적의 5%)을 그대로 쓴다.
        # 검증(scripts/verify_docling.py) 때는 0.0으로 낮춰서 "그림 감지 자체가
        # 되는지"를 확인했지만, 그 값을 운영에 그대로 쓰면 로고·작은 아이콘까지
        # 전부 캡션으로 인덱싱돼 검색 품질을 오히려 떨어뜨린다(2026-08-19 실측:
        # 0.0으로는 5페이지 문서에서 42개 캡션이 나왔는데 대부분 장식용 로고/
        # 아이콘이었음). 기본값이면 이런 작은 요소는 자연히 걸러지고, 인포그래픽처럼
        # 실제 정보가 담긴 큰 이미지는 그대로 캡션 대상이 된다.
    )
    pipeline_options.picture_description_options = picture_description_options

    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
    )
    result = converter.convert(str(path))
    doc = result.document

    page_texts: dict[int, list[str]] = {}
    for text_item in doc.texts:
        page_no = text_item.prov[0].page_no if text_item.prov else 1
        page_texts.setdefault(page_no, []).append(text_item.text)

    picture_count = 0
    detected_picture_count = 0  # 캡션 성공 여부와 무관하게, 레이아웃 모델이 "그림"으로 감지한 전체 개수
    pictures_without_caption = 0  # 그림으로는 감지됐지만 캡션이 안 달린 개수(면적 임계값 미달, API 실패 등)
    for picture in doc.pictures:
        if not isinstance(picture, PictureItem):
            continue
        detected_picture_count += 1
        page_no = picture.prov[0].page_no if picture.prov else 1
        caption = next(
            (annotation.text for annotation in picture.annotations if annotation.kind == "description"),
            None,
        )
        if caption:
            picture_count += 1
            page_texts.setdefault(page_no, []).append(f"[이미지: {caption}]")
        else:
            pictures_without_caption += 1

    last_page = max(page_texts, default=0)
    ordered_pages = ["\n".join(page_texts.get(page_no, [])) for page_no in range(1, last_page + 1)]
    content = "\f".join(ordered_pages)

    return {
        "document_id": _make_document_id(path),
        "path": str(path),
        "title": path.stem,
        "content": content,
        "metadata": {
            "source_type": "pdf_docling",
            "page_count": len(ordered_pages),
            "captioned_picture_count": picture_count,
            "detected_picture_count": detected_picture_count,
            "pictures_without_caption": pictures_without_caption,
        },
    }


def load_text(path: Path) -> RawDocument:
    """인코딩을 안전하게 판별해 일반 텍스트를 읽고 안정된 document_id를 생성한다."""

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # UTF-8이 아니면 흔한 한국어 인코딩(cp949)도 시도해봅니다.
        content = path.read_text(encoding="cp949", errors="replace")

    return {
        "document_id": _make_document_id(path),
        "path": str(path),
        "title": path.stem,
        "content": content,
        "metadata": {"source_type": "text"},
    }


def load_markdown(path: Path) -> RawDocument:
    """Markdown 제목/헤더 정보를 title·metadata에 반영해 문서를 읽는다."""

    content = path.read_text(encoding="utf-8")

    # 첫 번째 '# 제목' 헤더를 찾으면 그걸 title로 사용하고, 없으면 파일명을 씁니다.
    title = path.stem
    headers: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            header_text = stripped.lstrip("#").strip()
            headers.append(header_text)
            if title == path.stem and stripped.startswith("# "):
                title = header_text

    return {
        "document_id": _make_document_id(path),
        "path": str(path),
        "title": title,
        "content": content,
        "metadata": {"source_type": "markdown", "headers": headers},
    }