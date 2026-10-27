# Step 7 symptom matching

`DeterministicSymptomChecker` is the default checker used by `submit_repro`.
It makes no model calls and does not assign confidence. The verifier in Step 9
will need to determine confidence through repeated execution and fix checks.

For exceptions, the matcher extracts the final exception type and normalized
message and attempts to identify the innermost frame from standard Python,
IPython, or pytest output. `exact` requires the reported type, normalized
message and frame to match; `partial` requires the final exception type to
match but at least one other item to be missing or different; `none` means
there is no extracted matching final exception. Numeric values, paths,
hexadecimal IDs and addresses use the parser's normalization rules.

For wrong-output issues, an `exact` result requires a pytest `assert actual ==
expected` comparison matching both reported values. Other comparisons return
`none`. The matcher does not currently judge performance, regressions without
an exception, crashes without an exception, arbitrary application output,
complex assertion diffs, or exception groups. It does not call a model as a
tiebreaker. A `partial` result alone is not proof of causal equivalence.

Frame inference in pytest may rely on the function definition displayed just
before an error and the file location displayed just after it; unusual pytest
plugins, truncated traces and non-Python frames can make a match partial or
unavailable. Output is untrusted and can be forged by a test. The checker is a
filter and is not a security boundary.

The offline checkpoint is 15 saved, simulated failure outputs (including a
shortened pytest traceback based on the manually verified boltons repro):

```powershell
python -m pytest tests/test_matcher.py
python -m pytest -m "not docker and not network"
```
