-- ============================================================
-- 판매(Sales) 시맨틱 뷰
-- ------------------------------------------------------------
-- 주의: 이 파일은 `python -m etl.sales.ddl`로 재생성되는 ddl.sql과 다르다.
-- ddl.sql은 컬럼 메타데이터(etl/sales/schema.py)에서 자동 생성되는 반면,
-- 이 파일은 업무 정의(무엇을 "매출"이라 부를지 등)가 들어간 SELECT 문이라
-- 자동 생성할 수 없다. 사람이 직접 관리하며, 절대 자동 생성 도구로 덮어쓰지 않는다.
--
-- 목적: LLM이 만든 SQL이 원본 테이블 대신 이 뷰만 참조하도록 강제해서,
-- "매출 계산에 취소 주문을 넣을지"·"라인 합계에 헤더 금액을 실수로 더할지"
-- 같은 판단을 LLM에게 맡기지 않는다(SPEC.md 4절 참고).
--
-- 실행 방법 (최초 1회, 또는 정의를 바꿀 때마다):
--   mysql -u JangGGo -p sales < database/sales/views.sql
-- Windows PowerShell에서는 "<" 리다이렉션이 안 되므로 대신:
--   Get-Content database/sales/views.sql | mysql -u JangGGo -p sales
--
-- 실행 순서: 이 파일은 database/sales/ddl.sql로 테이블이 이미 만들어지고
-- ETL로 데이터가 적재된 뒤에 실행한다.
-- ============================================================

USE `sales`;

-- ---------------------------------------------------------------
-- v_sales_order : 유효한 주문(취소/초안 제외)
--   "매출"의 유일한 정의: 이 뷰의 order_amount 합계.
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_sales_order AS
SELECT
    o.sales_order_id,
    o.order_number,
    o.order_date,
    YEAR(o.order_date)                  AS order_year,
    QUARTER(o.order_date)               AS order_quarter,
    DATE_FORMAT(o.order_date, '%Y-%m')  AS order_month,
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
-- v_sales_order_line : 유효한 주문의 라인(상세) 단위
--   주문 헤더 금액(total_amount)을 의도적으로 포함하지 않는다.
--   헤더 금액과 라인을 JOIN해서 합치면 라인 수만큼 금액이 중복
--   합산되는 "뻥튀기(fan-out)"가 생기는데, 애초에 그 칼럼을 이
--   뷰에 안 넣어서 그런 실수 자체를 구조적으로 못 하게 막는다.
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
-- v_customer : 고객 마스터 (개인정보 컬럼 제외)
--   제외한 컬럼: contact_person, email, phone_number,
--   billing_address, shipping_address, tax_id, account_manager_id,
--   created_by_user_id
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
-- v_sales_order_status : 취소 포함 전체 주문 현황 (상태 x 월)
--   "취소된 주문이 몇 건이야?" 같은 질문 전용. v_sales_order와
--   달리 여기서는 취소/초안을 뺴지 않는다 — 그래서 매출 집계용
--   뷰와 분리해뒀다. 매출 질문에 이 뷰를 쓰면 취소분이 섞여
--   들어가므로, 스키마 리소스에서 이 뷰는 "현황" 질문에만
--   쓰라고 명시한다(schema.py 참고).
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
