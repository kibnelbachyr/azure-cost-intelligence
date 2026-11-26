# Threat model — trusted-operator prototype
Baseline 2f34f354ced49f4fb82064bbb50564ca1b867df4. Assets: credentials, subscription and resource metadata, financial evidence, model context, CI integrity and operator decisions. Trust boundaries: operator/configuration to process; model to local dispatcher; local process to Azure management and Foundry endpoints; repository to CI/package supply chain. Model output and provider metadata are untrusted. The local operator and host are trusted; malicious local code and multi-tenant hosting are outside supported scope.

| Threat | Existing control / evidence | Residual risk and disposition |
| --- | --- | --- |
| Prompt injection in question or resource labels | Local allowlist, schema checks, duplicate ID rejection, adversarial scripted evaluation | Model can still produce false or unsafe narrative; human review mandatory. No injection resistance claim. |
| Cross-subscription access | Handler rejects mismatched subscription; Graph configured scope; synthetic request traces | Direct service calls bypass handler; RBAC not verified live. No multi-user use. |
| Unauthorized changes | Seven read-oriented tools; provisioning script disabled; no mutation tool | Overprivileged identity remains possible; operator must use least privilege. Never execute narrative automatically. |
| Financial tampering or misleading totals | Explicit currency/period, unknown savings, partial-result rejection, regression tests | Provider truth and final prose not independently verified; reconcile with billing source. |
| Data disclosure | Explicit endpoint syntax, secret representation suppression, sanitized errors, store=false requested | Resource names, IDs, tags, spend and questions may be transmitted to Foundry; retention, residency and redaction not guaranteed. Live data requires classification and approval. |
| Denial of service / cost | Five model rounds, eight tool calls, byte/token bounds, provider timeout, CI timeout | SDK retries/pagination and response materialization can exceed local budgets; no total deadline or spend cap. No unattended use. |
| Credential exposure | Explicit identity, ignored .env/key files, no developer fallback | Local environment, logs, history and copies remain exposure surfaces; secret scanning and historical containment not established by ignore rules. |
| Supply chain / CI tampering | Exact package versions, strict advisory audit, pinned action SHAs, read-only CI token, no checkout credential persistence, active strict main rule | No artifact hash lock, OS/audit dependency coverage or independent approval requirement; audit is point-in-time. |
| Terminal/social engineering | Advisory label and human review | Untrusted narrative may contain deceptive links or terminal control characters; avoid sharing or executing output; terminal sanitization requires verification before wider use. |

## Operational boundaries
No public service, unattended remediation, actual savings guarantee or sensitive tenant use. No live request without authorization, approved data classification and budget. Suspected disclosure: stop execution, revoke/rotate affected credentials through owner, preserve sanitized evidence privately and assess downstream copies. Do not post credentials or tenant data in public issues. See SECURITY.md for reporting.
