-- ============================================================
-- 구매(Purchase) 시맨틱 뷰
-- ------------------------------------------------------------
-- 주의: 이 파일은 `python -m etl.purchase.ddl`로 재생성되는 ddl.sql과 다르다.
-- ddl.sql은 컬럼 메타데이터(etl/purchase/schema.py)에서 자동 생성되는 반면,
-- 이 파일은 업무 정의(무엇을 "구매액"이라 부를지 등)가 들어간 SELECT 문이라
-- 자동 생성할 수 없다. 사람이 직접 관리하며, 절대 자동 생성 도구로 덮어쓰지 않는다.
--
-- 목적: LLM이 만든 SQL이 원본 테이블 대신 이 뷰만 참조하도록 강제해서,
-- "구매액 계산에 취소 발주를 넣을지"·"라인 합계에 헤더 금액을 실수로 더할지"
-- 같은 판단을 LLM에게 맡기지 않는다(sales와 동일 원칙, SPEC.md 4절 참고).
--
-- 이전 버전(옛 purchase_db 스키마 기준)과 달리, 원천 엑셀 실측 결과를 그대로
-- 반영한다: company_id 컬럼 없음, Vendors에 PII 컬럼 없음, Invoice에
-- Due_Date/Payment_Date 없음, Status 컬럼명은 실제로 "Status"(Payment_Status
-- 아님).
--
-- 실행 방법 (최초 1회, 또는 정의를 바꿀 때마다):
--   mysql -u purchase -p1234 -h 127.0.0.1 purchase < database/purchase/views.sql
-- Windows PowerShell에서는 "<" 리다이렉션이 안 되므로 대신:
--   Get-Content database/purchase/views.sql | mysql -u purchase -p1234 -h 127.0.0.1 purchase
--
-- 실행 순서: 이 파일은 database/purchase/ddl.sql로 테이블이 이미 만들어지고
-- ETL(python -m etl.purchase.run_all)로 데이터가 적재된 뒤에 실행한다.
-- ============================================================

USE `purchase`;

-- ---------------------------------------------------------------
-- v_purchase_order : 유효한 발주(취소 제외)
--   "구매액"의 유일한 정의: 이 뷰의 po_amount 합계.
--   sales의 D-04(취소·초안 제외)와 달리 purchase에는 Draft 상태가
--   없어 Cancelled만 제외한다(실측: Approved/Sent/Partially Received/
--   Received/Closed는 전부 유효한 발주로 본다).
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_purchase_order AS
SELECT
    po.po_id,
    po.po_number,
    po.po_date,
    YEAR(po.po_date)                  AS po_year,
    QUARTER(po.po_date)               AS po_quarter,
    DATE_FORMAT(po.po_date, '%Y-%m')  AS po_month,
    po.vendor_id,
    v.vendor_name,
    v.country,
    po.status,
    po.currency,
    po.subtotal,
    po.tax_amount,
    po.total_amount                   AS po_amount
FROM purchase_orders po
LEFT JOIN vendors v ON v.vendor_id = po.vendor_id
WHERE po.status <> 'Cancelled';

-- ---------------------------------------------------------------
-- v_purchase_order_line : 유효한 발주의 라인(상세) 단위
--   발주 헤더 금액(total_amount)을 의도적으로 포함하지 않는다.
--   헤더 금액과 라인을 JOIN해서 합치면 라인 수만큼 금액이 중복
--   합산되는 "뻥튀기(fan-out)"가 생기는데, 애초에 그 칼럼을 이
--   뷰에 안 넣어서 그런 실수 자체를 구조적으로 못 하게 막는다.
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_purchase_order_line AS
SELECT
    pol.po_line_id,
    pol.po_id,
    po.po_number,
    po.po_date,
    YEAR(po.po_date)                  AS po_year,
    QUARTER(po.po_date)               AS po_quarter,
    DATE_FORMAT(po.po_date, '%Y-%m')  AS po_month,
    po.vendor_id,
    v.vendor_name,
    pol.item_id,
    pol.description                   AS item_name,
    pol.quantity,
    pol.unit_price,
    pol.discount_percent,
    pol.line_total,
    po.currency,
    po.status
FROM purchase_order_lines pol
JOIN purchase_orders po ON po.po_id = pol.po_id
LEFT JOIN vendors v     ON v.vendor_id = po.vendor_id
WHERE po.status <> 'Cancelled';

-- ---------------------------------------------------------------
-- v_vendor_invoice : 청구·지급·미지급금
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_vendor_invoice AS
SELECT
    i.invoice_id,
    i.invoice_number,
    i.invoice_date,
    YEAR(i.invoice_date)                  AS invoice_year,
    QUARTER(i.invoice_date)               AS invoice_quarter,
    DATE_FORMAT(i.invoice_date, '%Y-%m')  AS invoice_month,
    i.po_id,
    i.vendor_id,
    v.vendor_name,
    i.subtotal,
    i.tax_amount,
    i.total_amount                        AS invoice_amount,
    i.amount_paid,
    i.outstanding_amount,
    i.currency,
    i.status
FROM vendor_invoices i
LEFT JOIN vendors v ON v.vendor_id = i.vendor_id;

-- ---------------------------------------------------------------
-- v_vendor : 공급업체 마스터
--   실측 결과 원천 Vendors 시트에는 PII 컬럼(연락처/주소 등) 자체가
--   없다. 그래도 SELECT 목록을 고정해둔다 — 나중에 원본 테이블에
--   PII 컬럼이 추가되더라도 이 뷰가 자동으로 노출하지 않도록.
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_vendor AS
SELECT
    vendor_id,
    vendor_code,
    vendor_name,
    country,
    currency,
    payment_terms,
    is_active
FROM vendors;

-- ---------------------------------------------------------------
-- v_purchase_order_status : 취소 포함 전체 발주 현황 (상태 x 월)
--   "취소된 발주가 몇 건이야?" 같은 질문 전용. v_purchase_order와
--   달리 여기서는 취소를 빼지 않는다 — 그래서 구매액 집계용 뷰와
--   분리해뒀다. 구매액 질문에 이 뷰를 쓰면 취소분이 섞여 들어가므로,
--   스키마 리소스에서 이 뷰는 "현황" 질문에만 쓰라고 명시한다
--   (mcp_servers/data_tools/purchase/schema.py 참고).
-- ---------------------------------------------------------------
CREATE OR REPLACE VIEW v_purchase_order_status AS
SELECT
    po.status,
    po.currency,
    DATE_FORMAT(po.po_date, '%Y-%m') AS po_month,
    COUNT(*)             AS po_count,
    SUM(po.total_amount) AS total_amount
FROM purchase_orders po
GROUP BY po.status, po.currency, DATE_FORMAT(po.po_date, '%Y-%m');
