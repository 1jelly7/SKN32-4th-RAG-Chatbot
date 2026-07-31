-- ==================================================
-- Purchase DB 생성 스크립트
-- ------------------------------------------------------------
-- 프로젝트 최초 실행 시 한 번만 실행합니다.
-- 데이터베이스를 UTF-8(utf8mb4) 문자셋으로 생성합니다.
-- =======================================================

-- 기존 데이터베이스가 존재하면 삭제하려면 아래 주석을 해제하세요.
-- DROP DATABASE IF EXISTS purchase;

-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS purchase_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'JangGGo'@'%' IDENTIFIED BY '1234';
GRANT SELECT, INSERT, UPDATE, DELETE
ON `purchase_db`.*
TO 'JangGGo'@'%';

FLUSH PRIVILEGES;