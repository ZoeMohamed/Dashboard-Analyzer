"""Stable domain errors that are safe to map to API responses and run states."""

from __future__ import annotations

from app.contracts import ErrorCode


class DomainError(RuntimeError):
    code = ErrorCode.INVALID_PAYLOAD


class NotConfiguredError(DomainError):
    code = ErrorCode.NOT_CONFIGURED


class BudgetExhaustedError(DomainError):
    code = ErrorCode.BUDGET_EXHAUSTED


class ProviderTimeoutError(DomainError):
    code = ErrorCode.PROVIDER_TIMEOUT


class ProviderPermissionError(DomainError):
    code = ErrorCode.PROVIDER_PERMISSION


class InvalidProviderPayloadError(DomainError):
    code = ErrorCode.INVALID_PAYLOAD


class ProviderError(DomainError):
    code = ErrorCode.PROVIDER_ERROR


class DatabaseTimeoutError(DomainError):
    code = ErrorCode.DATABASE_TIMEOUT


class AlreadyRunningError(DomainError):
    code = ErrorCode.ALREADY_RUNNING


class TopicNotFoundError(DomainError):
    pass


class TopicLimitError(DomainError):
    pass
