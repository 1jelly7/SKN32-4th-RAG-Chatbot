-- ============================================================
-- erp_system DB - document_paths 스키마
-- ------------------------------------------------------------
-- docs/interface.md 계약: DocumentPathRecord는 document_id, title,
-- file_path, updated_at 4개 필드만 가진다. 문서 본문이나 접근권한(ACL)은
-- 이 DB에 저장하지 않는다 (본문은 파일시스템 + FAISS, ACL은 최종 스코프에서 제외됨).
--
-- 실행 방법:
--   mysql -u JangGGo -p1234 -h 127.0.0.1 erp_system < database/document/schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS erp_system CHARACTER SET utf8mb4;
USE erp_system;

CREATE TABLE IF NOT EXISTS document_paths (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,

    -- mcp_servers/document_tools/types.DocumentPathRecord.document_id 와 대응합니다.
    document_id  VARCHAR(100) NOT NULL UNIQUE,

    title        VARCHAR(255) NOT NULL,

    -- 문서 서버가 실제로 파일을 열 때 사용하는 절대/상대 경로입니다.
    file_path    VARCHAR(500) NOT NULL,

    -- 원본 파일이 실제로 마지막 수정된 시각입니다. (ingestion이 파일 mtime으로 채움)
    updated_at   DATETIME NOT NULL,

    is_active    BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_document_paths_active ON document_paths (is_active);
