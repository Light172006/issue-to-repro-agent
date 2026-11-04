# Benchmark Evaluation Results

Autonomous issue reproduction benchmark evaluated across pure-Python utility libraries.

**Evaluation Ground Rules & Metric Definitions:**
- **Feasible Success:** Candidate test must FAIL at buggy commit (exit 1, symptom match) and PASS cleanly at fix commit (exit 0).
- **Infeasible Success:** Agent must declare `not_feasible` with matching OS/network/hardware refusal reason.
- **Reproduction Rate:** Correct feasible reproductions / total feasible issues.
- **Fail-to-Pass:** Strict, matcher-independent count of tests that exit 1 at buggy and exit 0 at fix.
- **Symptom Match:** Count of candidate tests matching reported symptom signature at buggy commit.
- **Claims (Tot / Corr / Wr):** Total claims with status `reproduced` or `candidate_found` (correct claims / wrong claims).
- **Wrong-Claim Rate:** Wrong claims / all claims (lower is better; 0.0% is zero false positives).
- **Infeasible Refusal:** Correct refusals / total infeasible issues.
- **Overall Correctness:** All correct outcomes (reproductions + refusals) / total issues.

## Summary Comparison

| Arm | Split | Feasible Repro Rate | Fail-to-Pass | Symptom Match | Claims (Tot / Corr / Wr) | Wrong-Claim Rate | Infeasible Refusal | Overall Correctness | Total Cost ($) | Avg Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| `full` | development | **55.6%** (5/9) | 5/9 | 5/9 | 5 (5 / 0) | 0.0% | 100.0% (2/2) | **63.6%** (7/11) | $0.54 | 33.7s |
| `full` | held_out | **0.0%** (0/5) | 0/5 | 1/5 | 1 (0 / 1) | 100.0% | 100.0% (2/2) | **28.6%** (2/7) | $0.70 | 46.9s |
| `baseline_b` | development | **33.3%** (3/9) | 3/9 | 3/9 | 3 (3 / 0) | 0.0% | 100.0% (2/2) | **45.5%** (5/11) | $0.79 | 54.7s |
| `baseline_b` | held_out | **40.0%** (2/5) | 2/5 | 2/5 | 3 (2 / 1) | 33.3% | 100.0% (2/2) | **57.1%** (4/7) | $0.86 | 53.6s |
| `baseline_a` | development | **22.2%** (2/9) | 5/9 | 4/9 | 11 (2 / 9) | 81.8% | 0.0% (0/2) | **18.2%** (2/11) | $0.03 | 7.6s |
| `baseline_a` | held_out | **80.0%** (4/5) | 5/5 | 4/5 | 7 (4 / 3) | 42.9% | 0.0% (0/2) | **57.1%** (4/7) | $0.03 | 9.5s |

## Failure Taxonomy

| Failure Category | Full System (Dev) | Full System (Held-Out) | Baseline B (Dev) | Baseline B (Held-Out) | Baseline A (Dev) | Baseline A (Held-Out) | Description |
|---|---|---|---|---|---|---|---|
| `passed_at_buggy` | 0 | 0 | 0 | 0 | 0 | 0 | Test trivially passed at buggy commit; failed to reproduce bug |
| `failed_at_fix` | 0 | 1 | 0 | 0 | 2 | 0 | Test failed at fix commit; overfit, fragile or broke on fixed tree |
| `symptom_mismatch` | 0 | 0 | 0 | 1 | 5 | 1 | Test failed at buggy commit with different exception or signature |
| `false_positive_attempt` | 0 | 0 | 0 | 0 | 2 | 2 | Attempted test on infeasible issue (hardware/os/network constraint ignored) |
| `false_negative_refusal` | 0 | 0 | 0 | 0 | 0 | 0 | Wrongly refused a feasible issue as not_feasible |
| `gave_up` | 0 | 0 | 0 | 0 | 0 | 0 | Agent gave up without finding a reproduction candidate |
| `limit_hit` | 0 | 0 | 0 | 0 | 0 | 0 | Exceeded step, dollar, or timeout ceilings before completion |

## Detailed Issue-by-Issue Audit

| Issue ID | Arm | Split | Category | Run Status | Buggy Exit | Fix Exit | Fail to Pass | Symptom Match | Correct? | Cost USD | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `addict-102` | `baseline_a` | held_out | feasible | candidate_found | 1 | 0 | YES | none | NO | $0.00176625 | 5.2s |
| `addict-28` | `baseline_a` | held_out | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.001869 | 6.2s |
| `colorama-110` | `baseline_a` | held_out | infeasible | candidate_found | - | - | - | - | NO | $0.007975 | 18.2s |
| `colorama-89` | `baseline_a` | development | infeasible | candidate_found | - | - | - | - | NO | $0.00871725 | 24.1s |
| `gpustat-cuda` | `baseline_a` | held_out | infeasible | candidate_found | - | - | - | - | NO | $0.00908125 | 20.0s |
| `marshmallow-3082` | `baseline_a` | development | feasible | candidate_found | 1 | 1 | NO | none | NO | $0.00264325 | 9.8s |
| `more-itertools-1309` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | YES | none | NO | $0.001071 | 6.7s |
| `parse-250` | `baseline_a` | development | feasible | candidate_found | 1 | 1 | NO | partial | NO | $0.002122 | 4.5s |
| `parse-258` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | YES | none | NO | $0.00193425 | 5.5s |
| `parse-267` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.001687 | 4.4s |
| `parse-272` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.00271 | 6.1s |
| `parse-275` | `baseline_a` | development | feasible | candidate_found | 1 | 1 | NO | partial | NO | $0.00323025 | 8.0s |
| `semver-480` | `baseline_a` | held_out | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.00315525 | 3.8s |
| `semver-501` | `baseline_a` | held_out | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.00345625 | 8.3s |
| `tabulate-410` | `baseline_a` | held_out | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.001801 | 4.6s |
| `validators-dns` | `baseline_a` | development | infeasible | candidate_found | - | - | - | - | NO | $0.00149475 | 4.7s |
| `voluptuous-515` | `baseline_a` | development | feasible | candidate_found | 1 | 1 | NO | none | NO | $0.00219725 | 6.6s |
| `voluptuous-539` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | YES | none | NO | $0.001332 | 3.8s |
| `addict-102` | `baseline_b` | held_out | feasible | not_reproduced | - | - | - | - | NO | $0.244328 | 82.7s |
| `addict-28` | `baseline_b` | held_out | feasible | not_reproduced | - | - | - | - | NO | $0.21696275 | 123.6s |
| `colorama-110` | `baseline_b` | held_out | infeasible | not_feasible | - | - | - | - | **YES** | $0.003809 | 6.3s |
| `colorama-89` | `baseline_b` | development | infeasible | not_feasible | - | - | - | - | **YES** | $0.00506125 | 15.3s |
| `gpustat-cuda` | `baseline_b` | held_out | infeasible | not_feasible | - | - | - | - | **YES** | $0.00518225 | 10.1s |
| `marshmallow-3082` | `baseline_b` | development | feasible | needs_info | - | - | - | - | NO | $0.00386175 | 13.0s |
| `more-itertools-1309` | `baseline_b` | development | feasible | not_reproduced | - | - | - | - | NO | $0.27561925 | 132.7s |
| `parse-250` | `baseline_b` | development | feasible | not_reproduced | - | - | - | - | NO | $0.30034575 | 158.0s |
| `parse-258` | `baseline_b` | development | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.06688525 | 55.9s |
| `parse-267` | `baseline_b` | development | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.04072325 | 51.6s |
| `parse-272` | `baseline_b` | development | feasible | not_reproduced | - | - | - | - | NO | $0.04476925 | 108.6s |
| `parse-275` | `baseline_b` | development | feasible | needs_info | - | - | - | - | NO | $0.0042585 | 10.3s |
| `semver-480` | `baseline_b` | held_out | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.050376 | 30.0s |
| `semver-501` | `baseline_b` | held_out | feasible | candidate_found | 1 | 1 | NO | none | NO | $0.06275775 | 45.7s |
| `tabulate-410` | `baseline_b` | held_out | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.27813625 | 76.5s |
| `validators-dns` | `baseline_b` | development | infeasible | not_feasible | - | - | - | - | **YES** | $0.004097 | 12.7s |
| `voluptuous-515` | `baseline_b` | development | feasible | needs_info | - | - | - | - | NO | $0.00483225 | 13.6s |
| `voluptuous-539` | `baseline_b` | development | feasible | candidate_found | 1 | 0 | YES | partial | **YES** | $0.03861375 | 30.2s |
| `addict-102` | `full` | held_out | feasible | not_reproduced | - | - | - | - | NO | $0.0703895 | 59.7s |
| `addict-28` | `full` | held_out | feasible | not_reproduced | - | - | - | - | NO | $0.10620525 | 42.3s |
| `colorama-110` | `full` | held_out | infeasible | not_feasible | - | - | - | - | **YES** | $0.005509 | 11.1s |
| `colorama-89` | `full` | development | infeasible | not_feasible | - | - | - | - | **YES** | $0.00488275 | 15.0s |
| `gpustat-cuda` | `full` | held_out | infeasible | not_feasible | - | - | - | - | **YES** | $0.00546275 | 12.2s |
| `marshmallow-3082` | `full` | development | feasible | needs_info | - | - | - | - | NO | $0.00299475 | 10.9s |
| `more-itertools-1309` | `full` | development | feasible | reproduced | 1 | 0 | YES | partial | **YES** | $0.03750825 | 34.0s |
| `parse-250` | `full` | development | feasible | not_reproduced | - | - | - | - | NO | $0.33946425 | 148.2s |
| `parse-258` | `full` | development | feasible | reproduced | 1 | 0 | YES | partial | **YES** | $0.0189905 | 24.2s |
| `parse-267` | `full` | development | feasible | reproduced | 1 | 0 | YES | partial | **YES** | $0.06541225 | 46.6s |
| `parse-272` | `full` | development | feasible | reproduced | 1 | 0 | YES | partial | **YES** | $0.01737475 | 21.8s |
| `parse-275` | `full` | development | feasible | needs_info | - | - | - | - | NO | $0.00557175 | 13.1s |
| `semver-480` | `full` | held_out | feasible | reproduced | 1 | 1 | NO | partial | NO | $0.03919925 | 28.6s |
| `semver-501` | `full` | held_out | feasible | not_reproduced | - | - | - | - | NO | $0.19692875 | 79.2s |
| `tabulate-410` | `full` | held_out | feasible | not_reproduced | - | - | - | - | NO | $0.2770155 | 94.9s |
| `validators-dns` | `full` | development | infeasible | not_feasible | - | - | - | - | **YES** | $0.0043775 | 10.8s |
| `voluptuous-515` | `full` | development | feasible | needs_info | - | - | - | - | NO | $0.00662575 | 16.4s |
| `voluptuous-539` | `full` | development | feasible | reproduced | 1 | 0 | YES | partial | **YES** | $0.0385225 | 30.3s |
