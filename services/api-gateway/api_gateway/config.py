"""Gateway configuration (environment variables)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Upstream addresses, resilience parameters and security options."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    jwt_secret: str
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:8080"

    user_service_url: str = "http://user-service:8000"
    internship_service_url: str = "http://internship-service:8000"
    application_service_url: str = "http://application-service:8000"
    document_service_url: str = "http://document-service:8000"
    notification_service_url: str = "http://notification-service:8000"
    recommendation_service_url: str = "http://recommendation-service:8000"
    agent_service_url: str = "http://agent-service:8000"

    upstream_timeout: float = 10.0
    upstream_retries: int = 2
    breaker_failure_threshold: int = 5
    breaker_recovery_seconds: float = 15.0
    probe_timeout: float = 2.0

    def upstreams(self) -> dict[str, str]:
        """Map service name -> base URL."""
        return {
            "user-service": self.user_service_url,
            "internship-service": self.internship_service_url,
            "application-service": self.application_service_url,
            "document-service": self.document_service_url,
            "notification-service": self.notification_service_url,
            "recommendation-service": self.recommendation_service_url,
            "agent-service": self.agent_service_url,
        }
