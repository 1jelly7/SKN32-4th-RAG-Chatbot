from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    redis_url: str = "redis://localhost:6379/0"
    faiss_path: str = "data/faiss"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()
