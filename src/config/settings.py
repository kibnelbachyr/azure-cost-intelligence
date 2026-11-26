"""
Central configuration loaded from environment variables / .env file.
Copy .env.example to .env and fill in your values before running.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, SecretStr, model_validator, field_validator
import re
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    # ── Azure identity ────────────────────────────────────────────────────────
    azure_tenant_id: Optional[str] = Field(None, description="Entra tenant ID for service-principal mode")
    azure_subscription_id: str = Field(..., description="Default subscription to analyse")
    azure_client_id: Optional[str] = Field(None, description="Service principal client ID")
    azure_client_secret: Optional[SecretStr] = Field(None, description="Service principal secret", repr=False)
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
        for name in ("azure_tenant_id", "azure_client_id"):
            value = getattr(self, name)
            if value is not None:
                setattr(self, name, value.strip() or None)
        secret = self.azure_client_secret.get_secret_value() if self.azure_client_secret else ""
        if self.use_managed_identity:
            if secret:
                raise ValueError("Remove AZURE_CLIENT_SECRET in managed identity mode.")
        elif not (self.azure_tenant_id and self.azure_client_id and secret):
            raise ValueError("Service-principal mode requires tenant ID, client ID and secret.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
