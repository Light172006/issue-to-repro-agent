# Remaining work and release gates

Status: provisional. The event start is 2026-10-27; the exact submission deadline and time zone are not recorded. Reserve the final day as a buffer once the deadline is confirmed. No checkpoint is complete merely because its code exists. The owner runs Docker checks, approves each paid run, verifies labels, and creates tags.

Common gate for each checkpoint: run the offline suite three times and ruff; log counts, failures, fixes and flaky tests in `docs/STRESS_LOG.md`. Exercise applicable empty, null, large, Unicode and malformed inputs; timeout, interrupted and partial writes; KeyboardInterrupt, concurrency, disk-full and missing credentials. Fault-inject provider errors, rate limits, malformed tool calls and runaway loops; verify run and dollar caps with random costs. Compare a fake-provider fixture run with saved evidence, scan generated outputs for secrets, audit available tools, and check temporary resources and containers. Mark Docker/network-only checks honestly and provide Windows commands. No paid calls without a trace-based estimate and explicit approval.

## C1 — Close foundation and honesty gaps

- Goal: establish a trustworthy baseline and make environment limitations visible.
- Tasks: complete the audit and offline tests; verify the four statuses, questions and drafted comments; examine baseline-recording design and preserve actual observed failures without inventing them; diagnose the four `check_envs.py` cases and missing dependencies or incompatible pytest hooks. Do not insert issue-specific pins. Validate configuration and documentation against actual behavior; update HACKATHON. The four current environments have not established executable baseline suites.
- Files: `src/repro/triage.py`, `envbuilder.py`, `report.py`, tests, `scripts/check_envs.py`, `config/`, documentation and stress log, as needed.
- Done when: offline suite and ruff pass; honest statuses and comments have regression coverage; actual baseline outcomes are recorded or reported as unavailable; owner reruns the free environment check and reviews each case. Do not call a non-running suite a clean baseline.
- Stress: collection/import errors, missing plugins, empty metadata, failure classification, timeouts, atomic writes and interrupted runs; common gate above. Cost: $0 model spend.
- Risks: the current builder does not install all historical test dependencies; matching manually pinned suite counts may be impossible without a general design change. Options are dropping cases or explicitly treating them as environment-limited.
- Cut fallback: defer optional documentation polish, never honesty or the verifier.

## C2 — Validate escalation

- Goal: measure whether Wonder helps stalled Spark runs without exceeding limits.
- Tasks: first run forced-handoff plumbing on the owner's controlled fixture; then run Spark-only twice per eligible issue; run escalation only when both Spark runs fail. Compare verifier-confirmed outcomes and report even if there is no improvement. Fix the comparison script if it does not enforce this sequence. Current issue list has only four entries, and all four currently have environment problems.
- Files: `agent.py`, `stall.py`, `llm.py`, `scripts/e2e_step12.py`, tests and evidence.
- Done when: at least one Spark failure becomes a verified reproduction after escalation within the configured caps; forced handoff alone is not evidence. If no case qualifies or no success occurs, Step 12 remains unverified.
- Stress: fake-provider handoff, malformed calls, repeated failures, shared budget, context and cleanup; common gate. Cost: calculate from saved token traces and request approval before each paid group; worst case $1 per run. Risk: no qualifying case, provider behavior, environment failures, insufficient budget.
- Cut fallback: after explicit owner approval, disable Wonder and report Spark-only; this does not satisfy the original v0.4 escalation gate.

## C3 — Benchmark and held-out evaluation

- Goal: credible measured performance on 25–40 closed issues, with a roughly two-thirds development and one-third held-out split.
- Tasks: select new permissively licensed libraries, excluding parser-gold and Step 12 libraries and the controlled fixture; snapshot reporter-only text, document fixes, label 3–5 infeasible cases and run a contamination check. Implement Baseline A (single call), Baseline B (loop without verifier/minimizer), and full system. Score symptom plus fail-before/pass-after; review development failures, fix the two largest categories, and run held-out once. Generate `results.md` with all rows and failure categories in one command.
- Files: `bench/dataset.json`, dataset/runner/scorer scripts, benchmark tests, results and license credits.
- Done when: reproducible one-command held-out report includes all three systems, rates, cost, timing and refusal quality; labels and fixes are independently checked. No tuning on held-out.
- Stress: missing refs, corrupted snapshots, collection errors, timeouts, false positives, partial writes, restart and concurrency; common gate. Cost: estimate from actual trace tokens multiplied by runs and reserve worst-case budgets before approval. Risks: dataset discovery, old dependencies, runtime and cost.
- Cut fallback: only with owner approval, shrink to 20 issues while retaining a held-out split; never cut the benchmark or verifier.

## C4 — Viewer, documentation and examples

- Goal: make results inspectable and reproducible by a new user.
- Tasks: build static trace timeline; update README setup, Meta model roles, examples, limitations and generated benchmark table; update SECURITY and HACKATHON; save reviewed examples for each status with rights and attribution.
- Files: `viewer/`, README, SECURITY, HACKATHON, `examples/`, documentation and tests.
- Done when: timeline displays a real sanitized trace; clean Windows install works; benchmark table matches generated output; four status examples have provenance; credits and controls are accurate.
- Stress: malformed/large trace, unsafe text, missing fields, secrets and offline usage; common gate. Cost: $0 unless the owner explicitly approves a new example run. Risk: documentation can drift from actual implementation.
- Cut fallback: with approval, omit web viewer and display sanitized timeline in terminal.

## C5 — Submission and freeze

- Goal: release an honest, reproducible submission with an upload buffer.
- Tasks: complete section 15 checklist, demo script and backup recording plan; scan tracked files and full history for secrets; review credits and model provenance; perform final stress pass; freeze except for fixes. Owner verifies and applies tags and submits.
- Files: documentation, stress log, release checklist and demo artifacts.
- Done when: checklist is backed by evidence, history scan and stress pass are clean, demo and backup exist, and owner verifies submission deadline. Tags are owner's responsibility.
- Stress: full common gate plus installation from scratch and evidence review. Cost: $0 unless separately approved. Risks: missing exact deadline, recording/upload time, secret findings.
- Cut fallback: apply section 12 order only with owner consent: stretch features, viewer, Wonder, minimizer, then benchmark size; never cut verifier, benchmark or honest statuses. Keep final day for buffer.
