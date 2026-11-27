from __future__ import annotations

import os
from typing import Any, List, Optional
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "TBO InventoryIQ API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = "sqlite:///./inventoryiq.db"
    DATABASE_TEST_URL: str = "sqlite:///:memory:"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800
    DB_ECHO: bool = False
    
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
    FX_RATE_MAX_AGE_DAYS: int = 7

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

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        if self.ENVIRONMENT.lower() == "production":
            insecure_defaults = [
                "tbo_inventoryiq_super_secret_jwt_key_2026_sabuj_sangha",
                "secret",
                "changeme",
                "default",
            ]
            if self.SECRET_KEY in insecure_defaults or len(self.SECRET_KEY) < 32:
                raise ValueError("Insecure or default SECRET_KEY is not permitted in production. Must be at least 32 characters.")
            if self.WORKER_SECRET_TOKEN in ["tbo_worker_internal_secret_token_sabuj_sangha", "secret", "default"]:
                raise ValueError("Insecure or default WORKER_SECRET_TOKEN is not permitted in production.")
            if "*" in self.BACKEND_CORS_ORIGINS:
                raise ValueError("Wildcard '*' in BACKEND_CORS_ORIGINS is not permitted in production.")
            if self.DATABASE_URL.strip().lower().startswith("sqlite"):
                raise ValueError("SQLite DATABASE_URL is not permitted in production.")
            if "://" not in self.DATABASE_URL:
                raise ValueError("DATABASE_URL must include a valid database scheme.")
            if len(self.WORKER_SECRET_TOKEN) < 32:
                raise ValueError("WORKER_SECRET_TOKEN must be at least 32 characters in production.")
            if self.SOCKET_IO_CORS_ORIGINS == "*" or (isinstance(self.SOCKET_IO_CORS_ORIGINS, list) and "*" in self.SOCKET_IO_CORS_ORIGINS):
                raise ValueError("Wildcard '*' in SOCKET_IO_CORS_ORIGINS is not permitted in production.")
        return self
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()


def get_settings() -> Settings:
    return settings
