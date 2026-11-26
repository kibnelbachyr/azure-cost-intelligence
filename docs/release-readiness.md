# Experimental v0.1.0 release gate
Status: v0.1.0 experimental pre-release published by owner on 2026-11-26. Release engineering complete for experimental scope; broader security containment and historical review remain unresolved. This record does not certify those gates. See [frozen evidence](evidence/v0.1.0.md).

## Evidence baseline
- PR #7 merged: 2f34f354ced49f4fb82064bbb50564ca1b867df4.
- Main CI [45904185693](https://github.com/kibnelbachyr/azure-cost-intelligence/actions/runs/45904185693): all steps successful, including regression and SDK suites, conformance evaluation, lock verification, pip check, CLI help and strict advisory audit.
- Portfolio issue [#16](https://github.com/kibnelbachyr/engineering-portfolio/issues/16) records 48 tests, 19 scenarios, 57 executions, 507 checks and 43 locked versions. These are synthetic development regressions, not live quality metrics.
- Active [main ruleset](https://github.com/kibnelbachyr/azure-cost-intelligence/rules/28194823): PR required, strict required test check, deletion/non-fast-forward blocked, no bypass actors, zero required approving reviews. Owner review is a process gate, not enforced independent approval.

## Acceptance checklist
- [x] Architecture and trust boundaries documented against baseline.
- [x] Threat model and residual risks documented.
- [x] Baseline CI and repository main rule inspected.
- [x] Readiness PR #8 and licensing PR #9 merged; candidate main CI 45905332238 successful.
- [ ] Review current tree, all relevant Git refs/history, fixtures, examples, Actions logs/artifacts and release assets for secrets, employer/customer IP, third-party provenance and branding. Record sanitized scope/results privately; resolve findings.
- [ ] Owner confirms historical credential containment in portfolio #13 and rights review in #3/#16; no assumption of erasure.
- [x] Owner confirms independent publication rights for code, documentation and synthetic fixtures and approves Apache-2.0 (2026-11-26). License included in this increment; release authorization remains separate.
- [x] Owner approves experimental release with documented prototype limitations, including unverified narrative, no live RBAC, unbounded downstream runtime and potential metadata disclosure.
- [x] Capture exact candidate SHA, CI run and report digest; original archive downloaded and digest verified; durable aggregate evidence recorded in [evidence/v0.1.0.md](evidence/v0.1.0.md).
- [x] Owner explicitly authorized and manually published v0.1.0; tag and release target verified; release notes match approved scope. Bounded source scan does not certify absence of secrets.

## Repository security assessment
Current tree includes ignored local .env/key files, placeholder configuration, synthetic fixtures and one read-only CI workflow with SHA-pinned actions. There was no LICENSE file at reviewed baseline; Apache-2.0 added in the owner-approved licensing increment. Repository is public and owner rights confirmed; no further promotion pending broader containment clearance. Current-tree inventory and selected source review are not a complete secret scan; historical refs, secret scanning settings, alerts, logs and artifacts have not been exhaustively inspected. Dependency audit covers known advisories for locked application packages only. Do not claim full repository clearance.

## Release decision
The published version may be described only as an experimental, advisory-only, single-subscription prototype with reproducible synthetic evidence. The approved tag is frozen; this document does not authorize new releases, license changes or cloud execution. Live evaluation, deployment and production claims require a separate decision, synthetic/approved data, budget, held-out evaluation and operational controls. Remaining containment and historical review gates stay open; no additional promotion until resolved with the owner.
