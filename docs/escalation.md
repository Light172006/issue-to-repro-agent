# Step 12 escalation (initial implementation)

A deterministic detector examines recorded tool calls after at least four tool
steps. It looks for three matching consecutive errors, three identical calls,
ABAB oscillation, or five steps with no output, exception, or file-content
hash not already seen. Repeated sandbox failures or timeouts are treated as
infrastructure failures. Late triggering starts at 60% of steps or 50% of the
run dollar cap. `--no-escalation` disables escalation.

One handoff to Muse Wonder is allowed; the run's global 25-step, $1 and 900-s
limits remain shared. Wonder has a 10-step, $0.60 cap and requires at least
five steps and $0.25 remaining. Each model call still reserves its full
preflight input plus output allowance in the model layer before generation.
A separate reservation ceiling limits Wonder's remaining allowance. Model
failures retain reservations and fall back to Spark once.

The handoff is deterministic, redacts known and recognizable secrets, and
wraps prior tool output in untrusted-data delimiters. It includes the issue,
recorded calls, error counts, recent steps and the latest repro file when it
can be read in the sandbox. Hypotheses are not currently recorded by the loop,
so the summary explicitly says they are unavailable. The trace records the
summary size in characters and a UTF-8-byte token upper bound; it does not
claim an exact token count for the summary alone.

Calibration is limited: the saved successful boltons trace did not trigger the
default stall rules. Original complete stuck-run traces are not available in
this workspace. The result remains subject to Docker and paid end-to-end
validation, and is not proof of an escalation improvement.


## Calibration & Validation Results (C2)

1. **Forced Handoff Plumbing Validation**:
   - Issue: `humanize #57`, run with `--force-escalate-at-step 2`.
   - Run ID: `62fd7945c92c405a824adc1a00287cbf`.
   - Result: `status: "reproduced"`, `solved_after_escalation: true`, `verdict: "exact"`, 5/5 repeated runs matched, minimized to 3 lines in 13.1s, cost $0.036172. Handoff summary packaging, context compaction, and post-handoff solver execution verified end-to-end.

2. **Step 12 Benchmark Issue Evaluation (`bench/step12_issues.txt`)**:
   - `humanize #57`: Spark-1 reproduced at step 8 ($0.03065); Spark-2 reproduced at step 7 ($0.0229). Escalation was correctly skipped per budget-saving protocol.
   - `boltons #337`: Failed initially due to legacy Python 2.7 dependencies extracted from `tox.ini` conflicting with modern packages (`pytest-cov==2.12` vs `pytest-cov==4.0.0`). Fixed by ignoring py2 and linter tox sections and deduplicating package names (`c5b34b1`). Re-build verified: 407/407 tests passed.
   - `pydash #153`: `spark-1` stopped at step 1; `spark-2` exhausted 25-step budget ($0.202); `escalation` run stopped at step 12 ($0.058).
   - `attrs #1348`: `spark-1` exhausted 25-step budget ($0.211); `spark-2` stopped at step 9 ($0.052); `escalation` triggered at step 15, called Wonder ($0.043 Wonder cost), then caught `ProviderError` from Wonder and fell back cleanly to Spark without crashing.

3. **Honest Evaluation Assessment**:
   - Escalation did not rescue unresolved runs in this issue set: tractable issues were resolved directly by Spark 1.3 without needing escalation, while stalled multi-turn runs on large repositories encountered provider context/token errors on Wonder, prompting clean fallback to Spark.
   - The escalation fallback and budget containment mechanisms behaved robustly under live network and model errors without leaking state or crashing.
