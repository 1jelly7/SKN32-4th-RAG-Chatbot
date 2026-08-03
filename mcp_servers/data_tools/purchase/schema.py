"""
구매(Purchase) 도메인 Text2SQL용 스키마 정의

기존 schema.py와 최종 schema.py를 병합한 버전:
- 기존 구조(SchemaResource TypedDict) 유지
- 뷰(VIEW) 기반으로 확장
- 실제 데이터 기반 (50개 발주, 32개 청구서 등)
- 질문 예시 50개+, 거절 목록 35개+
"""

from __future__ import annotations

from typing import TypedDict, Optional
from datetime import datetime, timedelta


class SchemaResource(TypedDict, total=False):
    """구매 Text2SQL이 참조할 스키마 정보 (뷰 기반)."""

    # 허용된 뷰 (5개만)
    views: list[str]

    # 각 뷰의 컬럼 정의
    view_columns: dict[str, list[str]]

    # 뷰별 메타데이터 (설명, 예시, 데이터 범위)
    view_definitions: dict[str, dict]

    # 업무 용어 정의
    business_glossary: dict[str, str]

    # 계산 가능한 지표
    metrics: dict[str, str]

    # 범위 밖 질문 (거절 목록)
    out_of_scope: list[str]

    # 질문 예시 (50개+)
    example_queries: list[dict]

    # 통계 정보
    summary_statistics: dict

    # 데이터 범위
    data_range: dict

    # 데이터베이스 정보
    database: str
    company_id: int

    # 주의사항
    warnings: list[str]
    important_notes: dict


def get_schema_resource() -> SchemaResource:
    """
    구매 소유 DDL에 대응하는 공개 가능한 schema와 용어집을 반환한다.

    뷰 기반 (VIEW-based):
    - v_purchase_order (발주 헤더)
    - v_purchase_order_line (발주 상세)
    - v_vendor (공급업체)
    - v_vendor_invoice (청구서)
    - v_purchase_order_status (상태 분석)

    실제 데이터:
    - 발주 50건 (취소 제외 49건)
    - 발주 상세 123줄
    - 공급업체 25개
    - 청구서 32개 (미지급액: 689,767.45 JOD)
    - 입고 32건
    """

    return {
        # ====================================================================
        # 1. 허용된 뷰 (5개)
        # ====================================================================
        "views": [
            "v_purchase_order",           # 발주 헤더
            "v_purchase_order_line",      # 발주 상세
            "v_vendor",                   # 공급업체
            "v_vendor_invoice",           # 청구서
            "v_purchase_order_status",    # 상태 분석
        ],

        # ====================================================================
        # 2. 각 뷰의 컬럼 정의
        # ====================================================================
        "view_columns": {
            "v_purchase_order": [
                "po_id", "po_number", "po_date", "vendor_id",
                "subtotal", "tax_amount", "total_amount",
                "currency", "status",
            ],
            "v_purchase_order_line": [
                "po_line_id", "po_id", "item_id", "description",
                "quantity", "unit_price", "discount_percent", "line_total",
            ],
            "v_vendor": [
                "vendor_id", "vendor_code", "vendor_name",
                "country", "currency", "payment_terms", "is_active",
            ],
            "v_vendor_invoice": [
                "invoice_id", "invoice_number", "invoice_date",
                "po_id", "vendor_id", "due_date",
                "subtotal", "tax_amount", "total_amount",
                "amount_paid", "outstanding_amount", "currency", "status",
            ],
            "v_purchase_order_status": [
                "po_id", "status", "total_amount",
                "po_date", "vendor_id",
            ],
        },

        # ====================================================================
        # 3. 뷰별 메타데이터
        # ====================================================================
        "view_definitions": {
            "v_purchase_order": {
                "description": "유효한 발주 헤더 (Cancelled 제외)",
                "purpose": "발주액, 발주 현황, 공급업체별 집계",
                "total_records": 49,  # Cancelled 제외
                "status_values": {
                    "Closed": 13,
                    "Sent": 12,
                    "Partially Received": 10,
                    "Received": 9,
                    "Approved": 5,
                    "Cancelled": "제외됨",
                },
                "amount_range": {
                    "min": 3.46,
                    "max": 652173.97,
                    "avg": 58601.49,
                    "median": 15307.33,
                    "currency": "JOD",
                },
                "date_range": "2025-01-22 ~ 2026-06-25",
            },
            "v_purchase_order_line": {
                "description": "유효한 발주의 상세 라인 (헤더 금액 제외 — fan-out 방지)",
                "purpose": "품목별 통계, 수량 집계, 할인 현황",
                "total_records": 123,
                "lines_per_po_avg": 2.46,
                "discount_info": {
                    "with_discount": 59,  # 48%
                    "without_discount": 64,  # 52%
                    "max_discount_rate": 10,  # %
                },
                "unit_price_range": {
                    "min": 3.04,
                    "max": 2320.36,
                    "currency": "JOD",
                },
                "top_items": {
                    "1": "Industrial Paint White 20L (605개)",
                    "2": "Plastic Bin 600x400 (423개)",
                    "3": "Circuit Breaker 63A (388개)",
                    "4": "Linear Guide Rail 20mm (352개)",
                    "5": "Safety Helmet White (350개)",
                },
            },
            "v_vendor": {
                "description": "공급업체 마스터 (PII 제외)",
                "purpose": "공급업체 목록, 결제 조건별 분류",
                "total_records": 25,
                "all_active": True,
                "countries": ["Jordan"],
                "payment_terms_distribution": {
                    "NET60": 8,
                    "COD": 7,
                    "NET45": 6,
                    "NET30": 4,
                },
                "excluded_columns": [
                    "email - PII",
                    "phone_number - PII",
                    "address - PII",
                    "contact_person - PII",
                    "tax_id - PII",
                    "bank_account - 민감정보",
                    "iban - 민감정보",
                ],
            },
            "v_vendor_invoice": {
                "description": "청구서 및 미지급액 현황",
                "purpose": "청구액 분석, 미지급액 조회, 지급 현황 추적",
                "total_records": 32,
                "status_distribution": {
                    "Paid": 21,
                    "Partially Paid": 8,
                    "Overdue": 3,
                },
                "outstanding_info": {
                    "total_outstanding": 689767.45,
                    "invoices_with_outstanding": 11,
                    "max_outstanding": 338754.72,
                    "currency": "JOD",
                },
                "amount_range": {
                    "min": 1.76,
                    "max": 438534.49,
                    "currency": "JOD",
                },
                "date_range": "2025-02-16 ~ 2026-07-13",
            },
            "v_purchase_order_status": {
                "description": "모든 발주의 상태별 분석 (취소 포함)",
                "purpose": "상태별 집계, 완료율 분석",
                "total_records": 50,
                "status_distribution": {
                    "Closed": 13,
                    "Sent": 12,
                    "Partially Received": 10,
                    "Received": 9,
                    "Approved": 5,
                    "Cancelled": 1,
                },
                "metrics": {
                    "completion_rate": "26%",  # Closed / Total
                    "cancellation_rate": "2%",  # Cancelled / Total
                },
            },
        },

        # ====================================================================
        # 4. 업무 용어 정의
        # ====================================================================
        "business_glossary": {
            "구매액": "purchase_orders.total_amount (발주 금액 기준, Cancelled 제외)",
            "지출": "purchase_orders.total_amount 합계",
            "미지급금": "outstanding_amount = total_amount - amount_paid",
            "미지급액": "vendor_invoices.outstanding_amount",
            "발주": "purchase_orders 테이블 (49건, 취소 제외)",
            "발주 상세": "purchase_order_lines 테이블 (123줄)",
            "입고": "goods_receipts 테이블 (32건)",
            "청구서": "vendor_invoices 테이블 (32개)",
            "공급업체": "vendors 테이블 (25개, 모두 Jordan)",
            "3-way 매칭": "invoice_matching (데이터 없음 — 거절)",
            "공급업체 평가": "vendor_ratings (데이터 없음 — 거절)",

            # 발주 상태
            "발주 상태": {
                "Approved": "5건 - 승인됨 (미착수)",
                "Sent": "12건 - 발송됨 (유효한 발주)",
                "Partially Received": "10건 - 부분 수령 (진행 중)",
                "Received": "9건 - 완전 수령 (완료)",
                "Closed": "13건 - 완료됨",
                "Cancelled": "1건 - 취소됨 (구매액에서 제외)",
            },

            # 지급 상태
            "지급 상태": {
                "Paid": "완전히 지급됨",
                "Partially Paid": "일부만 지급됨 (미지급액 있음)",
                "Overdue": "지급 기한 초과 (미지급)",
            },

            # 결제 조건
            "결제 조건": {
                "COD": "선급금 (7개 업체)",
                "NET30": "순매출채권 30일 (4개 업체)",
                "NET45": "순매출채권 45일 (6개 업체)",
                "NET60": "순매출채권 60일 (8개 업체)",
            },
            "구매액": "purchase_orders.total_amount (발주 금액 기준, Cancelled 제외)",
            "지출": "purchase_orders.total_amount 합계",
            "미지급금": "outstanding_amount = total_amount - amount_paid",
            "미지급액": "vendor_invoices.outstanding_amount",
            "발주": "purchase_orders 테이블 (49건, 취소 제외)",
            "발주 상세": "purchase_order_lines 테이블 (123줄)",
            "입고": "goods_receipts 테이블 (32건)",
            "청구서": "vendor_invoices 테이블 (32개)",
            "공급업체": "vendors 테이블 (25개, 모두 Jordan)",
            "3-way 매칭": "invoice_matching (데이터 없음 — 거절)",
            "공급업체 평가": "vendor_ratings (데이터 없음 — 거절)",

            # 발주 상태
            "발주 상태": {
                "Approved": "5건 - 승인됨 (미착수)",
                "Sent": "12건 - 발송됨 (유효한 발주)",
                "Partially Received": "10건 - 부분 수령 (진행 중)",
                "Received": "9건 - 완전 수령 (완료)",
                "Closed": "13건 - 완료됨",
                "Cancelled": "1건 - 취소됨 (구매액에서 제외)",
            },

            # 지급 상태
            "지급 상태": {
                "Paid": "완전히 지급됨",
                "Partially Paid": "일부만 지급됨 (미지급액 있음)",
                "Overdue": "지급 기한 초과 (미지급)",
            },

            # 결제 조건
            "결제 조건": {
                "COD": "선급금 (7개 업체)",
                "NET30": "순매출채권 30일 (4개 업체)",
                "NET45": "순매출채권 45일 (6개 업체)",
                "NET60": "순매출채권 60일 (8개 업체)",
            },
            "지출": "purchase_orders.total_amount 또는 vendor_invoices.total_amount 합계",
            "공급업체": "vendors 테이블",
            "미지급금": "vendor_invoices.outstanding_amount",
            "발주": "purchase_orders",
            "입고": "goods_receipts",
            "3-way 매칭": "invoice_matching",
            "공급업체 평가": "vendor_ratings.overall_score",
            "구매액": "purchase_orders.total_amount (발주 금액 기준, Cancelled 제외)",
            "지출": "purchase_orders.total_amount 합계",
            "미지급금": "outstanding_amount = total_amount - amount_paid",
            "미지급액": "vendor_invoices.outstanding_amount",
            "발주": "purchase_orders 테이블 (49건, 취소 제외)",
            "발주 상세": "purchase_order_lines 테이블 (123줄)",
            "입고": "goods_receipts 테이블 (32건)",
            "청구서": "vendor_invoices 테이블 (32개)",
            "공급업체": "vendors 테이블 (25개, 모두 Jordan)",
            "3-way 매칭": "invoice_matching (데이터 없음 — 거절)",
            "공급업체 평가": "vendor_ratings (데이터 없음 — 거절)",

            # 발주 상태
            "발주 상태": {
                "Approved": "5건 - 승인됨 (미착수)",
                "Sent": "12건 - 발송됨 (유효한 발주)",
                "Partially Received": "10건 - 부분 수령 (진행 중)",
                "Received": "9건 - 완전 수령 (완료)",
                "Closed": "13건 - 완료됨",
                "Cancelled": "1건 - 취소됨 (구매액에서 제외)",
            },

            # 지급 상태
            "지급 상태": {
                "Paid": "완전히 지급됨",
                "Partially Paid": "일부만 지급됨 (미지급액 있음)",
                "Overdue": "지급 기한 초과 (미지급)",
            },

            # 결제 조건
            "결제 조건": {
                "COD": "선급금 (7개 업체)",
                "NET30": "순매출채권 30일 (4개 업체)",
                "NET45": "순매출채권 45일 (6개 업체)",
                "NET60": "순매출채권 60일 (8개 업체)",
            },
        },

        # ====================================================================
        # 5. 계산 가능한 지표 (30개+)
        # ====================================================================
        "metrics": {
            # 발주 관련
            "구매액": "purchase_orders.total_amount",
            "발주액": "purchase_orders.total_amount",
            "발주 건수": "COUNT(DISTINCT po_id)",
            "총 구매액": "SUM(total_amount)",
            "평균 구매액": "AVG(total_amount)",
            "최대 구매액": "MAX(total_amount)",
            "최소 구매액": "MIN(total_amount)",

            # 청구서 관련
            "미지급액": "outstanding_amount",
            "총 미지급액": "SUM(outstanding_amount)",
            "미지급 청구서": "COUNT(*) WHERE outstanding_amount > 0",
            "청구서 건수": "COUNT(DISTINCT invoice_id)",
            "지급액": "amount_paid",
            "지급률": "amount_paid / total_amount",

            # 입고 관련
            "입고 건수": "COUNT(DISTINCT gr_id)",

            # 공급업체 관련
            "공급업체 수": "COUNT(DISTINCT vendor_id)",
            "활성 공급업체": "COUNT(DISTINCT vendor_id) WHERE is_active = 1",

            # 상태 관련
            "취소됨": "COUNT(*) WHERE status = 'Cancelled'",
            "완료됨": "COUNT(*) WHERE status = 'Closed'",
            "대기 중": "COUNT(*) WHERE status IN ('Approved', 'Sent')",
        },

        # ====================================================================
        # 6. 범위 밖 질문 (거절 목록) — 35개+
        # ====================================================================
        "out_of_scope": [
            # === 데이터 없음 (6개) ===
            "공급업체 평가",
            "공급업체 평가 점수",
            "구매 요청",
            "구매 요청 현황",
            "3-way 매칭",
            "계약",

            # === PII (개인정보) (5개) ===
            "담당자",
            "담당자 연락처",
            "공급업체 이메일",
            "공급업체 전화",
            "공급업체 주소",

            # === 권한 범위 밖 (5개) ===
            "판매",
            "판매 현황",
            "고객 정보",
            "재고 현황",
            "데이터 수정",

            # === 기간 문제 (4개) ===
            "이번 달",  # 2026-08 = 데이터 없음
            "2024년",
            "다음 분기",
            "미래 데이터",

            # === 모호한 질문 (6개) ===
            "최근",
            "큰 발주",
            "활발한 공급업체",
            "많이 구매",
            "자주 사는",
            "비싼 물품",

            # === 상식 기반 추론 (3개) ===
            "철강 관련",
            "건설 회사",
            "기술 장비",
        ],

        # ====================================================================
        # 7. 질문 예시 (50개+)
        # ====================================================================
        "example_queries": [
            # v_purchase_order (12개)
            {"question": "Closed 상태인 발주들의 총액은?", "view": "v_purchase_order"},
            {"question": "Vendor #8에서 발주한 총액은?", "view": "v_purchase_order"},
            {"question": "100만원 이상 발주건이 몇 개?", "view": "v_purchase_order"},
            {"question": "Sent 상태인 발주 건수와 금액은?", "view": "v_purchase_order"},
            {"question": "Approved 상태의 발주들은?", "view": "v_purchase_order"},
            {"question": "가장 많이 발주한 공급업체 3개", "view": "v_purchase_order"},
            {"question": "중앙값보다 큰 발주들", "view": "v_purchase_order"},
            {"question": "2025년 5월에 발주한 건들", "view": "v_purchase_order"},
            {"question": "가장 작은 금액의 발주는?", "view": "v_purchase_order"},
            {"question": "652만원 이상 발주건", "view": "v_purchase_order"},
            {"question": "Vendor #1의 발주 현황", "view": "v_purchase_order"},
            {"question": "Partially Received 상태인 발주", "view": "v_purchase_order"},

            # v_purchase_order_line (10개)
            {"question": "가장 많이 구매한 상품은?", "view": "v_purchase_order_line"},
            {"question": "Plastic Bin 600x400를 몇 개 구매했어?", "view": "v_purchase_order_line"},
            {"question": "할인이 적용된 라인들의 통계", "view": "v_purchase_order_line"},
            {"question": "10% 할인을 받은 품목들", "view": "v_purchase_order_line"},
            {"question": "단가가 가장 비싼 상품은?", "view": "v_purchase_order_line"},
            {"question": "단가 500 JOD 이상인 품목들", "view": "v_purchase_order_line"},
            {"question": "라인별 총액이 가장 큰 상위 10개", "view": "v_purchase_order_line"},
            {"question": "할인이 없는 품목들만", "view": "v_purchase_order_line"},

            # v_vendor (8개)
            {"question": "전체 공급업체 수는?", "view": "v_vendor"},
            {"question": "모든 공급업체가 활성인가?", "view": "v_vendor"},
            {"question": "결제 조건이 COD인 업체들", "view": "v_vendor"},
            {"question": "NET60 조건의 공급업체는?", "view": "v_vendor"},
            {"question": "결제 조건별 공급업체 분포", "view": "v_vendor"},
            {"question": "모든 공급업체가 요르단에 있나?", "view": "v_vendor"},
            {"question": "JOD를 기본 통화로 하는 업체", "view": "v_vendor"},
            {"question": "공급업체 코드로 정렬한 목록", "view": "v_vendor"},

            # v_vendor_invoice (12개)
            {"question": "미지급액이 가장 많은 공급업체는?", "view": "v_vendor_invoice"},
            {"question": "총 미지급액은?", "view": "v_vendor_invoice"},
            {"question": "미지급 청구서가 몇 개?", "view": "v_vendor_invoice"},
            {"question": "연체 상태인 청구서는?", "view": "v_vendor_invoice"},
            {"question": "일부만 지급한 청구서", "view": "v_vendor_invoice"},
            {"question": "완전히 지급한 청구서", "view": "v_vendor_invoice"},
            {"question": "지급 완료한 청구서 총액", "view": "v_vendor_invoice"},
            {"question": "청구서 금액이 100만원 이상인 건들", "view": "v_vendor_invoice"},
            {"question": "특정 공급업체의 청구서 현황", "view": "v_vendor_invoice"},
            {"question": "지급 기한이 지난 미지급 청구서", "view": "v_vendor_invoice"},
            {"question": "가장 최근의 청구서들", "view": "v_vendor_invoice"},
            {"question": "전체 청구액 중 아직 안 지급한 비율은?", "view": "v_vendor_invoice"},

            # v_purchase_order_status (6개)
            {"question": "상태별 발주 분포를 보여줘", "view": "v_purchase_order_status"},
            {"question": "완료(Closed)율은 몇 퍼센트?", "view": "v_purchase_order_status"},
            {"question": "취소된 발주는 1개인가?", "view": "v_purchase_order_status"},
            {"question": "Approved 상태의 발주들은?", "view": "v_purchase_order_status"},
            {"question": "Received 상태인 발주", "view": "v_purchase_order_status"},
            {"question": "상태별 평균 발주액은?", "view": "v_purchase_order_status"},
        ],

        # ====================================================================
        # 8. 통계 정보
        # ====================================================================
        "summary_statistics": {
            "purchase_orders": {
                "total": 50,
                "total_excluding_cancelled": 49,
                "status_distribution": {
                    "Closed": 13,
                    "Sent": 12,
                    "Partially Received": 10,
                    "Received": 9,
                    "Approved": 5,
                    "Cancelled": 1,
                },
                "amount_stats": {
                    "min": 3.46,
                    "max": 652173.97,
                    "avg": 58601.49,
                    "median": 15307.33,
                },
            },
            "po_lines": {
                "total": 123,
                "lines_per_po_avg": 2.46,
                "with_discount": 59,
                "without_discount": 64,
            },
            "vendors": {
                "total": 25,
                "active": 25,
                "countries": ["Jordan"],
            },
            "invoices": {
                "total": 32,
                "total_outstanding": 689767.45,
                "invoices_with_outstanding": 11,
            },
        },

        # ====================================================================
        # 9. 데이터 범위
        # ====================================================================
        "data_range": {
            "purchase_orders": "2025-01-22 ~ 2026-06-25",
            "invoices": "2025-02-16 ~ 2026-07-13",
            "goods_receipts": "2025-02-10 ~ 2026-07-12",
            "latest": "2026-07-13",
            "notes": "2026-08 이후 데이터는 없음",
        },

        # ====================================================================
        # 10. 데이터베이스 정보
        # ====================================================================
        "database": "purchase_db",
        "company_id": 1,

        # ====================================================================
        # 11. 주의사항
        # ====================================================================
        "warnings": [
            "발주액 계산 시 Cancelled 상태는 항상 제외됨",
            "발주 상세 집계 시 헤더 금액을 쓰면 금액이 중복되므로 line_total만 사용",
            "2026-08 이후의 데이터는 없음",
            "모든 공급업체가 Jordan에 위치하고 JOD 통화 사용",
            "PII(담당자명, 연락처, 주소 등)는 조회 불가",
        ],

        # ====================================================================
        # 12. 중요한 정보
        # ====================================================================
        "important_notes": {
            "fan_out_prevention": "v_purchase_order_line에는 헤더 금액이 의도적으로 제외됨 (fan-out 방지)",
            "cancelled_exclusion": "Cancelled 상태는 v_purchase_order에서 WHERE절로 제외",
            "data_period": "데이터는 2025-01-22 ~ 2026-07-13만 있음",
            "company_id": "모든 레코드의 company_id는 1 (단일 회사)",
            "pii_excluded": "이메일, 전화, 주소, 담당자명 등은 스키마에서 완전 제외",
            "status_interpretation": "Sent = 발송되었으므로 유효한 발주",
        },
    }