-- ============================================================
-- chatbot DB - document_registry 스키마
-- ------------------------------------------------------------
-- 설계 방향 (옵션 B):
--   문서 "경로"는 여전히 ingestion/loaders.py가 data/raw/documents/를
--   직접 스캔해서 얻습니다. 이 테이블은 경로를 대신 저장하지 않고,
--   파일명을 key로 "제목 오버라이드 / 부서 / 카테고리 / 접근 가능 role"
--   같은 메타데이터만 보관합니다.
--
-- 실행 방법:
--   mysql -u etl_writer -p -h $MYSQL_WRITE_HOST chatbot < database/schema.sql
--
-- 계정 분리 (.env.example 기준):
--   조회(ingestion 시 메타데이터 lookup) -> chatbot_reader (SELECT만 가능)
--   등록/갱신(register_documents.py)     -> etl_writer   (INSERT/UPDATE 가능)
-- ============================================================

CREATE DATABASE IF NOT EXISTS chatbot CHARACTER SET utf8mb4;
USE chatbot;

CREATE TABLE IF NOT EXISTS document_registry (
    id               BIGINT PRIMARY KEY AUTO_INCREMENT,

    -- data/raw/documents/ 안에서의 파일명. loaders.py가 만드는 RawDocument와
    -- 이 파일명으로 매칭합니다. (예: "취업규칙[2025.06.25. 개정].pdf")
    filename         VARCHAR(255) NOT NULL UNIQUE,

    -- 비워두면 파일명에서 자동 유추한 제목을 그대로 씁니다. 지정하면 그 값으로 덮어씁니다.
    title_override   VARCHAR(255),

    department       VARCHAR(100),
    category         VARCHAR(100),
    version_date     DATE,

    -- 접근 가능한 role을 콤마로 구분해 저장합니다. (예: "user,hr,purchase")
    -- 접근 제어 계층은 allowed_roles가 없거나 손상되면 기본 거부해야 하므로, 이 컬럼은
    -- NULL을 허용하지 않고 항상 명시적인 값을 가지도록 합니다.
    -- 전 직원 공개 문서는 baseline role(예: "user")을 반드시 포함해야 합니다.
    allowed_roles    VARCHAR(255) NOT NULL DEFAULT 'user',

    is_active        BOOLEAN DEFAULT TRUE,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
