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
    ...
