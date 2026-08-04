-- ==================================================
-- Purchase DB 생성 스크립트
-- ------------------------------------------------------------
-- 프로젝트 최초 실행 시 한 번만 실행합니다.
-- 데이터베이스를 UTF-8(utf8mb4) 문자셋으로 생성합니다.
-- =======================================================

-- 기존 데이터베이스가 존재하면 삭제하려면 아래 주석을 해제하세요.
-- DROP DATABASE IF EXISTS purchase;

-- 데이터베이스 생성
-- 주의: DB 이름은 purchase_db가 아니라 purchase다. etl/purchase/config.py의
-- DB_CONFIG['database']와 app/core/config.py의 purchase_db_database 기본값이
-- 전부 'purchase'를 쓰고 있어서, 여기서도 이름을 맞춘다.
CREATE DATABASE IF NOT EXISTS purchase
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- ETL 쓰기 계정. etl/purchase/config.py의 DB_CONFIG(user='purchase')와 동일하게
-- 맞춘다. host는 'localhost'가 아니라 '%'를 쓴다 — Windows에서 pymysql이 TCP로
-- 접속하면 'localhost' 전용 계정과 매칭되지 않는 경우가 있다(sales 쪽에서도 같은
-- 문제를 겪어 '%'로 통일했다).
CREATE USER IF NOT EXISTS 'purchase'@'%' IDENTIFIED BY '1234';
GRANT ALL PRIVILEGES
ON `purchase`.*
TO 'purchase'@'%';

FLUSH PRIVILEGES;