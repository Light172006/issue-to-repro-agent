# Benchmark Evaluation Results

Autonomous issue reproduction benchmark evaluated across pure-Python utility libraries.

**Evaluation Ground Rules:**
- **Feasible Success:** Candidate test must FAIL at buggy commit (symptom match) and PASS cleanly at fix commit (exit code 0).
- **Infeasible Success:** Agent must declare `not_feasible` with matching OS/network/hardware refusal reason.
- **Baseline B:** Agent loop in sandbox without independent verifier or AST minimizer.

## Summary Comparison

| Arm | Split | Total | Correct | Correctness (%) | Precision (%) | Recall (%) | Total Cost ($) | Avg Cost ($) | Avg Time (s) |
|---|---|---|---|---|---|---|---|---|---|
| `full` | development | 11 | 5/11 | **45.5%** | 100.0% | 33.3% | $1.01 | $0.0919 | 48.5s |
| `full` | held_out | 0 | 0 | *Not Run* | *Not Run* | *Not Run* | $0.00 | $0.0000 | 0.0s |
| `baseline_a` | development | 11 | 9/11 | **81.8%** | 81.8% | 100.0% | $0.03 | $0.0026 | 7.6s |
| `baseline_a` | held_out | 0 | 0 | *Not Run* | *Not Run* | *Not Run* | $0.00 | $0.0000 | 0.0s |
| `baseline_b` | development | 11 | 5/11 | **45.5%** | 100.0% | 33.3% | $0.79 | $0.0717 | 54.7s |
| `baseline_b` | held_out | 0 | 0 | *Not Run* | *Not Run* | *Not Run* | $0.00 | $0.0000 | 0.0s |

## Failure Taxonomy

| Failure Category | Full System (Dev) | Full System (Held-Out) | Baseline A (Dev) | Baseline A (Held-Out) | Description |
|---|---|---|---|---|---|
| `passed_at_buggy` | 0 | 0 | 0 | 0 | Test trivially passed at buggy commit; failed to reproduce bug |
| `failed_at_fix` | 0 | 0 | 0 | 0 | Test failed at fix commit; overfit, fragile or broke on fixed tree |
| `symptom_mismatch` | 0 | 0 | 0 | 0 | Test failed at buggy commit with different exception or signature |
| `false_positive_attempt` | 0 | 0 | 2 | 0 | Attempted test on infeasible issue (hardware/os/network constraint ignored) |
| `false_negative_refusal` | 0 | 0 | 0 | 0 | Wrongly refused a feasible issue as not_feasible |
| `gave_up` | 0 | 0 | 0 | 0 | Agent gave up without finding a reproduction candidate |
| `limit_hit` | 0 | 0 | 0 | 0 | Exceeded step, dollar, or timeout ceilings before completion |

## Detailed Issue-by-Issue Audit

| Issue ID | Arm | Split | Category | Run Status | Buggy Exit | Fix Exit | Symptom Match | Correct? | Cost USD | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| `colorama-89` | `baseline_a` | development | infeasible | candidate_found | - | - | - | NO | $0.00871725 | 24.1s |
| `marshmallow-3082` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.00264325 | 9.8s |
| `more-itertools-1309` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.001071 | 6.7s |
| `parse-250` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.002122 | 4.5s |
| `parse-258` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.00193425 | 5.5s |
| `parse-267` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.001687 | 4.4s |
| `parse-272` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.00271 | 6.1s |
| `parse-275` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.00323025 | 8.0s |
| `validators-dns` | `baseline_a` | development | infeasible | candidate_found | - | - | - | NO | $0.00149475 | 4.7s |
| `voluptuous-515` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.00219725 | 6.6s |
| `voluptuous-539` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.001332 | 3.8s |
| `colorama-89` | `baseline_b` | development | infeasible | not_feasible | - | - | - | **YES** | $0.00506125 | 15.3s |
| `marshmallow-3082` | `baseline_b` | development | feasible | needs_info | - | - | - | NO | $0.00386175 | 13.0s |
| `more-itertools-1309` | `baseline_b` | development | feasible | not_reproduced | - | - | - | NO | $0.27561925 | 132.7s |
| `parse-250` | `baseline_b` | development | feasible | not_reproduced | - | - | - | NO | $0.30034575 | 158.0s |
| `parse-258` | `baseline_b` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.06688525 | 55.9s |
| `parse-267` | `baseline_b` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.04072325 | 51.6s |
| `parse-272` | `baseline_b` | development | feasible | not_reproduced | - | - | - | NO | $0.04476925 | 108.6s |
| `parse-275` | `baseline_b` | development | feasible | needs_info | - | - | - | NO | $0.0042585 | 10.3s |
| `validators-dns` | `baseline_b` | development | infeasible | not_feasible | - | - | - | **YES** | $0.004097 | 12.7s |
| `voluptuous-515` | `baseline_b` | development | feasible | needs_info | - | - | - | NO | $0.00483225 | 13.6s |
| `voluptuous-539` | `baseline_b` | development | feasible | candidate_found | 1 | 0 | exact | **YES** | $0.03861375 | 30.2s |
| `colorama-89` | `full` | development | infeasible | not_feasible | - | - | - | **YES** | $0.00488275 | 15.0s |
| `marshmallow-3082` | `full` | development | feasible | needs_info | - | - | - | NO | $0.00299475 | 10.9s |
| `more-itertools-1309` | `full` | development | feasible | not_reproduced | - | - | - | NO | $0.296299 | 126.5s |
| `parse-250` | `full` | development | feasible | not_reproduced | - | - | - | NO | $0.33946425 | 148.2s |
| `parse-258` | `full` | development | feasible | reproduced | 1 | 0 | exact | **YES** | $0.0198365 | 26.7s |
| `parse-267` | `full` | development | feasible | reproduced | 1 | 0 | exact | **YES** | $0.06541225 | 46.6s |
| `parse-272` | `full` | development | feasible | not_reproduced | - | - | - | NO | $0.22731075 | 89.2s |
| `parse-275` | `full` | development | feasible | needs_info | - | - | - | NO | $0.00557175 | 13.1s |
| `validators-dns` | `full` | development | infeasible | not_feasible | - | - | - | **YES** | $0.0043775 | 10.8s |
| `voluptuous-515` | `full` | development | feasible | needs_info | - | - | - | NO | $0.00662575 | 16.4s |
| `voluptuous-539` | `full` | development | feasible | reproduced | 1 | 0 | exact | **YES** | $0.0385225 | 30.3s |
