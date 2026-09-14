from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Runtime
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # Supabase
    supabase_url: str
    supabase_secret_key: str
    supabase_jwks_url: str

    # Database (Supabase Postgres, pooler connection string)
    database_url: str

    # Groq (script generation)
    groq_api_key: str
    # Confirm the exact model name when we build the script step.
    groq_model: str = Field(default="llama-3.3-70b-versatile")

    @property
    def sqlalchemy_database_url(self) -> str:

        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
