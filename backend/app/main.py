from __future__ import annotations

import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.router import api_router
from backend.app.core.config import get_settings
from backend.app.core.exceptions import AppBaseException
from backend.app.core.socket_manager import socket_manager

settings = get_settings()
logger = logging.getLogger("tbo_inventoryiq")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# Custom exception handler
@app.exception_handler(AppBaseException)
async def app_exception_handler(request: Request, exc: AppBaseException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "detail": exc.detail,
        },
        headers=exc.headers,
    )


# Health routes directly on root and under v1
@app.get("/health", tags=["Health"])
def root_health():
    return {"status": "ok", "service": settings.PROJECT_NAME, "version": settings.VERSION}


# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Socket.IO Real-Time Engine Mount
if settings.SOCKET_IO_ENABLED:
    app.mount(settings.SOCKET_IO_PATH, socket_manager.asgi_app)
    logger.info("Socket.IO real-time engine mounted at %s", settings.SOCKET_IO_PATH)


@app.on_event("startup")
async def startup_event():
    try:
        import asyncio
        from backend.app.services.notification_service import NotificationService
        NotificationService.set_main_loop(asyncio.get_running_loop())
        logger.info("NotificationService main event loop registered on startup.")
    except Exception as e:
        logger.warning("Could not set main loop on startup: %s", e)


@app.on_event("shutdown")
async def shutdown_socket_manager():
    if settings.SOCKET_IO_ENABLED:
        await socket_manager.shutdown()

