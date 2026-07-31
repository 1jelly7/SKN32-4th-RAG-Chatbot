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
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings:
    """환경 변수/.env에서 Settings를 한 번 읽어 검증된 설정 객체를 반환한다.

    API 키·DB 비밀번호는 오류 메시지나 로그에 포함하지 않는다. 반복 생성 비용을 줄이기
    위해 캐시할 수 있으나 테스트가 환경을 교체할 수 있는 방식으로 설계한다.
    """
    ...
