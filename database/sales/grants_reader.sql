-- ============================================================
-- 판매(Sales) 챗봇 조회 전용 계정
-- ------------------------------------------------------------
-- 이 계정은 원본 테이블에는 아무 권한이 없고, database/sales/views.sql의
-- 뷰 5개에만 SELECT 권한을 가진다. MySQL 뷰는 기본이 SQL SECURITY DEFINER라
-- (뷰를 만든 admin 계정의 권한으로 실행됨) 이 계정이 원본 테이블 권한 없이도
-- 뷰는 정상 조회할 수 있다 — 즉 LLM이 어떤 SQL을 만들어도 원본 테이블에는
-- 절대 닿을 수 없다.
--
-- 계정 모델 (SPEC.md / 팀 합의):
--   admin(JangGGo)    : sales + purchase + document 전부 (ETL 쓰기)
--   sales(sales_reader): sales 뷰만 (챗봇 판매 조회)
--   purchase(신규)     : purchase만 (purchase 담당이 별도 추가 예정)
--
-- 실행 방법 (최초 1회, admin 계정으로):
--   mysql -u JangGGo -p sales < database/sales/grants_reader.sql
--
-- 실행 전 database/sales/views.sql이 먼저 적용되어 있어야 한다.
-- ============================================================

-- 비밀번호는 .env의 SALES_READ_PASSWORD와 반드시 동일한 값으로 맞춘다.
CREATE USER IF NOT EXISTS 'sales_reader'@'%' IDENTIFIED BY 'sales_read_1234';

-- 원본 테이블 권한은 주지 않는다. 뷰에만 SELECT를 허용한다.
GRANT SELECT ON `sales`.`v_sales_order`        TO 'sales_reader'@'%';
GRANT SELECT ON `sales`.`v_sales_order_line`   TO 'sales_reader'@'%';
GRANT SELECT ON `sales`.`v_invoice`            TO 'sales_reader'@'%';
GRANT SELECT ON `sales`.`v_customer`           TO 'sales_reader'@'%';
GRANT SELECT ON `sales`.`v_sales_order_status` TO 'sales_reader'@'%';

FLUSH PRIVILEGES;
