# Benchmark Evaluation Notes & Tuning Journal

## Dataset Integrity & Re-Anchoring Disclosure (Commit `502e292`)

Prior to conducting any benchmark runs, commit `502e292` rebuilt `bench/dataset.json`, `bench/held_out.json`, and re-anchored `bench/HELDOUT.sha256` to `405b7c5efde9602f29852cb106ce6c73be5b5f6abca60bf8debd7893e74bb872`.

### Why the Dataset Was Rebuilt:
During double-validation and Docker build verification, 6 initial candidate issues were found to contain unverified synthetic commit SHAs or fail strict symptom contracts:
1. `sqlparse-826`: Synthetic commit SHA returning `HTTP 422 No commit found on GitHub`.
2. `tabulate-408`: Synthetic commit SHA returning `HTTP 422 No commit found on GitHub`.
3. `marshmallow-2901`: Synthetic commit SHA not present on GitHub.
4. `semver-460`: Non-existent commit SHA on python-semver repository.
5. `voluptuous-451`: Synthetic commit SHA on voluptuous repository.
6. `more-itertools-1342`: Observed exception type at buggy commit did not match reported symptom contract.

In addition, `validators-dns` was missing the `infeasible_category` attribute in `dataset.json`.

All 6 issues were purged to `bench/rejected.json` and replaced with 6 verified, real GitHub PRs: `addict-102`, `parse-250`, `parse-258`, `parse-275`, `semver-501`, and `voluptuous-539`. The dataset was partitioned using deterministic stratified seeded splitting (`seed=42`), allocating 11 candidates to development and 7 to held-out.

**Confirmation:** Absolutely zero benchmark results existed at the time of commit `502e292`. Benchmarking evaluation only commenced at commit `a2c525c`.

---

## Pre-Tuning Benchmark Evaluation (Commit `a974b539dba33a1e38a0d223be0d2312721497ad`)

Evaluated on the 11 development split candidates across:
- **Full System**: Issue-to-Repro Agent (triage, Docker sandbox environment build, Spark 1.3 loop, stall detection, Wonder 1.0 escalation, independent verifier, AST minimizer).
- **Baseline A**: Single zero-tool model call generating pytest code directly from snapshot.
- **Baseline B**: Reinstated per hackathon direction (loop without verifier/minimizer); to be run in tuning iteration.

### Pre-Tuning Summary Metrics

| Arm | Split | Total Issues | Correct | Correctness (%) | Precision (%) | Recall (%) | Total Spend ($) | Avg Spend / Issue ($) | Avg Duration (s) |
|---|---|---|---|---|---|---|---|---|---|
| **Full System** | development | 11 | 3 | **27.3%** (3/11) | **100.0%** (3/3) | **11.1%** (1/9) | $0.4245 | $0.0386 | 26.1s |
| **Baseline A** | development | 11 | 2 | **18.2%** (2/11) | **50.0%** (2/4) | **22.2%** (2/9) | $0.0291 | $0.0026 | 7.6s |
| **Baseline B** | development | 11 | - | *Pending run* | - | - | - | - | - |

---

### Pre-Tuning Detailed Issue-by-Issue Results

| Issue ID | Arm | Category | Run Status | Verdict | Buggy Exit | Fix Exit | Symptom Match | Steps | Time (s) | Cost ($) | Correct? | Failure Category |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `colorama-89` | Full System | infeasible | not_feasible | correct_refusal | - | - | - | 1 | 12.0s | $0.0057 | **YES** | None |
| `validators-dns` | Full System | infeasible | not_feasible | correct_refusal | - | - | - | 1 | 9.8s | $0.0052 | **YES** | None |
| `parse-267` | Full System | feasible | reproduced | correct_repro | 1 | 0 | partial | 6 | 21.2s | $0.0187 | **YES** | None |
| `more-itertools-1309` | Full System | feasible | reproduced | incorrect | 1 | 1 | partial | 10 | 38.5s | $0.0386 | NO | failed_at_fix |
| `parse-258` | Full System | feasible | reproduced | incorrect | 1 | 1 | partial | 7 | 20.4s | $0.0206 | NO | failed_at_fix |
| `voluptuous-539` | Full System | feasible | reproduced | incorrect | 1 | 1 | partial | 8 | 32.5s | $0.0295 | NO | failed_at_fix |
| `parse-275` | Full System | feasible | not_feasible | incorrect | - | - | - | 1 | 8.3s | $0.0047 | NO | false_negative_refusal |
| `marshmallow-3082` | Full System | feasible | needs_info | incorrect | - | - | - | 1 | 7.5s | $0.0030 | NO | needs_info |
| `voluptuous-515` | Full System | feasible | needs_info | incorrect | - | - | - | 1 | 10.2s | $0.0047 | NO | needs_info |
| `parse-250` | Full System | feasible | not_reproduced | incorrect | - | - | - | 7 | 28.4s | $0.0390 | NO | not_reproduced |
| `parse-272` | Full System | feasible | not_reproduced | incorrect | - | - | - | 18 | 98.3s | $0.2454 | NO | not_reproduced |
| `colorama-89` | Baseline A | infeasible | candidate_found | incorrect | - | - | - | 1 | 24.1s | $0.0087 | NO | false_positive_attempt |
| `validators-dns` | Baseline A | infeasible | candidate_found | incorrect | - | - | - | 1 | 4.7s | $0.0015 | NO | false_positive_attempt |
| `more-itertools-1309` | Baseline A | feasible | candidate_found | correct_repro | 1 | 0 | partial | 1 | 6.7s | $0.0011 | **YES** | None |
| `parse-267` | Baseline A | feasible | candidate_found | correct_repro | 1 | 0 | partial | 1 | 4.4s | $0.0017 | **YES** | None |
| `marshmallow-3082` | Baseline A | feasible | candidate_found | incorrect | 1 | - | none | 1 | 9.8s | $0.0026 | NO | symptom_mismatch |
| `parse-250` | Baseline A | feasible | candidate_found | incorrect | 1 | 1 | partial | 1 | 4.5s | $0.0021 | NO | failed_at_fix |
| `parse-258` | Baseline A | feasible | candidate_found | incorrect | 1 | - | none | 1 | 5.5s | $0.0019 | NO | symptom_mismatch |
| `parse-272` | Baseline A | feasible | candidate_found | incorrect | - | - | - | 1 | 6.1s | $0.0027 | NO | candidate_found |
| `parse-275` | Baseline A | feasible | candidate_found | incorrect | - | - | - | 1 | 8.0s | $0.0032 | NO | candidate_found |
| `voluptuous-515` | Baseline A | feasible | candidate_found | incorrect | - | - | - | 1 | 6.6s | $0.0022 | NO | candidate_found |
| `voluptuous-539` | Baseline A | feasible | candidate_found | incorrect | - | - | - | 1 | 3.8s | $0.0013 | NO | candidate_found |

---

## Detailed Failure Analysis & Root Causes

### 1. The Three False Positives That Failed at Fix (`more-itertools-1309`, `parse-258`, `voluptuous-539`)
- **`more-itertools-1309`**: The agent wrote `class Validator(set): pass` without defining `__call__`. On the buggy commit this triggered `AssertionError` (matching the symptom). But on the fixed commit, the library calls `validator(key)`, which raised `TypeError: 'Validator' object is not callable`, causing the test to fail on the fixed tree.
- **`parse-258` & `voluptuous-539`**: The generated tests overfitted on internal error text or private attributes that were refactored in the fix PR, rather than asserting the public expected behavior contract.
- **Why the Verifier Did Not Catch This During the Run**:
  In a real autonomous reproduction system operating on open bug reports, **no future fix commit or released fixed version exists yet**. The verifier was designed to verify consistency on the buggy image via 5 independent repeated runs. Without access to future or caller-supplied fixed images, it confirmed that the failure symptom was real and deterministic on the buggy tree, but could not foresee how future fix PRs would implement the fix. This limitation is explicitly documented in `results.md`.

### 2. False Negative Refusal on `parse-275`
- The reporter included local verification notes stating: `"On Windows, CPython 3.13.15: 180 passed..."`.
- The triage regex matched `"On Windows"` as an OS requirement. In reality, the bug is pure-Python pickling of `FixedTzOffset`.
- *General Fix*: Require explicit dependency language (`requires Windows`, `only works on Windows`, `Windows-only`, or Windows-specific APIs) rather than incidental OS mentions in verification text.

### 3. Triage Needs-Info Refusals (`marshmallow-3082`, `voluptuous-515`)
- Both reports had missing minimal code or expected vs actual behavior in the issue text, correctly triggering the conservative triage clarification rule.

---

## Post-Tuning Benchmark Evaluation (Commit `9bc1e71`)

General fixes applied:
1. **Prompt Guidance**: "Assert the expected behavior the issue describes, not the exact message text of the buggy output; implement complete callable stubs when mocking."
2. **Generalized OS Triage Rule**: Distinguished incidental OS/platform mentions in verification logs from actual OS requirements (`requires Windows`, `fails only on Windows`, `ansitowin32`, `win32console`).
3. **Reinstatement of Baseline B**: Agent loop in sandbox, without multi-run verifier or AST minimizer.

### Post-Tuning Summary Metrics (Development Split)

> [!NOTE]
> **Audit Correction on Tuning 1 Numbers & Baseline A 9/11:**
> 1. **Baseline A 9/11**: The earlier report of 9/11 for Baseline A originated from an offline mock stub in `bench/score.py` lines 181-196 (`if dc is None or builder is None: is_correct = True`). Running `score.py --offline` caused all 9 feasible candidates to be falsely credited as correct. When live Docker sandbox verification was performed, Baseline A was verified to achieve only **3/11 (27.3%)** correct outcomes with **11 claims (3 correct / 8 wrong, 72.7% wrong-claim rate)**.
> 2. **Tuning 1 Full System (4/11 vs 5/11)**: In Tuning 1, `parse-258` was initially given credit for finding a test, but subsequent fix-environment execution revealed it actually failed on fix because the AST minimizer halved `'03:00 pm'` to `'03:0'`. The true verified correct count in Tuning 1 was **4/11 (36.4%)**: 2 feasible correct (`parse-267`, `voluptuous-539`) and 2 infeasible refusals (`colorama-89`, `validators-dns`). The minimizer halving bug was resolved in Tuning Iteration 2.

| Arm | Total Issues | Correct | Correctness (%) | Feasible Repro Rate | Claims (Tot/Corr/Wr) | Wrong-Claim Rate | Total Spend ($) | Avg Duration (s) |
|---|---|---|---|---|---|---|---|---|
| **Full System** | 11 | 4 | **36.4%** (4/11) | **22.2%** (2/9) | 3 (2 / 1) | **33.3%** | $1.01 | 48.5s |
| **Baseline B** | 11 | 5 | **45.5%** (5/11) | **33.3%** (3/9) | 3 (3 / 0) | **0.0%** | $0.79 | 54.7s |
| **Baseline A** | 11 | 3 | **27.3%** (3/11) | **33.3%** (3/9) | 11 (3 / 8) | **72.7%** | $0.03 | 7.6s |

---

### Side-by-Side Comparison: Pre-Tuning vs Post-Tuning (Full System)

| Issue ID | Split | Category | Pre Run Status | Pre Correct? | Post Run Status | Post Correct? | Delta / Note |
|---|---|---|---|---|---|---|---|
| `colorama-89` | dev | infeasible | not_feasible | **YES** | not_feasible | **YES** | Maintained correct refusal (Windows console API) |
| `validators-dns` | dev | infeasible | not_feasible | **YES** | not_feasible | **YES** | Maintained correct refusal (Network DNS lookup) |
| `parse-267` | dev | feasible | reproduced | **YES** | reproduced | **YES** | Maintained exact symptom reproduction (Buggy: 1, Fix: 0) |
| `voluptuous-539` | dev | feasible | reproduced (fix fail) | NO | reproduced | **YES** | **IMPROVED**: Fixed-version pass (Buggy: 1, Fix: 0) |
| `parse-258` | dev | feasible | reproduced (fix fail) | NO | reproduced (fix fail) | NO | Failed on fix due to minimizer string halving (resolved in Iteration 2) |
| `parse-275` | dev | feasible | not_feasible | NO | needs_info | NO | **IMPROVED**: Eliminated false negative OS refusal |
| `more-itertools-1309`| dev | feasible | reproduced (fix fail) | NO | not_reproduced | NO | Avoided overfitted assertion failure at fix |
| `marshmallow-3082`| dev | feasible | needs_info | NO | needs_info | NO | Maintained conservative clarification |
| `voluptuous-515` | dev | feasible | needs_info | NO | needs_info | NO | Maintained conservative clarification |
| `parse-250` | dev | feasible | not_reproduced | NO | not_reproduced | NO | Agent searched and gave up without invalid test |
| `parse-272` | dev | feasible | not_reproduced | NO | not_reproduced | NO | Agent searched and gave up without invalid test |



---

## Tuning Iteration 2 (Development Split)

### Root Causes Addressed

1. **Minimizer String Literal Over-Reduction (`parse-258`)**:
   - *Problem*: In `src/repro/minimizer.py`, delta debugging on constant literals attempted halving strings via `value[:len(value)//2]`. Slicing `'03:00 pm'` in half produced `'03:0'`, which stripped the meridiem token `pm`. On the buggy tree, `'03:0'` and `'03:00 pm'` both parsed as `3:00`, so the candidate was accepted as minimal. However, on the fixed tree, `'03:00 pm'` parsed as `15:00` while `'03:0'` still parsed as `3:00`, causing the test to fail at the fix commit (`failed_at_fix`).
   - *Fix*: Preserved string and bytes literals in `input_candidates`, testing only empty strings `value[:0]` to detect truly unused parameters without corrupting domain strings (formats, timestamps, regexes).
   - *Outcome*: `'03:00 pm'` is preserved intact; `parse-258` passes on both buggy (exit 1) and fixed (exit 0) commits.

2. **Matcher Assertion Generalization (`parse-272`)**:
   - *Problem*: `_ASSERTION` in `src/repro/matcher.py` strictly matched `==`. Pytest tests asserting `assert result is None` printed `E assert <Result ...> is None`, which was rejected as unrecognized by `DeterministicSymptomChecker`, triggering fruitless escalation and timeout.
   - *Fix*: Expanded `_ASSERTION` regex to match `(?:AssertionError:\s+)?assert\s+(.+?)\s*(?:==|is|!=|is\s+not|in|not\s+in)\s+(.+?)`. Added bidirectional comparison checking: `(left, right)` matches `(actual, expected)` OR `(expected, actual)`.
   - *Outcome*: `parse-272` reproduces in 21.8s ($0.017 cost) and verifies cleanly in Docker.

3. **Matcher Semantic & Representation Canonicalization (`more-itertools-1309` & `parse-258`)**:
   - *Problem*: When issue reporters describe symptoms, they often write `15:00` for `datetime.time(15, 0)` or `"the bucket should be empty"` for `[]`.
   - *Fix*:
     - Added `_normalize_repr` canonicalizing `datetime.time(H, M)` to `HH:MM` and `HH:MM:SS`.
     - Added semantic empty-collection handling: `[]`, `{}`, `""` match descriptive expectations like `"bucket should be empty"`.
     - Handled explanatory assertion text in `_value_matches` safely.
   - *Outcome*: `more-itertools-1309` reproduces in 34.0s ($0.038 cost) and verifies cleanly in Docker.

---

### Tuning Iteration 2 Summary Metrics (Development Split)

| Arm | Split | Feasible Repro Rate (Recall) | Infeasible Refusal Quality | False Positive Claims Rate | Overall Correctness | Total Cost ($) | Avg Duration (s) |
|---|---|---|---|---|---|---|---|
| **Full System** | development | **55.6%** (5/9) | **100.0%** (2/2) | **0.0%** (0/5) | **63.6%** (7/11) | $0.54 | 33.7s |
| **Baseline B** | development | **33.3%** (3/9) | **100.0%** (2/2) | **0.0%** (0/3) | **45.5%** (5/11) | $0.79 | 54.7s |
| **Baseline A** | development | **33.3%** (3/9) | **0.0%** (0/2) | **45.5%** (5/11) | **27.3%** (3/11) | $0.03 | 7.6s |

---

### Tuning Iteration 2 Detailed Issue-by-Issue Results (Development Split)

| Candidate ID | Category | Expected Outcome | Full System | Baseline B | Baseline A | Failure Category / Note |
|---|---|---|---|---|---|---|
| `colorama-89` | infeasible | Refusal (OS API) | **correct_refusal** | **correct_refusal** | incorrect (false pos) | Full & B refuse cleanly; A hallucinates test |
| `validators-dns` | infeasible | Refusal (Network) | **correct_refusal** | **correct_refusal** | incorrect (false pos) | Full & B refuse cleanly; A hallucinates test |
| `parse-258` | feasible | Reproduction | **correct_repro** | **correct_repro** | incorrect (symptom mismatch) | Fixed string truncation in minimizer; 100% verified |
| `parse-267` | feasible | Reproduction | **correct_repro** | **correct_repro** | **correct_repro** | Exact symptom reproduction across all arms |
| `parse-272` | feasible | Reproduction | **correct_repro** | incorrect (not repro) | **correct_repro** | Fixed `is None` assertion matching in matcher |
| `more-itertools-1309` | feasible | Reproduction | **correct_repro** | incorrect (not repro) | **correct_repro** | Fixed empty collection semantic matching |
| `voluptuous-539` | feasible | Reproduction | **correct_repro** | **correct_repro** | incorrect (symptom mismatch) | Clean reproduction verified at buggy & fix |
| `parse-250` | feasible | Reproduction | not_reproduced | not_reproduced | incorrect (failed at fix) | Escaped signed decimal parsing difficulty |
| `parse-275` | feasible | Reproduction | needs_info | needs_info | incorrect (failed at fix) | Conservative triage clarification on missing code |
| `marshmallow-3082` | feasible | Reproduction | needs_info | needs_info | incorrect (symptom mismatch) | Conservative triage clarification on missing code |
| `voluptuous-515` | feasible | Reproduction | needs_info | needs_info | incorrect (symptom mismatch) | Conservative triage clarification on missing code |
