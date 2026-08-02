# [팀 공유 자료 2] rag_purchase — MCP Purchase SQL Tool 개발 방법 및 스펙 가이드

- **작성자**: rag_sales 담당 (PM 겸임)
- **읽는 대상**: rag_purchase 담당 (+ 참고용으로 팀 전체)
- **성격**: 이 문서는 **완성된 스펙이 아니라 가이드 + 템플릿**이다. sales와 purchase는
  코드 구조·방법론이 거의 동일하고 **다른 건 데이터뿐**이라, 우리(rag_sales)가 실제로
  밟은 과정을 그대로 따라올 수 있게 정리했다. 다만 "매출"에 해당하는 "구매액"의 정확한
  정의처럼 **업무 판단이 필요한 부분은 rag_purchase 담당자가 본인 데이터를 직접 열어보고
  결정해야 한다** — 우리도 그렇게 정했다 ([01_rag_sales_text2sql.md](01_rag_sales_text2sql.md) 참고).
- **근거 자료**: 이 문서의 데이터 관련 내용은 PM이 전달받은 원본 파일
  `ERP_Purchasing_Analytics.xlsx`를 직접 열어서 확인한 실측치다. 아직 DB에 적재되기
  전 상태이며, 실제 DB 적재 후에는 반드시 재검증이 필요하다(3.4절 참고).

---

## 0. 먼저 읽을 것

같은 용어(뷰, 가드, EXPLAIN, PII, fan-out, 환각)를 여기서 또 설명하지 않는다.
[01_rag_sales_text2sql.md의 0절](01_rag_sales_text2sql.md)을 먼저 읽고 오면 이 문서가
훨씬 빨리 읽힌다.

---

## 1. 왜 sales와 같은 방식을 쓰면 되는가

sales에서 7가지 Text2SQL 기법을 조사해서 "① 정의 고정(시맨틱 레이어) + ② 실행 피드백
자기수정" 조합을 골랐다. 그 이유가 **"테이블 개수가 적어서 스키마 전체를 프롬프트에
넣어도 부담이 없다"**는 것이었는데, purchase도 사정이 같다.

| | sales | purchase |
|---|---:|---:|
| DDL에 선언된 테이블 수 | 14개 | 13개 |
| 실제 원본 데이터가 있는 테이블 수 | 14개 (전부) | **5개뿐** (2.2절 참고) |

즉 purchase는 오히려 sales보다 **다뤄야 할 테이블이 더 적다.** 3·5·7번(스키마가 너무
커서 못 넣는 문제를 푸는 기법)이 필요 없는 이유가 sales보다도 더 명확하다. **1+2 조합을
그대로 가져다 쓰는 것을 권장한다.**

---

## 2. 지금 상태 확인 결과 (착수 전 반드시 먼저 처리할 것)

실제 코드를 열어봤고, **아래 두 가지는 스펙과 무관하게 지금 당장 막혀있는 문제라
가장 먼저 해결해야 한다.**

### 2.1 🔴 git 병합 충돌이 안 풀린 채로 코드에 남아있음

`mcp_servers/data_tools/purchase/schema.py`, `query.py`, `text2sql.py` 3개 파일에
git이 병합 충돌 났을 때 남기는 표시(`<<<<<<<< HEAD`, `========`, `>>>>>>>> origin/develop`)가
**그대로 코드 안에 남아있다.** 예를 들면:

```python
# mcp_servers/data_tools/purchase/schema.py 12~17번 줄
def get_schema_resource() -> SchemaResource:
<<<<<<<< HEAD:mcp_servers/data_tools/purchase/schema.py
    """Text2SQL에 구매 테이블·컬럼·업무 용어를 제공하는 MCP Resource를 만든다.
========
    """Text2SQL에 재무(구매/지출) 테이블·컬럼·업무 용어를 제공하는 MCP Resource를 만든다.
>>>>>>>> origin/develop:mcp_servers/data_tools/finance/schema.py
```

이 상태로는 **Python 파일로서 문법 오류라 import 자체가 안 된다.** 무엇을 구현하기
전에, 이 3개 파일부터 충돌을 해소해야 한다(둘 중 최신 버전을 고르거나 합치기). `finance`
라는 이름이 남은 쪽은 지워도 된다 — 프로젝트 전체가 `finance`→`purchase`로 이름을 바꾼
지 오래됐다(git log의 "Replace finance domain with purchase across project" 커밋 참고).

### 2.2 `query.py`가 없는 모듈을 import하고 있음

같은 이유로 [purchase/query.py:6-8](../../mcp_servers/data_tools/purchase/query.py)이
`mcp_servers.data_tools.finance.mysql` 같은 **`finance` 폴더**를 import하는데, 그
폴더는 이미 `purchase`로 이름이 바뀌어서 존재하지 않는다. 충돌 해소하면서 전부
`mcp_servers.data_tools.purchase.*`로 통일하면 된다.

> 참고로 `mysql.py`의 `settings.finance_db_database`는 **동작은 한다.**
> [app/core/config.py:31](../../app/core/config.py)에 `finance_db_database: str = "purchase"`로
> 필드 이름만 옛날 이름이 남아있고 실제 값은 `"purchase"`를 가리킨다. 헷갈리니 나중에
> `purchase_db_database`로 이름을 바꾸는 걸 권장하지만, 지금 당장 기능이 막히는 문제는
> 아니다.

### 2.3 sales에서 이미 제거하기로 한 것과 똑같은 하드코딩이 있음

[purchase/text2sql.py](../../mcp_servers/data_tools/purchase/text2sql.py)에
`OPENAI_API_KEY`가 없을 때 키워드만 보고 고정 SQL을 돌려주는 `_FALLBACK_TEMPLATES`가
있는데, 이건 sales에도 똑같이 있던 코드다. 우리는 이걸 **완전히 삭제하기로 결정**했다
(이유: "매출"이라는 단어만 들어있으면 질문 내용과 상관없이 항상 같은 SQL이 실행돼서,
기간·조건이 다른 질문에도 틀린 답을 에러 없이 돌려준다 — [01번 문서 3절 D-16](01_rag_sales_text2sql.md)
참고). **purchase도 동일하게 제거를 권장한다.**

### 2.4 스키마 정보에 이미 있는 "또는" 문제

[purchase/schema.py](../../mcp_servers/data_tools/purchase/schema.py)의
`business_glossary`에 이렇게 적혀있다.

```python
"지출": "purchase_orders.total_amount 또는 vendor_invoices.total_amount 합계",
```

이게 정확히 sales의 `schema.py`에서 우리가 고쳤던 문제와 같다. **"또는"이라고 적으면
LLM에게 골라도 된다고 알려주는 셈**이라, 같은 질문에 다른 답이 나올 수 있다. "지출"의
정의를 하나로 확정해서 못박아야 한다 (6절 참고).

---

## 3. purchase 데이터 현황 (원본 엑셀 실측)

`ERP_Purchasing_Analytics.xlsx`를 직접 열어서 확인한 값이다. **아직 DB에 적재되기 전
상태**라는 점을 꼭 유의해야 한다 — sales는 이미 ETL을 1회 실행해서 실제 DB에서 확인한
값이었지만, purchase는 원본 파일 기준이다. ETL 실행 후 반드시 재확인해야 한다(3.4절).

### 3.1 시트별 규모

| 시트 이름 | 행 수 | 대응 테이블(예상) | 비고 |
|---|---:|---|---|
| Purchase Orders | 50 | `purchase_orders` | 발주 헤더 |
| PO Lines | 123 | `purchase_order_lines` | 발주 상세, 발주 1건당 평균 2.46줄 |
| Vendors | 25 | `vendors` | 공급업체 마스터. 이 중 실제 발주 이력이 있는 곳은 22곳뿐(3곳은 거래 없음) |
| Invoices | 32 | `vendor_invoices` | 청구서 |
| Goods Receipts | 32 | `goods_receipts` | 입고 |

### 3.2 🔴 가장 중요한 발견 — 선언된 테이블 13개 중 5개만 실제 데이터가 있음

[purchase/schema.py](../../mcp_servers/data_tools/purchase/schema.py)와
[database/purchase/schema.sql](../../database/purchase/schema.sql) +
[schema_v2_vendor_extras.sql](../../database/purchase/schema_v2_vendor_extras.sql)에는
**13개 테이블**이 선언돼 있는데, 지금 받은 원본 엑셀에는 **시트가 5개뿐**이다.

```
데이터가 있는 5개(위 표)
      vs
데이터가 없을 가능성이 높은 8개:
  purchase_requisitions, purchase_requisition_lines,   ← 구매 요청(발주 전 단계)
  goods_receipt_lines,                                  ← 입고 상세
  vendor_invoice_lines,                                 ← 청구서 상세
  procurement_reports,                                  ← 구매 보고서
  vendor_contracts,                                      ← 계약
  vendor_ratings,                                        ← 공급업체 평가
  invoice_matching                                       ← 3-way 매칭(발주-입고-청구서 대사)
```

이건 정확히 sales에서 우리가 잡아낸 문제(`stock_levels`처럼 스키마에는 있지만 실제로는
비어있는 테이블을 LLM에게 알려주던 것)와 **같은 유형의 함정**이다. LLM에게 "이 테이블
있어요"라고 알려주면, 관련 질문이 왔을 때 SQL은 문법적으로 멀쩡하게 만들어지지만
실행하면 항상 0건이 나오거나, 최악의 경우 다른 파일이 나중에 이 테이블들을 채우게
되면 그때는 맞는데 그 전까지는 계속 틀린 "없다"는 답만 나온다.

**착수 전 확인 리스트:**
- [ ] 원본 데이터에 이 8개 테이블에 대응하는 별도 파일이 더 있는지 확인 (다른 시트가
      있는 엑셀 파일, 또는 별도 CSV 등)
- [ ] 없다면, 스키마 리소스(6절)에서 이 8개 테이블을 아예 빼거나, "아직 데이터 없음"으로
      명시하고 관련 질문은 거절 목록(8절)에 넣을 것
- [ ] `etl/purchase/*.py`가 현재 스켈레톤(`...`) 상태라 ETL이 한 번도 실행된 적이 없다.
      먼저 이 5개 시트에 대해서만 ETL을 구현·실행해서 실제 DB 행 수를 다시 확인할 것

### 3.3 실측 수치

| 항목 | 값 |
|---|---|
| 통화 | JOD 단일 (sales와 동일) |
| 발주(PO) 날짜 범위 | 2025-01-22 ~ 2026-06-25 |
| 청구서 날짜 범위 | 2025-02-16 ~ 2026-07-13 |
| 입고 날짜 범위 | 2025-02-10 ~ 2026-07-12 |
| company_id 컬럼 | **원본 Vendors 시트에 없음** — DDL에는 있지만 ETL이 어떤 값을 넣을지 확인 필요 (sales처럼 상수 1일 가능성이 높지만 가정하지 말 것) |

**발주(PO) 상태 분포**

| 상태 | 건수 | 금액 합계(JOD) |
|---|---:|---:|
| Approved | 5 | 124,164.16 |
| Closed | 13 | 1,165,481.48 |
| Partially Received | 10 | 888,176.80 |
| Received | 9 | 362,626.97 |
| Sent | 12 | 377,975.69 |
| **Cancelled** | **1** | **11,649.23** |
| **합계(전체)** | **50** | **2,930,074.33** |
| **합계(취소 제외)** | **49** | **2,918,425.10** |

취소 1건이 전체의 약 0.4%로 sales(약 7.3%)보다 비중은 작지만, **"취소를 셀지 말지"를
정해야 하는 구조적 문제는 sales와 똑같이 존재한다.** 몇 건 안 된다고 무시하면 안 되는
이유: 이건 데이터 우연이지, 나중에 데이터가 늘어나면 비중이 달라질 수 있는 "설계
결정"의 문제다.

**청구서(Invoice) 상태 분포**

| 상태 | 건수 | 청구액 합계(JOD) | 미지급액 합계(JOD) |
|---|---:|---:|---:|
| Paid | 21 | 1,316,503.16 | 0.00 |
| Partially Paid | 8 | 41,158.16 | 24,712.27 |
| Overdue | 3 | 665,055.18 | 665,055.18 |
| **합계** | **32** | | **689,767.45** |

sales의 invoice 상태값에는 `Unpaid`가 있었는데 purchase에는 없다 — 상태값 종류가
도메인마다 다르니 그대로 가정하지 말고 실제 값으로 확인할 것.

**fan-out(뻥튀기) 위험 — sales와 동일한 구조**

```
발주(PO) 50건 / 발주상세(PO Lines) 123건 = 평균 2.46줄/발주
```

sales의 주문-상세 비율(주문 70건 / 상세 192건 = 평균 2.7줄)과 거의 같은 구조다. 발주
헤더 금액과 발주상세를 그냥 JOIN해서 더하면 **상세 줄 수만큼 금액이 중복으로 더해진다.**
sales와 똑같은 대응이 필요하다 — 상세 단위 뷰에는 헤더 금액을 아예 넣지 않는다(6절).

### 3.4 개인정보(PII) — sales보다 위험이 낮아 보이지만 방심 금지

DDL([database/purchase/schema.sql](../../database/purchase/schema.sql))에는 `vendors`
테이블에 `email`, `phone_number`, `address`, `tax_id`, `bank_account`, `iban`,
`contact_person` 칼럼이 선언돼 있다. **그런데 지금 받은 원본 엑셀의 Vendors 시트에는
이 칼럼들이 아예 없다** (있는 건 `Vendor_ID, Vendor_Code, Vendor_Name, Country,
Currency, Payment_Terms, Is_Active` 7개뿐).

즉 이 파일로 ETL을 돌리면 저 PII 칼럼들은 전부 빈 값(NULL)으로 채워질 가능성이 높다.
**값이 비어있어도 원칙은 sales와 동일하게 가야 한다.** 스키마 리소스(LLM에게 주는
정보)와 뷰에서 이 칼럼들을 아예 빼는 것을 권장한다. 이유:

1. 나중에 다른 원본 파일로 이 칼럼들이 채워질 수도 있다 (지금 비어있다고 앞으로도
   비어있는다는 보장이 없음)
2. LLM에게 "이런 칼럼이 있다"는 정보 자체를 안 주는 게, "값이 비어있으니 안전하다"고
   믿는 것보다 훨씬 확실한 방어다 (01번 문서 D-11의 이유와 동일)
3. 특히 `bank_account`, `iban`(계좌번호)은 sales의 customers 테이블에는 없던 훨씬
   민감한 항목이다. 값이 비어있더라도 스키마에서 배제하는 원칙은 반드시 지킬 것

---

## 4. 우리와 동일하게 적용할 3중 방어 구조

sales에서 쓴 구조를 그대로 재사용하면 된다 (자세한 이유는
[01번 문서 3절](01_rag_sales_text2sql.md) 참고).

```
1층  MySQL 뷰       "구매액이 뭔지" 등 정의를 못박고, PII·fan-out을 구조로 차단
2층  DB 권한         조회 전용 계정은 뷰만 볼 수 있고 원본 테이블은 아예 못 봄
3층  SQL 검사        실행 전 문법·안전성 검사 + EXPLAIN 사전 채점
```

### 뷰 후보 (초안 — 실제 결정은 rag_purchase 담당자 몫)

3.2절에서 확인했듯 **실제 데이터가 있는 건 5개 테이블뿐**이라, 뷰도 그에 맞춰 작게
시작하는 걸 권장한다. 아래는 sales의 뷰 5개와 대응시킨 초안이다.

| 뷰(초안 이름) | 대응하는 sales 뷰 | 담는 내용 |
|---|---|---|
| `v_purchase_order` | `v_sales_order` | 유효한 발주(취소 제외 여부는 직접 결정) |
| `v_purchase_order_line` | `v_sales_order_line` | 발주 상세 (헤더 금액은 일부러 안 넣음 — fan-out 방지) |
| `v_vendor_invoice` | `v_invoice` | 청구·미지급금 |
| `v_vendor` | `v_customer` | 공급업체 정보 (PII 칼럼 제외) |
| `v_purchase_order_status` | `v_sales_order_status` | 취소 포함 발주 현황 (선택) |

`purchase_requisitions`, `goods_receipts`, `vendor_contracts`, `vendor_ratings`,
`invoice_matching` 등은 **데이터가 실제로 있는 것을 확인한 뒤에** 뷰 대상에 넣을지
결정할 것. 입고(`goods_receipts`, 32건)는 데이터가 있으니 뷰로 만들 가치가 있어
보이지만(3-way 매칭의 절반), 최종 판단은 rag_purchase 담당자가 한다.

---

## 5. 처리 순서 — sales와 완전히 동일하게 재사용 가능

이 흐름은 도메인에 상관없이 그대로 가져다 쓸 수 있다. **어떤 부분이 코드(Python)이고
어떤 부분이 LLM이고 어떤 부분이 MySQL인지**를 구분해두는 게 핵심이다 (01번 문서 5·6절
피드백 반영).

```
질문
 │
 ├─(1) 입력 확인 [코드]                빈 질문 / 500자 초과 → 거절
 │
 ├─(2) 범위 확인 [코드]                구매 범위 밖 → 거절 (권한 안내)
 │                                    뷰로 못 답하는 내용 → 거절 (되묻기)
 │                                    기간이 애매함 → 거절 (되묻기)
 │
 ├─(3) 프롬프트 재료 조립 [코드]        뷰 구조 + 지표 정의 + 오늘 날짜를 준비
 │
 ├─(4) SQL 작성 [LLM] ★               질문 + (3)의 재료 → SQL 문자열 1개
 │
 ├─(5) 1차 검사 [코드]                 SELECT 하나뿐인지 / 위험한 명령어 없는지 / 허용된 뷰만 쓰는지 / LIMIT 붙었는지
 │        │ 위반
 │        └─────────────┐
 ├─(6) EXPLAIN 채점 [MySQL]│  실패
 │        │              │    │
 │        │              ▼    ▼
 │        │        (6a) 재작성 [LLM] ★    실패 이유를 그대로 보여주고 SQL 다시 요청 (최대 1회)
 │        │              │
 │        │              └─→ 재검증도 실패 → QUERY_ERROR로 종료 [코드]
 │        ▼ 통과
 ├─(7) 실제 조회 실행 [MySQL]           조회 전용 계정, 최대 10초
 │
 ├─(8) 결과 정리 [코드]                0건이면 "없다"고 안내 / LLM용 50행 · 화면용 전체로 나눔
 │
 └─(9) 결과 반환 [코드]                query_purchase()의 최종 반환값 조립
```

**LLM은 (4)와 (6a) 딱 두 곳에서만 불린다.** 각 단계별 담당·입력·반환값의 자세한 표는
[01번 문서 6절](01_rag_sales_text2sql.md)의 표를 그대로 참고하면 된다 — 함수 이름만
`query_sales`→`query_purchase`, `sales_orders`→`purchase_orders`로 바꾸면 된다.

---

## 6. rag_purchase 담당자가 직접 답해야 할 질문 (체크리스트)

**여기부터는 우리가 대신 정할 수 없는 부분이다.** sales에서는 PM이 실제 데이터를
확인해가며 아래와 같은 질문에 하나씩 답하는 인터뷰 과정을 거쳤다
([01번 문서 1절](01_rag_sales_text2sql.md)). purchase도 같은 과정을 거쳐야 한다.
그대로 쓸 수 있게 질문만 도메인에 맞게 바꿔서 정리했다.

| 구분 | sales의 결정 (참고용) | purchase가 답해야 할 질문 |
|---|---|---|
| 핵심 지표 정의 | 매출 = `sales_orders.total_amount` 합 | "구매액/지출"은 `purchase_orders.total_amount`인가, `vendor_invoices.total_amount`인가? ("또는"이라고 하면 안 됨 — 2.4절) |
| 상태 필터 | Cancelled·Draft 제외 | Cancelled(1건, 0.4%)를 구매액 계산에서 뺄 것인가? `Sent`(발송만 되고 아직 승인 전)는 "유효한 구매"로 볼 것인가? |
| 라인 단위 집계 | `line_total` 사용, 헤더 금액 금지 | "품목별 구매액"은 `purchase_order_lines.line_total` 합계로 할 것인가? |
| 기준 시점 | 오늘 날짜 기준, 데이터는 ~2026-06-23까지 | purchase 데이터는 청구서가 2026-07-13까지 있다 — "오늘" 기준 최근 질문이 실제로 빈 결과가 나오는지 직접 확인했는가? |
| 범위 밖 처리 | 원가·재고 등 답 불가 목록 명시 | 구매 요청(`purchase_requisitions`), 공급업체 평가(`vendor_ratings`), 3-way 매칭(`invoice_matching`) 등 데이터가 없는(3.2절) 항목을 어떻게 거절할지 |
| PII | email 등 뷰에서 제외 | `bank_account`, `iban`(계좌번호)까지 포함해서 제외 목록 확정 |
| DB 계정 | `chatbot_reader` 신규 생성, 뷰만 GRANT | purchase용 조회 전용 계정을 sales와 같은 계정으로 공유할지, 별도로 만들지 (권장: 별도 — 도메인 간 교차 접근을 DB 권한으로도 막기 위해, 01번 문서 8.1절 참고) |
| company_id | 값이 1 하나뿐임을 확인 | 원본 데이터엔 company_id가 없다(3.3절) — ETL이 채워 넣을 값을 확인하고, 여러 회사가 섞여 있는지 반드시 검증 |

---

## 7. 답변 가능한 시나리오 (초안 — 데이터 재확인 후 확정)

5개 뷰가 만들어졌다는 가정하에:

| 질문 예시 | 사용할 뷰 |
|---|---|
| "2025년 4분기 구매액 알려줘" | `v_purchase_order` |
| "구매액 상위 5개 공급업체" | `v_purchase_order` |
| "가장 많이 구매한 품목 10개" | `v_purchase_order_line` |
| "미지급 청구서 총액" | `v_vendor_invoice` |
| "취소된 발주가 몇 건이야" | `v_purchase_order_status` |
| "공급업체 목록 국가별로 보여줘" | `v_vendor` |

## 8. 답변 불가능한 시나리오 (초안)

| 시나리오 | 이유 |
|---|---|
| "공급업체 평가 점수 알려줘" | `vendor_ratings` 데이터 없음(3.2절) — 실제 데이터 확인 전까지 거절 |
| "구매 요청이 발주로 전환되는 비율" | `purchase_requisitions` 데이터 없음 |
| "발주-입고-청구서가 다 맞게 처리됐는지" (3-way 매칭) | `invoice_matching` 데이터 없음 |
| "공급업체 계좌번호 알려줘" | PII, 애초에 스키마에서 배제(3.4절) |
| sales 관련 질문이 잘못 들어옴 | 권한 밖 — purchase 계정은 purchase DB만 조회 가능 (권장, 6절) |
| "이번 달 구매액"(오늘 기준) | 데이터 보유 기간을 실제로 확인한 뒤 sales와 같은 문제(항상 0건)가 있는지 검증 필요 |

---

## 9. 로그·에러코드 — sales와 같은 형식 그대로

일관성을 위해 로그 형식, 에러코드(`INVALID_INPUT`, `NO_RESULT`, `QUERY_ERROR`,
`INTERNAL_ERROR`), 거절 메시지 원칙("왜 안 되는지 + 대안")을 sales와 동일하게 맞추는
것을 권장한다. 자세한 표는 [01번 문서 9·10절](01_rag_sales_text2sql.md) 참고.

---

## 10. 착수 전 체크리스트

```
[ ] 2.1  git 병합 충돌 3개 파일 해소 (schema.py, query.py, text2sql.py)
[ ] 2.2  finance.* import를 purchase.*로 통일
[ ] 2.3  _FALLBACK_TEMPLATES 하드코딩 제거 여부 결정
[ ] 2.4  business_glossary의 "또는" 표현 확정된 정의로 교체
[ ] 3.2  8개 테이블에 실제 데이터가 있는지 확인 (다른 원본 파일 존재 여부)
[ ] 3.4  ETL 실행 후 PII 칼럼이 실제로 비어있는지 확인
[ ] 6절  체크리스트 질문에 전부 답하기 (본인 인터뷰 과정 — PM과 함께 진행 권장)
[ ] 4절  뷰 설계 확정 및 DDL 작성
[ ] RULE.md 5항에 따라 docs/plan/query-purchase-text2sql.md 작성 후 착수
```

---

## 참고

- sales 쪽 전체 스펙(구조가 거의 동일하니 참고): [SPEC.md](../../SPEC.md)
- sales 쪽 팀 공유 자료: [01_rag_sales_text2sql.md](01_rag_sales_text2sql.md)
- 프로젝트 공통 규칙: [RULE.md](../../RULE.md)
