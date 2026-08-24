"""사내 문서 검색을 위한 제한된 동의어 확장 규칙."""

from __future__ import annotations

MAX_DOCUMENT_QUERIES = 3

DOCUMENT_SYNONYM_GROUPS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "겸직",
            "겸업",
            "부업",
            "이중취업",
            "영리활동",
            "외부활동",
            "사외활동",
            "취업제한",
        ),
        "겸직 겸업 부업 이중취업 영리활동 외부활동 사외활동 취업 제한 취업규칙 복무규정",
    ),
    (
        (
            "법인카드",
            "회사카드",
            "업무용카드",
            "카드발급",
            "카드사용",
            "카드정산",
            "카드지침",
        ),
        "법인카드 회사카드 업무용 카드 발급 사용 정산 제한 지침",
    ),
    (
        (
            "부당한지시",
            "부당한업무지시",
            "부당지시",
            "위법부당업무지시",
            "직장내괴롭힘",
            "고충처리",
            "업무지시거부",
        ),
        "부당한 지시 부당지시 위법 부당 업무지시 직장 내 괴롭힘 고충처리 신고 절차 업무지시 거부",
    ),
    (
        ("부가급여", "복리후생", "부가급부", "급여외혜택", "보상및혜택"),
        "부가급여 복리후생 부가 급부 수당 급여 외 혜택 보상 및 혜택",
    ),
    (
        ("취업규정", "취업규칙", "인사규정", "복무규정", "근로조건", "채용및고용규정"),
        "취업 규정 취업규칙 인사규정 복무규정 근로조건 채용 및 고용 규정",
    ),
    (
        ("수입금징수", "수입금", "수납", "징수", "세입", "금전수납", "납부금관리"),
        "수입금 징수 수납 세입 금전 수납 납부금 관리",
    ),
    (
        (
            "특별안전보건교육",
            "안전보건교육",
            "유해위험작업교육",
            "산업안전교육",
            "법정의무교육",
        ),
        "특별 안전 보건 교육 특별안전보건교육 안전보건교육 유해 위험 작업 교육 산업안전 교육 법정 의무교육",
    ),
)


def expand_document_queries(question: str) -> list[str]:
    """원문과 일치한 업무 개념의 동의어 검색어를 최대 세 개 반환한다.

    문서 검색에만 사용하며, 원문은 항상 첫 번째 검색어로 보존한다. 여러 규정 주제를
    독립 검색하되 MCP 호출 폭증을 막기 위해 검색어 수를 제한한다.
    """
    original = question.strip()
    if not original:
        return []

    normalized = _normalize(original)
    queries = [original]
    for triggers, expanded_query in DOCUMENT_SYNONYM_GROUPS:
        if any(trigger in normalized for trigger in triggers):
            queries.append(expanded_query)
        if len(queries) >= MAX_DOCUMENT_QUERIES:
            break
    return list(dict.fromkeys(queries))


def _normalize(value: str) -> str:
    """띄어쓰기와 문장부호 차이를 제거해 업무 키워드를 비교한다."""
    return "".join(character for character in value.casefold() if character.isalnum())
