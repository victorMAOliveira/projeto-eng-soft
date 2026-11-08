"""internship-service configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Values read from environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    rabbitmq_url: str
    jwt_secret: str
    log_level: str = "INFO"
