# Step 10 minimizer

The minimizer operates only on a saved, verifier-confirmed pytest candidate.
It uses source ranges from Python's AST to remove statements, then tries line
removal and smaller string, bytes and integer literals. Every valid candidate
is run in a fresh network-disabled sandbox through the verifier's runner. The
matcher verdict and the normalized exception type, message and frame must
match the baseline. Unsupported symptoms are skipped rather than guessed.

The original baseline receives at most 60 seconds (or the configured timeout
if higher), subject to the remaining deadline. Subsequent candidate timeouts
are the greater of 10 seconds, the configured timeout and twice the measured
baseline wall time; the overall deadline still takes precedence. Syntax errors
do not use a container run. The default limit is 100 runs and 300 seconds,
with one worker. Candidate content hashes prevent duplicate executions.

The original test is retained as `test_repro.orig.py`. A proposed result is
accepted only after repeated verification, and when applicable a fixed-image
check, without lowering confidence. Evidence is written to `result.json` and
`minimize.jsonl`. A timed-out reduction may have to fall back if there is no
time left for mandatory final verification. Only completed reductions are
checked for single-statement minimality; this does not guarantee a globally
smallest program.

The existing pipeline has no `report.py` yet; reporting belongs to Step 11.
The local run script reads `test_repro.py`, so it uses the accepted minimized
file. Bare scripts, external `conftest.py` dependencies and tests requiring
plugins not installed in the image are not automatically supported by the
current verifier. Multiline literals, input-dependent error messages, and
complex AST transformations may limit reduction. An unchanged or unverified
candidate is kept intact.

The bundled bloated Docker fixture is based on boltons #337, an independently
verified real issue. The originally proposed dur-demo fixture was never supplied
as an accessible repository, so no behavior or test result is claimed for it.
