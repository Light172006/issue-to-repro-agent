# v0.1 adversarial test plan

| Risk | Module | Probe |
|---|---|---|
| Budget overflow, rounding, concurrent ledger use, invalid usage and unsafe errors | llm | Fake-only boundary, parallel and malformed-usage tests; inspect traces for sentinel secrets |
| URL handling, malformed API data, pagination, cache corruption and write failures | github | Offline mocked HTTP responses and filesystem faults |
| Cleanup, resource/network settings, binary/large output and timeouts | sandbox | Mock Docker; opt-in marked live Docker checks with bounded workloads |
| Ref resolution, checkout integrity, setup failures and metadata | envbuilder | Mock GitHub/Docker; test input validation and atomic writes |
| Configuration and offline operation | cross-cutting | Invalid config and full offline pytest suite; no real model calls |

Real Docker, actual GitHub rate limits, provider billing, destructive load and network isolation require a separately equipped environment; no dangerous workloads run on the host. Existing v0.1 supported behavior determines expected results; no new features are implied by unsupported URL or version forms.
