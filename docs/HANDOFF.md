# docs/HANDOFF.md — Catch-up report as of 2026-11-02

> [!IMPORTANT]
> **Hackathon deadline**: HACKATHON.md records the event start (2026-10-27) but **no submission deadline, time, or time zone**. PLAN.md also notes this gap. You must supply the exact deadline before any timeline-sensitive planning can be finalised.

Current local time: 2026-11-02 17:02 IST (UTC+05:30). Day 7 of the event.

---

## Verification of user summary claims

| Claim | Verified? | Evidence |
|---|---|---|
| Steps 0–4 done, tagged v0.1 | ✅ Correct | `git tag` shows `hackathon-start`, `v0.1`, `v0.2`, `v0.3`; `proof/v0.1.md` exists |
| Step 5 parser done | ✅ Correct | `parser.py` exists; HACKATHON.md records 10/10 version pass |
| Step 6 agent loop with tools and trace | ✅ Correct | `agent.py` 310 lines, `tools.py`, `trace.py`; `examples/v0.2-boltons/` evidence |
| Step 7 symptom matcher | ✅ Correct | `matcher.py`; 15-case gold set recorded |
| Step 8 test writer | ✅ Correct | `result_writer.py`, `report.py`; `examples/v0.2-boltons/test_repro.py` exists |
| Step 9 verifier | ✅ Correct | `verifier.py` 128 lines; 5-repeat, fixed-version check, confidence enum |
| Step 10 minimizer | ✅ Correct | `minimizer.py` 314 lines; AST ddmin + input shortening; `proof/v0.3/` evidence |
| Step 11 feasibility / four statuses / reporter questions UNCONFIRMED | ⚠️ Partially done | `triage.py` 55 lines implements `not_feasible`+`needs_info`; `report.py` writes `comment.md` with questions. But `scripts/check_step11.py` was never reported as passing; end-to-end "done when" unconfirmed. |
| Step 12 escalation partly built and unvalidated | ✅ Correct | `stall.py`, escalation branch in `agent.py`, `scripts/e2e_step12.py`, `bench/step12_issues.json` |
| Sandbox design (fresh container, writable `/work/repro`, `--network none`, non-root, limits) | ✅ Correct | Confirmed in sandbox.py and README |
| `bench/step12_issues.json` with 4 issues: humanize #57, boltons #337, pydash #153, attrs #1348 | ✅ Correct | File read; all 4 present with tiers C/C/M/H |
| Two unrelated baseline failures: pydash #153 and boltons #337 | ✅ Correct | Documented in `suite_older.failures` of each entry |
| Attrs mypy pin needs general solution | ✅ Correct | attrs entry uses two separate install commands including `mypy==1.11.1` |
| `bench/parser_gold.json` exists | ✅ Correct | File present |
| Excluded libraries list is correct | ✅ Correct | Matches step12_issues note + README |
| C1 ruff cleanup done | ✅ Correct | STRESS_LOG: "zero findings after source fixes"; ruff passes today |
| Evidence manifest hashed | ✅ Correct | SHA-256 manifests recorded in STRESS_LOG |
| Baseline recording and pre-existing failure rejection implemented | ✅ Correct | `baseline.py` 110 lines; `envbuilder.py` integrates it |
| 7 Docker tests are the full non-paid docker-marked set | ✅ Correct | Confirmed: 7 tests at `docker and not network`; the 8th is `docker and network` (paid) |
| Date-bounded dependency resolution implemented | ✅ Correct | `installenv.py` uses `uv pip install --exclude-newer` with fallback ladder |
| Fallback ladder recorded in `environment.json` | ✅ Correct | `resolution.json` written by installer, merged into `environment.json` |
| `testdeps.py` implemented but NOT wired to builder | ✅ Correct | Module exists; STRESS_LOG confirms "not connected to production builder" |
| Remaining C1 stress items open | ✅ Correct | STRESS_LOG lists them explicitly |

---

## Step status table (Steps 0–15)

| Step | Status | "Done when" met? | Evidence |
|---|---|---|---|
| 0 | ✅ Done and verified | Yes | `hackathon-start` tag; HACKATHON.md |
| 1 | ✅ Done and verified | Yes — real call verified by owner; guard tested | `llm.py`; HACKATHON.md |
| 2 | ✅ Done and verified | Yes — 5-repo live test passed | `github.py`; HACKATHON.md |
| 3 | ✅ Done and verified | Yes — Docker integration tests passed on Windows | `sandbox.py`; HACKATHON.md |
| 4 | ✅ Done and verified | Yes — 3-library live Git-checkout test passed | `envbuilder.py`; HACKATHON.md; `proof/v0.1.md` |
| 5 | ✅ Done and verified | Yes — 10/10 versions, 9/10 symptoms | `parser.py`; HACKATHON.md |
| 6 | ✅ Done and verified | Yes — boltons repro end-to-end | `agent.py`, `tools.py`, `trace.py`; `examples/v0.2-boltons/`; `v0.2` tag |
| 7 | ✅ Done and verified | Yes — 15 saved cases pass | `matcher.py`; `tests/fixtures/matcher_cases.json` |
| 8 | ✅ Done and verified | Yes — saved test failed independently | `result_writer.py`; HACKATHON.md; `v0.2` tag |
| 9 | ✅ Done and verified | Yes — 5 before/after checks; confidence correct | `verifier.py`; `proof/v0.3/`; `v0.3` tag |
| 10 | ✅ Done and verified | Yes — boltons repro 7→6 lines; hash matched | `minimizer.py`; `proof/v0.3/`; `v0.3` tag |
| 11 | ⚠️ Done but unverified | Code present; end-to-end "done when" NOT confirmed | `triage.py`, `report.py`; `scripts/check_step11.py` not reported passing |
| 12 | ⚠️ Partial, unvalidated | Stall detection + escalation branch + issue list present; no successful escalation case confirmed | `stall.py`, `agent.py`, `bench/step12_issues.json` |
| 13 | 🔴 Not started | No `bench/dataset.json`, `bench/run.py`, `bench/score.py`, `bench/results.md` | PLAN.md C3 |
| 14 | 🔴 Not started | No `viewer/`; README stops at step 5; SECURITY.md is stub | PLAN.md C4 |
| 15 | 🔴 Not started | No submission checklist, no demo script | PLAN.md C5 |

### Tags vs. checkpoints

| Tag | Exists | Spec checkpoint | Notes |
|---|---|---|---|
| `hackathon-start` | ✅ | Step 0 | Correct |
| `v0.1` | ✅ | Steps 0–4 | Correct |
| `v0.2` | ✅ | Steps 5–8 | Correct |
| `v0.3` | ✅ | Steps 9–10 | Correct |
| `v0.4` | ❌ Missing | Steps 11–12 — unverified; owner creates after verification | — |
| `v0.5` | ❌ Missing | Step 13 — not started | — |
| `v1.0` | ❌ Missing | Steps 14–15 — not started | — |

---

## Bugs found today (not in previous summary)

### BUG-1 — `test_parallel_atomic_metadata_writes_are_valid` FAILS on Windows

- **Location**: [`tests/test_baseline.py:124`](file:///d:/issue-to-repro-agent/tests/test_baseline.py#L120-L126) calling [`src/repro/envbuilder.py:76`](file:///d:/issue-to-repro-agent/src/repro/envbuilder.py#L68-L80)
- **Root cause**: `os.replace(tmp, dst)` on Windows raises `PermissionError` when another thread holds a read or write handle on `dst`. 40 threads all writing to the same path triggers this. Production use is always single-threaded, so the guard is correct in design but `os.replace` is not atomic across threads on Windows when the destination is concurrently locked.
- **Fix plan**: Add a small retry loop (3 attempts, 5 ms sleep) around `os.replace` in `_write_json` for Windows compatibility, **or** keep the test but document the Windows limitation with a `pytest.mark.skipif(sys.platform == 'win32' and ...)` noting this is a test-harness limitation that does not affect sequential production use. Either approach plus a comment is acceptable. I will add the retry loop (safer, no skip).

### BUG-2 — `test_date_bounded_install_records_commit_cutoff` FAILS on Windows

- **Location**: [`tests/test_installenv.py:25`](file:///d:/issue-to-repro-agent/tests/test_installenv.py#L25) calling [`src/repro/installenv.py:86-89`](file:///d:/issue-to-repro-agent/src/repro/installenv.py#L86-L89)
- **Root cause**: The test passes `Path('/repo')` as `source`. On Windows `str(Path('/repo'))` → `'\\repo'`, not `'/repo'`. `installenv.py` runs **inside a Linux container** and will never receive a Windows path in production, but the test runs on Windows and produces a Windows path.
- **Fix plan**: Change the test to use a raw string `'/repo'` instead of `Path('/repo')`, and update `resolve_install` to accept `str | os.PathLike` but coerce to `Path.as_posix()` only when building the command, or simply pass `PurePosixPath('/repo')` in the test. The simplest fix: change `calls[-1][0][-3:]` assertion to compare against the platform-native form, **or** (better) pass `pathlib.PurePosixPath` in the test so `str()` always yields `'/'`-separated paths.

---

## All TODOs and placeholders

| File | Issue | Severity |
|---|---|---|
| `config/models.yaml` | **No `base_url` field**. Spec §7: "Do NOT guess the base URL. Put it in config and leave a clear TODO." The key is entirely absent. `llm.py` reads the base URL from an environment variable only. | Medium — spec violation |
| `README.md` | Status section only covers steps 0–5; steps 6–12 not documented | Low — user-facing gap |
| `SECURITY.md` | Stub text says "planned and not implemented"; all controls ARE implemented | Medium — misleading |
| `HACKATHON.md` | C1 entries say "in progress"; no deadline | High — hackathon rule |
| `testdeps.py` | Entire module not wired into `EnvironmentBuilder` | High — C1 open item |
| `scripts/check_step11.py` | Exists, never reported as passing | Medium — step 11 gap |
| `installenv.py:73` | `bootstrap / 'bin' / 'python'` — Linux-only path; safe because container-only | Low |
| `bench/dataset.json` | Does not exist | High — C3 dependency |
| `bench/run.py`, `bench/score.py`, `bench/results.md` | Do not exist | High — C3 dependency |
| `viewer/` | Does not exist | Medium — C4; on cut list |

---

## Failing and skipped tests (baseline)

| Test | Status | Cause |
|---|---|---|
| `test_baseline.py::test_parallel_atomic_metadata_writes_are_valid` | **FAILING** | BUG-1 (Windows `os.replace` race) |
| `test_installenv.py::test_date_bounded_install_records_commit_cutoff` | **FAILING** | BUG-2 (Windows path separator) |
| 7 `docker and not network` tests | **DESELECTED** (correct) | Require `REPRO_DOCKER_TESTS=1` |
| 1 `docker and network` test | **DESELECTED** (correct) | Require paid approval + env var |
| `test_parser_network.py` and other network tests | **DESELECTED** (correct) | Require `REPRO_PARSER_GOLD_RUN=1` |

**Flakiness check (3 consecutive offline runs)**: Identical results each time — same 2 failures, 262 passed, 10 deselected, 9 subtests. No flaky tests observed.

---

## Spec conflicts

1. **Missing `base_url` in `config/models.yaml`**: Spec §7 is explicit. No `base_url` field exists; the provider URL is only in env vars.
2. **SECURITY.md is a stub**: Spec §8 requires listing implemented controls; the file says they are "planned".
3. **`testdeps.py` not wired**: C1 "Tasks" explicitly require it; it is not done.
4. **README status section stops at step 5**: Spec §10 shows a complete layout description.
5. **Real Docker baseline not verified**: C1 "Done when" says "actual baseline outcomes are recorded"; only mocked tests cover this.

---

## Hackathon rule compliance

| Rule | Status | Notes |
|---|---|---|
| Public repo with license | ✅ | — |
| First commit tagged `hackathon-start` | ✅ | — |
| HACKATHON.md listing components and build dates | ⚠️ Incomplete | C1 still "in progress"; needs update |
| Demo shows only event-built features | ✅ | — |
| All benchmark results from Meta's models | ✅ Spec-compliant | No benchmark runs yet |
| No banned project types | ✅ | — |
| No unlicensed code or data | ✅ | — |
| **Submission deadline recorded** | ❌ **MISSING** | Must be supplied |

---

## Days remaining

Event start: 2026-10-27. Today (UTC): 2026-11-02. **Day 7 of 10.**
Exact deadline: **unknown** — must be provided.
Estimate assuming 2026-11-06 23:59 AoE: ~4 days remain.
