"""
Central configuration loaded from environment variables / .env file.
Copy .env.example to .env and fill in your values before running.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, model_validator, field_validator
import re
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Azure identity ────────────────────────────────────────────────────────
    azure_tenant_id: str = Field(..., description="Azure Active Directory tenant ID")
    azure_subscription_id: str = Field(..., description="Default subscription to analyse")
    azure_client_id: Optional[str] = Field(None, description="Service principal client ID")
    azure_client_secret: Optional[str] = Field(None, description="Service principal secret")
    use_managed_identity: bool = Field(False, description="Use Managed Identity instead of SP")

    # ── Azure AI Foundry ──────────────────────────────────────────────────────
    azure_ai_project_endpoint: Optional[str] = Field(
        None, description="HTTPS Microsoft Foundry project endpoint (public Azure cloud)"
    )

    @field_validator("azure_ai_project_endpoint")
    @classmethod
    def _validate_endpoint(cls, value):
        if value is not None and not re.fullmatch(
            r"https://[a-zA-Z0-9-]+\.services\.ai\.azure\.com/api/projects/[a-zA-Z0-9_-]+/?",
            value,
        ):
            raise ValueError("Use a public Azure Foundry project HTTPS endpoint.")
        return value.rstrip("/") if value else value
    azure_openai_deployment_name: str = Field(
        "gpt-4o",
        description="Model deployment name in your AI Foundry project",
    )

    # ── Cost analysis defaults ────────────────────────────────────────────────
    default_cost_lookback_days: int = Field(30, ge=1, le=365)
    top_cost_drivers_limit: int = Field(10, ge=1, le=50)

    @model_validator(mode="after")
    def _validate_identity(self) -> "Settings":
        if not self.use_managed_identity:
            if not self.azure_client_id or not self.azure_client_secret:
                raise ValueError(
                    "Set USE_MANAGED_IDENTITY=true or provide "
                    "AZURE_CLIENT_ID and AZURE_CLIENT_SECRET."
                )
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
