# -*- coding: utf-8 -*-
"""Docling 이미지 캡셔닝이 실제로 동작하는지, 챗봇 질문이나 RAG 검색을 거치지
않고 로더 자체만 직접 호출해서 확인하는 스크립트입니다.

RAG 검색(top_score, 임계값)이나 라우팅(GENERAL/DOCUMENT) 같은 별개의 변수를
전부 제거하고, "Docling+비전 캡셔닝이 이미지에서 캡션을 뽑아내는가"만 딱
검증합니다. 어떤 PDF로 테스트해도 재사용 가능합니다 - 특정 문서 내용에
의존하지 않습니다.

전제:
    - .env에 ENABLE_DOCLING_CAPTIONING=true, OPENAI_API_KEY 설정돼 있어야 함
    - 검증할 PDF 안에 이미지(표/차트/사진 등)가 최소 1개는 있어야 함

실행:
    python scripts/verify_docling.py <PDF 경로>
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    if len(sys.argv) != 2:
        print("사용법: python scripts/verify_docling.py <PDF 경로>")
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"파일을 찾을 수 없습니다: {pdf_path}")
        sys.exit(1)

    from app.core.config import get_settings

    settings = get_settings()
    print("=" * 70)
    print("설정 확인")
    print("=" * 70)
    print(f"ENABLE_DOCLING_CAPTIONING = {settings.enable_docling_captioning}")
    print(f"OPENAI_API_KEY 설정됨     = {bool(settings.openai_api_key)}")
    print(f"OPENAI_MODEL              = {settings.openai_model}")
    if not settings.enable_docling_captioning:
        print(
            "\n주의: ENABLE_DOCLING_CAPTIONING=false라 실제로는 pypdf 경로로만 동작합니다."
        )
        print(".env에서 true로 켜고 다시 실행하세요.")

    print("\n" + "=" * 70)
    print(f"Docling 변환 시도: {pdf_path.name}")
    print("=" * 70)

    from ingestion.loaders import load_pdf_docling

    try:
        document = load_pdf_docling(pdf_path)
    except Exception as exc:  # noqa: BLE001 - 검증 스크립트라 원인 그대로 노출
        print(f"\n실패: {type(exc).__name__}: {exc}")
        print("\n원인 힌트:")
        print("- 최초 실행이면 레이아웃 분석 모델을 허깅페이스에서 내려받아야 해서")
        print("  인터넷 연결과 몇 분의 시간이 필요합니다.")
        print("- OpenAI API 호출 실패(키 미설정, 크레딧 부족 등)일 수도 있습니다.")
        sys.exit(1)

    metadata = document["metadata"]
    picture_count = metadata.get("captioned_picture_count", 0)
    detected_count = metadata.get("detected_picture_count", 0)
    no_caption_count = metadata.get("pictures_without_caption", 0)

    print(f"\nsource_type            = {metadata.get('source_type')}")
    print(f"page_count              = {metadata.get('page_count')}")
    print(f"레이아웃 모델이 감지한 그림 수  = {detected_count}")
    print(f"캡션 달린 이미지 수             = {picture_count}")
    print(f"그림으로 감지됐지만 캡션 없음   = {no_caption_count}")

    print("\n" + "=" * 70)
    if detected_count == 0:
        print("경고: 레이아웃 모델이 그림을 하나도 감지 못했습니다.")
        print("→ 이 PDF의 이미지가 벡터 도형/아이콘 폰트처럼 Docling이 '그림'으로")
        print("  분류하지 않는 형식일 가능성이 있습니다. Docling이 아니라 원본 PDF")
        print("  자체의 그림 삽입 방식 문제일 수 있어, 이 경우 코드 쪽에서 손볼")
        print("  여지가 크지 않습니다.")
    elif no_caption_count > 0 and picture_count == 0:
        print(f"그림은 {detected_count}개 감지됐는데 전부 캡션이 안 달렸습니다.")
        print("→ picture_area_threshold(그림 면적 임계값) 때문에 걸러졌거나,")
        print("  OpenAI API 호출 자체가 실패했을 가능성이 있습니다.")
        print("  (이 스크립트는 picture_area_threshold=0.0으로 이미 낮춰뒀습니다 -")
        print("   그래도 0개라면 API 호출 실패 쪽을 더 의심하세요.)")
    elif picture_count > 0:
        print(f"성공: 이미지 {picture_count}개에서 캡션을 뽑아냈습니다.")
    print("=" * 70)

    print("\n실제 페이지별 텍스트에 캡션이 어떻게 끼워졌는지:")
    print("-" * 70)
    for page_no, page_text in enumerate(document["content"].split("\f"), start=1):
        if "[이미지:" in page_text:
            idx = page_text.find("[이미지:")
            end = page_text.find("]", idx)
            print(f"[{page_no}페이지] {page_text[idx:end + 1]}")


if __name__ == "__main__":
    main()
