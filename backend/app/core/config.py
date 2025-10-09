"""
Application configuration settings.

Uses Pydantic Settings for configuration management with environment variable support.
Designed to support both MySQL (current) and CouchDB (future) databases.
"""

from typing import Optional, List
from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    model_config = SettingsConfigDict(
        env_file=("../.env", "../../.env", "../../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=()  # Allow MODEL_ field names
    )

    # Application
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production", description="Secret key for JWT tokens")

    # Database - MySQL (Current)
    MYSQL_HOST: str = Field(default="localhost", description="MySQL host")
    MYSQL_PORT: int = Field(default=3306, description="MySQL port")
    MYSQL_USER: str = Field(default="assisted_discovery", description="MySQL username")
    MYSQL_PASSWORD: str = Field(default="", description="MySQL password")
    MYSQL_DATABASE: str = Field(default="assisted_discovery", description="MySQL database name")

    # Database - CouchDB (Future)
    COUCHDB_HOST: str = Field(default="localhost", description="CouchDB host")
    COUCHDB_PORT: int = Field(default=5984, description="CouchDB port")
    COUCHDB_USER: str = Field(default="admin", description="CouchDB username")
    COUCHDB_PASSWORD: str = Field(default="", description="CouchDB password")
    COUCHDB_DATABASE: str = Field(default="assisted_discovery", description="CouchDB database name")

    # Cache - Redis
    REDIS_HOST: str = Field(default="localhost", description="Redis host")
    REDIS_PORT: int = Field(default=6379, description="Redis port")
    REDIS_PASSWORD: Optional[str] = Field(default=None, description="Redis password")
    REDIS_DB: int = Field(default=0, description="Redis database number")

    # LLM Configuration - Azure OpenAI
    AZURE_OPENAI_KEY: str = Field(default="", description="Azure OpenAI API key")
    AZURE_OPENAI_ENDPOINT: str = Field(default="", description="Azure OpenAI endpoint URL")
    AZURE_API_VERSION: str = Field(default="2025-01-01-preview", description="Azure OpenAI API version")
    MODEL_DEPLOYMENT_NAME: str = Field(default="gpt-4o", description="Primary model deployment name")
    FALLBACK_MODEL_DEPLOYMENT_NAME: str = Field(default="gpt-4o-mini", description="Fallback model deployment name")

    # LLM Configuration - OpenAI (fallback)
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    LLM_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI model name")

    # LLM Configuration - Google Gemini
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key")
    GEMINI_MODEL: str = Field(default="gemini-1.5-pro", description="Gemini model name")

    # LLM Provider Selection
    LLM_PROVIDER: str = Field(default="azure", description="LLM provider: azure, openai, or gemini")

    MAX_TOKENS_PER_REQUEST: int = Field(default=4000, description="Maximum tokens per LLM request")
    LLM_TEMPERATURE: float = Field(default=0.1, description="LLM temperature for consistent outputs")
    LLM_TOP_P: float = Field(default=0.0, description="LLM top_p for deterministic outputs")

    # XML Processing
    MAX_XML_SIZE_MB: int = Field(default=100, description="Maximum XML file size in MB")
    MAX_SUBTREE_SIZE_KB: int = Field(default=4, description="Maximum subtree size for LLM in KB")
    MICRO_BATCH_SIZE: int = Field(default=6, description="NodeFacts per LLM batch")

    # Pattern Discovery
    PATTERN_CONFIDENCE_THRESHOLD: float = Field(default=0.7, description="Minimum confidence for pattern matches")
    TOP_K_CANDIDATES: int = Field(default=5, description="Number of candidate patterns to retrieve")

    # Retry Configuration
    MAX_LLM_RETRIES: int = Field(default=3, description="Maximum retries for LLM calls")
    MAX_DB_RETRIES: int = Field(default=5, description="Maximum retries for database operations")
    RETRY_BACKOFF_FACTOR: float = Field(default=2.0, description="Exponential backoff factor for retries")

    # Security
    PII_MASKING_ENABLED: bool = Field(default=True, description="Enable PII masking")
    MAX_SNIPPET_LENGTH: int = Field(default=120, description="Maximum snippet length in characters")

    # Monitoring
    ENABLE_METRICS: bool = Field(default=True, description="Enable Prometheus metrics")
    METRICS_PORT: int = Field(default=9090, description="Metrics server port")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # CORS
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:8501", "http://127.0.0.1:8501"],
        description="Allowed CORS origins"
    )

    @validator("ENVIRONMENT")
    def validate_environment(cls, v):
        """Validate environment setting."""
        valid_environments = {"development", "staging", "production"}
        if v not in valid_environments:
            raise ValueError(f"Environment must be one of: {valid_environments}")
        return v

    @validator("LOG_LEVEL")
    def validate_log_level(cls, v):
        """Validate log level setting."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    @property
    def mysql_url(self) -> str:
        """Build MySQL connection URL."""
        password_part = f":{self.MYSQL_PASSWORD}" if self.MYSQL_PASSWORD else ""
        return f"mysql+pymysql://{self.MYSQL_USER}{password_part}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"

    @property
    def couchdb_url(self) -> str:
        """Build CouchDB connection URL."""
        auth_part = f"{self.COUCHDB_USER}:{self.COUCHDB_PASSWORD}@" if self.COUCHDB_PASSWORD else ""
        return f"http://{auth_part}{self.COUCHDB_HOST}:{self.COUCHDB_PORT}"

    @property
    def redis_url(self) -> str:
        """Build Redis connection URL."""
        password_part = f":{self.REDIS_PASSWORD}@" if self.REDIS_PASSWORD else ""
        return f"redis://{password_part}{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development."""
        return self.ENVIRONMENT == "development"


# Global settings instance
settings = Settings()
