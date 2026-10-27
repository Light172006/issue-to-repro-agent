# Step 8: saved test and result

When the Step 7 checker accepts a submission as `exact` or `partial`, the CLI
copies the submitted Python test from the sandbox's `repro/` mount to
`test_repro.py` in the run folder. It preserves the bytes rather than rewriting
or reformatting the test. It rejects paths outside `/work/repro`, symlinks,
non-regular files, files above 64 KiB, invalid UTF-8 Python and files without a
`test_` function. It never executes the file on the host. The test and JSON
result are written through temporary files and replaced atomically.

`result.json` retains the Step 6 agent fields and adds `status`, `confidence`,
`checks`, `verification`, `status_detail` and `test_file`. An accepted test is
an unverified candidate: its status remains `not_reproduced`, verification is
`pending`, and confidence is null. This means "not yet verified", not that no
failure occurred. Step 9 owns repeated-run and fixed-version verification and
will determine confidence. Runs without candidates use `verification: not_run`.
Pipeline failures after a run folder is created write a sanitized error result
when the filesystem permits it.

To save an already accepted Step 6 run without another model call:

```powershell
python scripts/save_step8_candidate.py runs\766a1a5dcba844ffb3dcf1de38e5b8d9
Get-Content runs\766a1a5dcba844ffb3dcf1de38e5b8d9\result.json
```

The script checks the saved issue record and submission output with the current
deterministic matcher before saving the test. It does not rerun the test, and
modified run records are not independent evidence. It is safe to invoke the
script again on the same run.

To run the saved test independently, with no model call, copy only the test to
a temporary directory and mount that directory read-only:

```powershell
$run = "runs\766a1a5dcba844ffb3dcf1de38e5b8d9"
$image = (Get-Content "$run\environment.json" | ConvertFrom-Json).image
$checkDir = Join-Path $env:TEMP ("repro-check-" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $checkDir | Out-Null
Copy-Item "$run\test_repro.py" "$checkDir\test_repro.py"
docker run --rm --network none --user 65534:65534 --read-only `
  --tmpfs /tmp:rw,noexec,nosuid,size=64m `
  -e PYTHONDONTWRITEBYTECODE=1 -e HOME=/tmp -e TMPDIR=/tmp `
  --mount "type=bind,source=$checkDir,target=/work/repro,readonly" `
  --workdir /var/tmp/repro/source `
  $image /var/tmp/repro/venv/bin/python -m pytest -p no:cacheprovider /work/repro/test_repro.py
$testExit = $LASTEXITCODE
Remove-Item -Recurse -Force $checkDir
Write-Host "Pytest exit code:" $testExit "(1 is expected for a failing test)"
```

The failure must match the reported symptom; a nonzero exit code alone is not
enough. This manual check does not replace the Step 9 verifier.
