"""Composition root: one explicit identity, one settings snapshot."""
from contextlib import ExitStack
from ..config import get_settings
from ..config.identity import build_credential
from ..services.cost_management import CostManagementService
from ..services.advisor import AdvisorService
from ..services.resource_graph import ResourceGraphService
from ..tools.handlers import ToolHandlers
from .foundry import FoundryResponsesProvider


def build_live_runtime():
    cfg = get_settings()
    if not cfg.azure_ai_project_endpoint:
        raise ValueError("Set AZURE_AI_PROJECT_ENDPOINT before live execution.")
    with ExitStack() as stack:
        credential = build_credential(cfg)
        stack.callback(credential.close)
        cost = CostManagementService(settings=cfg, credential=credential)
        stack.callback(cost.close)
        advisor = AdvisorService(settings=cfg, credential=credential)
        stack.callback(advisor.close)
        graph = ResourceGraphService(settings=cfg, credential=credential)
        stack.callback(graph.close)
        provider = FoundryResponsesProvider.from_settings(settings=cfg, credential=credential)
        stack.callback(provider.close)
        handlers = ToolHandlers(cost=cost, advisor=advisor, graph=graph,
                                subscription_id=cfg.azure_subscription_id)
        return provider, handlers, stack.pop_all()
