# ARCHITECTURE_MAP.md — Issue-to-Repro Agent

> This document is your maintenance guide. Every module is described so you can maintain and extend the project without any AI assistant.

---

## End-to-end data flow

```
User runs: repro <github-issue-url>
     │
     ▼
cli.py  ──── parses flags, loads config, opens Budget ledger
     │
     ├──→ github.py     fetch issue JSON + comments (cached to .cache/issues/)
     │
     ├──→ parser.py     model call → IssueRecord (repo, version, symptom, missing)
     │
     ├──→ triage.py     deterministic feasibility check → Triage | None
     │         if Triage: report.py → comment.md → EXIT with not_feasible or needs_info
     │
     ├──→ envbuilder.py  resolve commit, build Docker image, run baseline, write environment.json
     │         └── installenv.py  (runs INSIDE container) date-bounded uv install + fallback
     │
     ├──→ agent.py      step loop (max 25 steps, $1, 15 min)
     │         ├── llm.py       every model call goes here; budget guard; trace
     │         ├── tools.py     run_shell / read_file / write_file / run_pytest / give_up
     │         │     └── sandbox.py  fresh container per tool call
     │         ├── trace.py     every step → trace.jsonl (redacted)
     │         ├── stall.py     detect repeated errors / oscillation → escalation trigger
     │         └── (if stalled) → escalate to muse-wonder-1.0 via same llm.py
     │
     ├──→ matcher.py    does observed failure match reported symptom?  exact|partial|none
     │
     ├──→ verifier.py   5 independent runs; fixed-version run; compute confidence
     │
     ├──→ minimizer.py  AST ddmin + literal shortening → minimal candidate
     │
     ├──→ result_writer.py  write result.json, test_repro.py
     │
     └──→ report.py     Jinja2 → comment.md

All runs land in:  runs/<repo>-<issue>-<timestamp>/
```

---

## Run folder layout

```
runs/<repo>-<issue>-<timestamp>/
  result.json         status, confidence, checks, cost_usd, duration, minimization
  test_repro.py       minimal failing test (only if reproduced)
  test_repro.orig.py  pre-minimization copy (if minimized)
  comment.md          draft for the issue reporter (never posted automatically)
  trace.jsonl         one JSON line per step: model call, tool call, output, tokens, $
  environment.json    repo, commit, Python, packages, resolution strategy, baseline
  minimize.jsonl      minimizer step trace (if minimization ran)
  <run>/repro/        temporary writable mount used by verifier (cleaned up)
```

---

## Config files

### `config/models.yaml`

Valid JSON (YAML 1.2 subset). Keys are provider/model identifiers.

```json
{
  "fake": { "input_per_million": "1.25", "output_per_million": "4.25", "input_token_ceiling": 1000 },
  "muse-spark-1.3": { "input_per_million": "1.25", "output_per_million": "4.25", "input_token_ceiling": 1000000 },
  "muse-wonder-1.0": { "input_per_million": "4.00", "output_per_million": "20.00", "input_token_ceiling": 1000000, "cached_input_per_million": "0.20" }
}
```

- `input_per_million` / `output_per_million`: price per 1M tokens in USD (Decimal string).
- `input_token_ceiling`: used by the budget guard to reject absurdly large requests.
- `cached_input_per_million`: Wonder-only; currently billed at uncached rate in the ledger (conservative).
- **Missing key**: `base_url` — spec §7 requires this with a TODO. Currently the base URL comes from `META_MODEL_API_BASE` env var only.

### `config/limits.yaml`

Valid JSON. All numeric limits enforced by `llm.py` Budget class.

```json
{
  "max_steps": 25,           // hard cap: steps per run
  "max_run_usd": "1.00",     // hard cap: dollars per run
  "max_seconds": 900,        // hard cap: wall-clock seconds per run
  "max_daily_usd": "5.00",   // shared ledger: dollars per UTC day
  "max_total_usd": "120.00", // shared ledger: lifetime hard stop
  "minimizer": {
    "enabled": true,
    "time_limit_s": 300,       // total minimizer wall-clock budget
    "max_runs": 100,           // max sandbox invocations
    "candidate_timeout_s": 10, // per-candidate container timeout
    "workers": 1               // only 1 supported
  },
  "stall": {
    "min_steps": 4,                  // don't trigger before this many steps
    "repeat_error_threshold": 3,     // same error N times = stall
    "no_progress_steps": 5,          // no new observations for N steps = stall
    "late_step_fraction": 0.6,       // ≥60% of max_steps = late trigger
    "late_dollar_fraction": 0.5      // ≥50% of max_run_usd = late trigger
  },
  "escalation": {
    "enabled": true,
    "model": "muse-wonder-1.0",
    "max_escalations": 1,            // only one escalation per run
    "max_steps": 10,                 // Wonder gets at most 10 steps
    "max_dollars": "0.60",           // Wonder's share of the $1 run cap
    "min_remaining_dollars": "0.25", // don't escalate if less than this remains
    "min_remaining_steps": 5,        // don't escalate if fewer steps remain
    "max_output_tokens": 2048
  }
}
```

---

## Module-by-module reference

---

### `src/repro/llm.py`

**Purpose**: The only place that calls a model. Enforces all budget limits atomically via a SQLite ledger; provides a fake provider for testing.

**Spec**: §7 (models, budget), §5 (model layer component), build step 1.

**Public API**:
- `class Budget(ledger, limits, clock)` — thread-safe run-state + shared SQLite ledger. All monetary values stored as integer nanodollars.
  - `.steps` — incremented after each accepted response
  - `.run_charged` — nanodollars charged to this run
  - `.limits` — the limits dict passed in
  - `.clock()` / `.started` — monotonic time
- `call_model(provider, model, messages, tools, budget, model_config, trace_path, max_output_tokens, reasoning_effort, phase, **options) → Reply`
- `class Reply(message, input_tokens, output_tokens, cost_usd)` — frozen dataclass
- `class BudgetExceeded(RuntimeError)` — raised before making any request when a limit would be breached
- `class ProviderError(RuntimeError)` — provider HTTP/API failures
- `class UsageUnavailable(RuntimeError)` — usage data missing; reservation retained
- `dollars(value) → Decimal` — convert string/int to Decimal (used widely)

**Inputs**: messages (list of dicts), tool schemas (list of dicts), Budget object, model config dict, trace path string.

**Outputs**: `Reply` dataclass; side-effects: SQLite ledger updated, per-call trace file written.

**Files read**: `config/models.yaml` (read by caller, passed as `model_config`). SQLite ledger at path given in `Budget.__init__`.

**Files written**: SQLite ledger; `<trace_path>.model` (JSON lines of per-call data, no keys/prompts).

**Known limits**:
- Preflight count and actual billing are separate requests; a server-side change between them could exceed the reservation.
- Cached input is billed at the uncached rate in the ledger (conservative).
- No retry on failure (intentional — retries could produce unaccounted duplicate billing).
- `reasoning_effort` and `phase` are passed through to the provider but not validated.

**Tests**: `tests/test_llm.py`, `tests/edge/test_llm_edge.py`

**How to rebuild from scratch**: Implement `Budget` as a class that wraps a `threading.RLock` and a SQLite connection. Store reservations as rows in a `reservations` table (id, nanodollars, timestamp). Before each request, INSERT a reservation for `input_est * price + max_output * price`. After the response, UPDATE the row to the actual usage. Use `Decimal` for all arithmetic. The fake provider returns a configurable `Reply` without network calls.

---

### `src/repro/github.py`

**Purpose**: Fetch GitHub issue JSON (title, body, comments) and cache to disk. Parse issue URLs.

**Spec**: §5 (issue fetcher), build step 2.

**Public API**:
- `fetch_issue(url, client, *, cache_dir, refresh) → dict` — returns raw issue dict with `comments`, `urls_in_text` keys added
- `parse_issue_url(url) → tuple[str, str, int]` — `(owner, name, issue_number)`

**Inputs**: GitHub issue URL string, httpx client.

**Outputs**: Issue dict written as JSON to `.cache/issues/<hash>.json`.

**Files read/written**: `.cache/issues/*.json`

**Known limits**: Linked resources (logs, pastes) are listed but not fetched. Paginated comments (>30) are fetched with `per_page=100`. No markdown rendering.

**Tests**: `tests/test_github.py`, `tests/edge/test_github_edge.py`, `tests/edge/test_github_network.py` (network-marked, requires token)

**How to rebuild**: Use `httpx.Client` with `Accept: application/vnd.github+json`. Cache by hashing the URL. Store raw JSON plus extra keys: `reporter_login`, `comments` (list of `{login, body}` filtered to first 10 reporter comments), `urls_in_text` (regex scan for http/https).

---

### `src/repro/parser.py`

**Purpose**: Convert free-text GitHub issue to a structured `IssueRecord` via a model call with JSON schema.

**Spec**: §6 (structured issue record), §5 (issue parser), build step 5.

**Public API**:
- `class IssueRecord` (Pydantic model): `repo`, `issue`, `version`, `python`, `os`, `steps`, `expected`, `actual`, `symptom: Symptom`, `missing: list[str]`
- `class Symptom`: `kind` (`exception`|`wrong_output`|`regression`|`unknown`), `type`, `signature`
- `parse_issue(issue_dict, provider, budget, model_config, model) → IssueRecord`
- `issue_text(issue_dict) → str` — concatenate title + body + reporter comments
- `normalize_signature(exc_type, message) → str`

**Inputs**: Issue dict (from `github.py`), model provider.

**Outputs**: `IssueRecord` Pydantic model.

**Files read**: `config/parser.yaml` (prompt configuration).

**Known limits**: Only uses reporter's first 10 comments. Deterministic hints (regex for `pip install`, Python version strings) reduce model calls for clear cases.

**Tests**: `tests/test_parser.py`, `tests/test_parser_network.py` (requires `REPRO_PARSER_GOLD_RUN=1`), `bench/parser_gold.json`, `bench/score_parser.py`

**How to rebuild**: Build a JSON schema for `IssueRecord`. Extract deterministic fields first (version from `pip install` line, Python from `python --version`). Pass the remainder to the model with `temperature=0` and `response_format={"type": "json_schema"}`. Validate with Pydantic.

---

### `src/repro/triage.py`

**Purpose**: Deterministic early-exit decisions before any environment is built. Implements `not_feasible` and `needs_info`.

**Spec**: §3 (run statuses), §4 (feasibility check), §5 (feasibility check component), build step 11.

**Public API**:
- `class Triage(status, reason, questions)` — frozen dataclass
- `assess(issue_dict, record: IssueRecord) → Triage | None` — None means proceed

**Logic**:
1. Scan full issue text for explicit hardware/credential requirements via `_REQUIREMENT` regex (requires, needs, must have, only works with…) targeting: gpu, cuda, tpu, physical hardware, special hardware, private server/service, credentials, api key/token, internet/network access, windows, macos.
2. Negate if preceded by negation pattern.
3. If 3 or more of `steps`, `actual behavior`, `minimal code` are in `record.missing` → `needs_info` with mapped questions from `QUESTIONS` dict.

**Inputs**: raw issue dict, `IssueRecord` from parser.

**Outputs**: `Triage` dataclass or `None`.

**Files read/written**: None.

**Tests**: `tests/test_triage.py`

**Known limits**: Only catches explicit language; does not infer GPU from code patterns. Missing-field threshold is all three of `{steps, actual behavior, minimal code}` simultaneously.

**How to rebuild**: Write two regex patterns. `_REQUIREMENT` matches explicit dependency language. `_NEGATION` catches "does not require GPU" etc. For vague issues, check `IssueRecord.missing` against a fixed set of critical fields.

---

### `src/repro/sandbox.py`

**Purpose**: Run shell commands in disposable, isolated, resource-limited Docker containers. One fresh container per command.

**Spec**: §8 (security), §5 (sandbox), build step 3.

**Public API**:
- `class Sandbox(image, client, max_timeout, working_dir, writable_mount, network)` — context manager
  - `.run(command, timeout) → SandboxResult` — fresh non-root container, no networking, read-only root, dropped capabilities
  - `.run_setup(command, timeout) → SandboxResult` — network-enabled container for trusted install commands only
- `class SandboxResult(output, exit_code, timed_out, original_length)`
- `_is_wait_timeout(exc) → bool` — detect Docker wait timeout

**Inputs**: Docker image tag string, Docker client, command list, timeout float.

**Outputs**: `SandboxResult`; container filesystem changes discarded after every command.

**Files read/written**: Only via `writable_mount` parameter (host path → `/work/repro` in container). No host API keys or files are passed.

**Security properties**:
- `user='65534:65534'` (nobody)
- `network_mode='none'` for test commands
- `read_only=True` on root filesystem
- `cap_drop=['ALL']`, `security_opt=['no-new-privileges:true']`
- CPU, memory (`1g`), pids (`256`) limits
- `init=True` for proper signal handling

**Tests**: `tests/test_sandbox.py`, `tests/test_sandbox_integration.py`, `tests/edge/test_sandbox_docker.py`, `tests/edge/test_sandbox_edge.py` (docker-marked)

**Known limits**: Docker daemon itself is not covered by command timeout. Container logs are truncated after collection. Docker is not an absolute security boundary.

**How to rebuild**: Use `docker.from_env().containers.create()` with the security parameters above. Call `.start()`, then `.wait(timeout=N)`. Kill on timeout. Call `.logs()` for output. Remove with `.remove(force=True)` in a `finally` block.

---

### `src/repro/envbuilder.py`

**Purpose**: Build a reusable Docker image for a specific commit of a public GitHub repo. Record `environment.json` including baseline test results.

**Spec**: §5 (environment builder), build step 4, C1.

**Public API**:
- `class EnvironmentBuilder(docker_client, http_client, base_image='python:3.11')`
  - `.build(repo, version, output_dir, timeout, test_dependencies) → dict` — returns metadata dict; writes `environment.json`
- `resolve_commit(repo, version, client) → tuple[str, str]` — (sha, selected_ref)
- `_write_json(path, data)` — atomic write via temp file + `os.replace` (⚠️ BUG-1 on Windows under concurrent load)
- `class BuildError(RuntimeError)`
- `SETUP` — shell script run inside the build container (git clone + checkout + installer invocation)

**Inputs**: GitHub repo string (`owner/name`), version tag or None, output directory path, Docker client, httpx client.

**Outputs**: `environment.json` with keys: `repo`, `requested_version`, `selected_ref`, `commit`, `base_image_id`, `image`, `image_id`, `cache_hit`, `test_dependencies`, `python`, `packages` (list of `name==version`), `resolution` (strategy, cutoff, fallback reason), `baseline` (status, counts, failures).

**Files read**: `installenv.py` (read as text, hashed, passed to container as inline Python).

**Files written**: `<output_dir>/environment.json`.

**Image caching**: Cache key = SHA-256 of `[repo.lower(), sha, base_image_id, 'builder-v4-date-resolution', installer_digest, test_dependencies]`. If the image tag exists in Docker, it's a cache hit; no rebuild.

**Baseline**: After building, runs `pytest -ra -p no:cacheprovider` in the same offline container. Output is parsed by `baseline.py:baseline_from_result`. If the suite cannot run or times out, `baseline.status` is `timeout`/`runner_error`/`collection_error` — never a false clean.

**Tests**: `tests/test_envbuilder.py`, `tests/edge/test_envbuilder_edge.py`, `tests/test_installenv.py`

**Known limits**:
- Submodules are not initialized.
- Build-time pip runs project-controlled `setup.py` code in a network-enabled container.
- `testdeps.py` is NOT yet called; test dependencies must be passed manually via `--test-dependency`.

**How to rebuild from scratch**: Create a container from `base_image`. Run `SETUP` shell script that: creates `/var/tmp/repro`, shallow-clones via git fetch, checks out the exact SHA, verifies it, then runs `installenv.py` as inline Python. Commit the container as a new image. Then run the baseline pytest in a fresh offline Sandbox.

---

### `src/repro/installenv.py`

**Purpose**: Trusted setup script that runs **inside** the build container. Installs project dependencies using date-bounded `uv pip install --exclude-newer`, with fallback to latest.

**Spec**: §5 (environment builder), C1 (date-bounded resolution, fallback ladder).

**Public API** (called as `__main__`):
- `resolve_install(source, root, extra, run, clock, timeout) → dict` — strategy, cutoff, reason_for_fallback, install_duration_s
- `run_command(command, timeout) → tuple[int, str]` — subprocess wrapper with 32 KiB tail buffer

**Resolution strategy**:
1. Read commit timestamp: `git show -s --format=%cI HEAD`
2. Create bootstrap venv + install `uv` into it
3. Try `uv pip install --exclude-newer <cutoff> <source> pytest <extras>` (date-bounded)
4. If exit code != 0 and output contains resolution-failure keywords → fall back to `uv pip install <source> pytest <extras>` (unbounded latest)
5. Any other error → `RuntimeError` (no silent fallback)
6. Write `resolution.json` and `packages.txt` (uv pip freeze output)

**Inputs**: Source path (git checkout at `/var/tmp/repro/source`), root path, extra requirements (list of strings). Runs as `python installenv.py [extra...]`.

**Outputs**: `/var/tmp/repro/resolution.json`, `/var/tmp/repro/packages.txt`, `/var/tmp/repro/venv/` (Python virtualenv).

**Tests**: `tests/test_installenv.py` (⚠️ BUG-2 on Windows — path separator issue)

**Known limits**: Container-only code; uses Linux paths. Does not install test dependencies discovered by `testdeps.py` (not yet wired). `uv` binary path is `bootstrap/bin/uv` (Linux).

**How to rebuild**: The key insight is running `uv pip install --exclude-newer <ISO8601-datetime>`. Get the commit's author/committer ISO date from `git show`. Bootstrap uv into a separate venv to avoid version conflicts with the project itself.

---

### `src/repro/baseline.py`

**Purpose**: Parse pytest output into a structured baseline record; reject any candidate that matches a pre-existing failure.

**Spec**: C1 (baseline recording and rejection), verifier integrity.

**Public API**:
- `baseline_from_result(result) → dict` — parse a `SandboxResult` into `{status, counts, failures}`. Possible statuses: `complete`, `timeout`, `truncated`, `collection_error`, `no_tests`, `incomplete`, `runner_error`.
- `load_baseline(path) → dict` — read `environment.json`, extract `.baseline`; returns `{status: 'unavailable'}` on any error.
- `baseline_rejection(baseline, output) → str | None` — returns rejection reason string if the candidate output matches a pre-existing failure, else None.

**Failure matching**: Extracts a `_signature` (SHA-256 of `[exception_type, message, frame]`) for each baseline failure section. A candidate is rejected if any baseline failure's `test` ID appears in the candidate output, OR if any baseline failure's signature appears in the candidate output sections.

**Inputs**: `SandboxResult` (from sandbox.py) or `environment.json` path.

**Outputs**: Python dict; never writes files directly.

**Tests**: `tests/test_baseline.py` (⚠️ BUG-1: concurrent write test fails on Windows)

**Known limits**: Requires exact pytest output with FAILED lines and section headers. Truncated or collection-error output → `incomplete` or `truncated` → treated as unavailable (fail closed).

---

### `src/repro/testdeps.py`

**Purpose**: Statically discover test dependencies from project config files. **Not yet wired to production.**

**Spec**: C1 (test-dependency discovery), Step 4 improvement.

**Public API**:
- `class DependencyPlan(extras, requirements, plugins, warnings)` — frozen dataclass
- `discover_test_dependencies(files: dict[str, str]) → DependencyPlan` — accepts a dict of `{filename: text_content}`

**Discovery sources** (in order):
1. `pyproject.toml` — `[dependency-groups]` (test/tests/testing/dev), `[project.optional-dependencies]` extras, poetry groups (warns, no extraction)
2. `setup.cfg`, `tox.ini`, `pytest.ini` — `[options.extras_require]`, `[testenv*].deps`, pytest `addopts`
3. `requirements*.txt` files matching `requirements*test*.txt` or `requirements*dev*.txt` pattern
4. `noxfile.py` — parsed as AST, extracts literal string arguments to `.install()` calls

**Plugin detection**: Scans `addopts` for `--cov` → adds `pytest-cov` to `plugins`.

**Tests**: `tests/test_testdeps.py`

**Known limits**: Poetry group extraction not supported (warns). Dynamic deps (computed at runtime) produce warnings. Only a subset of PEP 517/518 patterns covered.

**How to wire into builder**: In `EnvironmentBuilder.build()`, before calling `resolve_commit`, fetch key files from the repo using the GitHub contents API at the resolved SHA. Pass them to `discover_test_dependencies`. Merge `plan.extras` → `.[extras]` install syntax, `plan.requirements` and `plan.plugins` into the `test_dependencies` list passed to `installenv.py`.

---

### `src/repro/agent.py`

**Purpose**: The step loop. Calls the model once per step, executes one tool, detects stalls, handles escalation to Wonder.

**Spec**: §4 (repro loop), §5 (agent loop), §7 (escalation), build step 6.

**Public API**:
- `run_agent(issue, toolbox, provider, budget, model_config, model, trace_path, tool_schemas, clock, stall_after, compact_after, force_escalate_at_step) → AgentResult`
- `class AgentResult(outcome, repro_path, verdict, steps, cost_usd, duration, stalled, reason, escalation)` — frozen dataclass

**Outcomes**: `candidate_found`, `gave_up`, `limit_hit:steps`, `limit_hit:time`, `limit_hit:dollars`, `error`

**Step loop**:
1. Check step/time/dollar limits → break if exceeded
2. Call `llm.call_model` (Spark or Wonder depending on `active_model`)
3. Extract first function call from response; handle no-call case (re-prompt once, then error)
4. Execute tool via `toolbox.execute(name, args)`
5. Append to history; compact if `len(history) > compact_after * 2 + 2` (replace with summary)
6. Check `result.outcome` for `candidate_found` or `gave_up`
7. Run `stall.detect_stall(steps_history, stall_config)` — trigger escalation if stalled/late

**Escalation**:
- Requires `policy['enabled'] = True`, sufficient remaining budget, not already attempted
- Switches `active_model` to Wonder; truncates history to system + user + handoff message + last 6 steps
- Wonder gets up to `policy['max_steps']` additional steps before forced termination

**Trace**: Every step written to `trace.jsonl` via `trace.TraceWriter`. Secrets redacted via `trace.redact`.

**Tests**: `tests/test_agent_foundation.py`, `tests/test_agent_tools.py`, `tests/test_agent_docker.py` (docker-marked), `tests/test_stall.py`, `tests/test_escalation.py`

**Known limits**: Only one escalation per run. History compaction replaces middle with a summary (lossy). Tool result is always the first call from a multi-call response.

---

### `src/repro/tools.py`

**Purpose**: The four tools the agent can call: `run_shell`, `read_file`, `write_file`, `run_pytest`. Each executes in a fresh sandbox container. Also `give_up`.

**Spec**: §5 (tools component), §8 (security), build step 6.

**Public API**:
- `class AgentToolbox(image, client, run_dir, deadline)` — context manager
  - `.execute(name, args) → dict` — dispatches to the right tool; returns `{output, exit_code?, outcome?}`
  - `.close()` — cleanup
  - `TOOL_SCHEMAS` — list of OpenAI-format tool definitions

**Tools**:
- `run_shell(command)` — runs arbitrary shell in container (network off)
- `read_file(path)` — reads a file from `/work/repro/` or library source
- `write_file(path, content)` — writes to `/work/repro/` only
- `run_pytest(path)` — runs pytest on a file under `/work/repro/`; returns output + exit code
- `give_up(reason)` — sets `outcome='gave_up'` in return dict

**Security**: All tool execution goes through `Sandbox.run()` (non-root, no network, read-only root, writable `/work/repro`). Write path is restricted to `/work/repro/` by toolbox validation.

**Tests**: `tests/test_step6_tools.py`, `tests/test_agent_tools.py`

---

### `src/repro/stall.py`

**Purpose**: Deterministic stall detection over the step history. No model calls, no mutable state.

**Spec**: §7 (escalation trigger), build step 12.

**Public API**:
- `class StallVerdict(stalled, reason, evidence, infrastructure)` — frozen dataclass
- `detect_stall(history, config) → StallVerdict` — 4 detection patterns: `repeated_timeout`, `repeated_error`, `repeated_tool_call`, `oscillation`, `no_progress`
- `summarize(history, max_chars) → str` — compact deterministic history for compaction
- `handoff(issue_json, history, verdict, repro_content, max_chars) → str` — bounded handoff for Wonder context

**Stall patterns**:
1. `repeated_timeout`: last N steps all have "command timed out" in output
2. `repeated_error`: last N steps all produce the same error fingerprint
3. `repeated_tool_call`: last N steps all make the identical tool call
4. `oscillation`: alternating between exactly two tool calls for 4 steps
5. `no_progress`: no new observations in the last 5 steps (output, errors, file writes)

**Tests**: `tests/test_stall.py`

---

### `src/repro/matcher.py`

**Purpose**: Deterministic symptom matching. Compares observed pytest failure to reported symptom. Never uses a model for this judgment.

**Spec**: §5 (symptom matcher), §4 pipeline step 5, build step 7.

**Public API**:
- `class MatchResult(verdict, exception_type, message, frame)` — frozen dataclass; `verdict ∈ {exact, partial, none}`
- `class DeterministicSymptomChecker(baseline)` — `.check(issue, output) → MatchResult`
- `extract_failure(output) → MatchResult | None` — extract exception type, message, innermost project frame from pytest output

**Matching rules** (in order):
1. `exact`: exception type matches AND (message matches OR frame matches)
2. `partial`: exception type matches OR message/frame heuristic overlap
3. `none`: no match

**Tests**: `tests/test_matcher.py`, `tests/fixtures/matcher_cases.json` (15 cases)

**Known limits**: Wrong-output matching is weaker than exception matching. Race conditions and timing bugs are flagged but not reliably matched.

---

### `src/repro/verifier.py`

**Purpose**: Model-free verification of a candidate test. Runs 5 independent times; optionally runs on a fixed version; computes confidence from checks.

**Spec**: §4 pipeline step 6, §3 (confidence), build step 9.

**Public API**:
- `verify(issue, candidate, buggy_image, client, runs, fixed_image, fixed_ref, timeout, deadline, runner, baseline) → dict`
- `save_verification(folder, verification) → dict` — atomically update `result.json`
- `_run_once(client, image, candidate, runs, timeout) → SandboxResult` — internal; each call gets a fresh container + temp dir

**Confidence logic**:
- `high`: all 5 runs match (exact), fingerprints identical, fixed version passes
- `medium`: all 5 runs match, fingerprints identical, no fixed version to compare
- `low`: partial match, or inconsistent fingerprints, or fixed version fails

**A failed fixed-version check means `status = not_reproduced`** — not just low confidence.

**Tests**: `tests/test_verifier.py`, `tests/test_verifier_release.py`

---

### `src/repro/minimizer.py`

**Purpose**: Shrink a verified repro test using AST-aware ddmin + literal shortening. Re-verify after minimization; only replace if the confidence does not decrease.

**Spec**: §4 pipeline step 7, §5 (minimizer), build step 10.

**Public API**:
- `minimize(repro_path, record, runner, matcher, limits) → MinimizeResult`
- `minimize_run(folder, record, client, buggy_image, fixed_image, fixed_ref, config, enabled, deadline) → dict` — full pipeline integration
- `class MinimizeResult(status, original_lines, final_lines, runs, duration_s, source)` — frozen dataclass; `status ∈ {minimized, unchanged, skipped, timeout}`

**Algorithm**:
1. AST ddmin on top-level statements (functions, classes, imports)
2. AST ddmin on inner statements within functions
3. Line-by-line ddmin
4. Literal input shortening (`str`→empty/half, `int`→0)
5. Repeat top-level + inner ddmin until stable
6. Add `# Minimized from test_repro.orig.py` header if accepted

**Guard**: `accept(candidate)` requires same exception fingerprint as original (type + message + frame). A candidate that merely fails differently is rejected.

**Tests**: `tests/test_minimizer.py`, `tests/test_minimizer_ast.py`, `tests/test_minimizer_docker.py` (docker-marked)

**Known limits**: Workers = 1 only (no parallel minimization). Does not shrink imports individually. Does not remove decorator arguments.

---

### `src/repro/report.py`

**Purpose**: Write `comment.md` — a Jinja2-rendered Markdown draft for the issue reporter. Never posts automatically.

**Spec**: §5 (report generator), §4 pipeline step 8, build step 11.

**Public API**:
- `write_report(folder, result, questions, secrets) → Path`

**Template** (inline Jinja2): renders `status`, `detail`, `confidence` (if reproduced), `questions` (if needs_info), `environment` block, `test_repro.py` code block with auto-extended fence.

**Inputs**: Result dict (from `result_writer.py`), question strings from `triage.py`, secrets tuple for redaction.

**Outputs**: `<folder>/comment.md` (atomic write).

**Tests**: `tests/test_report.py`

---

### `src/repro/result_writer.py`

**Purpose**: Atomic writes of `result.json` and `test_repro.py`.

**Public API**:
- `_atomic_write(path, data_bytes)` — write to temp file, then `os.replace`
- `write_result(folder, status, confidence, checks, cost_usd, duration, issue, escalation) → dict`
- `write_candidate(folder, candidate_bytes) → Path`

**Tests**: `tests/test_result_writer.py`

---

### `src/repro/trace.py`

**Purpose**: Write every agent step to `trace.jsonl`; redact secrets from all written data.

**Public API**:
- `class TraceWriter(path, secrets)` — `.write(event_dict)` — appends JSON line; redacts secrets
- `redact(value, secrets) → value` — recursively replace secret strings in dicts/lists/strings

**Known limits**: Redaction is string-replacement only; does not detect encoded or split secrets.

**Tests**: `tests/test_trace.py`

---

### `src/repro/cli.py`

**Purpose**: Entry point. `repro <issue-url>` wires all components together.

**Spec**: §5 (CLI component), build step 6.

**Tests**: `tests/test_cli.py`

---

## Scripts reference

| Script | Purpose | Run command |
|---|---|---|
| `scripts/check_muse.py` | Verify Meta API key + live call | `python scripts/check_muse.py` (set `META_MODEL_API_KEY`) |
| `scripts/check_isolation.py` | Verify Docker network isolation (requires Docker) | `$env:REPRO_DOCKER_TESTS=1; python scripts/check_isolation.py` |
| `scripts/check_envs.py` | Build environments for step12_issues.json and report gaps | `python scripts/check_envs.py` (requires Docker) |
| `scripts/check_parser.py` | Offline parser gold-set dry run (no model calls) | `python scripts/check_parser.py` |
| `scripts/check_step11.py` | End-to-end test of triage + report | `python scripts/check_step11.py` |
| `scripts/e2e_step6.py` | Full agent run on fixture issue | `python scripts/e2e_step6.py --issue-url <url>` |
| `scripts/e2e_step10.py` | Full pipeline through minimizer | `python scripts/e2e_step10.py ...` |
| `scripts/e2e_step12.py` | Spark-only runs + optional escalation comparison | `python scripts/e2e_step12.py ...` |
| `scripts/verify_four_step9.py` | Run verifier on 4 known cases | `python scripts/verify_four_step9.py` |

---

## Test directory layout

```
tests/
  test_agent_foundation.py    agent loop, budget, stall trigger, escalation branch
  test_agent_tools.py         tool dispatch, path guards, give_up
  test_agent_docker.py        mount persistence (docker-marked)
  test_baseline.py            baseline parsing, rejection, atomic writes
  test_check_envs.py          check_envs script unit tests
  test_cli.py                 CLI argument parsing and wiring
  test_envbuilder.py          resolve_commit, _write_json, EnvironmentBuilder mocks
  test_escalation.py          escalation plumbing, budget sharing, Wonder handoff
  test_github.py              fetch_issue, parse_issue_url, caching
  test_installenv.py          resolve_install, fallback, timeout, bad dates
  test_llm.py                 Budget, call_model, fake provider, rate limits
  test_matcher.py             DeterministicSymptomChecker on 15 saved cases
  test_minimizer.py           minimize() on in-memory fixtures
  test_minimizer_ast.py       units(), remove_units(), input_candidates()
  test_minimizer_docker.py    minimize_run() with boltons image (docker-marked)
  test_parser.py              parse_issue offline with fake provider
  test_parser_network.py      gold-set scorer (network-marked, paid)
  test_report.py              write_report() for all four statuses
  test_result_writer.py       atomic writes, write_result
  test_sandbox.py             Sandbox mocked
  test_sandbox_integration.py Docker integration: network, nonroot, timeout (docker)
  test_stall.py               all 5 stall patterns, oscillation, no-progress
  test_step6_network.py       full agent run with network (docker+network marked)
  test_step6_tools.py         tool schemas, tool execution mocks
  test_testdeps.py            discover_test_dependencies on all file types
  test_trace.py               TraceWriter, redact
  test_triage.py              assess() for not_feasible, needs_info, pass-through
  test_verifier.py            verify() with mocked runner
  test_verifier_release.py    verify() with fixed-version check
  edge/
    test_envbuilder_edge.py   edge cases for resolve_commit
    test_github_edge.py       malformed URLs, pagination edge cases
    test_github_network.py    live GitHub fetch (network-marked)
    test_llm_edge.py          budget guard edge cases, malformed responses
    test_sandbox_docker.py    binary cleanup, IPv6 isolation (docker-marked)
    test_sandbox_edge.py      timeout edge cases
  fixtures/
    matcher_cases.json         15 saved pytest output → verdict cases
    minimizer/bloated.py       test fixture for minimizer
    minimizer/boltons_bloated.py
```

---

## How to run components in isolation

```powershell
# Offline suite (no Docker, no network, no model calls)
.venv\Scripts\python.exe -m pytest -m "not docker and not network" -v

# Docker tests (requires Docker Desktop running, Linux containers)
$env:REPRO_DOCKER_TESTS = "1"
.venv\Scripts\python.exe -m pytest -m "docker and not network" -v
Remove-Item Env:REPRO_DOCKER_TESTS

# Ruff
.venv\Scripts\python.exe -m ruff check src/ tests/ scripts/ bench/

# Individual module test
.venv\Scripts\python.exe -m pytest tests/test_matcher.py -v

# Fetch an issue (Step 2)
.venv\Scripts\python.exe -m repro.github https://github.com/encode/httpx/issues/3433

# Build an environment (Step 4, requires Docker)
.venv\Scripts\python.exe -m repro.envbuilder pallets/itsdangerous --version 2.1.2 --output-dir environment/test

# Parser dry run (no model calls)
.venv\Scripts\python.exe bench/score_parser.py

# Stall detection standalone
.venv\Scripts\python.exe -c "
from repro.stall import detect_stall
print(detect_stall([{'tool':'run_shell','arguments':{},'output':'err'}]*4, {'min_steps':4,'repeat_error_threshold':3}))
"
```

---

## Component dependency graph

```
cli.py
  ├── github.py
  ├── parser.py → llm.py
  ├── triage.py → parser.py
  ├── envbuilder.py → sandbox.py, installenv.py, baseline.py, matcher.py
  ├── agent.py → llm.py, tools.py, sandbox.py, stall.py, trace.py, matcher.py
  ├── verifier.py → sandbox.py, matcher.py, result_writer.py
  ├── minimizer.py → sandbox.py, verifier.py, matcher.py
  ├── report.py → result_writer.py, trace.py
  └── result_writer.py → trace.py

testdeps.py   ← STANDALONE, not yet wired
```
