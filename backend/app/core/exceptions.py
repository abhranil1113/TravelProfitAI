from __future__ import annotations

from typing import Any, Optional
from fastapi import HTTPException, status


class AppBaseException(HTTPException):
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = "ERROR",
        headers: dict[str, str] | None = None,
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code


class EntityNotFoundError(AppBaseException):
    def __init__(self, entity_name: str, identifier: Any):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{entity_name} with identifier '{identifier}' was not found.",
            error_code="NOT_FOUND",
        )


class AuthenticationError(AppBaseException):
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="AUTHENTICATION_FAILED",
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionDeniedError(AppBaseException):
    def __init__(self, detail: str = "Insufficient permissions to perform this operation"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="PERMISSION_DENIED",
        )


class ConflictError(AppBaseException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code="CONFLICT",
        )


class FinancialConstraintError(AppBaseException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="FINANCIAL_CONSTRAINT_VIOLATION",
        )


class InvalidStateTransitionError(AppBaseException):
    def __init__(self, current_status: str, target_status: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transition from state '{current_status}' to '{target_status}'.",
            error_code="INVALID_STATE_TRANSITION",
        )


class BadRequestException(AppBaseException):
    def __init__(self, detail: str, error_code: str = "BAD_REQUEST"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code=error_code,
        )


class NotFoundException(AppBaseException):
    def __init__(self, detail: str, error_code: str = "NOT_FOUND"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
            error_code=error_code,
        )


class ConflictException(AppBaseException):
    def __init__(self, detail: str, error_code: str = "CONFLICT"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
            error_code=error_code,
        )


BadRequestError = BadRequestException
NotFoundError = NotFoundException
UnauthorizedError = AuthenticationError
ForbiddenError = PermissionDeniedError
UnauthorizedException = AuthenticationError
ForbiddenException = PermissionDeniedError
