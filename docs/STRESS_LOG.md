# Stress test log

## 2026-10-31 — C1 (in progress, not passed)

- Ruff 0.17.3: 48 findings before changes; zero after source fixes and narrowly scoped evidence/fixture ignores. Three deliberate `BLE001` exceptions sanitize potentially sensitive provider or HTTP exceptions.
- Python 3.11.17: offline suite run three times during this work; each run reported 233 passed, 10 deselected and 9 subtests passed. No flaky test observed in these three runs. This does not exercise Docker or network tests.
- Evidence integrity: 25 files in the pre-change SHA-256 manifest were checked after lint work; all 25 matched. Manifest SHA-256: `27b71ddf8940a85a3d9c8f9c1327f2c46338ff72e23eab56deb6b03500aa69ce`.
- Environment test evidence supplied by owner: all four images built, but humanize missed freezegun, boltons had an incompatible pytest hook, pydash missed pytest-cov and attrs missed hypothesis. Baseline failures were not recorded. These are open problems, not successful baseline verification.
- Still required: implement and test baseline capture and failure rejection, corrupted/partial metadata, baseline timeouts, missing runner, concurrent builds, secret scan of generated output and full history, fake-provider fixture regression, resource cleanup and all remaining stress-plan cases. Run owner-side Docker checks. No claim of C1 completion.
- Paid model calls: none in this checkpoint.

## 2026-10-31 — C1 baseline safeguards (in progress)

- Python 3.11.17, three full offline runs after the changes: each 249 passed, 10 deselected, 9 subtests passed. No flaky tests observed in these runs. Ruff 0.17.3: all checks passed.
- Mocked baseline coverage: clean and failing suites, collection error, timeout, absent runner, truncated output, all skipped, corrupted metadata, baseline-signature and test-ID rejection, different failure acceptance, missing baseline, and 100 deterministic randomized baseline cases through the verifier.
- Forty concurrent atomic metadata writes produced valid JSON without leftover temporary files. This tests atomic writes, not concurrent Docker image builds. Existing fake-provider and budget regression tests passed in the full suite.
- The first integration test exposed two CLI mocks without baseline data and an incorrectly labeled fixture header; unavailable baselines now fail closed, and the fixture was corrected. An initial verifier test fixture was updated to provide an explicit clean baseline.
- Evidence manifest: 25 files before and after; identical SHA-256 of canonical manifest `d96cc2e79766c64e7723848bed8ec86c1e762c2f7174ee6a9ca37ffb508df0b1`. Common credential-shaped strings: zero matches in those 25 evidence files. This is not a comprehensive secret scan.
- Docker collection found 8 tests: 7 unpaid (`docker and not network`) and one paid/network test. Owner reported all 7 unpaid tests passed before these baseline changes. Docker unavailable here; baseline integration, isolation and environment scripts have not been rerun.
- Still open: real Docker baseline verification, collection output that cannot produce complete signatures, concurrent image builds, process/container cleanup, full history and generated-log secret scans, fake-provider dur-demo end-to-end regression and remaining fault-injection stress items. C1 is not complete. No model calls.

## 2026-11-01 — C1 dependency discovery foundation (in progress)

- Added a static, deterministic parser for a subset of declared extras, dependency groups, test requirements, tox dependencies and literal nox install arguments, plus pytest-cov detection. Nox input is parsed as Python syntax and never executed by this parser.
- Python 3.11.17 offline suite, three runs: 255 passed, 10 deselected, 9 subtests passed each; Ruff 0.17.3 passed. New tests cover empty, invalid and large inputs, deterministic output, supported pins and data-only nox parsing.
- Evidence manifest: 25 files before and after, both `d96cc2e79766c64e7723848bed8ec86c1e762c2f7174ee6a9ca37ffb508df0b1`.
- This component is NOT connected to the production builder. Date-bounded resolution, safe fallback, complete dependency and plugin discovery, metadata changes, generalization checks and Docker validation remain unimplemented. No model calls. C1 remains incomplete.
