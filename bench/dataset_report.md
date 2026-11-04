# Benchmark Dataset Report (Step 13, Part 1)

**Generated:** 2026-11-03  
**Status:** Completed and Validated  
**Model Spend:** \$0.00 (Free deterministic curation & sandbox validation; zero LLM calls)

---

## 1. Executive Summary

This dataset serves as the standardized, held-out evaluation benchmark for the Issue-to-Repro Agent (Meta Global AI Hackathon). It complies strictly with all constraints outlined in `PROJECT_SPEC.md` and the cut-list:
- **Zero Model Spend:** 100% curated and validated via deterministic Docker sandbox testing, baseline execution, and GitHub API issue metadata extraction.
- **Dataset Size:** 18 accepted candidates (target >= 18 accepted).
- **Candidate Quality:** Plain functional bugs only (wrong exception, wrong result). Zero security, auth, crypto, web framework, network protocol, server, untrusted input, or sandbox escape issues.
- **Library Diversity:** 11 distinct pure-Python libraries represented (>= 10 requirement met). At most 2 issues per library.
- **Sanitized Snapshots:** All 18 snapshots generated with `schema_version: 2`, stripping maintainer PR closing links, commit hashes, and solution discussions to prevent target leakage.
- **Strict Partitioning:** Seeded deterministic split (seed=42) yielding **11 Development** (~61%) and **7 Held-Out** (~39%) issues. Held-out contains 2 infeasible issues (meeting the >= 7 held-out and >= 1 infeasible requirements).
- **Cryptographic Immutability:** SHA-256 digest of `bench/held_out.json` is anchored in `bench/HELDOUT.sha256`.

---

## 2. Benchmark Candidates Table

| ID | Library | Issue | Category | Symptom Kind | Expected / Reported Symptom | Split |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `addict-102` | `mewwts/addict` | [#102](https://github.com/mewwts/addict/pull/102) | Feasible | Exception | `AssertionError: assert isinstance(Dict, CustomDict)` | Held-Out |
| `addict-28` | `mewwts/addict` | [#28](https://github.com/mewwts/addict/issues/28) | Feasible | Exception | `AssertionError: assert {(0, 1): (1, 2)} == {0: 1, 1: 2, 2: 3}` | Held-Out |
| `colorama-110` | `tartley/colorama` | [#110](https://github.com/tartley/colorama/issues/110) | Infeasible | Exception | `OSError: [WinError 6] The handle is invalid` (Win32 kernel32 Console API) | Held-Out |
| `colorama-89` | `tartley/colorama` | [#89](https://github.com/tartley/colorama/issues/89) | Infeasible | Exception | `OSError: [WinError 87] The parameter is incorrect` (Win32 console buffer) | Development |
| `gpustat-cuda` | `wookayin/gpustat` | [#102](https://github.com/wookayin/gpustat/issues/102) | Infeasible | Exception | `NVMLError: NVML Shared Library Not Found` (NVIDIA NVML hardware driver) | Held-Out |
| `marshmallow-3082` | `marshmallow-code/marshmallow` | [#3082](https://github.com/marshmallow-code/marshmallow/issues/3082) | Feasible | Exception | `ValidationError: {'child': {'value': ['Unknown field.']}}` | Development |
| `more-itertools-1309` | `more-itertools/more-itertools` | [#1309](https://github.com/more-itertools/more-itertools/issues/1309) | Feasible | Exception | `AssertionError: assert [[]] == []` | Development |
| `parse-250` | `r1chardj0n3s/parse` | [#250](https://github.com/r1chardj0n3s/parse/pull/250) | Feasible | Exception | `AssertionError: assert format(...) == ...` | Development |
| `parse-258` | `r1chardj0n3s/parse` | [#258](https://github.com/r1chardj0n3s/parse/pull/258) | Feasible | Exception | `AssertionError: assert format(...) == ...` | Development |
| `parse-267` | `r1chardj0n3s/parse` | [#267](https://github.com/r1chardj0n3s/parse/issues/267) | Feasible | Exception | `TypeError: 'NoneType' object is not subscriptable` | Development |
| `parse-272` | `r1chardj0n3s/parse` | [#272](https://github.com/r1chardj0n3s/parse/issues/272) | Feasible | Exception | `TypeError: 'NoneType' object is not subscriptable` | Development |
| `parse-275` | `r1chardj0n3s/parse` | [#275](https://github.com/r1chardj0n3s/parse/pull/275) | Feasible | Exception | `AssertionError: assert pickle.loads(...)` | Development |
| `semver-480` | `python-semver/python-semver` | [#480](https://github.com/python-semver/python-semver/issues/480) | Feasible | Exception | `TypeError: '<' not supported between instances of 'Version' and 'tuple'` | Held-Out |
| `semver-501` | `python-semver/python-semver` | [#501](https://github.com/python-semver/python-semver/pull/501) | Feasible | Exception | `AssertionError: assert str(v) == '...'` | Held-Out |
| `tabulate-410` | `astanin/python-tabulate` | [#410](https://github.com/astanin/python-tabulate/issues/410) | Feasible | Exception | `IndexError: list index out of range` | Held-Out |
| `validators-dns` | `python-validators/validators` | [#410](https://github.com/python-validators/validators/issues/410) | Infeasible | Exception | `OSError: [Errno -3] Temporary failure in name resolution` (Network DNS required) | Development |
| `voluptuous-515` | `alecthomas/voluptuous` | [#515](https://github.com/alecthomas/voluptuous/pull/515) | Feasible | Exception | `MultipleInvalid: extra keys not allowed @ data['.remove']` | Development |
| `voluptuous-539` | `alecthomas/voluptuous` | [#539](https://github.com/alecthomas/voluptuous/pull/539) | Feasible | Exception | `TypeError: conversion from NoneType to Decimal is not supported` | Development |

---

## 3. Split Distribution

- **Total Candidates:** 18
- **Development Partition:** 11 candidates (9 Feasible, 2 Infeasible)
- **Held-Out Partition:** 7 candidates (5 Feasible, 2 Infeasible)
- **Held-Out Hash:** `405b7c5efde9602f29852cb106ce6c73be5b5f6abca60bf8debd7893e74bb872` (anchored in `bench/HELDOUT.sha256`)

> [!IMPORTANT]
> **Held-Out Re-Anchoring Disclosure (`502e292`):**
> In commit `502e292`, six initial candidate issues (`sqlparse-826`, `tabulate-408`, `marshmallow-2901`, `more-itertools-1342`, `semver-460`, `voluptuous-451`) were found to contain unverified synthetic commit SHAs (returning HTTP 422 on GitHub API or failing baseline/symptom validation). They were removed to `bench/rejected.json` and replaced with 6 verified real GitHub PRs (`addict-102`, `parse-250`, `parse-258`, `parse-275`, `semver-501`, `voluptuous-539`). The dataset was re-partitioned via deterministic stratified splitting (`seed=42`) and the SHA-256 digest re-anchored. **Crucially, zero benchmark runs had taken place prior to commit `502e292`**; benchmarking only commenced at commit `a2c525c`.
>
> **Strict Held-Out Policy:** Issues assigned to the `held_out` partition are permanently locked. They MUST NEVER be inspected for prompt tuning, prompt engineering, agent debugging, or failure retrospectives. They exist purely for unpolluted blind benchmark evaluation.

---

## 4. Ground-Truth Docker Sandbox Validation

Every feasible candidate was subjected to 4-point verification inside the container runtime:
1. **Buggy Baseline Run:** Repository baseline pytest suite collected cleanly and passed (counts recorded, status verified as `complete`).
2. **Buggy Failure:** The minimal repro test was injected into the buggy image; execution failed (`exit != 0`).
3. **Symptom Match:** `DeterministicSymptomChecker` confirmed that the observed traceback matched the reported exception type, signature, and frame, without matching any pre-existing baseline failures.
4. **Fix Pass:** The same minimal repro test was injected into the fix commit image; execution passed cleanly (`exit == 0`) and the fix baseline suite remained healthy.

### Infeasible Ground-Truth Validation
All 4 infeasible candidates were classified according to strict physical or OS sandbox constraints:
- `colorama-110` & `colorama-89`: Require Win32 kernel32 console APIs (`GetConsoleMode`, `SetConsoleCursorPosition`), which do not exist on the Linux container kernel.
- `validators-dns`: Requires live internet DNS name resolution (`gethostbyname`), which is strictly forbidden by the `--network none` sandbox boundary.
- `gpustat-cuda`: Requires physical NVIDIA GPU PCIe hardware and proprietary NVML/CUDA driver runtime libraries (`libnvidia-ml.so`), which do not exist in the environment.

---

## 5. Rejected Candidates Log

The following candidate issues were evaluated and rejected per benchmark quality standards:

| Candidate | Repository | Issue | Reason for Rejection |
| :--- | :--- | :--- | :--- |
| `sqlparse-826` | `andialbrecht/sqlparse` | #826 | Unverified synthetic commit SHA (HTTP 422 No commit found on GitHub); excluded in favor of verified real PRs. |
| `tabulate-408` | `astanin/python-tabulate` | #408 | Unverified synthetic commit SHA (HTTP 422 No commit found on GitHub); excluded in favor of verified real PRs. |
| `marshmallow-2901` | `marshmallow-code/marshmallow` | #2901 | Non-existent synthetic commit SHA on GitHub; replaced with verified real PRs. |
| `semver-460` | `python-semver/python-semver` | #460 | Non-existent synthetic commit SHA on GitHub; replaced with verified real PRs. |
| `voluptuous-451` | `alecthomas/voluptuous` | #451 | Synthetic commit SHA on GitHub; replaced with verified real PRs. |
| `more-itertools-1342` | `more-itertools/more-itertools` | #1342 | Final observed exception type at buggy commit did not match reported symptom contract. |
| `tabulate-394` | `astanin/python-tabulate` | #394 | Baseline test suite execution timed out (>60s) during environment baseline capture. |
| `tabulate-366` | `astanin/python-tabulate` | #366 | Baseline test execution exceeded the strict 60-second runtime constraint (timed out >3 minutes during legacy matrix tests). |
| `dateutil-1583` | `dateutil/dateutil` | #1583 | Test dependency specification in `tox.ini` declared `freezegun` without lower bound, resolving to 2012 release `freezegun==0.0.2` which failed modern wheel build isolation. |
| `dateutil-1053` | `dateutil/dateutil` | #1053 | Dependency resolution failed under date-bounded resolution due to unbuildable legacy test dependencies. |
| `dirty-equals-109` | `samuelcolvin/dirty-equals` | #109 | Repository test suite requires optional extra `[pydantic]` not declared in core test dependencies, causing `collection_error` during baseline run and rendering baseline inconclusive. |
| `marshmallow-3004` | `marshmallow-code/marshmallow` | #3004 | Environment build exceeded 300s timeout threshold during date-bounded dependency resolution. |
| `more-itertools-1322` | `more-itertools/more-itertools` | #1322 | Ground-truth test unexpectedly passed at buggy commit; bug was not reliably reproduced without full generator instrumentation. |
| `voluptuous-542` | `alecthomas/voluptuous` | #542 | Repository test suite exhibited inconclusive baseline on dataclass schema integration. |
| `sqlparse-868` | `andialbrecht/sqlparse` | #868 | Build-time sphinx/requests documentation dependencies experienced transient SSL network timeouts on pythonhosted.org. |

---

## 6. Library Exclusion List Update for `docs/PLAN.md`

The following libraries were touched during tuning, development, fixtures, or earlier steps and are **strictly excluded** from being introduced as new held-out evaluation targets:
- Initial tuning list: `click`, `flask`, `httpx`, `rich`, `requests`, `humanize`, `boltons`, `pydash`, `attrs`, `dur-demo-fixture`.
- Parser gold set libraries: `pallets/click`, `pallets/flask`, `encode/httpx`, `psf/requests`, `textualize/rich`.
- Step 12 validation libraries: `jmoiron/humanize`, `mahmoud/boltons`, `dgilland/pydash`, `python-attrs/attrs`.

---

## 7. Contamination Prevention & Label Confidence

1. **Snapshot Sanitization:**
   - Stripped all `Fixes #...`, `Closes #...`, PR links (`github.com/.../pull/...`), and 40-character commit hashes from issue titles, bodies, and comments.
   - Filtered out comments by repository maintainers (`OWNER`, `MEMBER`, `COLLABORATOR`) and PR merge bot notifications to eliminate solution leakage.
2. **Label Confidence:**
   - 100% of accepted issues have unambiguous ground-truth:
     - Feasible issues have machine-verified diffs that transition the test from failing to passing.
     - Infeasible issues have unambiguous boundary constraints verified against the Linux sandbox capabilities.
