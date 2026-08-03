# SPEC — `query_sales` MCP Tool (판매 도메인 Text2SQL)

- **문서 상태**: 구현 완료 (1~8단계 전부 커밋·검증됨). 이 문서는 여전히 설계 근거로 유효하며,
  실제 구현 후 값이 바뀐 부분(데이터 규모·계정명 등)은 최신 실측치로 갱신했다.
  세션 이력은 [docs/progress/sales/2026-08-02.md](docs/progress/sales/2026-08-02.md),
  결과 리포트는 [docs/report/query-sales-text2sql.md](docs/report/query-sales-text2sql.md) 참고.
- **최초 작성**: 2026-08-01 · **개정**: 2026-08-02 (구현 완료 반영)
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

`.env`의 쓰기 계정으로 sales DB를 직접 들여다본 값이다. **이 수치는 2026-08-04 기준 실측이며,
원본 1.4년치(2025-01~2026-06) 데이터에 4년치를 추가로 생성해 5년치·800건으로 확장한 뒤의
값이다** (합성 데이터 확장 배경은 [docs/plan/sales-synthetic-data-5y.md](docs/plan/sales-synthetic-data-5y.md)
참고). 원본 70건은 값 하나도 안 바뀌고 그대로 포함돼 있다.

### 2.1 테이블 14개와 각각 몇 건씩 들어있는지

| 테이블 | 행 수 | 테이블 | 행 수 |
|---|---:|---|---:|
| customers (고객) | 130 | sales_orders (주문) | 800 |
| sales_order_lines (주문 상세) | 2,207 | invoices (청구서) | 604 |
| sales_quotes (견적) | 686 | sales_quote_lines (견적 상세) | 1,908 |
| order_fulfillment (배송) | 637 | fulfillment_lines (배송 상세) | 1,760 |
| sales_reports (보고서) | 206 | sales_forecasts (예측) | 457 |
| price_lists (가격표) | 130 | credit_limits (여신한도) | 130 |
| customer_contracts (계약) | 83 | discounts (할인) | 39 |

### 2.2 설계에 직접 영향을 준 사실들

| 확인한 사실 | 왜 중요한가 |
|---|---|
| **회사가 딱 1개뿐** | `company_id`가 모든 데이터에서 값이 `1` 하나뿐. "여러 회사 데이터가 섞일 위험"이 아예 없어서, 신경 쓸 필요가 사라짐 |
| **데이터 기간이 2021-08-18 ~ 2026-08-04로 넓어짐** | 5년치라 "연도별·월별 추이" 질문이 처음으로 의미를 갖게 됐다. "이번 달" 질문도 더 이상 항상 0건이 아니다(2026년 8월에 실제로 2건의 유효 주문이 있음) — 예전 SPEC의 "R-01: 이번 달은 항상 0건" 리스크가 이번 확장으로 해소됨 |
| **통화가 요르단 디나르(JOD) 하나뿐** | 원화로 착각하지 않게 답변에 단위를 꼭 붙여야 함 |
| **취소·초안 상태 주문이 섞여있음** | Cancelled 31건(1,064,687.21) + Draft 25건(278,937.27) = 전체의 약 4.8%. 매출 계산에 넣고 빼고에 따라 답이 달라짐 |
| **품목 이름을 담은 별도 테이블이 없음** | 상품명은 `sales_order_lines.description` 칸에만 적혀 있음(86개 품목명, 원본과 동일 카탈로그 재사용). "품목별 매출"은 이 칸으로 묶어서 계산해야 함 |
| **주문 하나에 상세 항목이 평균 2.76개** | 주문 금액과 상세 항목을 그냥 JOIN해서 더하면 뻥튀기(fan-out)됨 |
| **가짜 데이터라 상식과 안 맞는 값이 있음** | 예: 제약회사인데 업종이 '에너지'로, 통신사인데 '은행'으로 적혀있음. LLM이 "제약회사니까 당연히 이 업종이겠지" 하고 짐작하면 틀림 |
| **연도별 매출은 감소, 주문 건수는 증가하는 추세로 설계됨** | 5년치 확장 시 의도적으로 반영한 사업 서사(건당 단가는 작아지고 거래는 잦아짐). "작년 대비 매출 증감" 같은 질문에 실제로 의미 있는 답이 나온다 |

### 2.3 주문 상태별 현황

| 상태 | 건수 | 합계(JOD) | 매출 계산에 포함? |
|---|---:|---:|---|
| Invoiced | 274 | 11,757,556.06 | 포함 |
| Delivered | 172 | 5,574,955.31 | 포함 |
| Shipped | 160 | 4,603,072.26 | 포함 |
| Confirmed | 107 | 3,527,473.45 | 포함 |
| Partially Shipped | 31 | 1,355,098.23 | 포함 |
| **Cancelled(취소)** | 31 | 1,064,687.21 | **제외** |
| **Draft(초안)** | 25 | 278,937.27 | **제외** |
| **합계(유효 매출)** | 744 | **26,818,155.31** | |

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

## 5. DB 계정과 권한 (구현 완료)

> 저장 위치: `database/sales/grants_reader.sql`. 계정명은 초안 단계의 `chatbot_reader`
> 대신 실제로는 **`sales_reader`**로 만들었다 — 팀 전체가 3계정 모델(admin/sales/purchase)로
> 합의하면서 도메인이 드러나는 이름으로 통일했다.

```sql
CREATE USER IF NOT EXISTS 'sales_reader'@'%'
    IDENTIFIED BY '<.env의 SALES_READ_PASSWORD와 동일하게>';

-- 원본 테이블 권한은 주지 않는다. 뷰에만 SELECT를 허용한다.
GRANT SELECT ON `sales`.`v_sales_order`        TO 'sales_reader'@'%';
GRANT SELECT ON `sales`.`v_sales_order_line`   TO 'sales_reader'@'%';
GRANT SELECT ON `sales`.`v_invoice`            TO 'sales_reader'@'%';
GRANT SELECT ON `sales`.`v_customer`           TO 'sales_reader'@'%';
GRANT SELECT ON `sales`.`v_sales_order_status` TO 'sales_reader'@'%';

FLUSH PRIVILEGES;
```

MySQL 뷰는 "뷰를 만든 사람"의 권한으로 실행되는 게 기본값이라(SECURITY DEFINER 방식),
`sales_reader`가 원본 테이블 권한이 전혀 없어도 뷰는 정상 조회된다. 이 덕분에
**LLM이 아무리 이상한 SQL을 만들어도 원본 테이블에는 절대 닿을 수 없다.**

**실제로 만들면서 알게 된 것 2가지 (초안 단계에는 없던 내용):**

1. **`CREATE USER`는 admin(`JangGGo`) 계정으로 못 만든다.** `JangGGo`는 `sales.*`에 대한
   `ALL PRIVILEGES`는 있지만, 그건 데이터베이스 단위 권한이고 `CREATE USER`는 전역
   권한이라 별개다. 실제로는 `root` 계정으로 이 스크립트를 실행해야 했다.
2. **`EXPLAIN`은 `sales_reader`로 못 돌린다.** 실제 `SELECT`는 SECURITY DEFINER 덕분에
   원본 테이블 권한 없이도 되지만, `EXPLAIN`은 MySQL이 호출 계정에게 원본 테이블 권한을
   직접 요구한다(`1345: lacking privileges for underlying table`). `EXPLAIN`은 실행
   계획만 보여주고 실제 행 데이터는 안 주므로, `EXPLAIN` 전용으로만 admin 계정을 쓰고
   실제 데이터 조회는 계속 `sales_reader`로 제한했다(`mysql.py`의
   `ExplainOnlyMySQLClient` 참고, 6·10절).

`.env`에는 다음을 추가했다(3계정 모델에 맞춰 `MYSQL_READ_*`를 그대로 두고 sales 전용
값을 별도로 추가 — purchase에 영향 없음, 14.1절 C-02 참고).

```env
SALES_DB_HOST=127.0.0.1
SALES_DB_USER=JangGGo          # admin, ETL 쓰기용 (기존)
SALES_DB_PASSWORD=
SALES_DB_DATABASE=sales

SALES_READ_USER=sales_reader   # 챗봇 조회 전용 (신규)
SALES_READ_PASSWORD=
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
- 우리가 가진 데이터의 시작일·마지막일(실측 2021-08-18 ~ 2026-08-04, 2절 참고)은
  프로그램이 켜질 때 한 번 조회해서 기억해둔다. ETL로 데이터를 새로 채워 넣은 뒤에는
  프로그램을 다시 켜야 한다.

### 6.2 결과가 0건일 때

`행 수 == 0`은 오류가 아니라 **"조회 조건에 맞는 데이터가 실제로 없다"는 사실**이다.
그 사실을 숨기거나 얼버무리지 않고 이런 식으로 정직하게 안내한다.

```
조회 조건에 해당하는 판매 데이터가 없습니다.
현재 보유한 주문 데이터 기간은 2021-08-18 ~ 2026-08-04 입니다.
기간·조건을 다시 확인하신 뒤 질문해 주세요.
```

데이터를 5년치(2021-08-18~2026-08-04)로 확장하면서, 예전에는 "이번 달"·"최근 1개월"
질문이 항상 0건이었던 게(원본은 2026-06-23까지만 있었음) 이제는 그렇지 않다 — 실측 결과
2026년 8월에도 유효 주문이 이미 2건 있다(2절 참고). 그래도 0건이 나오는 경우(예: 아직
존재하지 않는 미래 기간, 데이터가 없는 특정 조합)는 여전히 생기므로 이 안내는 그대로
유지한다. 핵심은 "왜 0건인지 시스템이 증명해 보이는 것"이 아니라 **"없다는 사실과, 무엇을
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

## 8. 도구 사용 방법 (입력/출력) — 실제 구현 반영

> 이 절의 초안(구현 착수 전 버전)은 우리가 MCP 공통 envelope 변환 함수까지 직접 만든다고
> 가정했다. 실제로는 병합 과정에서 통합팀이 그 역할을 `mcp_servers/data_tools/server.py`의
> `execute_data_tool`/`_execute_query`로 이미 구현해뒀다는 걸 확인했다 — 그래서 우리는
> `query_sales` 하나만 기존 계약대로 만들면 되고, 별도 `query_sales_tool` 래퍼는 필요
> 없어졌다. 8.3·8.4절을 실제 반환값 기준으로 다시 썼다.

### 8.1 함수

```python
async def query_sales(question: str) -> list[dict[str, Any]]:
    """LangGraph와 MCP server가 함께 쓰는 함수. 원소 1개 리스트를 반환한다."""
```

`app/agent/nodes.py`(LangGraph 경로)와 `mcp_servers/data_tools/server.py`(MCP 경로)
양쪽 모두 이 함수 하나를 그대로 호출한다.

### 8.2 입력

```json
{ "question": "2025년 4분기 고객별 매출 상위 5개" }
```

| 항목 | 형식 | 조건 |
|---|---|---|
| `question` | 문자열 | 필수, 1~500자, 빈 칸만 있으면 거절 |

### 8.3 출력 — `query_sales`가 실제로 돌려주는 것

```python
{
    "type": "database",
    "domain": "sales",
    "generated_sql": "SELECT ... FROM v_sales_order ...",
    "row_count": 5,
    "rows": [...],                   # 화면·LLM 공용, 최대 200행(LIMIT 상한)
    "elapsed_ms": 143.2,
    "metadata": {
        "views_used": ["v_sales_order"],
        "data_coverage": {"min_order_date": "2021-08-18", "max_order_date": "2026-08-04"},
        "retry_count": 0,             # EXPLAIN 실패로 다시 만든 횟수 (0 또는 1)
        "currency": "JOD",
        "truncated": false,           # row_count가 200(LIMIT 상한)에 닿으면 true
        "chart_hint": "bar",          # "bar" | "line" | null — 04_chart_spec.md 참고
    },
}
```

**초안과 달라진 부분**: `rows`를 LLM용(50행)·화면용(전체)으로 나누는 `rows_for_llm`
필드는 만들지 않았다. `mcp_servers/data_tools/server.py`의 공통 envelope가 `rows`
하나만 그대로 `data`에 실어 보내는 구조로 이미 고정돼 있어서(통합 담당 소유, 8.4절 참고),
지금은 화면과 LLM이 같은 `rows`(최대 200행)를 본다. 우리 데이터가 아직 작아서(제일 큰
표도 2,207행 중 `LIMIT`으로 잘라낸 200행) 당장 문제는 아니지만, `metadata`에
`views_used`·`data_coverage`·`retry_count`·`currency`·`truncated`·`chart_hint`는
전부 채워서 반환해뒀다 — `server.py`가 지금은 이 필드들을 버리지만(8.4절), 확장 요청이
받아들여지면 한 줄만 바꿔서 쓸 수 있다.

### 8.4 출력 — MCP 공통 형식 (통합 담당의 `mcp_servers/data_tools/server.py`가 조립)

이 형식은 우리가 만드는 게 아니라 통합 담당이 소유한 공통 envelope다. 실제로 무엇이
나가는지 정확히 알아야 우리 쪽 메시지·metadata가 어디까지 전달되는지 알 수 있어서 여기
남겨둔다.

성공했을 때 (`server.py`의 `_execute_query`가 만드는 실제 모양):

```json
{
  "status": "success",
  "domain": "sales",
  "message": null,
  "data": [ { "customer_name": "...", "revenue": 123456.78 } ],
  "sources": [],
  "metadata": {
    "generated_sql": "SELECT ...",
    "row_count": 5,
    "elapsed_ms": 143.2
  }
}
```

**주의**: `sources`는 항상 빈 배열이고, `metadata`도 `generated_sql`·`row_count`·
`elapsed_ms` 3개만 통과한다. 우리가 8.3절에서 반환한 `views_used`·`data_coverage`·
`currency`·`chart_hint` 등은 **지금은 여기서 버려진다.** 이건 설계 실수가 아니라
D-1 결정(현재 envelope 제약 안에서 구현하고, 확장은 통합팀에 요청만 한다)에 따른
의도된 결과다 — 요청 내역은 [03_cross_team_requests.md](docs/team_share/03_cross_team_requests.md)
참고.

실패했을 때 — 우리가 SPEC 9.2절에서 설계한 "왜 못 답하는지 + 대안" 문장은 **아직 여기까지
전달되지 않는다.** `query_sales`가 범위 밖 질문에 `rows=[]`를 돌려주면, `server.py`가
질문 내용과 무관하게 고정 메시지로 바꾼다:

```json
{
  "status": "error",
  "domain": "sales",
  "message": "조회 가능한 결과가 없습니다.",
  "error_code": "NO_RESULT",
  "data": [],
  "sources": [],
  "metadata": {}
}
```

("영업이익" 질문이든 "재고" 질문이든 이유를 구분해주는 필드가 없으므로, 사용자는 같은
고정 메시지만 보게 된다. `server.py`의 `_error_envelope`는 `metadata`를 항상 빈 객체로
만든다 — `query_sales`가 `_empty_evidence`에 채워둔 `views_used`·`data_coverage` 등은
성공(`status: "success"`) 경로에서만 살아남고, 그마저도 `generated_sql`·`row_count`·
`elapsed_ms` 3개로 줄어든다. 오류 경로에서는 아예 전달되지 않는다.)

---

## 9. 에러 처리 — 실제 구현 반영

> 초안(9.1·9.2)은 `query_sales`가 거절 사유별로 다른 `error_code`와 안내 문장을 직접
> 고른다고 가정했다. 실제로는 `server.py`(8.4절)가 `query_sales`의 결과를 딱 두 가지로만
> 본다 — **`rows`가 비었나, 안 비었나** — 그래서 거절 사유가 뭐든 사용자에게는 같은 고정
> 문장만 간다. 아래는 `mcp_servers/data_tools/server.py::_execute_query`를 그대로 읽은
> 실제 동작이다.

### 9.1 에러 코드 정리 (실제)

| error_code | 언제 나오나 | 무슨 내용을 알려주나 | SQL을 만들었나 |
|---|---|---|---|
| `INVALID_INPUT` | 질문이 공백뿐이라 `server.py`가 `query_sales`를 아예 부르기 전에 걸러냄 | "질문이 비어 있습니다." (고정) | 안 만듦 |
| `NO_RESULT` | `query_sales`가 `rows=[]`를 반환한 모든 경우 — 500자 초과, 범위 밖(구매·문서), 답할 수 없는 지표(영업이익 등), 조건에 맞는 행이 실제로 0건인 경우를 **전부 포함** | "조회 가능한 결과가 없습니다." (고정, 사유 구분 없음) | 안 만들었거나(범위 밖) 만들어서 실행했지만 0건 |
| `QUERY_ERROR` | `query_sales` 호출 중 예외 발생 — EXPLAIN 재작성까지 실패, 실행 타임아웃(10초, `MAX_EXECUTION_TIME`), DB 연결 실패, 그 외 처리되지 않은 예외 | "업무 데이터 조회에 실패했습니다." (고정, 원인 구분 없음) | 경우에 따라 다름 |
| `INTERNAL_ERROR` | `query_sales`가 반환한 evidence의 모양이 계약과 다름(원소 개수≠1, `domain` 불일치, `rows`가 list가 아님 등) | "조회 결과 형식이 올바르지 않습니다." (고정) | 해당 없음 — 정상 동작에서는 발생하지 않아야 함 |

**초안과 달라진 부분**: 초안은 "판매 범위 밖"·"답할 수 없는 지표"·"기간 애매함"을 서로
다른 안내 문장의 `INVALID_INPUT`으로 나눴지만, 실제로는 이 셋 다 `query_sales`가
`rows=[]`를 반환하는 경로(`_empty_evidence`, 8.3절)를 타고 **`NO_RESULT`로 합쳐진다.**
"질문이 500자를 넘음"도 같은 `_empty_evidence` 경로라 `NO_RESULT`가 된다(초안엔
`INVALID_INPUT`으로 적혀 있었음). 10초 타임아웃 자체는 실제로 구현돼 있다
([mysql.py:36,77](mcp_servers/data_tools/sales/mysql.py:36) `SET SESSION
MAX_EXECUTION_TIME=10000`) — 다만 초과 시 pymysql 예외가 그대로 올라가 다른 모든
예외와 똑같이 `QUERY_ERROR`+고정 문장으로 처리될 뿐, "조회 시간이 초과됐다"는 전용
메시지는 없다. `EVIDENCE_INSUFFICIENT`는
`app/agent/evidence_eval.py`(통합 담당 소유)가 쓰는 코드라 이 도구에서는 여전히 안 쓴다.

### 9.2 거절 원칙(D-08)이 실제로는 전달되지 않는다는 것

초안은 "답할 수 없습니다"로 끝내지 말고 **왜 안 되는지와 대안**을 같이 주자는 원칙(D-08)
아래 질문별 맞춤 문장을 설계했었다. 이 문장들은 `mcp_servers/data_tools/sales/query.py`
어디에도 존재하지 않는다 — `_empty_evidence`는 이유를 가리지 않고 그냥 `rows=[]`만
반환하고, 그 위의 `server.py`가 고정 문장 "조회 가능한 결과가 없습니다."로 덮어쓴다.
즉 아래 표는 **"우리가 원래 하고 싶었던 것"**이며, 지금 사용자가 실제로 받는 문장은 전부
"조회 가능한 결과가 없습니다." 하나다.

| 질문 | 원래 의도했던 답변 (현재 미전달) |
|---|---|
| "이번 달 영업이익 알려줘" | "영업이익은 원가 정보가 없어 계산할 수 없습니다. 매출(수주액) 기준으로는 안내해 드릴 수 있습니다." |
| "최근 매출 어때?" | "기간을 알려주시면 정확히 조회하겠습니다. 예: '2026년 상반기', '최근 3개월'. 참고로 데이터는 2021-08-18 ~ 2026-08-04까지 있습니다." |
| "공급업체별 발주액" | "판매 데이터 조회 권한 범위를 벗어난 질문입니다. 구매 관련 조회는 담당 도구가 따로 있습니다." |
| "삼성 매출" | "고객 목록에서 '삼성'을 찾지 못했습니다. 정확한 고객명을 알려주시겠어요?" |

이 문장들을 실제로 전달하려면 `server.py`가 `query_sales`의 `metadata`(또는 새 필드)를
읽어 `message`에 반영하도록 확장해야 한다 — D-1 결정에 따라 이번 범위에서는 구현하지
않고 [03_cross_team_requests.md](docs/team_share/03_cross_team_requests.md)에 요청만
남긴다.

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

## 13. 바뀌는 파일 목록 — 실제 구현 반영

### 13.1 우리 몫 — 새로 만든 파일

| 파일 | 내용 |
|---|---|
| `database/sales/views.sql` | 뷰 5개 생성 SQL (4.3절) |
| `database/sales/grants_reader.sql` | `sales_reader` 계정 생성 + 뷰 5개에만 `SELECT` 권한 부여 (5절) |
| `mcp_servers/data_tools/sales/sql_guard.py` | 1차 검사(단일 SELECT/WITH, 금지 키워드, 뷰 화이트리스트, `LIMIT` 자동 부착·상한) (10절) |
| `docs/team_share/04_chart_spec.md` | 통합 담당에게 전달하는 차트(막대+꺾은선) 구현 스펙 (14.2절) |

### 13.2 우리 몫 — 고친 파일

| 파일 | 뭘 바꿨나 |
|---|---|
| `mcp_servers/data_tools/sales/schema.py` | **통째로 교체.** 없는 테이블 3개 삭제, 뷰 기반 구조(`views`/`metrics`/`out_of_scope`/`data_coverage`/`currency`)로 재작성 (7절) |
| `mcp_servers/data_tools/sales/text2sql.py` | `_FALLBACK_TEMPLATES` 등 하드코딩 부분 **완전히 삭제**(D-16). 프롬프트 12개 규칙으로 새로 작성, `generate_sql_with_error` 재시도 함수 추가 |
| `mcp_servers/data_tools/sales/mysql.py` | `ReadOnlyMySQLClient`는 그대로 두고, EXPLAIN 전용 `ExplainOnlyMySQLClient`(admin 계정)를 **별도 클래스로** 신설(5절 "알게 된 것" 참고). 가드 검사 로직은 `sql_guard.py`로 이동 |
| `mcp_servers/data_tools/sales/query.py` | 6절의 처리 순서 조립, 8.3절의 `metadata` 확장 evidence dict 반환. `query_sales_tool`은 만들지 않았다 — 8.1절 참고(통합 담당이 `server.py`로 이미 그 역할을 구현해둠) |
| `app/core/config.py` | `sales_read_user`/`sales_read_password` 필드 추가 (기본값 `""`, 5절) |
| `etl/sales/config.py` | `SALES_DB_*`로 ETL 쓰기 계정 분리 (다른 팀의 `MYSQL_DATABASE` 변경과 충돌 방지) |

### 13.3 우리 몫 — 테스트

| 파일 | 내용 |
|---|---|
| `tests/unit/test_sales_text2sql.py` | 스키마 정합성·가드·재시도 흐름 단위 테스트(21개) + `RUN_LOCAL_MYSQL_TESTS=1` 골든 케이스(12개). 초안엔 `test_data_mcp.py`를 고친다고 적었으나 실제로는 sales 전용 새 파일을 만들었다 |
| `tests/fixtures/cases/text2sql_cases.jsonl` | 질문-정답 테스트 세트 12건 (7.4절 초안은 빈 파일이었음, 실측 근거는 15.3절) |

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

### 14.2 그래프/차트 — 완료: 스펙 전달함

> 초안에서는 "이번 범위에서 뺀다"고 적었지만, 데이터가 5년치로 늘어나면서 사용자가
> 개발 범위에 다시 추가했다. sales가 직접 고칠 수 있는 건 SQL 생성 프롬프트 규칙뿐이고
> `chat.js`·`nodes.py`·`schemas/chat.py`·`index.html`은 전부 통합 담당 소유라, sales
> 몫(프롬프트 규칙)만 구현하고 나머지는
> [04_chart_spec.md](docs/team_share/04_chart_spec.md)로 상세 스펙을 만들어 전달했다
> (사용자 결정: "sales 부분만 + 상세 스펙 전달", 차트 종류 "막대 + 꺾은선").

sales가 이미 구현한 것(7.5절 프롬프트 규칙 8번, `text2sql.py`의 `SYSTEM_PROMPT`):

- 기간 라벨은 뷰의 문자열 컬럼(`order_month`)을 우선 사용
- 시계열 질문은 기간 오름차순 정렬
- 값(금액·수량) 컬럼은 `SELECT` 목록 맨 마지막
- 카테고리 비교는 12개, 시계열은 60개 이하로 `LIMIT`

`04_chart_spec.md`에서 통합 담당에게 요청한 것 — 실제 OpenAI 호출로 재현한 버그(`order_year`처럼
정수형 기간 컬럼이 라벨일 때 `_build_tables`가 문자열 컬럼만 찾아 차트가 안 그려지는 문제)를
포함해 `TableData.chart_type` 필드 추가, `_build_tables` 라벨/값 선택 개선, `chat.js` 수정,
Chart.js CDN→로컬 이관을 상세히 정리해뒀다. 검증 체크리스트는 그 문서 5절 참고.

---

## 15. 테스트로 확인할 것 — 실제 결과 반영

`tests/unit/test_sales_text2sql.py`(21개 오프라인 테스트 + 12개 골든 케이스)로 구현했다.
초안이 가정한 `INVALID_INPUT`/`test_data_mcp.py` 기반 시나리오는 9절에서 밝힌 대로 실제
에러코드 체계와 달라, 아래처럼 실측 기준으로 다시 정리한다.

### 15.1 단위 테스트 (LLM·DB는 가짜로 대체) — 전부 통과 ✅

- [x] 뷰 화이트리스트 = `schema.py`가 광고하는 뷰 집합 (`test_schema_only_advertises_allowed_views`)
- [x] 유령 테이블 3개가 스키마 리소스 어디에도 없음 (`test_schema_has_no_phantom_tables`)
- [x] "매출" 지표는 `v_sales_order.order_amount`로 고정, 설명에 "또는" 없음 (`test_revenue_metric_is_defined_once_without_or`)
- [x] `_FALLBACK_TEMPLATES`/`_DEFAULT_FALLBACK_SQL`/`_generate_sql_fallback` 심볼이 모듈에 없음 (`test_fallback_templates_removed`)
- [x] `OPENAI_API_KEY`가 없으면 `generate_sql`이 `RuntimeError`를 냄(→ `server.py`가 `QUERY_ERROR`로 변환. 초안엔 `INTERNAL_ERROR`로 적혀 있었으나 실제로는 예외가 `query()` 호출 안에서 나므로 `QUERY_ERROR`다) (`test_generate_sql_raises_without_api_key`)
- [x] 1차 검사: 복수 문장 / `UPDATE` / 주석 / 화이트리스트 밖 테이블 / `INTO OUTFILE` → 5건 전부 거부 (`test_guard_rejects_unsafe_sql`, 파라미터화)
- [x] `LIMIT` 없는 SQL에 `LIMIT 200` 자동 부착, `LIMIT 5000`은 `LIMIT 200`으로 하향, `LIMIT 10`처럼 상한 이내는 그대로 유지 (3개 테스트)
- [x] `referenced_tables`가 다중 JOIN에서 테이블 2개를 모두 찾음
- [x] LLM이 `NO_SQL`로 답하면(범위 밖) `rows=[]`, `retry_count=0` (`test_query_sales_returns_empty_when_llm_declines`)
- [x] 빈 질문("   ")·500자 초과 질문 → `query_sales` 단독 호출 시 `rows=[]` (2개 테스트).
      단, `server.py`까지 거치는 실제 경로에서 공백뿐인 질문은 `query_sales`가 불려지기도
      전에 `server.py` 자체 검사에서 `INVALID_INPUT`으로 끝난다(9.1절) — 이 테스트는
      `query_sales`가 그 검사 없이 단독으로 호출돼도 안전한지를 확인하는 방어적 테스트다.
      500자 초과는 `server.py`의 검사(공백 여부만 봄)를 통과하므로 실제로 `query_sales`까지
      도달해 `NO_RESULT`가 된다
- [x] EXPLAIN 실패 → 오류 메시지를 재작성 함수에 전달해 1회만 재시도, `retry_count=1` 기록 (`test_query_sales_retries_once_on_explain_failure`)
- [x] 재시도까지 실패하면 예외를 그대로 올림(→ `server.py`가 `QUERY_ERROR`로 변환) (`test_query_sales_raises_when_retry_also_fails`)
- [x] `chart_hint`: 기간 컬럼(`_month`/`_quarter`/`_year`)이 있으면 `"line"`, 아니면 `"bar"`, 빈 결과면 `None` (`test_chart_hint_prefers_line_for_period_columns`)

### 15.2 뷰 검증 (진짜 DB, `RUN_LOCAL_MYSQL_TESTS=1`로 확인) — 완료 ✅

- [x] `SELECT SUM(order_amount) FROM v_sales_order` = **26,818,155.31** (2.3절 근거, 초안의 6,165,466.50은 70건 시절 값)
- [x] `v_sales_order`에 `status`가 Cancelled·Draft인 행이 0건
- [x] `v_sales_order_line`이 헤더 금액 컬럼을 갖지 않아 fan-out 구조적으로 차단됨
- [x] `v_customer`에 이메일·세금번호·전화번호·주소·담당자·계약관리자 컬럼(PII 7개)이 없음
- [x] `sales_reader` 계정으로 `SELECT * FROM sales_orders` 시도 → **권한 오류 발생** (초안의 `chatbot_reader`는 실제로 만든 계정명이 아니다)
- [x] `sales_reader` 계정으로 `SELECT * FROM v_sales_order` → 정상 조회됨 (SQL SECURITY DEFINER)

### 15.3 질문-정답 테스트 세트 (`text2sql_cases.jsonl`) — 12건 작성, 12건 모두 실제 OpenAI+DB로 통과 ✅

| 유형 | 건수 | 실제 케이스 |
|---|---:|---|
| 기간별 집계 | 3 | "2025년 4분기 매출", "연도별 매출 추이", "월별 매출 추이" |
| 고객별 집계 | 2 | "매출 상위 5개 고객", "2025년 고객별 매출" |
| 품목별 집계 | 2 | "가장 많이 팔린 품목 10개"(`v_sales_order.order_amount` 금지), "품목별 판매 수량 상위 5개" |
| 미수금 | 1 | "연체된 미수금 총액" → `v_invoice` |
| 주문 현황 | 1 | "취소된 주문이 몇 건이야" → `v_sales_order_status` |
| 거절 — 답할 수 없는 지표/범위 밖 | 3 | "이번 달 영업이익", "재고 얼마나 남았어", "공급업체별 발주액" → 전부 `expect_no_sql: true` |

초안의 "예상 에러코드" 컬럼은 넣지 않았다 — 9.1절에서 확인했듯 `query_sales` 단계에서는
아직 에러코드가 없고(그건 `server.py`가 매기는 것), 골든 케이스는 SQL 생성 결과(뷰 사용
여부, 금지 표현 포함 여부, `NO_SQL` 여부)만 검증하는 게 더 정확하다.

### 15.4 완료 기준 — 달성 ✅

1. 15.1 단위 테스트 전부 통과: `.venv/Scripts/python.exe -m pytest tests/unit/test_sales_text2sql.py`
2. 15.2 뷰 검증 6개 항목을 `RUN_LOCAL_MYSQL_TESTS=1`로 실제 DB에서 확인
3. 15.3 질문-정답 테스트 세트 12개 **전부** 통과 (초안의 "10개 이상" 기준을 넘음)
4. `_FALLBACK_TEMPLATES` 관련 코드가 저장소에 하나도 안 남음 — `test_fallback_templates_removed`로 회귀 방지까지 확보
5. 작업 결과는 [docs/report/query-sales-text2sql.md](docs/report/query-sales-text2sql.md)에, 진행 기록은 [docs/progress/sales/2026-08-02.md](docs/progress/sales/2026-08-02.md)와 `docs/history/`에 남김

---

## 16. 알아둬야 할 한계와 위험

| # | 내용 | 영향 | 대응 |
|---|---|---|---|
| R-01 | 오늘(2026-08-03) 기준 "이번 달"은 더 이상 항상 0건은 아니다(2.2절 — 2026-08에 유효 주문 2건 존재). 다만 미래 어느 시점에서든 특정 기간이 우연히 0건일 수는 있음 | 시연 중 특정 질문이 빈 답변을 낼 수 있음(버그 아님) | 보유 기간 안내(6.2). 실제로는 9.2절에서 확인했듯 이 안내 문구가 지금 화면까지 전달되진 않는다 — 03_cross_team_requests.md에 요청 |
| R-02 | 품목을 구분하는 별도 코드가 없고 문자열(`description`)만 있음 | 같은 품목이 다르게 적혀 있으면 집계가 나뉨 | 800건 규모에서도 실제 위험 낮음(표기 패턴 재사용 확인됨). 표기가 다른 경우 발견되면 별도 기록 |
| R-03 | 가짜 데이터라 업종·국가가 실제와 안 맞음 | "제약회사 매출" 같은 상식 기반 질문은 실패함 | 프롬프트에서 상식 추측 금지(7.5-6). 테스트 세트에도 이런 질문은 넣지 않음 |
| R-04 | 위험 단어 검사가 문자열 안의 단어까지 걸러냄 | 정상 질문이 거부될 수 있음 | 10.2절에 기록. 거부되는 게 통과되는 것보다 안전하다고 판단 |
| R-05 | 뷰가 10개 테이블은 다루지 않음 | 견적·배송·여신·예측 관련 질문 불가 | 4.4절에 명시하고 거절 |
| R-06 | `LIMIT 200`이 이제 실제로 데이터를 자른다(`sales_order_lines` 2,207행 등, 초안 작성 시점엔 없던 위험) | 큰 결과를 요청하면 화면·LLM 모두 200행까지만 봄. "전체 몇 건"류 질문은 `COUNT`가 아니면 부정확할 수 있음 | `metadata.truncated`로 잘렸는지 신호는 주고 있음(8.3절). 프롬프트가 집계형(COUNT/SUM) 질문을 우선하도록 유도(7.5절), 화면에 "더 있음" 표시는 04_chart_spec.md 범위 밖이라 별도 후속 필요 |
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
| `LIMIT 200` 상한 | `sql_guard.py` | 결과가 너무 많이 나오는 걸 막음. **초안 작성 시점(주문 70건)엔 "제일 큰 표도 192행이라 안 잘린다"고 적었으나, 800건·5년치로 늘어난 지금은 실제로 잘려나간다** — `sales_order_lines` 뷰가 2,207행이라 `LIMIT 200`이 걸리는 질문이 나올 수 있다. `metadata.truncated`(8.3절)로 잘렸는지는 알 수 있지만, 그 사실이 사용자 화면까지 전달되는지는 통합 담당 몫이라 확인이 더 필요하다(R-06) |
| 실행 최대 10초 | `mysql.py` (`SET SESSION MAX_EXECUTION_TIME`) | 너무 오래 걸리는 조회를 막음. 실제 구현됨(9.1절) |
| 재시도는 최대 1번 | `query.py` | D-09. 무한 반복과 비용 폭증 방지 |

**초안에서 빠진 것**: "LLM에게는 50행만 보여준다"(D-13, `rows_for_llm`)는 실제로 구현하지
않았다 — 8.3절에서 밝혔듯 `rows`(최대 200행) 하나만 있고, `server.py`가 `metadata` 전체를
버리는 지금 구조에서는 별도 필드를 만들어도 전달할 방법이 없다. 확장 요청으로만 남겨뒀다.

### 아직 안 고친 것

- 위험 단어 검사가 문자열 안의 단어까지 걸러내는 문제(R-04). SQL을 제대로 해석하는
  도구가 필요한데, 이번 범위에서는 다루지 않기로 함.

---

## 18. 구현 순서 — 실제로는 아래 10단계로 진행, 전부 완료 ✅

초안의 8단계 제안 대신, 실제 승인된 계획([docs/plan/query-sales-text2sql.md](docs/plan/query-sales-text2sql.md))은
계정 모델(3계정)과 차트 범위 추가가 반영된 10단계로 진행됐다. RULE.md 2항(작은 단위로
나눠서, 단계마다 커밋)에 따라 단계마다 커밋했다.

| 단계 | 할 일 | 상태 |
|---|---:|---|
| 1 | `database/sales/views.sql` 작성·실행 (뷰 5개) | 완료 — 15.2절 뷰 검증 |
| 2 | `sales_reader` 조회 전용 계정 생성 + `app/core/config.py`/`.env` 연결 | 완료 — 15.2절 권한 검증 |
| 3 | `schema.py` 통째로 교체 (유령 테이블 제거) | 완료 |
| 4 | `text2sql.py` 재작성 (하드코딩 삭제 + 12개 프롬프트 규칙, 차트 친화 규칙 포함) | 완료 |
| 5 | `sql_guard.py` 신설 + `ExplainOnlyMySQLClient` 추가 | 완료 |
| 6 | `query.py` 파이프라인 조립 (검증→EXPLAIN→재시도→실행→metadata 확장) | 완료 |
| 7 | 단위 테스트(21개) + 골든 케이스(12개) 작성 | 완료 — 15.1·15.3절 |
| 8 | `RUN_LOCAL_MYSQL_TESTS=1`로 실DB 계약 테스트 실행 | 완료 — `PROGRESS.md` Sales 차단 요인 해소 |
| 9 | `docs/team_share/04_chart_spec.md` 작성 (통합 담당에게 전달) | 완료 — 14.2절 |
| 10 | `SPEC.md`·`docs/progress/`·`docs/report/`·`docs/history/`·`03_cross_team_requests.md` 정리 | 진행 중(이 문서) |

> RULE.md 5항에 따라 구현 시작 전 `docs/plan/query-sales-text2sql.md`를 먼저 만들었고,
> Plan Mode로 사용자 승인을 받은 뒤 착수했다.
