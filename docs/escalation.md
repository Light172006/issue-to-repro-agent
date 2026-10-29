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
