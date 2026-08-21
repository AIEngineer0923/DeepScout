"""Explicit deployment modes. Hosted never silently degrades to local."""

from __future__ import annotations

from enum import StrEnum
from uuid import UUID

LOCAL_SYSTEM_PRINCIPAL_ID = UUID("00000000-0000-4000-a000-000000000001")


class DeploymentMode(StrEnum):
    LOCAL = "local"
    HOSTED = "hosted"


class PrincipalKind(StrEnum):
    LOCAL_SYSTEM = "local_system"
    USER = "user"


class CredentialProvider(StrEnum):
    GOOGLE = "google"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    TAVILY = "tavily"
    LANGSMITH = "langsmith"


class CredentialStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    INVALID = "invalid"
    UPDATE_REQUIRED = "update_required"
    DISABLED = "disabled"
