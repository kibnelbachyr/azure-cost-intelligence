"""Credential selection and ownership with fictional values, no token acquisition."""
import unittest
from unittest.mock import Mock, patch
from pydantic import ValidationError
from src.config.settings import Settings
from src.config.identity import build_credential
from src.agent import runtime
from src.agent.foundry import FoundryResponsesProvider
from src.services.cost_management import CostManagementService
from src.services.advisor import AdvisorService
from src.services.resource_graph import ResourceGraphService

ENDPOINT = "https://example.services.ai.azure.com/api/projects/demo"


def settings(**kwargs):
    return Settings(_env_file=None, azure_subscription_id="demo", **kwargs)


class IdentityTests(unittest.TestCase):
    def test_system_assigned_has_no_fallback_or_client_id(self):
        cfg = settings(use_managed_identity=True)
        with patch("src.config.identity.ManagedIdentityCredential") as mi, patch("src.config.identity.ClientSecretCredential") as sp:
            self.assertIs(build_credential(cfg), mi.return_value)
            mi.assert_called_once_with()
            sp.assert_not_called()

    def test_user_assigned_client_id(self):
        cfg = settings(use_managed_identity=True, azure_client_id="fictional-mi")
        with patch("src.config.identity.ManagedIdentityCredential") as mi:
            build_credential(cfg)
            mi.assert_called_once_with(client_id="fictional-mi")

    def test_service_principal_and_secret_repr(self):
        cfg = settings(use_managed_identity=False, azure_tenant_id="fictional-tenant",
                       azure_client_id="fictional-client", azure_client_secret="fictional-secret-value")
        self.assertNotIn("fictional-secret-value", repr(cfg))
        with patch("src.config.identity.ClientSecretCredential") as sp, patch("src.config.identity.ManagedIdentityCredential") as mi:
            build_credential(cfg)
            sp.assert_called_once_with(tenant_id="fictional-tenant", client_id="fictional-client",
                                       client_secret="fictional-secret-value")
            mi.assert_not_called()

    def test_invalid_identity_modes_fail_before_construction(self):
        with self.assertRaises(ValidationError):
            settings(use_managed_identity=True, azure_client_secret="fictional-secret")
        with self.assertRaises(ValidationError):
            settings(use_managed_identity=False, azure_client_id="fictional-client")
        with self.assertRaises(ValidationError):
            settings(use_managed_identity=False, azure_tenant_id="fictional-tenant",
                     azure_client_id=" ", azure_client_secret="fictional-secret")

    def test_all_management_adapters_use_explicit_settings_and_ownership(self):
        cfg = settings(use_managed_identity=True)
        for service, module, client_name in [
            (CostManagementService, "cost_management", "CostManagementClient"),
            (AdvisorService, "advisor", "AdvisorManagementClient"),
            (ResourceGraphService, "resource_graph", "ResourceGraphClient"),
        ]:
            with self.subTest(service=service.__name__):
                prefix = "src.services." + module + "."
                with patch(prefix+"build_credential") as factory, patch(prefix+client_name) as client:
                    instance = service(settings=cfg)
                    factory.assert_called_once_with(cfg)
                    self.assertIs(client.call_args.kwargs["credential"], factory.return_value)
                    instance.close()
                    client.return_value.close.assert_called_once_with()
                    factory.return_value.close.assert_called_once_with()
                with patch(prefix+"build_credential") as factory, patch(prefix+client_name) as client:
                    credential = Mock()
                    instance = service(settings=cfg, credential=credential)
                    factory.assert_not_called()
                    self.assertIs(client.call_args.kwargs["credential"], credential)
                    instance.close()
                    client.return_value.close.assert_called_once_with()
                    credential.close.assert_not_called()
                injected = Mock()
                service(settings=cfg, client=injected).close()
                injected.close.assert_not_called()

    def test_foundry_borrows_shared_credential(self):
        cfg = settings(use_managed_identity=True, azure_ai_project_endpoint=ENDPOINT)
        credential = Mock()
        with patch("azure.ai.projects.AIProjectClient") as project, patch("src.config.identity.build_credential") as factory:
            provider = FoundryResponsesProvider.from_settings(settings=cfg, credential=credential)
            project.assert_called_once_with(endpoint=ENDPOINT, credential=credential)
            factory.assert_not_called()
            provider.close()
            project.return_value.get_openai_client.return_value.close.assert_called_once_with()
            project.return_value.close.assert_called_once_with()
            credential.close.assert_not_called()

    def test_composition_shares_one_identity_and_closes_reverse_order(self):
        cfg = settings(use_managed_identity=True, azure_ai_project_endpoint=ENDPOINT)
        order = []
        credential = Mock()
        credential.close.side_effect = lambda: order.append("credential")
        with patch.object(runtime,"get_settings",return_value=cfg), patch.object(runtime,"build_credential",return_value=credential) as factory, patch.object(runtime,"CostManagementService") as cost, patch.object(runtime,"AdvisorService") as advisor, patch.object(runtime,"ResourceGraphService") as graph, patch.object(runtime,"FoundryResponsesProvider") as provider:
            for item,name in [(cost,"cost"),(advisor,"advisor"),(graph,"graph")]:
                item.return_value.close.side_effect = lambda n=name: order.append(n)
            provider.from_settings.return_value.close.side_effect = lambda: order.append("provider")
            _, _, stack = runtime.build_live_runtime()
            factory.assert_called_once_with(cfg)
            for item in (cost,advisor,graph):
                item.assert_called_once_with(settings=cfg,credential=credential)
            provider.from_settings.assert_called_once_with(settings=cfg,credential=credential)
            stack.close()
            self.assertEqual(order,["provider","graph","advisor","cost","credential"])

    def test_partial_initialization_closes_prior_resources(self):
        cfg = settings(use_managed_identity=True, azure_ai_project_endpoint=ENDPOINT)
        credential = Mock()
        with patch.object(runtime,"get_settings",return_value=cfg), patch.object(runtime,"build_credential",return_value=credential), patch.object(runtime,"CostManagementService") as cost, patch.object(runtime,"AdvisorService",side_effect=RuntimeError("synthetic failure")):
            with self.assertRaises(RuntimeError):
                runtime.build_live_runtime()
            cost.return_value.close.assert_called_once_with()
            credential.close.assert_called_once_with()
