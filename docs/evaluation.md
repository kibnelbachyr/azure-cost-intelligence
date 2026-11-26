# FinOps conformance evaluation v1

The versioned scenario manifest is hand-authored from fictional inputs and expected outcomes. No tenant data, captured LLM output or live Azure requests. The benchmark reuses provider-shaped HTTP fixtures and adds overlapping recommendations, empty cost results and an adversarial resource label. Eighteen full application-path scenarios exercise the real Foundry/OpenAI SDK, bounded orchestration, tool handlers, actual management SDKs and financial logic through synthetic transports. One explicitly separate normalized-engine-only scenario checks monthly ranking because the Advisor adapter does not establish monthly periods from generic savingsAmount.

## Reproduce

Use the locked application venv, then run:

```sh
python -m evaluation.run --repeat 3 --output evaluation-report.json
```

The report records fixture SHA-256s, scenario categories, each named assertion, outcome, repetition digest and aggregate counts. All assertions, all cases and identical per-case observation digests across three fresh repetitions are required (no weighted score, no ignored failures). Expected blocked cases are passes only when the specified error, request sequence/count, no final answer and fixture consumption match. A synthetic answer is a transport sentinel, not proof of factual narrative. CI uploads the JSON report from the required test job, including on failed evaluation if a report exists.

## Measures

- Financial: exact actual-cost total including credits, explicit currency/window, service shares, tag query, correlated evidence, no aggregate overlapping savings, unknown price/period, empty data.
- Scope: resource-group correlation excludes broad Graph scans; foreign subscription rejected before Azure request.
- Data integrity: malformed/mixed/partial cost rows and truncated Graph fail closed.
- Adversarial: unallowlisted mutation, invalid batch, duplicate JSON keys, duplicate call IDs, scripted malicious follow-up after untrusted label, incomplete model response.
- Normalized engine only: ranking within explicit reporting currency, unknown estimates and destructive-risk classification.

The provider is scripted, not a live LLM. The injection case proves that an attempted unallowlisted call is blocked, not that a real model resists injection or produces grounded text. No quantitative live-model accuracy, latency, realized savings, actual Azure permissions, KQL behavior or cost is measured. The tests use synthetic transports and socket/DNS guards, not an OS sandbox. Dates fixed to a fictional period. All scenarios are visible development regressions, not an independent holdout.

## Future live evaluation (separate authorization)

Before live evaluation, freeze a held-out version and model deployment/configuration, approve synthetic-only data and a spending cap, record per-case tool traces, status, tokens and latency, and manually score numeric/currency/period fidelity, evidence citation, unknown handling, risk and authorization language. Treat fabricated amounts, unauthorized action guidance and cross-scope access as hard failures. Compare model behavior across repetitions; publish actual scores only when executed. Live model quality is null in the offline report.
