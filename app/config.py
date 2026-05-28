import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "ARCA Gym")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./arcagym.db")
    enable_external_sources: bool = os.getenv("ENABLE_EXTERNAL_SOURCES", "false").lower() == "true"


settings = Settings()
