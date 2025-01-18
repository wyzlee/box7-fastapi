from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    # Existing settings
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "https://box7-react.onrender.com"
    ]
    allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    allowed_headers: List[str] = [
        "Accept", 
        "Authorization", 
        "Content-Type", 
        "X-Requested-With",
        "X-CSRF-Token",
        "Origin"
    ]

    # Add these new settings
    api_domain: Optional[str] = "localhost"  # Pour le développement local
    cookie_domain: Optional[str] = None  # Laisser à None en dev pour que le navigateur le gère
    cors_expose_headers: List[str] = ["Set-Cookie"]

    # Your existing settings...
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    secret_key: Optional[str] = None
    access_token_expire_minutes: Optional[int] = 30
    local_llm_url: Optional[str] = None
    frontend_url: Optional[str] = None
    database_url: Optional[str] = None
    debug: Optional[bool] = False
    environment: Optional[str] = "development"  # Changed to development by default

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # Add a method to get the correct domain based on environment
    def get_cookie_domain(self):
        if self.environment == "production":
            return self.api_domain
        return None  # En développement, laissez le navigateur gérer le domaine

settings = Settings()