# Step 6: local verification

The manual issue is https://github.com/mahmoud/boltons/issues/337. It reports
version 23.0.0 and an AttributeError during a pickle round trip. The temporary
checker only supports exceptions, using the exception type and function name.
It is a heuristic, not a verifier; Step 7 replaces it. A candidate is not a
proven reproduction until the saved test is independently checked.

Each tool command runs in a new non-root, network-disabled container with a
read-only root filesystem and a size-limited `/tmp`. A single host folder,
`runs/<id>/repro`, is mounted read-write at `/work/repro`; traces, ledgers,
and results are outside that mount. The folder is created with mode 0777 on
Unix so UID 65534 can write; this makes its contents writable by other local
users who can traverse the run directory. Windows Docker Desktop translates
host permissions and must be verified locally. Newly built images store their
virtualenv and source at `/var/tmp/repro`; the builder cache key was bumped.
Images created by earlier versions should be rebuilt.

From PowerShell, after installing the package and with Linux containers enabled:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -m "not docker and not network"
docker pull python:3.11-slim
docker pull python:3.11
python -m pytest -m docker
python -m repro.envbuilder mahmoud/boltons --version 23.0.0 --output-dir environment/boltons --test-dependency "pytest<9"
$image = (Get-Content environment\boltons\environment.json | ConvertFrom-Json).image
python scripts/check_isolation.py --image $image
```

The Docker-marked tests and isolation script require a running Docker daemon.
The script checks that a host-side localhost listener cannot be reached from
the container. The image's network mode is configured as `none` in every agent
run. Network and Docker tests have not been run in the development environment.

Only after approving the estimated cost, run the paid test:

```powershell
$env:META_MODEL_API_KEY = Read-Host "Meta API key"
python -u scripts/e2e_step6.py
Remove-Item Env:META_MODEL_API_KEY
```

Do not paste the key in chat. A typical 10–20-call run is roughly $0.15–$0.50,
depending on token usage; the configured per-run cap is $1.00. The cap also
reserves cost conservatively when usage is unavailable. Verify the candidate
repro by running the saved test independently against the reported version.
No real paid end-to-end run has yet been performed. Step 6 remains unverified
until the isolation checks and the manual run pass.

Known limitations: the trace records cached tokens as null because the current
model interface does not expose them. The existing model-call trace is written
separately from the agent step trace. The naive checker cannot judge wrong
output, performance, crashes without an exception, or causal equivalence.
