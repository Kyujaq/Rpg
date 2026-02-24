from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENGINE_KEY: str = "dev-secret-key"
    DATABASE_URL: str = "sqlite:///./ttrpg.db"
    AI_ONLY_STREAK_LIMIT: int = 3
    AI_PLAYER_COOLDOWN_SECONDS: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
