"""Endpoint-based Foundry model provider; no hosted agent mutation."""
from __future__ import annotations

from .prompts import SYSTEM_PROMPT
from .runner import MAX_OUTPUT_TOKENS


class FoundryResponsesProvider:
    def __init__(self, project, *, model: str, credential=None, http_client=None):
        self._project = project
        self._credential = credential
        self._model = model
        kwargs = {"timeout": 30.0, "max_retries": 0}
        if http_client is not None:
            kwargs["http_client"] = http_client
        self._client = project.get_openai_client(**kwargs)

    @classmethod
    def from_settings(cls):
        from azure.ai.projects import AIProjectClient
        from azure.identity import ManagedIdentityCredential, ClientSecretCredential
        from ..config import get_settings

        cfg = get_settings()
        if not cfg.azure_ai_project_endpoint:
            raise ValueError("Set AZURE_AI_PROJECT_ENDPOINT to the Foundry project endpoint.")
        credential = (
            ManagedIdentityCredential(client_id=cfg.azure_client_id)
            if cfg.use_managed_identity and cfg.azure_client_id
            else ManagedIdentityCredential()
            if cfg.use_managed_identity
            else ClientSecretCredential(cfg.azure_tenant_id, cfg.azure_client_id, cfg.azure_client_secret)
        )
        project = AIProjectClient(endpoint=cfg.azure_ai_project_endpoint, credential=credential)
        try:
            return cls(project, model=cfg.azure_openai_deployment_name, credential=credential)
        except Exception:
            project.close()
            credential.close()
            raise

    def respond(self, items: list[dict], tools: list[dict]) -> dict:
        response = self._client.responses.create(
            model=self._model,
            instructions=SYSTEM_PROMPT,
            input=items,
            tools=tools,
            parallel_tool_calls=False,
            store=False,
            include=["reasoning.encrypted_content"],
            max_output_tokens=MAX_OUTPUT_TOKENS,
        )
        return {
            "status": response.status,
            "output": [item.model_dump(mode="json", exclude_none=True) for item in response.output],
        }

    def close(self):
        try:
            self._client.close()
        finally:
            try:
                self._project.close()
            finally:
                if self._credential is not None:
                    self._credential.close()
