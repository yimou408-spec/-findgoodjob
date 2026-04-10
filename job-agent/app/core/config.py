from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "job-agent"
    env: str = "dev"
    database_url: str = "sqlite:///./job_agent.db"

    openai_api_key: str = ""
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    llm_timeout: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
