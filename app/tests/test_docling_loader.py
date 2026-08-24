"""ingestion/loaders.py의 Docling 이미지 캡셔닝 경로를 검증한다.

실제 Docling 변환(무거운 레이아웃 모델 다운로드)이나 OpenAI 호출은 절대 하지
않는다 - DocumentConverter.convert()를 monkeypatch로 대체해 결과 문서 구조만
고정하고, load_pdf_docling()이 그걸 프로젝트 표준 RawDocument
({"content": "...\\f..."}) 형태로 정확히 바꾸는지만 본다.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ingestion import loaders


def _text_item(text: str, page_no: int) -> SimpleNamespace:
    return SimpleNamespace(text=text, prov=[SimpleNamespace(page_no=page_no)])


def _picture_item(page_no: int, caption: str | None) -> SimpleNamespace:
    annotations = [SimpleNamespace(kind="description", text=caption)] if caption else []
    return SimpleNamespace(
        prov=[SimpleNamespace(page_no=page_no)], annotations=annotations
    )


class _FakeDoclingDocument:
    def __init__(self, texts: list, pictures: list) -> None:
        self.texts = texts
        self.pictures = pictures


class _FakeConvertResult:
    def __init__(self, document: _FakeDoclingDocument) -> None:
        self.document = document


class _FakeDocumentConverter:
    def __init__(self, fake_document: _FakeDoclingDocument, **_: object) -> None:
        self._fake_document = fake_document

    def convert(self, _path: str) -> _FakeConvertResult:
        return _FakeConvertResult(self._fake_document)


@pytest.fixture
def fake_settings(monkeypatch):
    """load_pdf_docling()/load_pdf_with_docling_fallback()은 함수 안에서
    `from app.core.config import get_settings`를 지연 import하므로, ingestion.loaders가
    아니라 실제 소스 모듈(app.core.config)의 get_settings를 patch해야 실제로 먹힌다.
    """
    settings = SimpleNamespace(
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
        enable_docling_captioning=True,
    )
    import app.core.config as config_module

    monkeypatch.setattr(config_module, "get_settings", lambda: settings)
    return settings


def _patch_docling_internals(monkeypatch, fake_document: _FakeDoclingDocument) -> None:
    """load_pdf_docling() 내부의 지연 import 대상들을 전부 가짜로 바꾼다.

    실제 함수는 함수 안에서 `from docling... import ...`를 하므로, 모듈 자체를
    sys.modules에 가짜로 등록해 진짜 docling이 로드되지 않게 막는다.
    """
    import sys
    import types

    fake_pipeline_options_mod = types.ModuleType("docling.datamodel.pipeline_options")
    fake_pipeline_options_mod.PdfPipelineOptions = lambda: SimpleNamespace(
        do_picture_description=False, picture_description_options=None
    )
    fake_pipeline_options_mod.PictureDescriptionApiOptions = lambda **kwargs: kwargs

    fake_base_models_mod = types.ModuleType("docling.datamodel.base_models")
    fake_base_models_mod.InputFormat = SimpleNamespace(PDF="pdf")

    fake_converter_mod = types.ModuleType("docling.document_converter")
    fake_converter_mod.DocumentConverter = lambda **kwargs: _FakeDocumentConverter(
        fake_document
    )
    fake_converter_mod.PdfFormatOption = lambda **kwargs: kwargs

    fake_doc_types_mod = types.ModuleType("docling_core.types.doc")
    fake_doc_types_mod.PictureItem = (
        SimpleNamespace  # isinstance 체크를 통과시키기 위함이 아니라 아래에서 우회
    )

    monkeypatch.setitem(
        sys.modules, "docling.datamodel.pipeline_options", fake_pipeline_options_mod
    )
    monkeypatch.setitem(
        sys.modules, "docling.datamodel.base_models", fake_base_models_mod
    )
    monkeypatch.setitem(sys.modules, "docling.document_converter", fake_converter_mod)
    monkeypatch.setitem(sys.modules, "docling_core.types.doc", fake_doc_types_mod)


def test_load_pdf_docling_embeds_captions_inline_per_page(
    tmp_path, monkeypatch, fake_settings
) -> None:
    fake_document = _FakeDoclingDocument(
        texts=[
            _text_item("제1조(목적) 이 문서는 테스트용입니다.", page_no=1),
            _text_item("두 번째 페이지 텍스트", page_no=2),
        ],
        pictures=[_picture_item(page_no=1, caption="파란 배경의 막대 차트 이미지")],
    )
    _patch_docling_internals(monkeypatch, fake_document)

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")

    document = loaders.load_pdf_docling(pdf_path)

    pages = document["content"].split("\f")
    assert len(pages) == 2
    assert "제1조(목적)" in pages[0]
    assert "[이미지: 파란 배경의 막대 차트 이미지]" in pages[0]
    assert "두 번째 페이지 텍스트" in pages[1]
    assert "[이미지:" not in pages[1]
    assert document["metadata"]["captioned_picture_count"] == 1
    assert document["metadata"]["detected_picture_count"] == 1
    assert document["metadata"]["pictures_without_caption"] == 0
    assert document["metadata"]["source_type"] == "pdf_docling"


def test_load_pdf_docling_reports_detected_pictures_without_caption(
    tmp_path, monkeypatch, fake_settings
) -> None:
    """실제 사고 재현 회귀 테스트(2026-08-19): 레이아웃 모델이 그림을 감지했지만
    (작은 아이콘이라 picture_area_threshold에 걸리는 등의 이유로) 캡션이 하나도
    안 달린 상황을, "그림 자체를 아예 못 찾음"과 구분해서 진단할 수 있어야 한다.
    """
    fake_document = _FakeDoclingDocument(
        texts=[_text_item("본문", page_no=1)],
        pictures=[
            _picture_item(page_no=1, caption=None),
            _picture_item(page_no=1, caption=None),
        ],
    )
    _patch_docling_internals(monkeypatch, fake_document)

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake content")

    document = loaders.load_pdf_docling(pdf_path)

    assert document["metadata"]["detected_picture_count"] == 2
    assert document["metadata"]["captioned_picture_count"] == 0
    assert document["metadata"]["pictures_without_caption"] == 2
    assert "[이미지:" not in document["content"]


def test_load_pdf_with_docling_fallback_uses_pypdf_when_disabled(
    tmp_path, monkeypatch
) -> None:
    """설정이 꺼져 있으면(기본값) Docling을 아예 건드리지 않고 기존 pypdf 경로로 간다."""
    settings = SimpleNamespace(
        openai_api_key="sk-test",
        openai_model="gpt-4o-mini",
        enable_docling_captioning=False,
    )
    import app.core.config as config_module

    monkeypatch.setattr(config_module, "get_settings", lambda: settings)

    called = {"docling": False}

    def _should_not_be_called(_path):
        called["docling"] = True
        raise AssertionError(
            "enable_docling_captioning=False인데 load_pdf_docling이 호출됨"
        )

    monkeypatch.setattr(loaders, "load_pdf_docling", _should_not_be_called)

    pdf_path = tmp_path / "empty.pdf"
    # pypdf가 열 수 있는 최소한의 빈 PDF
    pdf_path.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
    )

    document = loaders.load_pdf_with_docling_fallback(pdf_path)

    assert called["docling"] is False
    assert document["metadata"]["source_type"] == "pdf"  # load_pdf() 결과


def test_load_pdf_with_docling_fallback_falls_back_on_exception(
    tmp_path, monkeypatch, fake_settings
) -> None:
    """Docling이 켜져 있어도, 변환 중 예외가 나면 재인덱싱 전체가 안 죽고 pypdf로 폴백한다."""
    attempted = {"docling": False}

    def _raise(_path):
        attempted["docling"] = True
        raise RuntimeError("모델 다운로드 실패 시뮬레이션")

    monkeypatch.setattr(loaders, "load_pdf_docling", _raise)

    pdf_path = tmp_path / "empty.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
    )

    document = loaders.load_pdf_with_docling_fallback(pdf_path)

    assert attempted["docling"] is True  # docling이 켜져 있으니 실제로 시도는 됐어야 함
    assert document["metadata"]["source_type"] == "pdf"  # 실패 후 pypdf 결과로 폴백
