# Experimental v0.1.0 release gate
Status: NOT RELEASED / publication blocked pending owner approval.

## Evidence baseline
- PR #7 merged: 2f34f354ced49f4fb82064bbb50564ca1b867df4.
- Main CI [45904185693](https://github.com/kibnelbachyr/azure-cost-intelligence/actions/runs/45904185693): all steps successful, including regression and SDK suites, conformance evaluation, lock verification, pip check, CLI help and strict advisory audit.
- Portfolio issue [#16](https://github.com/kibnelbachyr/engineering-portfolio/issues/16) records 48 tests, 19 scenarios, 57 executions, 507 checks and 43 locked versions. These are synthetic development regressions, not live quality metrics.
- Active [main ruleset](https://github.com/kibnelbachyr/azure-cost-intelligence/rules/28194823): PR required, strict required test check, deletion/non-fast-forward blocked, no bypass actors, zero required approving reviews. Owner review is a process gate, not enforced independent approval.

## Acceptance checklist
- [x] Architecture and trust boundaries documented against baseline.
- [x] Threat model and residual risks documented.
- [x] Baseline CI and repository main rule inspected.
- [ ] Review and merge readiness PR with green required check; re-run main CI at exact candidate commit.
- [ ] Review current tree, all relevant Git refs/history, fixtures, examples, Actions logs/artifacts and release assets for secrets, employer/customer IP, third-party provenance and branding. Record sanitized scope/results privately; resolve findings.
- [ ] Owner confirms historical credential containment in portfolio #13 and rights review in #3/#16; no assumption of erasure.
- [ ] Owner explicitly selects license and approves distribution; add appropriate notices only after decision. Public visibility is not a license or proof of rights.
- [ ] Owner accepts documented prototype limitations, including unverified narrative, no live RBAC, unbounded downstream runtime and potential metadata disclosure.
- [ ] Capture exact candidate SHA, CI run and report digest; retain sanitized evidence before artifact expiration.
- [ ] Owner explicitly authorizes tag/release and publication text; verify no sensitive files or unsupported claims. No automatic publication.

## Repository security assessment
Current tree includes ignored local .env/key files, placeholder configuration, synthetic fixtures and one read-only CI workflow with SHA-pinned actions. There is no LICENSE file at reviewed baseline. Repository is already public; do not broaden distribution until rights are established. Current-tree inventory and selected source review are not a complete secret scan; historical refs, secret scanning settings, alerts, logs and artifacts have not been exhaustively inspected. Dependency audit covers known advisories for locked application packages only. Do not claim full repository clearance.

## Release decision
The candidate may be described only as an experimental, advisory-only, single-subscription prototype with reproducible synthetic evidence. No tag, release, license or cloud execution is authorized by this document. Live evaluation, deployment and production claims require a separate decision, synthetic/approved data, budget, held-out evaluation and operational controls. If any publication gate fails, retain work without promoting it and resolve with the owner.
