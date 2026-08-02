# SPEC — `query_sales` MCP Tool (판매 도메인 Text2SQL)

- **문서 상태**: 확정 (인터뷰 완료, 구현 착수 전)
- **최초 작성**: 2026-08-01 · **개정**: 2026-08-02
- **담당**: 판매(rag_sales) 파트
- **브랜치**: `rag_sales`
- **관련 문서**: [README.md](README.md), [docs/interface.md](docs/interface.md), [docs/ownership.md](docs/ownership.md), [RULE.md](RULE.md)

---

## 0. 먼저 알아두면 좋은 말 몇 개

이 문서에서 자주 나오는데 낯설 수 있는 말을 미리 풀어둔다. 아래 설명만 알면 나머지는 다 읽힌다.

| 용어 | 쉬운 설명 |
|---|---|
| **뷰(VIEW)** | "이 SQL을 실행한 결과"를 마치 테이블처럼 이름 붙여 저장해두는 것. 원본 테이블은 안 건드리고, 미리 걸러놓은 결과만 보여주는 창문 같은 것 |
| **가드(guard)** | LLM이 만든 SQL을 실행하기 전에 "이거 위험한 거 아니야?" 검사하는 코드 |
| **EXPLAIN** | MySQL에게 "이 SQL 진짜 실행할 수 있어?"만 미리 물어보는 명령. 실제 데이터는 안 건드리고 문법·존재 여부만 채점해줌 |
| **PII** | 이메일, 전화번호, 주소처럼 특정 개인/거래처를 식별할 수 있는 민감 정보 |
| **fan-out(뻥튀기)** | 주문 1건에 딸린 라인이 3개면, 주문 금액을 라인 3개에 각각 JOIN하는 순간 그 금액이 3배로 더해지는 현상 |
| **환각(hallucination)** | LLM이 실제로는 없는 사실이나 잘못된 숫자를 그럴듯하게 만들어내는 것 |

---

## 1. 목적과 범위

자연어로 들어온 판매 질문을 받아서 sales MySQL DB를 조회하고, "어떤 SQL로 어떤 결과가
나왔는지"를 근거로 같이 돌려주는 MCP 도구를 만든다.

### 우리가 만드는 부분

- `mcp_servers/data_tools/sales/` 폴더 전체 (`query.py`, `text2sql.py`, `schema.py`, `mysql.py`, `sql_guard.py`)
- `database/sales/` 폴더의 뷰 생성 SQL, 읽기 전용 계정 생성 SQL
- 위 코드에 대한 테스트

### 우리가 안 만드는 부분

- `app/agent/`, `app/mcp/`, `app/cache/`, `app/web/` — 통합(backend) 담당 몫
- `mcp_servers/data_tools/server.py` — 통합 담당 몫
- `mcp_servers/data_tools/purchase/` — 구매 담당 몫
- `etl/sales/` — 이미 1회 실행 완료. 이번 작업에서 손대지 않음

### 지금은 안 하는 것 (나중에)

**채팅창에 막대그래프 그리는 기능은 이번 스펙에서 뺀다.** 표(테이블)와 SQL을 보여주는 것까지만
하고, Chart.js로 그래프를 그리는 부분은 나중에 별도로 다시 다룬다. 자세한 내용은 14.2절 참고.

---

## 2. 실제 데이터 확인 결과 (2026-08-01 기준 실측)

`.env`의 쓰기 계정으로 sales DB를 직접 들여다본 값이다. **이 절의 숫자들은 데이터에 대한
고정된 사실이라 날짜가 지나도 그대로 유효하다** (반대로 "오늘 날짜" 같은 값은 이 절에 없다).

### 2.1 테이블 14개와 각각 몇 건씩 들어있는지

| 테이블 | 행 수 | 테이블 | 행 수 |
|---|---:|---|---:|
| customers (고객) | 40 | sales_orders (주문) | 70 |
| sales_order_lines (주문 상세) | 192 | invoices (청구서) | 53 |
| sales_quotes (견적) | 60 | sales_quote_lines (견적 상세) | 190 |
| order_fulfillment (배송) | 56 | fulfillment_lines (배송 상세) | 157 |
| sales_reports (보고서) | 18 | sales_forecasts (예측) | 40 |
| price_lists (가격표) | 40 | credit_limits (여신한도) | 40 |
| customer_contracts (계약) | 25 | discounts (할인) | 12 |

### 2.2 설계에 직접 영향을 준 사실들

| 확인한 사실 | 왜 중요한가 |
|---|---|
| **회사가 딱 1개뿐** | `company_id`가 모든 데이터에서 값이 `1` 하나뿐. "여러 회사 데이터가 섞일 위험"이 아예 없어서, 신경 쓸 필요가 사라짐 |
| **가장 최근 주문이 2026-06-23** | "이번 달", "최근 1개월" 같은 질문은 오늘 날짜 기준으로 계산하면 **항상 결과가 0건**이 됨(버그 아님, 데이터 사실). 빈 결과일 때 이 사실을 안내해야 함 |
| **통화가 요르단 디나르(JOD) 하나뿐** | 원화로 착각하지 않게 답변에 단위를 꼭 붙여야 함 |
| **취소·초안 상태 주문이 섞여있음** | Cancelled 3건(474,946.72) + Draft 2건(11,779.66) = 전체의 약 7.3%. 매출 계산에 넣고 빼고에 따라 답이 달라짐 |
| **품목 이름을 담은 별도 테이블이 없음** | 상품명은 `sales_order_lines.description` 칸에만 적혀 있음. "품목별 매출"은 이 칸으로 묶어서 계산해야 함 |
| **주문 하나에 상세 항목이 평균 2.7개** | 주문 금액과 상세 항목을 그냥 JOIN해서 더하면 뻥튀기(fan-out)됨 |
| **가짜 데이터라 상식과 안 맞는 값이 있음** | 예: 제약회사인데 업종이 '에너지'로, 통신사인데 '은행'으로 적혀있음. LLM이 "제약회사니까 당연히 이 업종이겠지" 하고 짐작하면 틀림 |

### 2.3 주문 상태별 현황

| 상태 | 건수 | 합계(JOD) | 매출 계산에 포함? |
|---|---:|---:|---|
| Invoiced | 26 | 2,066,603.13 | 포함 |
| Shipped | 13 | 2,116,334.26 | 포함 |
| Delivered | 14 | 799,197.77 | 포함 |
| Confirmed | 9 | 849,584.71 | 포함 |
| Partially Shipped | 3 | 333,746.63 | 포함 |
| **Cancelled(취소)** | 3 | 474,946.72 | **제외** |
| **Draft(초안)** | 2 | 11,779.66 | **제외** |
| **합계(유효 매출)** | 65 | **6,165,466.50** | |

---

## 3. 확정된 결정 사항

인터뷰로 정한 것 16가지다. 이후 무언가 바뀌면 이 표를 먼저 고친다.

| # | 항목 | 결정 |
|---|---|---|
| D-01 | 어떤 방식으로 SQL을 만들 것인가 | **① 정의를 미리 못 박아두는 방식(시맨틱 레이어) + ② SQL 실패 시 스스로 고치는 방식(자기수정)**. 조사한 7가지 기법 중 이 둘을 채택 |
| D-02 | 정의를 못 박는 위치 | **MySQL 뷰**로 만든다. LLM은 뷰만 보고, 원본 테이블은 아예 못 봄 |
| D-03 | "매출"의 정의 | `sales_orders.total_amount`(주문 금액)의 합 |
| D-04 | 어떤 주문을 셀 것인가 | 취소·초안 상태는 뷰 단계에서 항상 제외 |
| D-05 | 품목별로 셀 때 | `sales_order_lines.line_total`을 합하고, 품목명은 `description` 사용 (주문 헤더 금액은 절대 안 씀 — 뻥튀기 방지) |
| D-06 | company_id 처리 | 회사가 1개뿐이라 필터도 노출도 안 함 |
| D-07 | "오늘"은 언제인가 | **실제 오늘 날짜** 기준. 데이터가 없으면 없다고 정직하게 답하고 보유 기간을 알려줌 |
| D-08 | 애매하거나 답 못하는 질문 | SQL을 아예 만들지 않고 되묻거나 거절 |
| D-09 | SQL 검증 방법 | 실행 전에 EXPLAIN으로 먼저 채점, 틀리면 1번만 다시 만들어봄 |
| D-10 | DB 계정 | 조회 전용 계정을 새로 만들고, 이 계정은 뷰만 볼 수 있게 함 |
| D-11 | 개인정보(PII) | 뷰와 LLM에게 주는 정보 목록에서 아예 뺌 (LLM이 그런 항목이 있는지조차 모르게) |
| D-12 | 그래도 개인정보가 나온다면 | 결과에 안내 문구를 붙임 (D-11 덕분에 사실상 발생할 일이 거의 없는 안전망) |
| D-13 | 결과를 얼마나 보여줄 것인가 | LLM에게는 최대 50행만, 화면에는 전체를 보여줌 |
| D-14 | 생성된 SQL 노출 | 사용자에게 **보여준다** (근거를 눈으로 확인시켜주기 위해) |
| D-15 | 판매 범위 밖 질문 | 권한 밖이라고 거절 (이 계정은 sales DB만 볼 수 있음) |
| D-16 | 기존 하드코딩 처리 | `_FALLBACK_TEMPLATES`(키워드로 고정 SQL 고르던 코드) **완전히 삭제** |

---

## 4. 뷰로 만드는 "정의 고정 장치"

### 4.1 왜 뷰로 만드나

지난 대화에서 든 비유를 다시 쓰면: 식당마다 "곱빼기"의 양이 다르면 손님이 혼란스럽다.
그래서 "곱빼기 = 면 200g"이라고 주방 규칙에 못 박아두면, 어떤 요리사가 만들어도 같은 양이
나온다.

뷰가 그 역할을 한다. **"매출 = 취소·초안 뺀 주문 금액 합"** 같은 정의를 뷰 안에 넣어두면,
LLM이 SQL을 어떻게 쓰든 결과가 항상 같은 규칙을 따르게 된다. LLM에게 "이 규칙 지켜주세요"라고
부탁하는 게 아니라, **애초에 규칙을 어길 방법 자체가 없게 만드는 것**이다.

### 4.2 만들 뷰 5개

| 뷰 이름 | 무엇을 담나 | 용도 |
|---|---|---|
| `v_sales_order` | 유효한 주문 1건씩 (취소·초안 제외) | 매출, 고객별·기간별 집계 |
| `v_sales_order_line` | 유효한 주문의 상세 항목 1건씩 | 품목별·수량 집계 |
| `v_invoice` | 청구서 1건씩 | 청구액, 미수금, 연체 |
| `v_customer` | 고객 정보 (개인정보 칸은 뺌) | 고객 목록·속성 |
| `v_sales_order_status` | 상태별·월별로 미리 묶어둔 것 | "취소된 주문이 몇 건이야?" 같은 질문 |

`v_sales_order`와 `v_sales_order_line`은 취소·초안을 아예 빼고 보여주기 때문에 "취소된
주문"을 물으면 답할 수 없다. 그건 `v_sales_order_status`가 담당한다. 이렇게 나눠두면
**취소된 데이터가 매출 집계에 섞여 들어갈 방법이 구조적으로 없다.**

### 4.3 뷰 만드는 SQL

> 저장 위치: `database/sales/views.sql`

```sql
-- ---------------------------------------------------------------
-- v_sales_order : 유효한 주문(취소/초안 제외)
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_sales_order AS
SELECT
    o.sales_order_id,
    o.order_number,
    o.order_date,
    YEAR(o.order_date)                  AS order_year,
    QUARTER(o.order_date)               AS order_quarter,
    DATE_FORMAT(o.order_date, '%Y-%m')  AS order_month,   -- 미리 문자열로 만들어둠(집계용 라벨)
    o.customer_id,
    c.customer_name,
    c.customer_type,
    c.industry,
    c.country,
    o.status,
    o.currency,
    o.subtotal,
    o.discount_amount,
    o.tax_amount,
    o.total_amount                      AS order_amount,
    o.required_delivery_date,
    o.payment_terms
FROM sales_orders o
LEFT JOIN customers c ON c.customer_id = o.customer_id
WHERE o.status NOT IN ('Cancelled', 'Draft');

-- ---------------------------------------------------------------
-- v_sales_order_line : 유효한 주문의 상세 항목
--   ★ 주문 헤더 금액(total_amount)은 일부러 넣지 않는다.
--     이 뷰만 보면 헤더 금액을 합칠 방법이 없어서, 뻥튀기(fan-out)를 원천 차단한다.
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_sales_order_line AS
SELECT
    l.sales_order_line_id,
    l.sales_order_id,
    o.order_number,
    o.order_date,
    YEAR(o.order_date)                  AS order_year,
    QUARTER(o.order_date)               AS order_quarter,
    DATE_FORMAT(o.order_date, '%Y-%m')  AS order_month,
    o.customer_id,
    c.customer_name,
    c.industry,
    c.country,
    l.item_id,
    l.description                       AS item_name,
    l.quantity,
    l.unit_price,
    l.discount_percent,
    l.line_total,
    l.quantity_delivered,
    o.currency,
    o.status
FROM sales_order_lines l
JOIN sales_orders o      ON o.sales_order_id = l.sales_order_id
LEFT JOIN customers c    ON c.customer_id = o.customer_id
WHERE o.status NOT IN ('Cancelled', 'Draft');

-- ---------------------------------------------------------------
-- v_invoice : 청구·수금·미수금
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_invoice AS
SELECT
    i.invoice_id,
    i.invoice_number,
    i.invoice_date,
    i.due_date,
    YEAR(i.invoice_date)                  AS invoice_year,
    QUARTER(i.invoice_date)               AS invoice_quarter,
    DATE_FORMAT(i.invoice_date, '%Y-%m')  AS invoice_month,
    i.customer_id,
    c.customer_name,
    c.customer_type,
    c.country,
    i.order_id,
    i.subtotal,
    i.tax_amount,
    i.total_amount                        AS invoice_amount,
    i.amount_paid,
    i.outstanding_amount,
    i.currency,
    i.status,
    i.payment_terms
FROM invoices i
LEFT JOIN customers c ON c.customer_id = i.customer_id;

-- ---------------------------------------------------------------
-- v_customer : 고객 정보 (개인정보 칸 제외)
--   뺀 칸: contact_person, email, phone_number,
--          billing_address, shipping_address, tax_id,
--          account_manager_id, created_by_user_id
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_customer AS
SELECT
    customer_id,
    customer_code,
    customer_name,
    customer_type,
    industry,
    country,
    currency,
    payment_terms,
    is_active,
    created_at
FROM customers;

-- ---------------------------------------------------------------
-- v_sales_order_status : 취소 포함 전체 주문 현황 (상태 × 월)
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_sales_order_status AS
SELECT
    o.status,
    o.currency,
    DATE_FORMAT(o.order_date, '%Y-%m') AS order_month,
    COUNT(*)              AS order_count,
    SUM(o.total_amount)   AS total_amount
FROM sales_orders o
GROUP BY o.status, o.currency, DATE_FORMAT(o.order_date, '%Y-%m');
```

### 4.4 뷰로 답할 수 없는 것

다음 10개 테이블은 이번에 뷰로 만들지 않는다. 관련 질문은 "지원하지 않는다"고 거절한다.

`sales_quotes(견적)`, `sales_quote_lines`, `order_fulfillment(배송)`, `fulfillment_lines`,
`sales_reports(보고서)`, `sales_forecasts(예측)`, `price_lists(가격표)`, `credit_limits(여신한도)`,
`customer_contracts(계약)`, `discounts(할인)`

> 나중에 이 범위를 넓히려면 뷰를 추가하고 이 절과 7절(스키마 정보)을 같이 고친다.
> 뷰 없이 원본 테이블 권한을 직접 여는 방식은 쓰지 않는다(D-02 위반).

---

## 5. DB 계정과 권한

> 저장 위치: `database/sales/grants_reader.sql`

```sql
-- 주의: 앱 서버가 DB와 다른 컴퓨터/컨테이너에서 접속한다면
-- 'localhost' 부분을 실제 접속 host(또는 '%')로 바꿔야 한다.
CREATE USER IF NOT EXISTS 'chatbot_reader'@'localhost'
    IDENTIFIED BY '<.env의 MYSQL_READ_PASSWORD와 동일하게>';

-- 원본 테이블 권한은 주지 않는다. 뷰에만 SELECT를 허용한다.
GRANT SELECT ON sales.v_sales_order        TO 'chatbot_reader'@'localhost';
GRANT SELECT ON sales.v_sales_order_line   TO 'chatbot_reader'@'localhost';
GRANT SELECT ON sales.v_invoice            TO 'chatbot_reader'@'localhost';
GRANT SELECT ON sales.v_customer           TO 'chatbot_reader'@'localhost';
GRANT SELECT ON sales.v_sales_order_status TO 'chatbot_reader'@'localhost';

FLUSH PRIVILEGES;
```

MySQL 뷰는 "뷰를 만든 사람"의 권한으로 실행되는 게 기본값이라(SECURITY DEFINER 방식),
`chatbot_reader`가 원본 테이블 권한이 전혀 없어도 뷰는 정상 조회된다. 이 덕분에
**LLM이 아무리 이상한 SQL을 만들어도 원본 테이블에는 절대 닿을 수 없다.**

`.env`에 다음을 추가해야 한다 (지금은 없음 — 통합 담당과 협의 필요, 14.1절 참고).

```env
MYSQL_READ_HOST=localhost
MYSQL_READ_USER=chatbot_reader
MYSQL_READ_PASSWORD=
SALES_DB_DATABASE=sales
```

---

## 6. 처리 순서

```
질문
 │
 ├─(1) 입력 확인          빈 질문 / 500자 초과 → 거절
 │
 ├─(2) 범위 확인          판매 범위 밖 → 거절 (권한 안내)
 │                       뷰로 못 답하는 내용 → 거절 (되묻기)
 │                       기간이 애매함 → 거절 (되묻기)
 │
 ├─(3) 뷰 정보 + 오늘 날짜 + 지표 정의를 LLM에게 전달
 │
 ├─(4) LLM이 SQL 작성 (1회)
 │
 ├─(5) 코드로 1차 검사    SELECT 하나뿐인지 / 위험한 명령어 없는지 / 허용된 뷰만 쓰는지 / LIMIT 붙었는지
 │        │ 위반
 │        └─────────┐
 ├─(6) EXPLAIN 채점    │  실패
 │        │           │    │
 │        │           ▼    ▼
 │        │     (6a) 실패 이유를 LLM에게 다시 보여주고 1번만 재작성
 │        │           │
 │        │           └─→ 그래도 실패 → 오류로 종료
 │        ▼ 통과
 ├─(7) 조회 전용 계정으로 실제 실행     최대 10초
 │
 ├─(8) 결과 정리          0건이면 → "데이터 없음" + 보유 기간 안내
 │                       LLM용 최대 50행 / 화면용 전체로 나눔
 │
 └─(9) 결과 + 생성된 SQL 반환
```

### 6.1 "오늘"을 어떻게 계산하나 (D-07)

- LLM에게 프롬프트로 **"오늘 날짜는 ○○○입니다"를 그때그때 실제 서버 날짜로 넣어준다.**
  이 문서(SPEC)에는 그 예시로 특정 날짜를 고정해서 적지 않는다 — 문서를 나중에 다시 읽을 때
  이미 지난 날짜가 박혀 있으면 헷갈리기 때문이다. "실행하는 순간의 오늘 날짜를 자동으로 계산해
  넣는다"는 동작 규칙만 코드에 있으면 된다.
- SQL 안에는 `CURDATE()` 대신 **실제 날짜(예: `'2026-05-01'`)를 직접 써넣도록** LLM에게
  지시한다. 이유: 사용자에게 SQL을 보여주기로 했으니(D-14), "최근 3개월이 정확히 어느
  기간인지"가 SQL 문장만 봐도 눈에 보여야 한다.
- 우리가 가진 데이터의 시작일·마지막일(2025-01-16 ~ 2026-06-23)은 프로그램이 켜질 때 한 번
  조회해서 기억해둔다. ETL로 데이터를 새로 채워 넣은 뒤에는 프로그램을 다시 켜야 한다.

### 6.2 결과가 0건일 때

`행 수 == 0`은 오류가 아니라 **"조회 조건에 맞는 데이터가 실제로 없다"는 사실**이다.
그 사실을 숨기거나 얼버무리지 않고 이런 식으로 정직하게 안내한다.

```
조회 조건에 해당하는 판매 데이터가 없습니다.
현재 보유한 주문 데이터 기간은 2025-01-16 ~ 2026-06-23 입니다.
기간·조건을 다시 확인하신 뒤 질문해 주세요.
```

2.2절에 적었듯, 오늘 날짜 기준 "이번 달"·"최근 1개월" 질문은 **항상 0건이 나온다.** 이건
버그가 아니라 데이터가 그렇게 생겼기 때문인데, 이 안내가 없으면 사용자는 "매출이 0원인가?"로
오해한다. 핵심은 "왜 0건인지 시스템이 증명해 보이는 것"이 아니라 **"없다는 사실과, 무엇을
다시 확인해야 하는지를 명확히 알려주는 것"**이다.

---

## 7. LLM에게 알려주는 정보 (스키마 정보)

`mcp_servers/data_tools/sales/schema.py`를 통째로 새로 쓴다.

### 7.1 지금 코드의 문제

| 위치 | 문제 |
|---|---|
| [schema.py:17](mcp_servers/data_tools/sales/schema.py:17) | `stock_levels`, `inventory_items`, `inventory_transfers` — **실제로 적재되지 않은 테이블**을 LLM에게 있다고 알려주고 있음 |
| [schema.py:29](mcp_servers/data_tools/sales/schema.py:29) | 위 테이블의 칼럼 목록까지 적혀있음 |
| [schema.py:33](mcp_servers/data_tools/sales/schema.py:33) | `"매출": "sales_orders.total_amount 합계 또는 invoices.total_amount 합계"` — **"또는"이라고 적혀서 LLM이 마음대로 골라도 되는 것처럼 읽힘.** 정의를 못 박겠다는 목적과 정반대 |
| [schema.py:36](mcp_servers/data_tools/sales/schema.py:36) | `"재고": "stock_levels.quantity_available"` — 없는 테이블을 가리키고 있음 |

### 7.2 새로 만들 구조

```python
class SchemaResource(TypedDict):
    views: dict[str, ViewSpec]        # 뷰 이름 -> 칼럼·설명
    metrics: dict[str, MetricSpec]    # 지표 이름 -> 뷰·칼럼·계산방법·꼭 붙여야 하는 조건
    data_coverage: dict[str, str]     # {"min_order_date": ..., "max_order_date": ...}
    currency: str                     # "JOD"
    out_of_scope: list[str]           # 답할 수 없는 지표 이름 목록
```

("오늘 날짜"는 여기 저장해두는 값이 아니라 요청이 올 때마다 새로 계산해서 프롬프트에
끼워 넣는다. 6.1절 참고.)

### 7.3 지표 정의표

| 지표 | 어느 뷰 | 어느 칼럼 | 계산 방법 | 꼭 지킬 조건 |
|---|---|---|---|---|
| 매출 / 수주액 | `v_sales_order` | `order_amount` | 합계 | 뷰가 이미 취소·초안을 뺌 |
| 주문 건수 | `v_sales_order` | `sales_order_id` | 개수 | — |
| 품목별 매출 | `v_sales_order_line` | `line_total` | 합계 | `item_name`으로 묶기 |
| 판매 수량 | `v_sales_order_line` | `quantity` | 합계 | — |
| 청구액 | `v_invoice` | `invoice_amount` | 합계 | — |
| 미수금 | `v_invoice` | `outstanding_amount` | 합계 | — |
| 연체 미수금 | `v_invoice` | `outstanding_amount` | 합계 | `status = 'Overdue'`만 |
| 주문 현황(취소 포함) | `v_sales_order_status` | `order_count`, `total_amount` | — | — |

### 7.4 답할 수 없는 지표

왜 안 되는지 사용자에게 설명해줄 수 있도록 미리 목록으로 만들어둔다.

`영업이익`, `매출총이익`, `원가`, `마진율`, `재고`, `재고회전율`, `구매`, `발주`,
`공급업체`, `미지급금`, `견적`, `출하`, `배송`, `여신한도`, `할인정책`, `매출예측`

### 7.5 LLM에게 지시할 것 (SQL 생성 프롬프트 원칙)

1. 제공된 **뷰만** 쓸 것. 원본 테이블 이름을 쓰면 권한 오류가 난다고 알려줌
2. `SELECT` 문 하나만 만들 것. 설명·마크다운 없이 SQL만 출력
3. `LIMIT`을 꼭 붙일 것
4. 오늘 날짜와 데이터 보유 기간을 알려주고, "최근"·"이번 달" 같은 표현은 실제 날짜로
   바꿔 쓰게 함
5. 지표 정의를 임의로 바꾸지 말 것 (매출은 `order_amount`, 품목별은 `line_total`)
6. **상식으로 추측 금지** — 회사 이름·업종·국가는 데이터에 적힌 값만 사용
   (예: "제약회사니까 업종이 Pharma겠지"라고 짐작하면 안 됨. 2.2절 참고)
7. 통화는 JOD 하나뿐
8. **표가 지저분해지지 않게**: `SELECT *` 금지, 목록형 질문(기간 나열 등)은 칼럼 5~7개로
   제한, 기간을 나타낼 땐 뷰에 이미 있는 `order_month` 같은 문자열 칼럼을 사용
   (이 규칙은 표를 깔끔하게 보여주기 위한 것이고, 나중에 그래프 기능을 붙일 때도 그대로
   도움이 된다 — 14.2절 참고)

---

## 8. 도구 사용 방법 (입력/출력)

### 8.1 함수 두 개

`nodes.py`가 지금 `query_sales`를 직접 불러 쓰고 있어서(`app/agent/nodes.py`, 통합 담당
소유) **기존 함수 이름과 반환 형태는 그대로 유지**하고, MCP 규격에 맞춘 함수를 하나 더
추가한다.

```python
async def query_sales(question: str) -> list[dict[str, Any]]:
    """LangGraph에서 쓰는 함수. 기존과 같은 형태를 유지한다."""

async def query_sales_tool(question: str) -> dict[str, Any]:
    """MCP 서버에 등록할 함수. docs/interface.md의 공통 응답 형식으로 감싼다."""
```

### 8.2 입력

```json
{ "question": "2025년 4분기 고객별 매출 상위 5개" }
```

| 항목 | 형식 | 조건 |
|---|---|---|
| `question` | 문자열 | 필수, 1~500자, 빈 칸만 있으면 거절 |

### 8.3 출력 — `query_sales`가 돌려주는 것

> **주의**: 이전 버전 문서에서 `rows`를 "LLM용 50행", `rows_full`을 "화면용 전체"라고
> 반대로 적었었다. 하지만 화면 쪽 코드([app/web/chat.js](app/web/chat.js))가 이미
> `rows`라는 이름으로 전체 결과를 읽고 있어서, 그 이름을 바꾸지 않으려면 아래처럼
> **`rows`를 화면용(전체)**, **`rows_for_llm`을 LLM용(최대 50행)**으로 둬야 한다. 이렇게
> 하면 화면 쪽 코드를 한 줄도 안 고쳐도 된다.

```python
{
    "type": "database",
    "domain": "sales",
    "generated_sql": "SELECT ... FROM v_sales_order ...",
    "views_used": ["v_sales_order"],
    "row_count": 5,                  # 실제 조회된 전체 행 수
    "rows": [...],                   # 화면 표시용, 전체 (최대 200행)
    "rows_for_llm": [...],           # 답변 생성용, 최대 50행
    "truncated": false,              # row_count가 50 넘으면 true
    "elapsed_ms": 143.2,
    "retry_count": 0,                # EXPLAIN 실패로 다시 만든 횟수 (0 또는 1)
    "data_coverage": {"min_order_date": "2025-01-16", "max_order_date": "2026-06-23"},
    "currency": "JOD",
    "notice": null,                  # 빈 결과 안내 / 개인정보 관련 안내 문구
    "error": null,
    "error_code": null,
}
```

`nodes.py`의 `_build_tables` 함수는 `rows`·`generated_sql`·`domain`만 읽으므로 그대로
호환된다. `rows_for_llm`을 실제로 프롬프트에 쓰려면 `answer_synthesis` 쪽에서 한 줄
바꿔야 하는데, 이건 통합 담당과 협의가 필요하다(14.1절). 협의 전까지는 LLM도 그냥
`rows`(전체)를 보게 되는데, 우리 데이터가 원래 작아서(제일 큰 표가 192행) 당장 큰 문제는
아니다.

### 8.4 출력 — MCP 공통 형식 (`query_sales_tool`)

성공했을 때:

```json
{
  "status": "success",
  "domain": "sales",
  "message": null,
  "data": [ { "customer_name": "...", "revenue": 123456.78 } ],
  "sources": [
    { "type": "database", "domain": "sales",
      "views": ["v_sales_order"],
      "sql": "SELECT ...",
      "row_count": 5 }
  ],
  "metadata": {
    "generated_sql": "SELECT ...",
    "views_used": ["v_sales_order"],
    "row_count": 5,
    "truncated": false,
    "elapsed_ms": 143.2,
    "retry_count": 0,
    "currency": "JOD",
    "data_coverage": { "min_order_date": "2025-01-16", "max_order_date": "2026-06-23" }
  }
}
```

실패했을 때:

```json
{
  "status": "error",
  "domain": "sales",
  "message": "판매 데이터로는 영업이익을 계산할 수 없습니다. 원가 정보가 없기 때문입니다. 매출(수주액) 기준으로 안내해 드릴까요?",
  "error_code": "INVALID_INPUT",
  "data": [],
  "sources": [],
  "metadata": { "reason": "out_of_scope_metric", "requested_metric": "영업이익" }
}
```

---

## 9. 에러 처리

### 9.1 에러 코드 정리

| error_code | 언제 나오나 | 무슨 내용을 알려주나 | SQL을 만들었나 |
|---|---|---|---|
| `INVALID_INPUT` | 빈 질문 / 500자 초과 | 입력 형식 안내 | 안 만듦 |
| `INVALID_INPUT` | 판매 범위 밖 (구매·문서 등) | "판매 데이터 조회 권한 범위를 벗어났다" | 안 만듦 |
| `INVALID_INPUT` | 답할 수 없는 지표(영업이익 등) | 왜 안 되는지 + 대안 제시 | 안 만듦 |
| `INVALID_INPUT` | 기간·범위가 애매함 | 어떤 정보가 더 필요한지 되묻기 | 안 만듦 |
| `NO_RESULT` | SQL은 성공했는데 0건 | 보유 기간 안내(6.2) | 만듦 |
| `QUERY_ERROR` | 1차 검사에서 걸림 | "안전하지 않은 조회라 중단했다" | 만듦 |
| `QUERY_ERROR` | EXPLAIN 재작성해도 또 실패 | "SQL로 바꾸지 못했다" | 만듦 |
| `QUERY_ERROR` | 실행이 10초 넘게 걸림 | "조회 시간이 초과됐다" | 만듦 |
| `INTERNAL_ERROR` | OPENAI_API_KEY 없음 / LLM 호출 실패 | "일시적인 오류" | 안 만듦 |
| `INTERNAL_ERROR` | DB 연결 실패 / 설정 누락 | "일시적인 오류" | 해당 없음 |

`EVIDENCE_INSUFFICIENT`는 `app/agent/evidence_eval.py`(통합 담당 소유)가 쓰는 코드라
이 도구에서는 안 쓴다.

### 9.2 거절할 때 지킬 원칙 (D-08)

"답할 수 없습니다"로 끝내지 말고, **왜 안 되는지와 대안**을 같이 준다.

| 질문 | 답변 |
|---|---|
| "이번 달 영업이익 알려줘" | "영업이익은 원가 정보가 없어 계산할 수 없습니다. 매출(수주액) 기준으로는 안내해 드릴 수 있습니다." |
| "최근 매출 어때?" | "기간을 알려주시면 정확히 조회하겠습니다. 예: '2026년 상반기', '최근 3개월'. 참고로 데이터는 2026-06-23까지 있습니다." |
| "공급업체별 발주액" | "판매 데이터 조회 권한 범위를 벗어난 질문입니다. 구매 관련 조회는 담당 도구가 따로 있습니다." |
| "삼성 매출" | "고객 목록에서 '삼성'을 찾지 못했습니다. 정확한 고객명을 알려주시겠어요?" |

### 9.3 재시도 규칙 (D-09)

- EXPLAIN이 실패하면 **딱 1번만** 다시 만들어본다.
- 다시 만들 때는 실패했던 SQL과 MySQL이 뱉은 오류 메시지를 그대로 LLM에게 보여준다.
- 2번째도 실패하면 `QUERY_ERROR`로 끝낸다. 계속 반복하지 않는다.
- 몇 번 다시 만들었는지(`retry_count`)를 기록해서, 나중에 얼마나 자주 재시도가
  일어나는지 확인할 수 있게 한다.

---

## 10. SQL 안전장치 (`sql_guard.py`)

`mcp_servers/data_tools/sales/sql_guard.py`를 새로 만든다. 4절(뷰)과 5절(DB 권한)에
이은 **세 번째 방어선**이다.

### 10.1 검사 순서

| # | 무엇을 검사하나 | 걸리면 |
|---|---|---|
| 1 | 주석(`--`, `#`, `/* */`) 제거 후 검사 | 제거하고 계속 진행 |
| 2 | 세미콜론으로 나눴을 때 실행할 문장이 1개인지 | 거부 |
| 3 | `SELECT` 또는 `WITH`로 시작하는지 | 거부 |
| 4 | 위험한 명령어가 없는지: `INSERT UPDATE DELETE DROP ALTER CREATE TRUNCATE GRANT REVOKE REPLACE MERGE RENAME LOCK CALL HANDLER LOAD OUTFILE INFILE` | 거부 |
| 5 | `INTO`가 없는지 (파일로 결과를 빼돌리는 것 방지) | 거부 |
| 6 | 언급된 테이블이 허용된 뷰 5개 안에만 있는지 | 거부 |
| 7 | `LIMIT`이 없으면 `LIMIT 200`을 붙임. 200보다 크면 200으로 줄임 | 자동으로 고침 |
| 8 | `EXPLAIN <sql>`을 실행해서 통과하는지 확인 | 실패 시 1번 재작성 |

### 10.2 알아둬야 할 한계 하나

기존 [mysql.py:37-39](mcp_servers/data_tools/sales/mysql.py:37)의 검사 방식은 **문자열
안에 들어있는 단어까지 걸러낸다.** 예를 들어 `WHERE customer_name = 'Update Corp'`라는
정상적인 조건도 `UPDATE`라는 단어 때문에 거부당한다.

지금 고객 40곳 이름에는 이런 단어가 없어서 실제로 문제되진 않는다. 완전히 고치려면
SQL을 제대로 해석하는 도구(`sqlparse` 등)가 필요한데, 이번 범위에서는 **"멀쩡한 걸
거부하는 것"이 "위험한 걸 통과시키는 것"보다 훨씬 안전**하다고 보고 지금 방식을 유지한다.

---

## 11. 이 질문이 판매 담당 몫이 맞는지 확인하기 (D-15)

### 11.1 누가 처음 판단하나

어떤 도구를 쓸지("DATABASE" → `query_sales` 호출)는 `app/agent/nodes.py`(통합 담당)가
먼저 정한다. 그런데 이 도구도 **들어온 질문이 진짜 판매 범위가 맞는지 한 번 더 스스로
확인한다.**

### 11.2 판단 순서

```
1) 답할 수 없는 지표가 섞여있음    → 거절
2) 구매나 문서 관련 질문임이 확실   → 거절 (권한 안내)
3) 5개 뷰로 답할 수 있음          → 진행
4) 그 외 애매한 경우             → 거절 (되묻기)
```

### 11.3 "문서+DB 둘 다" 필요한 질문에서는

[docs/interface.md](docs/interface.md)에 "한쪽 도구가 실패해도 다른 쪽 결과가 있으면
부분 답변으로 처리한다"는 규칙이 있다. 그래서 이 도구가 거절해도 구매 쪽 결과가 있으면
전체 답변은 성립한다. 즉 **범위 밖 질문에 억지로 답하려 하지 않는 게 오히려 전체 품질을
높인다.**

---

## 12. 기록(로그) 남기기

한 줄에 이벤트 하나씩, [docs/ownership.md](docs/ownership.md)에 정해진 형식을 따른다.

```
2026-08-02T14:23:11+09:00 | INFO | mcp_servers.data_tools.sales.query | sql_generated | retry=0 views=v_sales_order
2026-08-02T14:23:11+09:00 | WARN | mcp_servers.data_tools.sales.sql_guard | explain_failed | reason=Unknown column 'revenue'
2026-08-02T14:23:12+09:00 | INFO | mcp_servers.data_tools.sales.query | query_executed | rows=5 elapsed_ms=143.2
2026-08-02T14:23:12+09:00 | INFO | mcp_servers.data_tools.sales.query | out_of_domain_rejected | reason=out_of_scope_metric
```

### 꼭 남겨야 하는 이벤트

`question_received`(질문 받음), `out_of_domain_rejected`(범위 밖 거절),
`sql_generated`(SQL 생성), `guard_rejected`(1차 검사 거부), `explain_failed`(EXPLAIN 실패),
`sql_retried`(재시도), `query_executed`(실행 완료), `query_empty`(빈 결과),
`query_error`(오류), `pii_notice_attached`(개인정보 안내 붙음)

### 어디에 저장하나

`logs/mcp_sales.log.txt` (새로 만들 것을 제안). [docs/ownership.md](docs/ownership.md)의
로그 표에 아직 이 항목이 없어서 통합 담당과 상의가 필요하다(14.1절).

---

## 13. 바뀌는 파일 목록

### 13.1 우리 몫 — 새로 만드는 파일

| 파일 | 내용 |
|---|---|
| `database/sales/views.sql` | 뷰 5개 생성 SQL (4.3절) |
| `database/sales/grants_reader.sql` | `chatbot_reader` 계정 생성 + 권한 부여 (5절) |
| `mcp_servers/data_tools/sales/sql_guard.py` | 1차 검사 + EXPLAIN 검증 (10절) |

### 13.2 우리 몫 — 고치는 파일

| 파일 | 뭘 바꾸나 |
|---|---|
| `mcp_servers/data_tools/sales/schema.py` | **통째로 교체.** 없는 테이블 3개 삭제, 뷰 기반 구조로 재작성 (7절) |
| `mcp_servers/data_tools/sales/text2sql.py` | `_FALLBACK_TEMPLATES` 등 하드코딩 부분 **완전히 삭제**(D-16). 프롬프트 새로 작성, 재시도 로직 추가 |
| `mcp_servers/data_tools/sales/mysql.py` | `explain()` 기능 추가. 검사 로직은 `sql_guard.py`로 옮김 |
| `mcp_servers/data_tools/sales/query.py` | 6절의 처리 순서 조립, 8.3절의 확장된 결과 형태 반환, `query_sales_tool` 추가 |
| `database/sales/README.md` | 뷰 만들기·권한 주기 실행 순서 추가 |

### 13.3 우리 몫 — 테스트

| 파일 | 내용 |
|---|---|
| `tests/unit/test_data_mcp.py` | 검사·거절·에러코드 단위 테스트 |
| `tests/fixtures/cases/text2sql_cases.jsonl` | 질문-정답 테스트 세트 (현재 빈 파일) |

---

## 14. 다른 파트와 상의할 것

### 14.1 지금 필요한 것 (표 관련 — 우선순위 순)

| # | 항목 | 상대방 | 내용 |
|---|---|---|---|
| C-01 | 구매 import 경로 정리 | 통합 담당 | 해결: Agent는 `MCPClient.purchase_query()`를 통해 정본 purchase Tool을 호출하며 앱 진입점 import로 경로를 검증한다. |
| C-02 | `.env`에 읽기 계정 정보 추가 | 통합 담당 | `MYSQL_READ_HOST/USER/PASSWORD`가 없어서 지금은 조회 자체가 안 됨 |
| C-03 | 사용자 입력·SQL·답변에 이스케이프 처리 없음 (보안) | 통합 담당 | [chat.js](app/web/chat.js)가 사용자 입력·DB 값·LLM 답변을 아무 처리 없이 그대로 화면에 꽂아넣는다. `<script>` 같은 걸 입력하면 그대로 실행됨. **SQL과 표를 더 많이 보여줄수록 이 문제가 커짐** — 시급 |
| C-04 | 두 번째 질문부터 이전 표·그래프가 깨짐 | 통합 담당 | [chat.js](app/web/chat.js)가 `innerHTML +=` 방식으로 채팅 내용을 계속 새로 그려서, 이미 그려진 화면이 통째로 다시 그려짐 |
| C-05 | 표가 옆으로 넘칠 때 스크롤이 안 됨 | 통합 담당 | 칼럼이 많은 질문(예: 기간 나열)에서 표가 화면 밖으로 삐져나갈 수 있음 |
| C-06 | 결과 0건일 때 "없다"는 안내 문구가 최종 답변에 정확히 전달되는지 확인 | 통합 담당 | 0건은 버그가 아니라 "그 조건의 데이터가 없다"는 사실이다(D-07 때문에 자주 발생). query_sales가 돌려주는 안내 문구(6.2절 — "데이터 없음 + 보유 기간 + 다시 확인해서 질문해달라")가 화면의 최종 답변에 그대로 반영되는지 확인 필요. 이 문구가 안 보이면 사용자가 "매출이 0원"으로 오해할 수 있음 |
| C-07 | 숫자·통화 표기가 안 맞춰져 있음 | 통합 담당 | 표에는 `6165466.5`처럼 그대로 찍히는데 답변 문장에는 "약 616만 JOD"처럼 다르게 나와서 같은 값인데 달라 보임 |
| C-08 | 화면에 전체 행 보여주기 반영 | 통합 담당 | D-13(화면 전체) 구현하려면 8.3절의 `rows_for_llm` 분리를 `answer_synthesis`가 실제로 써야 함 |
| C-09 | 조회 캐시가 데이터 갱신을 못 따라감 | 통합 담당 | [app/cache/key.py:20](app/cache/key.py:20)이 캐시 키 재료로 쓰는 `database_freshness_bucket` 값을 아무도 채워주지 않아서 항상 비어있음. ETL로 데이터를 새로 넣어도 최대 5분간 예전 표가 그대로 나올 수 있음 |
| C-10 | `metadata` 항목 확장 | 통합 담당 | [docs/interface.md](docs/interface.md)의 `metadata`에 `views_used`, `data_coverage`, `retry_count` 추가 반영 필요 |
| C-11 | Data MCP 중복 패키지 정리 | 통합 담당 | 해결: `data_tools/`를 유일한 정본으로 확정하고 미등록 설계 스켈레톤을 제거했다. |

### 14.2 나중에 처리 (그래프/차트 — 지금은 보류)

**채팅창에 막대그래프를 그리는 기능은 이번 스펙 범위에서 뺀다.** 아래는 나중에 그래프
작업을 다시 시작할 때 참고할 내용이다.

| 항목 | 내용 |
|---|---|
| 그래프 그리는 코드 위치 | [chat.js:41-70](app/web/chat.js:41) `renderChartPlaceholder`, `drawChart` — Chart.js 라이브러리 사용 |
| 인터넷이 막힌 곳에서는 그래프가 조용히 안 뜸 | 지금 [index.html](app/web/index.html)이 Chart.js를 인터넷(CDN)에서 받아오는데, 네트워크가 막혀 있으면 에러도 없이 그냥 그래프만 안 나옴. 나중에 파일을 프로젝트 안에 내려받아 두는 걸 권장 |
| "그래프를 그릴 수 있는 표"의 조건 | 지금 코드는 "문자열 칼럼 하나 + 숫자 칼럼 하나"가 있어야 그래프를 그림. 7.5절의 SQL 작성 규칙(칼럼 제한, `order_month` 활용)을 이미 지켜두면, 나중에 그래프 기능을 켤 때 손댈 게 거의 없어짐 |

---

## 15. 테스트로 확인할 것

### 15.1 단위 테스트 (LLM·DB는 가짜로 대체)

- [ ] 빈 질문·500자 초과 → `INVALID_INPUT`
- [ ] "영업이익"처럼 답할 수 없는 지표 → SQL 안 만들고 `INVALID_INPUT`, 대안 포함
- [ ] "공급업체 발주"처럼 구매 관련 질문 → `INVALID_INPUT`, 권한 안내 포함
- [ ] 1차 검사: 문장 여러 개 / SELECT 아님 / 위험 명령어 / 허용 안 된 테이블 → 전부 거부
- [ ] 1차 검사: `LIMIT` 없는 SQL에 `LIMIT 200` 자동으로 붙음
- [ ] 1차 검사: `LIMIT 5000`은 `LIMIT 200`으로 줄어듦
- [ ] EXPLAIN 실패 → 1번 재작성 시도, `retry_count=1` 기록됨
- [ ] EXPLAIN이 2번 다 실패 → `QUERY_ERROR`
- [ ] 결과 0건 → `NO_RESULT` + 보유 기간 안내 문구 포함
- [ ] 결과가 50행 넘으면 → `rows`는 전체, `rows_for_llm`은 50행, `truncated=true`
- [ ] 숫자(Decimal)·날짜 값이 화면에 표시 가능한 형태로 잘 바뀜
- [ ] `OPENAI_API_KEY`가 없으면 → `INTERNAL_ERROR` (예전처럼 고정 SQL이 실행되면 안 됨)

### 15.2 뷰 검증 (진짜 DB로 확인)

- [ ] `SELECT SUM(order_amount) FROM v_sales_order` = **6,165,466.50**
- [ ] `v_sales_order`에 `status`가 Cancelled·Draft인 행이 0건
- [ ] `v_sales_order_line`의 행 수가 실제 상세 항목 합계와 일치
- [ ] `v_customer`에 이메일·세금번호·전화번호·주소 칼럼이 없음
- [ ] `chatbot_reader` 계정으로 `SELECT * FROM sales_orders` 시도 → **권한 오류 발생**
- [ ] `chatbot_reader` 계정으로 `SELECT * FROM v_sales_order` → 정상 조회됨

### 15.3 질문-정답 테스트 세트 (`text2sql_cases.jsonl`)

최소 12개를 만든다. 각각 "질문", "써야 할 뷰", "예상 에러코드", "SQL에 꼭 있어야 할 부분",
"SQL에 있으면 안 되는 부분"을 적는다.

| 유형 | 최소 개수 | 예시 |
|---|---:|---|
| 기간별 집계 | 2 | "2025년 4분기 매출" |
| 고객별 집계 | 2 | "매출 상위 5개 고객" |
| 품목별 집계 | 2 | "가장 많이 팔린 품목 10개" → `v_sales_order_line` 사용, `order_amount`는 쓰면 안 됨 |
| 미수금 | 1 | "연체된 미수금 총액" |
| 주문 현황 | 1 | "취소된 주문 몇 건이야" → `v_sales_order_status` |
| 거절 — 답할 수 없는 지표 | 2 | "영업이익", "재고" |
| 거절 — 다른 도메인 | 1 | "공급업체별 발주액" |
| 빈 결과 | 1 | "2026년 8월 매출" → `NO_RESULT` + 보유 기간 안내 |

### 15.4 완료로 볼 수 있는 기준

1. 위 단위 테스트 전부 통과 (`pytest tests/unit/test_data_mcp.py`)
2. 15.2 뷰 검증 6개 항목을 진짜 DB에서 직접 확인
3. 질문-정답 테스트 세트 12개 중 **10개 이상** 통과
4. `_FALLBACK_TEMPLATES` 관련 코드가 저장소에 하나도 안 남아있음 (검색으로 확인)
5. 작업 결과를 `docs/report/`에, 진행 기록을 `docs/history/`에 남김

---

## 16. 알아둬야 할 한계와 위험

| # | 내용 | 영향 | 대응 |
|---|---|---|---|
| R-01 | 오늘 기준 "이번 달"·"최근 1개월"은 항상 0건 | 시연 중 빈 답변이 나올 수 있음 | 보유 기간 안내(6.2). 시연 질문은 2026-06 이전 기간으로 준비 |
| R-02 | 품목을 구분하는 별도 코드가 없고 문자열(`description`)만 있음 | 같은 품목이 다르게 적혀 있으면 집계가 나뉨 | 지금 규모(192건)에서는 실제 위험 낮음. 표기가 다른 경우 발견되면 별도 기록 |
| R-03 | 가짜 데이터라 업종·국가가 실제와 안 맞음 | "제약회사 매출" 같은 상식 기반 질문은 실패함 | 프롬프트에서 상식 추측 금지(7.5-6). 테스트 세트에도 이런 질문은 넣지 않음 |
| R-04 | 위험 단어 검사가 문자열 안의 단어까지 걸러냄 | 정상 질문이 거부될 수 있음 | 10.2절에 기록. 거부되는 게 통과되는 것보다 안전하다고 판단 |
| R-05 | 뷰가 10개 테이블은 다루지 않음 | 견적·배송·여신·예측 관련 질문 불가 | 4.4절에 명시하고 거절 |
| R-06 | 데이터가 적어서(주문 70건) 집계 결과의 의미가 약할 수 있음 | "상위 5개 고객" 같은 순위가 크게 의미 없을 수 있음 | 데이터 자체의 한계. 시연 시 언급 |
| R-07 | 회사 1개·통화 1개를 전제로 설계함 | 나중에 데이터가 여러 회사로 늘어나면 다시 봐야 함 | 2.2절에 근거를 남겨둠. 뷰 수정으로 대응 가능 |

---

## 17. 하드코딩/임시방편 사용 기록

> [RULE.md](RULE.md) 3항에 따라 남기는 필수 기록.

### 이번에 **없애는** 기존 하드코딩

| 대상 | 위치 | 왜 없애나 |
|---|---|---|
| `_FALLBACK_TEMPLATES` | [sales/text2sql.py:14-40](mcp_servers/data_tools/sales/text2sql.py:14) | `OPENAI_API_KEY`가 없을 때 **질문 내용과 상관없이** 키워드만 보고 고정 SQL을 실행함. 기간 조건이 없는 SQL이 "2025년 3분기 매출"이라는 질문에 전체 기간 합계를 돌려줘도 에러가 안 나서, 사용자가 틀린 답인 줄 알 방법이 없음. 우리가 만든 시맨틱 레이어와 EXPLAIN 검증을 전부 우회함 |
| `_DEFAULT_FALLBACK_SQL` | [sales/text2sql.py:42](mcp_servers/data_tools/sales/text2sql.py:42) | 위와 같은 이유 |
| 없는 테이블 참조 | [sales/schema.py:17,29,36](mcp_servers/data_tools/sales/schema.py:17), [sales/text2sql.py:34](mcp_servers/data_tools/sales/text2sql.py:34) | `stock_levels`·`inventory_items`·`inventory_transfers`는 ETL로 넣은 적 없음. LLM에게 없는 테이블이 있다고 알려주고 있었음 |

### 이번에 **의도적으로** 넣는 고정값

아래는 임시방편이 아니라 **일부러 고정해둔 것**이다.

| 고정값 | 위치 | 왜 고정하나 |
|---|---|---|
| `status NOT IN ('Cancelled','Draft')` | 뷰 정의 | D-04. 업무 규칙을 LLM이 못 바꾸게 하는 게 목적이라 뷰에 못 박아둠 |
| `LIMIT 200` 상한 | `sql_guard` | 결과가 너무 많이 나오는 걸 막음. 제일 큰 표도 192행이라 실제로 잘려나가는 데이터는 없음 |
| LLM에게는 50행만 | `query.py` | D-13. 프롬프트가 너무 길어지지 않게 |
| 실행 최대 10초 | `mysql.py` | 너무 오래 걸리는 조회를 막음 |
| 재시도는 최대 1번 | `query.py` | D-09. 무한 반복과 비용 폭증 방지 |

### 아직 안 고친 것

- 위험 단어 검사가 문자열 안의 단어까지 걸러내는 문제(R-04). SQL을 제대로 해석하는
  도구가 필요한데, 이번 범위에서는 다루지 않기로 함.

---

## 18. 구현 순서 제안

RULE.md 2항(작은 단위로 나눠서, 단계마다 커밋)에 따른 순서다.

| 단계 | 할 일 | 확인 방법 |
|---|---|---|
| 1 | `.env`에 읽기 계정 정보 추가 (14.1절 C-02 상의) | 설정이 정상적으로 읽힘 |
| 2 | `database/sales/views.sql` 작성·실행 | 15.2절 뷰 검증 4개 항목 |
| 3 | `database/sales/grants_reader.sql` 작성·실행 | 15.2절 권한 검증 2개 항목 |
| 4 | `schema.py` 통째로 교체 | 뷰 5개만 있고 없는 테이블은 0개 |
| 5 | `sql_guard.py` 새로 작성 | 검사 단위 테스트 통과 |
| 6 | `text2sql.py` 다시 작성 (하드코딩 삭제) | 검색해서 하드코딩 코드 0건 확인 |
| 7 | `mysql.py`에 `explain()` 추가 | EXPLAIN 실패 감지 테스트 |
| 8 | `query.py` 전체 조립 | 전체 단위 테스트 통과 |
| 9 | 질문-정답 테스트 세트 작성·실행 | 12개 중 10개 이상 통과 |
| 10 | `docs/report/`·`docs/history/` 기록 | RULE.md 2·5항 |

> RULE.md 5항에 따라, 구현 시작 전에 `docs/plan/query-sales-text2sql.md`를 먼저 만든다.
