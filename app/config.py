from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    bot_token: str = Field(..., env="BOT_TOKEN")

    # Эти поля не обязательны для SQLite, но чтобы не было ошибок
    db_host: str = Field("localhost", env="DB_HOST")
    db_port: int = Field(5432, env="DB_PORT")
    db_user: str = Field("postgres", env="DB_USER")
    db_password: str = Field("postgres", env="DB_PASSWORD")
    db_name: str = Field("furniture_bot", env="DB_NAME")

    @property
    def db_url(self) -> str:
        return "sqlite+aiosqlite:///./furniture.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Игнорируем лишние поля


settings = Settings()