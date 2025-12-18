from pydantic_settings import BaseSettings
from pydantic import SecretStr

class Settings(BaseSettings):
    BOT_TOKEN: SecretStr
    OPENAI_API_KEY: SecretStr
    ADMIN_ID: int
    DATABASE_URL: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()