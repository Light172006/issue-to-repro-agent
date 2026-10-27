# Issue-to-Repro Agent

A Python tool under development that aims to turn GitHub bug reports into verified, minimal failing tests, or explain why a bug could not be reproduced. Built for the Meta Global AI Hackathon, indie track, Build for Your World.

## Status

Step 0 and the Step 1 real-call check are complete. Step 2 includes an issue fetcher; its five-repository live test remains pending. No reproduction or sandbox functionality has been implemented.

## Windows setup and validation

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

To verify the Meta integration, set `META_MODEL_API_KEY` in your own PowerShell session (do not commit or share it), then run:

```powershell
$env:META_MODEL_API_KEY = Read-Host "Meta API key"
python scripts/check_muse.py
Remove-Item Env:META_MODEL_API_KEY
```

## Budget and limitations

All model calls go through `repro.llm.call_model`. The guard caps configured limits at 25 model calls per run, $1 per run, 900 seconds, $5 per UTC day, and $120 total. It uses a shared SQLite ledger and atomic reservations. Successful responses reconcile the reservation to the standard uncached token-rate estimate; errors or missing usage retain the reservation. Do not delete or replace the ledger, or bypass the model layer. Keep it in a stable location and share it across runs and processes.

For Meta, the layer sends the same text messages and local function-tool definitions to Meta's Responses token-count endpoint before generation. It reserves the preflight input count plus a 1% or 128-token safety margin (whichever is larger), and the full output-token allowance. It rejects unknown providers, hosted tools, multimodal input and unrecognized Meta models. Reasoning tokens count toward the output cap. SDK retries are disabled to avoid unaccounted duplicate requests.

**Limit of the guarantee:** Preflight and inference are separate requests, and Meta describes the count as a context measurement, not a billing estimate. A server-side change or unexpected billing between them could exceed the reservation. Rates or account charges may also change. Consequently this is a conservative application budget, not a provider-enforced billing guarantee. Set an account-level hard spending cap if Meta offers one and monitor billing. The API timeout is not an absolute cancellation of work already accepted by the server. The time and step guards currently cover model calls, not future tool or sandbox steps.

`config/models.yaml` and `config/limits.yaml` are JSON, a YAML 1.2 subset. The standard Muse prices were checked against [Meta's pricing documentation](https://dev.meta.ai/docs/pricing-rate-limits); confirm them before use. Cached input is charged at the higher uncached rate in this ledger. No prompts, responses, API keys, or tool output are written to the trace.

## Fetch an issue (Step 2)

```powershell
python -m repro.github https://github.com/encode/httpx/issues/3433
```

The command saves a JSON record in `.cache/issues/`. Repeat it to use the cache; add `--refresh` to fetch fresh data or `--cache-dir PATH` to choose a different folder. An optional read-only `GITHUB_TOKEN` environment variable increases GitHub API rate limits. Records contain untrusted issue text, labels, all comments and URLs found in text. Linked resources are listed but not downloaded. Treat cached issue text as untrusted, and avoid committing it or sharing it without review.

Step 2's five-repository live test is pending. The main `repro` CLI, parser and sandbox belong to later steps.
