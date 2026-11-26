# Dependency reproducibility and explicit identity

## Version lock

The complete application package version set comes from [main CI 45901901657](https://github.com/kibnelbachyr/azure-cost-intelligence/actions/runs/45901901657), Python 3.11 on Linux x86_64. requirements.in records direct inputs; requirements.txt installs the pinned set. Management-only inputs are constrained to it. CI uses a fresh venv, installs the lock with --no-deps, verifies exact names and versions (excluding bootstrap pip/setuptools/wheel), runs pip check and all suites. This is a platform-specific version lock, not an artifact-hash lock, reproducible build or guarantee of cross-platform compatibility.

To update: in a fresh Python 3.11 Linux x86_64 venv install requirements.in with normal resolution, run pip check, freeze the resolved versions (exclude bootstrap tooling), review the diff and re-run the exact-install and full CI checks. Review advisory findings and compatibility rather than silently ignoring or downgrading them.

## Advisory gate

The existing required test job runs pip-audit 2.9.0 in a separate venv against the complete pinned application list, using PyPI advisories, with --no-deps, --disable-pip and --strict. Known vulnerabilities or collection failures block the job; no exclusions. Public PyPI access is required. Audit tooling/its dependencies, OS packages, unknown vulnerabilities, code-level defects and artifact authenticity are outside scope. A clean result is time-bound, not a security guarantee.

## Identity and ownership

One validated settings snapshot and one explicit credential are shared across three management clients and Foundry in the default live runner. No DefaultAzureCredential fallback to CLI/developer/environment credentials. Managed identity selects system-assigned without a client ID or user-assigned with the configured ID; a secret in that mode is rejected. Service-principal mode requires tenant ID, client ID and secret. SecretStr and settings repr exclusion reduce accidental disclosure; do not log validation error structures or configuration dumps. Sanitized provider log messages omit raw service details.

The composition root closes owned clients in reverse order and then the credential, including partial initialization failure. Injected clients and credentials remain caller-owned. The unused Advisor refresh mutation helper is removed. Local tool allowlists and Azure RBAC are distinct boundaries. Constructor, configuration and lifecycle tests use fictional values and mocks. No live authentication, role changes or resources tested or created.
