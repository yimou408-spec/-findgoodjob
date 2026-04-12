from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    deepseek_timeout_seconds: float = 90.0
    zhipu_api_key: str | None = None
    zhipu_embedding_model: str = "embedding-3"
    zhipu_embedding_dimensions: int = 1024
    zhipu_embedding_base_url: str = "https://open.bigmodel.cn/api/paas/v4/embeddings"
    zhipu_embedding_timeout_seconds: float = 60.0
    database_url: str = "sqlite:///./findgoodjob.db"
    app_env: str = "development"
    debug: bool | str = False

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
