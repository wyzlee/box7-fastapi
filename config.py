from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    allowed_origins: List[str] = ["http://localhost:3000"]
    allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    allowed_headers: List[str] = ["Authorization", "Content-Type"]

    # Ajoutez les variables manquantes ici
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    secret_key: Optional[str] = None
    access_token_expire_minutes: Optional[int] = 30
    local_llm_url: Optional[str] = None
    frontend_url: Optional[str] = None
    database_url: Optional[str] = None
    debug: Optional[bool] = False
    environment: Optional[str] = "production"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

settings = Settings()