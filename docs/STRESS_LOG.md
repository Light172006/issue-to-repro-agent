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

## 2026-11-02 — C1 Windows bug fixes (in progress)

- Catch-up review found two Windows-specific failures in the offline suite:
  - BUG-1: `test_parallel_atomic_metadata_writes_are_valid` — `os.replace` raises `PermissionError` (WinError 5) on Windows under 40 concurrent threads. Fixed by adding a 3-attempt retry with 5 ms sleep on `win32` only; non-Windows and third attempt re-raise immediately. Production writes are always sequential.
  - BUG-2: `test_date_bounded_install_records_commit_cutoff` — `Path('/repo')` evaluates to `'\\repo'` on Windows. `resolve_install` is container-only (Linux) code. Fixed by using `PurePosixPath('/repo')` in the test so `str()` always yields the POSIX form.
- Python 3.11.9 (host), three offline runs after fix: 264 passed, 10 deselected, 9 subtests passed each. No flaky tests. Ruff 0.17.3: all checks passed.
- These two tests passed previously (STRESS_LOG recorded 255 passed at last entry) because they were added between then and now but not caught as Windows-failing. They were always failing on Windows; the previous log entry was from a Linux-compatible runner.
- Commit: `2a5cffd fix: retry os.replace on Windows and use PurePosixPath in installenv test`.
- Still open from prior entries: testdeps wiring, real Docker baseline verification, secret scan, fake-provider end-to-end regression, fault injection, step 11 "done when" confirmation, HACKATHON.md update. No model calls.

## 2026-11-02 — C1 test dependency discovery, isolation and Docker verification

- Wired `testdeps.py` into both `envbuilder.py` (preflight discovery) and `installenv.py` (in-container disk-based discovery).
  - Inside the build container, `installenv.py` discovers config files directly from `/var/tmp/repro/source` without requiring unauthenticated GitHub API calls, avoiding rate limits.
  - Automatically identifies test extras (`tests`, `test`, `dev`, `testing`), package requirements, and pytest plugins (`pytest-cov`).
  - Appends discovered extras to source spec (`source[tests]`), allowing tools like `uv` to resolve historical dependencies (e.g. `freezegun` for humanize, `hypothesis` for attrs).
  - Records discovery metadata in `(root / 'discovery.json')` and merges into `environment.json`.
- Secret scan across full git history and tracked files (`scripts/scan_secrets.py`):
  - Checked for GitHub tokens (`ghp_`, `github_pat_`), OpenAI/Meta keys, bearer tokens, API keys.
  - Result: 0 real credentials leaked. Only one synthetic mock token (`ghp_12345678901234567890`) in `tests/test_trace.py` for redaction testing.
- Real Docker verification on Windows Docker Desktop:
  - `scripts/check_isolation.py`: All 13 isolation and resource checks PASSED (non-root UID, virtualenv python, volume mount persistence, read-only root and source filesystem, blocked DNS and public IP, host localhost access blocked, host environment variables hidden, docker socket absent, timeout killing container, 50 MiB output bounded to head/tail truncation).
  - Full docker-marked test suite (7 tests): All 7 PASSED in 68.63s with `REPRO_DOCKER_TESTS=1` and `REPRO_STEP10_IMAGE`:
    - `test_binary_and_background_cleanup` PASSED
    - `test_network_disabled_ipv4_ipv6` PASSED
    - `test_repro_mount_persists_across_isolated_containers` PASSED
    - `test_minimizer_with_boltons_image` PASSED
    - `test_network_is_disabled` PASSED
    - `test_nonroot_and_command` PASSED
    - `test_timeout_kills_container` PASSED
  - `scripts/check_step11.py`: PASSED (both hardware-bound `not_feasible` and vague `needs_info` with reporter questions).
- Offline test suite: 274 passed, 10 deselected, 9 subtests passed; run three consecutive times with identical counts (0 flakes). Ruff 0.17.3 clean across all files.
- Paid model calls: $0.00 spent.

## 2026-11-02 — C1 Windows file-locking retry hardening

- Caught intermittent failure in test_parallel_atomic_metadata_writes_are_valid:
  - 8 threads executing 40 concurrent writes targeting the same environment.json file on Windows NTFS triggered PermissionError: [WinError 5] Access is denied in os.replace.
  - The previous 3-attempt / 5ms sleep window (15ms total) was insufficient to handle contention among 8 threads.
  - Hardened _write_json in src/repro/envbuilder.py with up to 100 attempts on Windows and randomized backoff sleep (0.005 + random.uniform(0.002, 0.015)).
  - Validated by running test_parallel_atomic_metadata_writes_are_valid 20 consecutive times in a subprocess loop: 20/20 passed cleanly.
- Full offline test suite (274 passed, 10 deselected, 9 subtests) run three consecutive times: 0 failures, 0 flakes.
- Commit: 8d75541 fix: harden atomic json write retry for Windows file lock contention.
- Paid model calls: .00 spent.


## 2026-11-02 — C2 Step 12 Escalation Validation & Evaluation

- Validated Step 12 forced escalation plumbing with live Meta Model API (`muse-spark-1.3` -> `muse-wonder`) on `humanize #57` with `--force-escalate-at-step 2`:
  - Run ID: `62fd7945c92c405a824adc1a00287cbf`
  - Result: `status: "reproduced"`, `solved_after_escalation: true`, `verdict: "exact"`, 5/5 repeated runs matched, minimized to 3 lines in 13.1s, cost $0.036172.
- Step 12 Natural Evaluation across `bench/step12_issues.txt`:
  - `humanize #57`: Solved on Spark-1 (8 steps, $0.03065) and Spark-2 (7 steps, $0.0229). Escalation correctly skipped (preserving budget).
  - `boltons #337`: Failed initially due to legacy Python 2.7 dependencies extracted from `tox.ini` conflicting with modern packages (`pytest-cov==2.12` vs `pytest-cov==4.0.0`). Fixed by ignoring py2 and linter tox sections and deduplicating package names in `c5b34b1`. Re-build verified: 407/407 tests passed.
  - `pydash #153`: `spark-1` stopped at step 1; `spark-2` stopped at step 25 ($0.202); `escalation` run stopped at step 12 ($0.058).
  - `attrs #1348`: `spark-1` reached 25 steps ($0.211); `spark-2` stopped at step 9 ($0.052); `escalation` triggered at step 15, called Wonder ($0.043 Wonder cost), then caught `ProviderError` from Wonder and fell back cleanly to Spark without crashing.
- Offline Test Suite: 277 offline tests passed, 10 deselected, 9 subtests passed (run 3 times without flakiness). Ruff clean across repository.
- Spend: $1.31 today, lifetime ledger total $1.62.
