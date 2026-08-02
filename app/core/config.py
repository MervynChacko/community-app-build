from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Defines the environment variables required by the application.
    Pydantic will load these values automatically from environment variables
    or from the local `.env` file.
    """
    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    
    # Auth
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # 24 hours (60 * 24)

    @property
    def DATABASE_URL(self) -> str:
        """
        Dynamically builds the PostgreSQL connection URL standard format 
        from individual config attributes.
        """
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Configures Pydantic to look for a `.env` file in the root directory
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Reads settings once and caches the result in memory."""
    return Settings()


# Singleton instance ready for import elsewhere in the app
settings = get_settings()
