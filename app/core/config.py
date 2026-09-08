from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    SECRET_KEY: str
    
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_NAME: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str

    REDIS_HOST: str
    REDIS_PASSWORD: str
    REDIS_PORT: int

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    SENDER_EMAIL: str
    EMAIL_PASSWORD: str

    model_config = SettingsConfigDict(
        env_file=".env"
    )

settings = Settings()


def get_db_url():
    return (
        f"postgresql+asyncpg://"
        f"{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/"
        f"{settings.POSTGRES_NAME}"
    )


def get_sync_db_url():
    return (
        f"postgresql+psycopg2://"
        f"{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@"
        f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/"
        f"{settings.POSTGRES_NAME}"
    )