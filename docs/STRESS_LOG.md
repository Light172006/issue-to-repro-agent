# Stress test log

## 2026-10-31 — C1 (in progress, not passed)

- Ruff 0.17.3: 48 findings before changes; zero after source fixes and narrowly scoped evidence/fixture ignores. Three deliberate `BLE001` exceptions sanitize potentially sensitive provider or HTTP exceptions.
- Python 3.11.17: offline suite run three times during this work; each run reported 233 passed, 10 deselected and 9 subtests passed. No flaky test observed in these three runs. This does not exercise Docker or network tests.
- Evidence integrity: 25 files in the pre-change SHA-256 manifest were checked after lint work; all 25 matched. Manifest SHA-256: `27b71ddf8940a85a3d9c8f9c1327f2c46338ff72e23eab56deb6b03500aa69ce`.
- Environment test evidence supplied by owner: all four images built, but humanize missed freezegun, boltons had an incompatible pytest hook, pydash missed pytest-cov and attrs missed hypothesis. Baseline failures were not recorded. These are open problems, not successful baseline verification.
- Still required: implement and test baseline capture and failure rejection, corrupted/partial metadata, baseline timeouts, missing runner, concurrent builds, secret scan of generated output and full history, fake-provider fixture regression, resource cleanup and all remaining stress-plan cases. Run owner-side Docker checks. No claim of C1 completion.
- Paid model calls: none in this checkpoint.
