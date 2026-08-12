from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://pinsight:pinsight@postgres:5432/pinsight"
    database_url_sync: str = "postgresql://pinsight:pinsight@postgres:5432/pinsight"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Groq API
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    # Pricing last checked: August 2026. (Assume $0.60 per 1M tokens)
    groq_cost_per_token: float = 0.60 / 1000000.0

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    admin_username: str = "admin"
    admin_password: str = "supersecret123"
    jwt_expire_minutes: int = 60

    # App
    env: str = "development"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
