from __future__ import annotations

import sys
from datetime import datetime
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.models.schema import MLModel
from backend.app.schemas.health import (
    ChampionModelHealthItem,
    ChampionModelHealthResponse,
    HealthResponse,
    ReadinessResponse,
    VersionResponse,
)

settings = get_settings()


class HealthService:

    @staticmethod
    def get_health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.PROJECT_NAME,
            version=settings.VERSION,
        )

    @staticmethod
    def check_readiness(db: Session) -> ReadinessResponse:
        # Check database connectivity
        db_status = "connected"
        try:
            db.execute(text("SELECT 1"))
        except Exception:
            db_status = "degraded"

        # Redis is intentionally not configured (infrastructure constraint: Redis/Celery not implemented)
        redis_status = "not_configured"

        overall = "ready" if db_status == "connected" else "not_ready"
        return ReadinessResponse(
            status=overall,
            database=db_status,
            redis=redis_status,
            timestamp=datetime.utcnow(),
        )

    @staticmethod
    def get_version_info() -> VersionResponse:
        return VersionResponse(
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            api_version=settings.API_V1_STR,
        )

    @staticmethod
    def get_champion_models_health(db: Session) -> ChampionModelHealthResponse:
        import os
        models = db.execute(
            select(MLModel).where(MLModel.is_champion.is_(True))
        ).scalars().all()

        items = []
        all_healthy = True
        for m in models:
            # Check model artifact on disk if artifact_dir is present
            artifact_exists = True
            if m.artifact_dir and not os.path.exists(m.artifact_dir):
                artifact_exists = False

            model_st = m.model_status or ("DEPLOYED" if artifact_exists else "DEGRADED")
            if not artifact_exists or model_st == "DEGRADED":
                all_healthy = False

            items.append(
                ChampionModelHealthItem(
                    model_type=m.model_type.value,
                    version=m.version,
                    is_champion=m.is_champion,
                    status=model_st,
                )
            )

        return ChampionModelHealthResponse(
            models=items,
            all_healthy=all_healthy if models else True,
        )
