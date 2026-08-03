"""환경 변수에서 애플리케이션의 외부 연결 계약을 검증한다.

설정값을 소유 모듈에 전달할 뿐 연결을 열지 않으며, 비밀값을 로그나 주석에 노출하지
않는다. 공개 설정 필드 변경은 추적되는 ``.env.example``과 함께 검토해야 한다.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """API, MCP, 캐시, 읽기/쓰기 DB 경계에 필요한 환경 설정 모델."""

    openai_api_key: str
    openai_model: str
    redis_url: str
    mysql_read_host: str
    mysql_read_user: str
    mysql_read_password: str
    mysql_write_host: str
    mysql_write_user: str
    mysql_write_password: str
    mysql_database: str
    document_mcp_url: str
    data_mcp_url: str
    faiss_path: str
    document_db_host: str
    document_db_user: str
    document_db_password: str
    document_db_database: str
    account_db_host: str = "127.0.0.1"
    account_db_port: int = 3306
    account_db_name: str = "account_db"
    account_db_user: str = ""
    account_db_password: str = ""
    auth_secret_key: str = "change-this-in-production"
    auth_access_token_expire_minutes: int = 60
    auth_cookie_secure: bool = False
    account_seed_admin_password: str | None = None
    account_seed_hr_password: str | None = None
    account_seed_finance_password: str | None = None

    # 임베딩 백엔드: "local"(기본값, 외부 API 불필요) 또는 "openai".
    embedding_backend: str = "local"
    # local 백엔드를 쓸 때의 임베딩 벡터 차원입니다.
    local_embedding_dimension: int = 384
    sbert_model_name: str = "jhgan/ko-sroberta-multitask"

    # Data MCP가 조회할 도메인별 DB 이름입니다. (읽기 계정/호스트는 mysql_read_*를 재사용)
    purchase_db_database: str = "purchase"
    sales_db_database: str = "sales"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """환경 변수/.env에서 Settings를 한 번 읽어 검증된 설정 객체를 반환한다.

    API 키·DB 비밀번호는 오류 메시지나 로그에 포함하지 않는다. 반복 생성 비용을 줄이기
    위해 캐시할 수 있으나 테스트가 환경을 교체할 수 있는 방식으로 설계한다.
    """
    return Settings()
