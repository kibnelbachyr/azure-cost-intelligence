# Azure management SDK compatibility — contract suite

## Scope

A pinned direct-version baseline for the three Azure management SDKs: Cost Management 5.0.0, Advisor 9.0.1 and Resource Graph 8.0.1; Azure Identity 1.27.0. This is not a full dependency lock or vulnerability audit. The standard-library tests remain separate from the installed-SDK checks. CI installs packages from PyPI, then executes the synthetic fixture tests with no Azure account, real token or network transport.

```sh
python -m unittest discover -s tests -v
python -m pip install -r requirements-management.txt
python -m pip check
python -m unittest discover -s sdk_tests -v
```

The versioned JSON in sdk_tests/fixtures/provider-responses-v1.json is fabricated from documented REST response shapes, not captured customer data. Real SDK clients serialize requests and deserialize the JSON via a fixture-only RequestsTransport and a fictional credential; direct socket/DNS guards supplement the fixture transport. This is not an OS-level network sandbox. Unexpected requests fail. Tests inspect request scopes, aggregation, dates, grouping, tags, Advisor filter and savings metadata, Resource Graph object arrays and truncation. CI must pass before compatibility is claimed.

## Deliberate limits and decisions

- Cost Management 5.0.0 uses the nested QueryResult.properties envelope and QueryComparisonExpression.values_property constructor. Cost scope uses a leading slash; QueryTimePeriod receives UTC datetimes; "None" is sent explicitly for ungrouped aggregation, not assumed to exist as an SDK enum. Detected partial pages and malformed schemas fail closed.
- Advisor normalizes returned model properties and preserves unknown-period savings. Resource-group filter rejects malformed input.
- Resource Graph explicitly requests object arrays, rejects partial/inconsistent results, and requires a disk to report Unattached and no managedBy before it becomes a candidate. This is a query contract, not verification of real KQL behavior or safety of deletion. No paging is implemented; large results may fail.
- No live credentials, actual billing records, regional prices, provider accuracy, throttling, real authorization, or LLM quality are validated.
- The legacy Foundry runner relies on from_connection_string and older thread/run surfaces. The current endpoint-based SDK requires a separate migration and independent orchestration fixtures. Do not infer compatibility of requirements.txt or live Foundry execution from these management-only checks. No cloud operations or remote agent changes performed.

## Reference contracts

- [Cost Management Query Usage](https://learn.microsoft.com/en-us/rest/api/cost-management/query/usage)
- [QueryTimePeriod](https://learn.microsoft.com/en-us/python/api/azure-mgmt-costmanagement/azure.mgmt.costmanagement.models.querytimeperiod)
- [Advisor recommendations](https://learn.microsoft.com/en-us/rest/api/advisor/recommendations/list)
- [Resource Graph QueryResponse](https://learn.microsoft.com/en-us/python/api/azure-mgmt-resourcegraph/azure.mgmt.resourcegraph.models.queryresponse)
- [Resource Graph paging](https://learn.microsoft.com/en-us/azure/governance/resource-graph/concepts/paging-results)
- [Foundry migration](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/migrate-project)
