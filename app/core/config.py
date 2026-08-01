from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
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

    # 임베딩 백엔드: "local"(기본값, 외부 API 불필요) 또는 "openai".
    embedding_backend: str = "local"
    # local 백엔드를 쓸 때의 임베딩 벡터 차원입니다.
    local_embedding_dimension: int = 384

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
