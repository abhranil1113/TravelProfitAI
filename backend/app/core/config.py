from __future__ import annotations

import os
from typing import Any, List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "TBO InventoryIQ API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./inventoryiq.db"
    DATABASE_TEST_URL: str = "sqlite:///:memory:"
    
    # Security & Auth
    SECRET_KEY: str = "tbo_inventoryiq_super_secret_jwt_key_2026_sabuj_sangha"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ACTION_TOKEN_EXPIRE_HOURS: int = 24
    WORKER_SECRET_TOKEN: str = "tbo_worker_internal_secret_token_sabuj_sangha"
    
    # Celery & Redis
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # File Storage
    UPLOAD_DIR: str = "data/uploads"
    ARTIFACT_DIR: str = "data/artifacts"
    REPORTS_DIR: str = "data/reports"
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]
    
    # Socket.IO Configuration
    SOCKET_IO_ENABLED: bool = True
    SOCKET_IO_PATH: str = "/socket.io"
    SOCKET_IO_PING_INTERVAL: int = 25
    SOCKET_IO_PING_TIMEOUT: int = 20
    SOCKET_IO_CORS_ORIGINS: Any = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("SOCKET_IO_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_socket_cors(cls, v: Any) -> Any:
        if isinstance(v, str):
            if v.strip() == "*":
                return "*"
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()


def get_settings() -> Settings:
    return settings
