# Issue-to-Repro Agent

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/release/python-3110/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An autonomous agent that turns raw GitHub issue reports into verified, minimal pytest reproduction tests—or proves why reproduction is not feasible. Built for the **Meta Global AI Hackathon (Indie Track: Build for Your World)**.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   Untrusted GitHub Issue    |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |     Guarded Issue Parser    |
                      |   (Deterministic Hints +    |
                      |   Meta Muse Spark 1.3 LLM)  |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |    Deterministic Triage     |
                      | (Hardware / OS / Net Check) |
                      +--------------+--------------+
                                     |
                     +---------------+---------------+
                     |                               |
              [Infeasible / Vague]              [Feasible]
                     |                               |
                     v                               v
        +-------------------------+    +---------------------------+
        | Refusal / Clarification |    |  Environment Builder      |
        | (not_feasible/needs_info|    |  (Git shallow checkout,   |
        | + reporter questions)   |    |  isolated pip install)    |
        +-------------------------+    +-------------+-------------+
                                                     |
                                                     v
                                       +---------------------------+
                                       | Docker Sandbox Tool Loop  |
                                       | (Non-root, read-only root,|
                                       | network=none, CPU/RAM cap)|
                                       |                           |
                                       | * Muse Spark 1.3 Contrib  |
                                       | * Stall Detection         |
                                       | * Escalation to Wonder 1.0|
                                       +-------------+-------------+
                                                     |
                                                     v
                                       +---------------------------+
                                       | Deterministic Verifier    |
                                       | (5x independent runs,     |
                                       | exact symptom matching)   |
                                       +-------------+-------------+
                                                     |
                                                     v
                                       +---------------------------+
                                       | AST Test Minimizer        |
                                       | (Delta-debugging on AST)  |
                                       +-------------+-------------+
                                                     |
                                                     v
                                       +---------------------------+
                                       | Artifacts & Report        |
                                       | (result.json, comment.md, |
                                       | test_repro.py, trace.json)|
                                       +---------------------------+
```

---

## Key Capabilities

1. **Guarded LLM Accounting & Escalation**:
   - Strict preflight token reservations and thread-safe SQLite ledger tracking (`runs/spend.sqlite`).
   - Caps: max 25 steps/run, $1.00/run, 900s timeout, $10.00 daily spend cap, $120.00 hard project ceiling.
   - Tiered execution: Starts with cost-efficient **Muse Spark 1.3**; automatically detects repeated error stalls or no-progress steps and escalates to frontier **Muse Wonder 1.0** with full conversation state handoff.

2. **Deterministic Triage**:
   - Refuses hardware-bound (GPU/CUDA/TPU), network-bound (DNS/external services), or OS-bound (Windows/macOS) issues with zero model calls (`status: not_feasible`).
   - Generates targeted questions for incomplete or vague bug reports (`status: needs_info`).

3. **Isolated Docker Sandbox**:
   - Discardable Linux containers created per command execution.
   - Enforces `--network none`, dropped Linux capabilities, read-only root filesystem, non-root UID, memory caps, and process limits (`pids_limit`).
   - Completely offline test execution preventing accidental host modification or network leaks.

4. **Model-Free Verification & Minimization**:
   - Runs five independent verification executions in clean containers to verify consistent symptom matching without model hallucinations.
   - Compares against fixed commits to prevent false positives.
   - AST-based delta-debugging minimizer trims superfluous code lines while retaining the exact error signature.

5. **Actionable Maintainer Output**:
   - Emits machine-readable `result.json` with verified status, cost, execution duration, and confidence score.
   - Generates polished markdown comments (`comment.md`) ready to be posted directly to GitHub issue threads.

---

## Installation & Setup

### Prerequisites
- Python 3.11+
- Docker Desktop (with Linux container mode enabled)
- Git

### Setup Virtual Environment
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

### Configure Credentials
Create a `.env` file in the project root:
```ini
META_MODEL_API_KEY=your_meta_responses_api_key_here
GITHUB_TOKEN=your_optional_github_token_here
```

### Run Test Suite
```powershell
# Run full offline test suite (298+ unit and edge tests)
pytest -m "not docker and not live and not network"

# Run Docker integration tests (requires Docker Desktop running)
$env:REPRO_DOCKER_TESTS = "1"
pytest tests/test_sandbox.py tests/test_sandbox_integration.py
Remove-Item Env:REPRO_DOCKER_TESTS
```

---

## Running the CLI

Reproduce an issue from a live GitHub URL:
```powershell
python -m repro https://github.com/pallets/click/issues/1234
```

Inspect the generated artifacts in `runs/<run-id>/`:
- `result.json`: Machine-readable execution verdict, confidence, cost, and checks.
- `comment.md`: Formatted comment ready for GitHub issue discussion.
- `test_repro.py`: Minimized, standalone reproduction test.
- `trace.jsonl`: Redacted step-by-step action log with model token metrics.

---

## Benchmark Evaluation

We evaluate the system against an 18-issue ground-truth benchmark across 11 pure-Python utility libraries (14 feasible, 4 infeasible across `addict`, `colorama`, `gpustat`, `marshmallow`, `more-itertools`, `parse`, `semver`, `tabulate`, `validators`, `voluptuous`):
- **Development Split**: 11 candidates (9 feasible, 2 infeasible).
- **Held-Out Split**: 7 candidates (5 feasible, 2 infeasible), anchored by cryptographic digest `bench/HELDOUT.sha256`.

### Benchmark Arms
- **Full System**: Complete autonomous pipeline (triage, Docker environment build, Spark 1.3 agent loop, stall detection, Wonder 1.0 escalation, independent verifier, AST minimizer).
- **Baseline A**: Single zero-tool model call to generate `test_repro.py` directly from the issue snapshot.
- **Baseline B**: Cut per project cut-list directive.

### Run Benchmark
```powershell
# Run Baseline A on development split
python bench/run.py --arm baseline_a --split development --workers 3

# Run Full System on development split
python bench/run.py --arm full --split development --workers 3

# Run Held-Out Evaluation (Pre-authorized single pass)
python bench/run.py --arm all --split held_out --workers 3

# Score benchmark runs against Docker ground-truth and generate results.md
python bench/score.py --output results.md
```

---

## Results Summary

| Metric | Full System (Dev) | Baseline A (Dev) | Full System (Held-Out) | Baseline A (Held-Out) |
|---|---|---|---|---|
| **Total Candidates** | 11 | 11 | 7 | 7 |
| **Correct Decisions** | *See results.md* | *See results.md* | *See results.md* | *See results.md* |
| **Infeasible Refusals** | 2 / 2 (100%) | 0 / 2 (0%) | 2 / 2 (100%) | 0 / 2 (0%) |
| **Precision** | High | Low (Hallucinations) | High | Low |
| **Average Cost / Run** | ~$0.04 - $0.09 | ~$0.002 | ~$0.04 - $0.09 | ~$0.002 |

*Full issue-by-issue audit and metrics are available in [results.md](results.md).*

---

## Honest Limitations

1. **Non-Linux & Specialized Hardware**: The Docker sandbox runs on Linux; issues specific to Windows APIs, macOS GUI, or physical GPUs are intentionally refused by design (`status: not_feasible`).
2. **Network Isolation**: Tests requiring live internet DNS queries or external REST APIs cannot be reproduced under the mandatory `--network none` boundary.
3. **Escalation Dynamics**: Escalation from Muse Spark 1.3 to Muse Wonder 1.0 resolves stubborn semantic stalls, but bounded per-run cost limits ($1.00) halt exploration if an issue involves circular imports or deep environment dependency incompatibilities.
4. **Vague Bug Reports**: The system will not hallucinate missing reproduction steps for incomplete reports; it emits targeted clarifying questions (`status: needs_info`).

---

## Examples

See `examples/` for saved outputs representing all execution states:
- `examples/reproduced/`: Successfully reproduced, verified, and minimized bug report.
- `examples/not_feasible/`: Hardware/OS-bound issue refused at triage with explanatory rationale.
- `examples/needs_info/`: Vague report refused with targeted follow-up questions for the reporter.

---

## License

MIT License. Built for the Meta Global AI Hackathon 2026.
