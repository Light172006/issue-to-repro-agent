# Benchmark Evaluation Notes & Tuning Journal

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

| Arm | Total Issues | Correct | Correctness (%) | Precision (%) | Recall (%) | Total Spend ($) | Avg Spend / Issue ($) | Avg Duration (s) |
|---|---|---|---|---|---|---|---|---|
| **Full System** | 11 | 5 | **45.5%** (+18.2% vs pre) | **100.0%** (5/5) | **33.3%** (3/9) | $1.01 | $0.0919 | 48.5s |
| **Baseline B** | 11 | 5 | **45.5%** (5/11) | **100.0%** (5/5) | **33.3%** (3/9) | $0.79 | $0.0717 | 54.7s |
| **Baseline A** | 11 | 9 | **81.8%** (9/11) | **81.8%** (9/11) | **100.0%** (9/9) | $0.03 | $0.0026 | 7.6s |

---

### Side-by-Side Comparison: Pre-Tuning vs Post-Tuning (Full System)

| Issue ID | Split | Category | Pre Run Status | Pre Correct? | Post Run Status | Post Correct? | Delta / Note |
|---|---|---|---|---|---|---|---|
| `colorama-89` | dev | infeasible | not_feasible | **YES** | not_feasible | **YES** | Maintained correct refusal (Windows console API) |
| `validators-dns` | dev | infeasible | not_feasible | **YES** | not_feasible | **YES** | Maintained correct refusal (Network DNS lookup) |
| `parse-267` | dev | feasible | reproduced | **YES** | reproduced | **YES** | Maintained exact symptom reproduction (Buggy: 1, Fix: 0) |
| `parse-258` | dev | feasible | reproduced (fix fail) | NO | reproduced | **YES** | **IMPROVED**: Fixed-version pass (Buggy: 1, Fix: 0) |
| `voluptuous-539` | dev | feasible | reproduced (fix fail) | NO | reproduced | **YES** | **IMPROVED**: Fixed-version pass (Buggy: 1, Fix: 0) |
| `parse-275` | dev | feasible | not_feasible | NO | needs_info | NO | **IMPROVED**: Eliminated false negative OS refusal |
| `more-itertools-1309`| dev | feasible | reproduced (fix fail) | NO | not_reproduced | NO | Avoided overfitted assertion failure at fix |
| `marshmallow-3082`| dev | feasible | needs_info | NO | needs_info | NO | Maintained conservative clarification |
| `voluptuous-515` | dev | feasible | needs_info | NO | needs_info | NO | Maintained conservative clarification |
| `parse-250` | dev | feasible | not_reproduced | NO | not_reproduced | NO | Agent searched and gave up without invalid test |
| `parse-272` | dev | feasible | not_reproduced | NO | not_reproduced | NO | Agent searched and gave up without invalid test |

