"""Explicit credential selection without developer-credential fallback."""
from azure.identity import ClientSecretCredential, ManagedIdentityCredential
from .settings import Settings


def build_credential(settings: Settings):
    if settings.use_managed_identity:
        if settings.azure_client_id:
            return ManagedIdentityCredential(client_id=settings.azure_client_id)
        return ManagedIdentityCredential()
    return ClientSecretCredential(
        tenant_id=settings.azure_tenant_id,
        client_id=settings.azure_client_id,
        client_secret=settings.azure_client_secret.get_secret_value(),
    )
