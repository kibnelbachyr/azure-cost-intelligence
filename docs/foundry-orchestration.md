# ADR — client-managed Foundry Responses orchestration

## Decision

Use endpoint-based AIProjectClient.get_openai_client() and the Responses API with model deployment name, instead of remote agent CRUD and classic thread/run polling. The application supplies SYSTEM_PROMPT on every model request. No stale hosted agent reuse, creation, deletion or migration. Direct versions: azure-ai-projects 2.11.0 and openai 3.59.0. See [dependency security](dependency-security.md) for the application version lock and advisory gate. The live composition root shares one explicit credential across the four clients.

Each question starts an independent context. Replay all output items (including encrypted reasoning if returned) and function results within the question; store=false is requested, not a guarantee of zero provider retention. No previous_response_id or cross-question history. Interactive mode deliberately requires restating scope.

## Authority and failure boundaries

Only the seven existing read-oriented tools are allowed. Validate the whole batch of tool requests before any dispatch: exact allowlist, unique IDs, JSON object with no duplicate keys, required/allowed fields, primitive types, enums and input limits. No dynamic tool registration or write operations. ToolHandlers still enforces configured subscription scope. Tool results/resource metadata are untrusted data; prompt guidance is not a security boundary.

At most 5 model requests and 8 tool calls per question, 4 KiB arguments/question, 32 KiB per tool result, 128 KiB serialized context, 2,000 requested output tokens per response. Provider SDK timeout 30s and no automatic model retries. These are application-level limits, not a total wall-clock/token/cost cap or a bound on all underlying management SDK retries/pages. Unsupported output types, duplicate IDs, invalid arguments, tool errors, incomplete/failed status, missing final text and oversized data abort without a stale answer. Provider errors are sanitized. No quantitative narrative verification; the model can still make inaccurate statements, so human review remains required.

CLI and example entrypoints require --allow-live; legacy automatic provisioning is disabled. Library use of default AgentRunner is a live-capable path; inject both provider and dispatcher for offline use.

## Verification

Standard-library deterministic fixtures exercise orchestration, malformed calls and failures. Installed-SDK tests use the real AIProjectClient and OpenAI client with a fictional credential and httpx2.MockTransport to inspect actual serialized Responses requests and deserialize synthetic responses. Socket/DNS guards supplement the mock transport; not an OS network sandbox. CI installs dependencies from PyPI, no Azure calls. Neither live inference, model quality, model availability, actual financial accuracy nor provider retention is validated.

## References

- [Microsoft Foundry SDK](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-projects-readme)
- [Responses API](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses)
