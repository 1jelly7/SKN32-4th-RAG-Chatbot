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

    # 임베딩 백엔드: "local"(기본값, 외부 API 불필요) 또는 "openai".
    embedding_backend: str = "local"
    # local 백엔드를 쓸 때의 임베딩 벡터 차원입니다.
    local_embedding_dimension: int = 384
    sbert_model_name: str = "jhgan/ko-sroberta-multitask"

    # Data MCP가 조회할 도메인별 DB 이름입니다. (읽기 계정/호스트는 mysql_read_*를 재사용)
    purchase_db_database: str = "purchase"
    sales_db_database: str = "sales"

    # 판매 도메인 전용 조회 계정입니다. sales.* 뷰에만 SELECT 권한을 가진
    # sales_reader를 쓰기 위한 필드로, 비어 있으면 mysql_read_*로 폴백합니다
    # (팀원이 아직 .env를 안 바꿔도 기존 계정으로 계속 동작하게 하기 위함).
    # mysql_read_*는 purchase도 같이 쓰므로 여기서 바꾸지 않습니다.
    sales_read_user: str = ""
    sales_read_password: str = ""

    # 구매 도메인 전용 조회 계정입니다. purchase_reader를 쓰기 위한 필드로,
    # sales_read_*와 같은 패턴입니다. 비어 있으면 mysql_read_*로 폴백합니다.
    purchase_read_user: str = ""
    purchase_read_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """환경 변수/.env에서 Settings를 한 번 읽어 검증된 설정 객체를 반환한다.

    API 키·DB 비밀번호는 오류 메시지나 로그에 포함하지 않는다. 반복 생성 비용을 줄이기
    위해 캐시할 수 있으나 테스트가 환경을 교체할 수 있는 방식으로 설계한다.
    """
    return Settings()
