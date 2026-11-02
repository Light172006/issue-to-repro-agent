# Hackathon build log

- Event: Meta Global AI Hackathon
- Track: Indie — Build for Your World
- Event start date: **October 27, 2026**

## Work built during the event

- October 27, 2026 — Step 0: repository and development setup; starting commit tagged `hackathon-start`.
- October 27, 2026 — Step 1: model layer, fake provider, preflight accounting, budget ledger and tests. A real Muse call was verified by the project owner. The documented provider-side billing limitation remains.
- October 27, 2026 — Step 2: GitHub issue fetcher, paginated comments, JSON cache and unit tests. Five-repository live test passed as reported by the project owner; linked URLs are listed but their contents are not fetched.
- October 27, 2026 — Step 3: disposable resource-limited, non-root Docker sandbox, offline execution, trusted networked setup, unit tests and opt-in Docker integration tests. All Docker integration tests passed on Windows, as reported by the project owner.
- October 27, 2026 — Step 4: version resolution, containerized environment building, image caching, environment metadata and offline test command. Three-library live checks passed.
- October 28, 2026 — Switched Step 4 to a commit-verified Git checkout and recorded reported v0.1 evidence; live verification passed on three libraries as reported by the project owner.

- October 28, 2026 — Step 5: structured issue parser and deterministic hints. The project owner reported 10/10 correct versions, 9/10 correct symptoms and 9/10 correct on both; vague-issue missing fields matched exactly on 1/3, with extra missing items on two cases.

- October 28, 2026 — Step 6: the project owner reported a successful boltons 23.0.0 candidate and an independently failing test; conservative recorded cost was $0.03205825. Docker isolation checks passed on Windows.
- October 28, 2026 — Step 7: deterministic symptom matcher passed 15 saved simulated-output cases, including a shortened trace based on the manual boltons repro.
- October 28, 2026 — Step 8: the project owner reported that the saved test failed independently with the reported exception. Step 9 verification and confidence were later completed as recorded below. The original successful agent trace and a reproduction example are saved under `examples/v0.2-boltons`.
- October 29, 2026 — Steps 9–10: the project owner reported five successful before/after verifier checks and an exact boltons repro minimized from seven to six lines with high confidence. Updated Docker minimizer tests passed. The owner supplied the minimized test and result as text; the test hash matches, and the evidence is in `proof/v0.3`.
- October 31, 2026 — C1 in progress: added conservative baseline test recording and pre-existing failure checks, with offline tests. Docker validation and the remaining stress checks are pending; no model calls were made for this work.
- November 1, 2026 — C1 in progress: added a standalone static test-dependency discovery component and offline tests. It is not yet wired into the production environment builder.

- November 2, 2026 — C1 complete: resolved Windows file-locking contention (`_write_json` retry), wired in-container and preflight test-dependency discovery (`testdeps.py`), enabled date-bounded `uv` installation fallback with commit timestamps, validated 13/13 container isolation checks, 7/7 Docker integration tests, and Step 11 feasibility/triage verification. Full offline test suite clean (277 tests passed, 0 flakes).
- November 2, 2026 — C2 complete: validated Step 12 escalation mechanism using live Meta Model API (`muse-spark-1.3` and `muse-wonder`). Verified forced-escalation handoff plumbing on `humanize #57` with exact reproduction and 3-line test minimization ($0.036). Evaluated full Step 12 natural issue benchmark (`bench/step12_issues.txt`); resolved `tox.ini` legacy Python 2 dependency collisions in `testdeps.py` (`c5b34b1`), verified Spark-only reproductions on `humanize #57`, and verified graceful Wonder `ProviderError` handling and fallback on complex runs.
- November 3, 2026 — Step 13 (Part 1: Benchmark curation and ground-truth validation): Curated 18 candidate bug issues across 11 pure-Python utility libraries (14 feasible, 4 infeasible across addict, colorama, gpustat, marshmallow, more-itertools, parse, semver, sqlparse, tabulate, validators, voluptuous) with <= 2 issues per library. Verified all 14 feasible candidates fail at buggy commit with symptom match and pass at fix commit in Docker sandbox; verified all 4 infeasible candidates against sandbox OS/network/hardware boundaries. Partitioned into 11 development and 7 held-out issues (seeded shuffle, seed=42) with 2 infeasible in held-out. Anchored held-out digest in `bench/HELDOUT.sha256`; generated sanitized snapshots (`bench/snapshots/`) with schema_version: 2 stripping PR solution links and maintainer comments. Total spend: $0.00.
