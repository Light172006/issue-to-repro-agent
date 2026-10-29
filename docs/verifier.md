# Step 9 verifier

For each candidate the CLI makes five fresh, network-disabled container runs.
Each receives a separate temporary writable mount containing the same saved test.
The matcher checks the actual pytest output. A timeout, collection error, or
other exit code is not a matching failure. The normalized exception type,
message and innermost frame must agree across repetitions; wrong-output checks
must match the reported actual and expected values on every repetition.

Confidence is computed from the observations. Exact and consistent failures
are medium until a later fixed environment passes; a successful fixed check
makes them high. Partial or inconsistent matches are low. A fixed check that
fails or cannot run does not establish a verified reproduction. A passing run
must report at least one passed pytest test; skipped-only runs are not passes.

Replay a saved run without model calls:

```powershell
python scripts/verify_step9.py runs\<run-id> --fixed-version <known-fixed-tag>
```

The optional `--find-release` selects the first later stable numeric GitHub
release from the first 100 releases. It is a candidate, not evidence of a fix;
the saved test must pass there. If a repository has no suitable GitHub release,
or uses unusual tag names, provide a known fixed tag or commit explicitly.
The caller must confirm that an explicitly supplied commit contains the fix.
No fixed release yields at most medium confidence. The CLI initially performs
only the five buggy-version checks; use the replay script for the comparison.
Each replay writes its evidence and the test SHA-256 to `result.json`. The
fixed environment metadata, when built, is in `fixed_environment/`.

Docker and image builds are required for real verification. The verifier makes
no model calls. The Step 9 checkpoint still requires five independently verified
real issues, with failing buggy versions and passing fixed versions.
