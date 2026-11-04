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
# Run full offline test suite (315+ unit and edge tests)
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

## Benchmark Evaluation & Results

We evaluate against an 18-issue ground-truth benchmark across 10 pure-Python libraries (`addict`, `colorama`, `gpustat`, `marshmallow`, `more-itertools`, `parse`, `semver`, `tabulate`, `validators`, `voluptuous`), comprising 14 feasible and 4 infeasible issues.

The dataset is partitioned into:
- **Held-Out Split (n=7)**: 5 feasible, 2 infeasible (`colorama-110` Win32 API, `gpustat-cuda` NVIDIA NVML). Cryptographically locked by `bench/HELDOUT.sha256` (`405b7c5efde9602f29852cb106ce6c73be5b5f6abca60bf8debd7893e74bb872`). Evaluated once with zero tuning or cherry-picking.
- **Development Split (n=11, used for tuning)**: 9 feasible, 2 infeasible (`colorama-89` Win32 API, `validators-dns` live network).

### Evaluated Benchmark Arms
- **Full System**: End-to-end pipeline (deterministic triage, Docker environment builder, Meta Muse Spark 1.3 agent loop, semantic stall detector with Muse Wonder 1.0 escalation, 5-run Docker verifier, AST minimizer).
- **Baseline B**: Identical agent loop in Docker sandbox without the independent verifier or AST minimizer.
- **Baseline A**: Single-prompt zero-shot generation of `test_repro.py` directly from the issue snapshot without tools, sandbox feedback, or triage.

---

### Primary Results: Held-Out Split (Unseen Test Set, n=7)

*All numbers generated directly from Docker ground-truth execution via `bench/score.py` into `results.md`.*

| Arm | Feasible Repro Rate | Fail-to-Pass (Strict) | Symptom Match | Claims (Tot / Corr / Wr) | Wrong-Claim Rate | Infeasible Refusal | Overall Correctness | Total Cost ($) | Avg Time (s) |
|---|---|---|---|---|---|---|---|---|---|
| **Full System** | **0.0%** (0/5) | 0/5 | 1/5 | 1 (0 / 1) | 100.0% (1/1) | **100.0%** (2/2) | **28.6%** (2/7) | $0.70 | 46.9s |
| **Baseline B** | **40.0%** (2/5) | 2/5 | 2/5 | 3 (2 / 1) | 33.3% (1/3) | **100.0%** (2/2) | **57.1%** (4/7) | $0.86 | 53.6s |
| **Baseline A** | **80.0%** (4/5) | 5/5 | 4/5 | 7 (4 / 3) | 42.9% (3/7) | **0.0%** (0/2) | **57.1%** (4/7) | $0.03 | 9.5s |

### Secondary Results: Development Split (Used for Tuning, n=11)

| Arm | Feasible Repro Rate | Fail-to-Pass (Strict) | Symptom Match | Claims (Tot / Corr / Wr) | Wrong-Claim Rate | Infeasible Refusal | Overall Correctness | Total Cost ($) | Avg Time (s) |
|---|---|---|---|---|---|---|---|---|---|
| **Full System** | **55.6%** (5/9) | 5/9 | 5/9 | 5 (5 / 0) | **0.0%** (0/5) | **100.0%** (2/2) | **63.6%** (7/11) | $0.54 | 33.7s |
| **Baseline B** | **33.3%** (3/9) | 3/9 | 3/9 | 3 (3 / 0) | **0.0%** (0/3) | **100.0%** (2/2) | **45.5%** (5/11) | $0.79 | 54.7s |
| **Baseline A** | **22.2%** (2/9) | 5/9 | 4/9 | 11 (2 / 9) | 81.8% (9/11) | **0.0%** (0/2) | **18.2%** (2/11) | $0.03 | 7.6s |

---

### Honest Benchmark Analysis & Positioning

1. **Trading Recall for Trust**:
   - The Full System does not claim to beat raw zero-shot LLM generation on finding reproduction candidates. On the held-out split, **Baseline A had the highest recall** (4/5 feasible, 80.0% repro rate, 5/5 strict fail-to-pass), but it achieved this by guessing aggressively: Baseline A claimed a reproduction on **every single issue**, resulting in 3 wrong claims out of 7 on held-out (42.9% wrong-claim rate), 9 wrong claims out of 11 on dev (81.8% wrong-claim rate), and hallucinating fake tests for all 4 infeasible issues (0/2 refusals on both splits).
   - In contrast, the Full System and Baseline B **refused 100.0% of infeasible issues** (4/4 total across dev and held-out: `colorama-89`, `colorama-110`, `validators-dns`, `gpustat-cuda`) at zero model cost during triage.
2. **Held-Out Conservatism**:
   - On the held-out split, the Full System was **too conservative**: it scored 0/5 feasible reproductions. It returned `not_reproduced` on 4 issues (`addict-102`, `addict-28`, `semver-501`, `tabulate-410`) because it refused to declare victory without an exact verified symptom match across multiple container runs.
   - On `semver-480`, the Full System successfully reproduced the bug and verified it across 5/5 clean container runs at the buggy commit. However, the AST minimizer over-reduced the assertion, making it over-constrained such that it also failed on the fix tree (`failed_at_fix`). In contrast, Baseline B's unminimized candidate passed on the fix tree.
3. **Summary Verdict**:
   - If a maintainer wants raw candidate ideas and is willing to manually filter 40–80% false positives, single-prompt LLM generation (Baseline A) is cheap.
   - If a maintainer needs automated triage they can trust without chasing phantom reproductions or platform-infeasible issues, the guarded agent loop provides verified execution and zero wrong claims on development (though tuning for held-out generalization remains an active research direction).

---

### Benchmark Audit & Disclosures

1. **Held-Out Hash Integrity**:
   - `bench/HELDOUT.sha256` was verified before running and re-verified immediately after scoring. SHA-256: `405b7c5efde9602f29852cb106ce6c73be5b5f6abca60bf8debd7893e74bb872`.
2. **Held-Out Re-Anchoring Disclosure**:
   - In commit `502e292`, `dataset.json` and `held_out.json` were rebuilt and `bench/HELDOUT.sha256` was updated after rejecting 6 invalid issues (`marshmallow-2901`, `more-itertools-1342`, `semver-460`, `sqlparse-826`, `tabulate-408`, `voluptuous-451`) that lacked verifiable ground-truth fix commits or valid git tags. No benchmark results existed prior to this re-anchoring.
3. **`addict-102` Snapshot Sanitization**:
   - Issue `addict-102` originated from a pull request URL (`/pull/102`) that resolved issue #101. The snapshot `bench/snapshots/addict-102.json` originally included the PR description and test notes. Prior to the held-out benchmark run, it was sanitized to contain exclusively the original Issue #101 bug report text from reporter `MisterVladimir` (subclass attribute loss and error), stripping PR solution text and Coveralls comments. Neither `bench/dataset.json` nor `bench/held_out.json` was altered.
4. **`tabulate-410` Infrastructure Flake**:
   - During the single held-out run of `full`, `tabulate-410` encountered a transient Windows socket collision (`[WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions`) during Docker port binding. The crash log was preserved in `runs/infrastructure_failures/full_tabulate-410_result.json`. Per benchmark ground rules, only that single issue was rerun once, completing cleanly with `status: not_reproduced` ($0.277 USD, 94.9s).
5. **Score Generation**:
   - `results.md` is generated exclusively via `bench/score.py` running in live Docker sandboxes. It is never manually edited.

---

## Known Limitations

1. **Minimizer Over-Reduction**:
   - The AST delta-debugging minimizer can over-reduce test logic. While `parse-258` was fixed by preserving top-level assertions, `semver-480` on held-out suffered a recurrence: the agent produced a valid 5/5 reproduction, but the minimizer's generated assertion failed at the fix commit (`failed_at_fix`). The benchmark results reflect this limitation honestly without post-hoc patching.
2. **Platform & Hardware Boundaries**:
   - Sandbox environments run Linux containers (`python:3.11`). Bugs requiring native Win32 console APIs (`colorama`), macOS Cocoa, or physical NVIDIA GPU hardware/NVML (`gpustat`) cannot be reproduced and are refused by design.
3. **Network Isolation**:
   - Docker containers enforce `--network none`. Issues requiring live internet DNS lookups (`validators`) or external endpoints are intentionally refused.
4. **Vague Bug Reports**:
   - The agent requires clear reproduction steps or an identifiable exception symptom; ambiguous issues are returned with clarifying questions (`status: needs_info`).

---

## Credits & Model Roles

- **Meta Muse Spark 1.3 Contributor**: Default high-throughput, low-latency model used for issue parsing, initial reproduction script drafting, and routine tool loop exploration.
- **Meta Muse Wonder 1.0 Frontier**: Escalation model invoked automatically when semantic stalls, syntax errors, or loop cycles are detected by the runner.
- **Framework & Libraries**: Built with Python 3.11, `docker-py`, `pytest`, `httpx`, and `tree-sitter`.

---

## Examples

See `examples/` for saved outputs representing all execution states:
- `examples/reproduced/`: Successfully reproduced, verified, and minimized bug report.
- `examples/not_feasible/`: Hardware/OS-bound issue refused at triage with explanatory rationale.
- `examples/needs_info/`: Vague report refused with targeted follow-up questions for the reporter.

---

## License

MIT License. Built for the Meta Global AI Hackathon 2026.
