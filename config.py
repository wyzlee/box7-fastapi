# config.py
from pydantic import BaseSettings
from typing import List

class Settings(BaseSettings):
    allowed_origins: List[str] = ["http://localhost:3000"]  # Valeur par défaut
    allowed_methods: List[str] = ["GET", "POST", "PUT", "DELETE"]
    allowed_headers: List[str] = ["Authorization", "Content-Type"]

    class Config:
        env_file = ".env"  # Charge les variables depuis le fichier .env
        env_file_encoding = "utf-8"

# Charge les variables d'environnement
settings = Settings()