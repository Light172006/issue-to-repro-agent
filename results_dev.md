# Benchmark Evaluation Results

Autonomous issue reproduction benchmark evaluated across pure-Python utility libraries.

**Evaluation Ground Rules:**
- **Feasible Success:** Candidate test must FAIL at buggy commit (symptom match) and PASS cleanly at fix commit (exit code 0).
- **Infeasible Success:** Agent must declare `not_feasible` with matching OS/network/hardware refusal reason.
- **Baseline B:** Skipped per hackathon cut list ("not run").

## Summary Comparison

| Arm | Split | Total | Correct | Correctness (%) | Precision (%) | Recall (%) | Total Cost ($) | Avg Cost ($) | Avg Time (s) |
|---|---|---|---|---|---|---|---|---|---|
| `full` | development | 11 | 3/11 | **27.3%** | 100.0% | 11.1% | $0.42 | $0.0377 | 26.1s |
| `full` | held_out | 0 | 0 | *Not Run* | *Not Run* | *Not Run* | $0.00 | $0.0000 | 0.0s |
| `baseline_a` | development | 11 | 2/11 | **18.2%** | 50.0% | 22.2% | $0.03 | $0.0026 | 7.6s |
| `baseline_a` | held_out | 0 | 0 | *Not Run* | *Not Run* | *Not Run* | $0.00 | $0.0000 | 0.0s |
| `baseline_b` | development | 0 | 0 | *Not Run* | *Not Run* | *Not Run* | $0.00 | $0.0000 | 0.0s |
| `baseline_b` | held_out | 0 | 0 | *Not Run* | *Not Run* | *Not Run* | $0.00 | $0.0000 | 0.0s |

## Failure Taxonomy

| Failure Category | Full System (Dev) | Full System (Held-Out) | Baseline A (Dev) | Baseline A (Held-Out) | Description |
|---|---|---|---|---|---|
| `passed_at_buggy` | 0 | 0 | 0 | 0 | Test trivially passed at buggy commit; failed to reproduce bug |
| `failed_at_fix` | 3 | 0 | 1 | 0 | Test failed at fix commit; overfit, fragile or broke on fixed tree |
| `symptom_mismatch` | 0 | 0 | 2 | 0 | Test failed at buggy commit with different exception or signature |
| `false_positive_attempt` | 0 | 0 | 2 | 0 | Attempted test on infeasible issue (hardware/os/network constraint ignored) |
| `false_negative_refusal` | 1 | 0 | 0 | 0 | Wrongly refused a feasible issue as not_feasible |
| `gave_up` | 0 | 0 | 0 | 0 | Agent gave up without finding a reproduction candidate |
| `limit_hit` | 0 | 0 | 0 | 0 | Exceeded step, dollar, or timeout ceilings before completion |

## Detailed Issue-by-Issue Audit

| Issue ID | Arm | Split | Category | Run Status | Buggy Exit | Fix Exit | Symptom Match | Correct? | Cost USD | Time (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| `colorama-89` | `baseline_a` | development | infeasible | candidate_found | - | - | - | NO | $0.00871725 | 24.1s |
| `marshmallow-3082` | `baseline_a` | development | feasible | candidate_found | 1 | - | none | NO | $0.00264325 | 9.8s |
| `more-itertools-1309` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | partial | **YES** | $0.001071 | 6.7s |
| `parse-250` | `baseline_a` | development | feasible | candidate_found | 1 | 1 | partial | NO | $0.002122 | 4.5s |
| `parse-258` | `baseline_a` | development | feasible | candidate_found | 1 | - | none | NO | $0.00193425 | 5.5s |
| `parse-267` | `baseline_a` | development | feasible | candidate_found | 1 | 0 | partial | **YES** | $0.001687 | 4.4s |
| `parse-272` | `baseline_a` | development | feasible | candidate_found | - | - | - | NO | $0.00271 | 6.1s |
| `parse-275` | `baseline_a` | development | feasible | candidate_found | - | - | - | NO | $0.00323025 | 8.0s |
| `validators-dns` | `baseline_a` | development | infeasible | candidate_found | - | - | - | NO | $0.00149475 | 4.7s |
| `voluptuous-515` | `baseline_a` | development | feasible | candidate_found | - | - | - | NO | $0.00219725 | 6.6s |
| `voluptuous-539` | `baseline_a` | development | feasible | candidate_found | - | - | - | NO | $0.001332 | 3.8s |
| `colorama-89` | `full` | development | infeasible | not_feasible | - | - | - | **YES** | $0.0057455 | 12.0s |
| `marshmallow-3082` | `full` | development | feasible | needs_info | - | - | - | NO | $0.00300325 | 7.5s |
| `more-itertools-1309` | `full` | development | feasible | reproduced | 1 | 1 | partial | NO | $0.03862375 | 38.5s |
| `parse-250` | `full` | development | feasible | not_reproduced | - | - | - | NO | $0.03898375 | 28.4s |
| `parse-258` | `full` | development | feasible | reproduced | 1 | 1 | partial | NO | $0.02059175 | 20.4s |
| `parse-267` | `full` | development | feasible | reproduced | 1 | 0 | partial | **YES** | $0.0186565 | 21.2s |
| `parse-272` | `full` | development | feasible | not_reproduced | - | - | - | NO | $0.245437 | 98.3s |
| `parse-275` | `full` | development | feasible | not_feasible | - | - | - | NO | $0.004692 | 8.3s |
| `validators-dns` | `full` | development | infeasible | not_feasible | - | - | - | **YES** | $0.005185 | 9.8s |
| `voluptuous-515` | `full` | development | feasible | needs_info | - | - | - | NO | $0.00465375 | 10.2s |
| `voluptuous-539` | `full` | development | feasible | reproduced | 1 | 1 | partial | NO | $0.0295105 | 32.5s |
