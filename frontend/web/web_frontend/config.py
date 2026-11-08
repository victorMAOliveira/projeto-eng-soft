"""Frontend configuration."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Values read from environment variables."""

    model_config = SettingsConfigDict(extra="ignore")

    gateway_url: str = "http://api-gateway:8000"
    gateway_timeout: float = 20.0
    cookie_secure: bool = False
    log_level: str = "INFO"
