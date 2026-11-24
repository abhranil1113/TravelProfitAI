from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    redis: str
    timestamp: datetime


class VersionResponse(BaseModel):
    version: str
    environment: str
    python_version: str
    api_version: str


class ChampionModelHealthItem(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    model_type: str
    version: str
    is_champion: bool
    status: str


class ChampionModelHealthResponse(BaseModel):
    models: List[ChampionModelHealthItem]
    all_healthy: bool
