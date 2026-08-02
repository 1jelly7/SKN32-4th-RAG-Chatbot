-- 판매(Sales) 도메인 MySQL 데이터베이스 생성 스크립트
--
-- 이 프로젝트를 처음 셋업하는 사람이 1회 실행한다 (README 안내 대상).
-- DB 생성 권한이 있는 관리자 계정(root 등)으로 실행해야 한다.
-- 이 파일이 실행된 뒤에야 `database/sales/ddl.sql`(테이블 생성)과
-- `etl/sales/` 파이프라인(UPSERT 적재)을 실행할 수 있다.

-- 1) 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS `sales`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- 2) ETL 쓰기 계정 준비
--    .env의 MYSQL_WRITE_USER/MYSQL_WRITE_PASSWORD와 반드시 동일한 값으로 맞춘다.
--    호스트는 'localhost'가 아니라 '%'를 사용한다. Windows에서 pymysql이 TCP로
--    접속하면 'localhost' 전용 계정과 매칭되지 않는 경우가 있어(유닉스 소켓/
--    named pipe 전용으로 취급) 접속 계정이 'user'@'%'로 잡히기 때문이다.
--    계정이 이미 있다면 CREATE USER 문은 건너뛰어도 된다(중복 생성 시 에러 방지를
--    위해 IF NOT EXISTS를 사용했다).
CREATE USER IF NOT EXISTS 'JangGGo'@'%' IDENTIFIED BY '1234';

GRANT SELECT, INSERT, UPDATE, DELETE ON `sales`.* TO 'JangGGo'@'%';

-- 3) (선택) 챗봇 조회 전용 계정도 함께 준비하려면 아래 주석을 해제한다.
--    query_sales(read-only) Tool이 이 계정을 사용한다 (mcp_servers/data_tools/sales/mysql.py).
-- CREATE USER IF NOT EXISTS 'chatbot_reader'@'%' IDENTIFIED BY '변경하세요';
-- GRANT SELECT ON `sales`.* TO 'chatbot_reader'@'%';

FLUSH PRIVILEGES;
