# Financial evidence contract — experimental MVP

## Trust and scope

The recommendation engine is deterministic and advisory only. A single configured subscription is supported. The handler rejects requests for another subscription before calling any service, and omits subscription-wide idle scans from resource-group correlation. The offline service injection path is tested with fictional objects; it is not a live Azure authorization boundary.

## Actual cost versus savings

Actual Cost rows must contain an explicit consistent three-letter currency code and finite numeric Cost. Empty results return unknown total/currency. Missing/mixed currency, invalid amounts and detected next-page links fail closed rather than reporting a partial or fabricated total. Negative actual cost can represent credits. Decimal aggregation precedes JSON numeric conversion; this is not an accounting ledger. SDK field names, paging and cost semantics require real provider validation.

Monthly savings require explicit nonnegative finite amount and currency. The current Advisor adapter retains generic savingsAmount and currency as provider evidence with unknown period; it never guesses a monthly interval. Resource Graph observations carry no verified price, so idle VM, disk and public IP savings are unknown. No fixed USD price, FX conversion, realized savings or annualization is inferred.

Ranking scores are available only for explicit monthly inputs in the cost summary's reporting currency. Unknown and other-currency estimates remain visible but unranked by money. Distinct opportunities affecting the same resource may overlap; aggregate potential savings is deliberately null. Counts by currency describe evidence coverage, not a financial total. Heuristic quick wins still require review. All recommendations are advisory, not execution authorization.

Spend-driver observations require matching scope, dates and currency. The engine recomputes share from actual total and driver cost; a spend observation is not a savings claim.

## Reproduction and limits

Run `python -m unittest discover -s tests -v` on Python 3.11; no credentials, SDK installation or real service required for this suite. It exercises pure financial helpers, engine and injected tool handlers. It does not validate actual Azure SDK responses, network security, authorization or LLM adherence. The current client-managed Responses loop sends instructions on every request and does not reuse or modify existing hosted agents. Live SDK compatibility, dependency locking/audit, provider pricing/period mapping and a real evaluation remain separate gates. No license or publication status is changed.

The separate [SDK contract suite](sdk-contracts.md) exercises real installed management SDKs with synthetic HTTP responses, not Azure services. Cost and Resource Graph pagination are rejected rather than silently truncated. Foundry orchestration has a separate synthetic contract suite; full dependency audit remains open.
