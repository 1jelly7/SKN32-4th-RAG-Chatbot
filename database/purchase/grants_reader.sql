-- ============================================================
-- 구매(Purchase) 챗봇 조회 전용 계정
-- ------------------------------------------------------------
-- 이 계정은 원본 테이블에는 아무 권한이 없고, purchase_db의 뷰 5개에만 SELECT
-- 권한을 가진다. MySQL 뷰는 기본이 SQL SECURITY DEFINER라(뷰를 만든 admin
-- 계정의 권한으로 실행됨) 이 계정이 원본 테이블 권한 없이도 뷰는 정상 조회할
-- 수 있다 — 즉 LLM이 어떤 SQL을 만들어도 원본 테이블(및 PII 컬럼)에는 절대
-- 닿을 수 없다.
--
-- 계정 모델 (SPEC.md / 팀 합의):
--   admin(JangGGo)      : sales + purchase + document 전부 (ETL 쓰기)
--   sales(sales_reader) : sales 뷰만 (챗봇 판매 조회)
--   purchase(purchase_reader): purchase 뷰만 (챗봇 구매 조회) — 이 파일
--
-- 실행 방법 (최초 1회, admin 계정으로):
--   mysql -u JangGGo -p purchase_db < database/purchase/grants_reader.sql
--
-- 실행 전 5개 뷰(v_purchase_order, v_purchase_order_line, v_vendor,
-- v_vendor_invoice, v_purchase_order_status)가 purchase_db에 이미 만들어져
-- 있어야 한다.
-- ============================================================

-- 비밀번호는 .env의 PURCHASE_READ_PASSWORD와 반드시 동일한 값으로 맞춘다.
CREATE USER IF NOT EXISTS 'purchase_reader'@'%' IDENTIFIED BY 'purchase_read_1234';

-- 원본 테이블 권한은 주지 않는다. 뷰에만 SELECT를 허용한다.
GRANT SELECT ON `purchase_db`.`v_purchase_order`        TO 'purchase_reader'@'%';
GRANT SELECT ON `purchase_db`.`v_purchase_order_line`   TO 'purchase_reader'@'%';
GRANT SELECT ON `purchase_db`.`v_vendor`                TO 'purchase_reader'@'%';
GRANT SELECT ON `purchase_db`.`v_vendor_invoice`        TO 'purchase_reader'@'%';
GRANT SELECT ON `purchase_db`.`v_purchase_order_status` TO 'purchase_reader'@'%';

FLUSH PRIVILEGES;
