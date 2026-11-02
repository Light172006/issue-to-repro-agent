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
| `addict-28` | `mewwts/addict` | [#28](https://github.com/mewwts/addict/issues/28) | Feasible | Exception | `AssertionError: assert {(0, 1): (1, 2)} == {0: 1, 1: 2, 2: 3}` | Held-Out |
| `colorama-89` | `tartley/colorama` | [#89](https://github.com/tartley/colorama/issues/89) | Infeasible | Exception | `OSError: [WinError 87] The parameter is incorrect` (Win32 console buffer) | Development |
| `colorama-110` | `tartley/colorama` | [#110](https://github.com/tartley/colorama/issues/110) | Infeasible | Exception | `OSError: [WinError 6] The handle is invalid` (Win32 kernel32 Console API) | Held-Out |
| `gpustat-cuda` | `wookayin/gpustat` | [#102](https://github.com/wookayin/gpustat/issues/102) | Infeasible | Exception | `NVMLError: NVML Shared Library Not Found` (NVIDIA NVML hardware driver) | Held-Out |
| `marshmallow-2901` | `marshmallow-code/marshmallow` | [#2901](https://github.com/marshmallow-code/marshmallow/issues/2901) | Feasible | Exception | `AttributeError: 'NoneType' object has no attribute 'match'` | Held-Out |
| `marshmallow-3082` | `marshmallow-code/marshmallow` | [#3082](https://github.com/marshmallow-code/marshmallow/issues/3082) | Feasible | Exception | `ValidationError: {'child': {'value': ['Unknown field.']}}` | Held-Out |
| `more-itertools-1309` | `more-itertools/more-itertools` | [#1309](https://github.com/more-itertools/more-itertools/issues/1309) | Feasible | Exception | `AssertionError: assert [[]] == []` | Held-Out |
| `more-itertools-1342` | `more-itertools/more-itertools` | [#1342](https://github.com/more-itertools/more-itertools/issues/1342) | Feasible | Exception | `TypeError: predicate must return boolean` | Development |
| `parse-267` | `r1chardj0n3s/parse` | [#267](https://github.com/r1chardj0n3s/parse/issues/267) | Feasible | Exception | `TypeError: 'NoneType' object is not subscriptable` | Development |
| `parse-272` | `r1chardj0n3s/parse` | [#272](https://github.com/r1chardj0n3s/parse/issues/272) | Feasible | Exception | `TypeError: 'NoneType' object is not subscriptable` | Development |
| `semver-460` | `python-semver/python-semver` | [#460](https://github.com/python-semver/python-semver/issues/460) | Feasible | Exception | `TypeError: expected string or bytes-like object` | Development |
| `semver-480` | `python-semver/python-semver` | [#480](https://github.com/python-semver/python-semver/issues/480) | Feasible | Exception | `TypeError: '<' not supported between instances of 'Version' and 'tuple'` | Development |
| `sqlparse-826` | `andialbrecht/sqlparse` | [#826](https://github.com/andialbrecht/sqlparse/issues/826) | Feasible | Exception | `AssertionError: assert len(stmts) == 4` | Development |
| `tabulate-408` | `astanin/python-tabulate` | [#408](https://github.com/astanin/python-tabulate/issues/408) | Feasible | Exception | `AssertionError: asciidoc format output contains trailing whitespace` | Development |
| `tabulate-410` | `astanin/python-tabulate` | [#410](https://github.com/astanin/python-tabulate/issues/410) | Feasible | Exception | `IndexError: list index out of range` | Development |
| `validators-dns` | `python-validators/validators` | [#410](https://github.com/python-validators/validators/issues/410) | Infeasible | Exception | `OSError: [Errno -3] Temporary failure in name resolution` (Network DNS required) | Development |
| `voluptuous-451` | `alecthomas/voluptuous` | [#451](https://github.com/alecthomas/voluptuous/issues/451) | Feasible | Exception | `MultipleInvalid: length of value must be at least 0` | Held-Out |
| `voluptuous-515` | `alecthomas/voluptuous` | [#515](https://github.com/alecthomas/voluptuous/issues/515) | Feasible | Exception | `TypeError: argument of type 'int' is not iterable` | Development |

---

## 3. Split Distribution

- **Total Candidates:** 18
- **Development Partition:** 11 candidates (9 Feasible, 2 Infeasible)
- **Held-Out Partition:** 7 candidates (5 Feasible, 2 Infeasible)
- **Held-Out Hash:** `25c3861a6997d70601735c4effda410ea142eb970beeafb13179bdf30642de9a` (recorded in `bench/HELDOUT.sha256`)

> [!IMPORTANT]
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
| `tabulate-366` | `astanin/python-tabulate` | #366 | Baseline test execution exceeded the strict 60-second runtime constraint (timed out >3 minutes during legacy matrix tests). |
| `dateutil-1583` | `dateutil/dateutil` | #1583 | Test dependency specification in `tox.ini` declared `freezegun` without lower bound, resolving to 2012 release `freezegun==0.0.2` which failed modern wheel build isolation. |
| `dateutil-1053` | `dateutil/dateutil` | #1053 | Dependency resolution failed under date-bounded resolution due to unbuildable legacy test dependencies. |
| `dirty-equals-109` | `samuelcolvin/dirty-equals` | #109 | Repository test suite requires optional extra `[pydantic]` not declared in core test dependencies, causing `collection_error` during baseline run and rendering baseline inconclusive. |

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
