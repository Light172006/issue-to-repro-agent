# Security Policy & Control Architecture

The Issue-to-Repro Agent executes potentially untrusted issue reproduction code submitted by anonymous or untrusted third parties on GitHub. To safely handle untrusted code and adversarial prompts, the system implements defense-in-depth isolation across the operating system, container runtime, network stack, LLM tool boundaries, and credential stores.

---

## 1. Threat Model & Boundaries

The system is designed under the assumption that:
1. **GitHub issue reports, snippets, and comments are untrusted**: An issue description may contain prompt injection, malicious shell commands, fork bombs, cryptominers, or path traversal payloads.
2. **Repository code at requested commits may contain vulnerabilities**: Python packages being debugged may contain unsafe `setup.py` / `build-backend` hooks or exploitable dependencies.
3. **The LLM can be misled or hallucinate**: Generated pytest scripts or tool invocation sequences could attempt to access local network services, modify host files, or exhaust resources.

---

## 2. Docker Sandbox Runtime Controls

All untrusted reproduction steps, commands, and pytest invocations execute inside discardable Linux Docker containers (`python:3.11-slim` or project-specific cached base images).

The container runtime (`src/repro/sandbox.py`) enforces the following isolation parameters on every single command execution:

| Security Parameter | Enforced Configuration | Purpose & Threat Mitigation |
|---|---|---|
| **Network Isolation** | `network_mode='none'` | Containers have zero network interfaces (except loopback). Prevents data exfiltration, port scanning, botnet command-and-control, and SSRF attacks against internal network metadata services. |
| **Non-Root Execution** | `user='65534:65534'` | Executes as unprivileged `nobody:nogroup`. Even if a sandbox breakout exploit exists within a Python C-extension, container processes hold no root permissions. |
| **Read-Only Root Filesystem** | `read_only=True` | The container root filesystem is mounted strictly read-only. Prevents malware persistence, tampering with system binaries, or modifying Python runtime libraries. |
| **Capability Dropping** | `cap_drop=['ALL']` | All Linux kernel capabilities are explicitly stripped (e.g., `CAP_NET_RAW`, `CAP_SYS_ADMIN`, `CAP_CHOWN`, `CAP_SETUID`). |
| **Privilege Escalation Block** | `security_opt=['no-new-privileges:true']` | Disallows `setuid` binaries or privilege transitions within child processes. |
| **Scoped Mount Boundaries** | Single bind mount `/work/repro` | Only a verified, local run folder (`runs/<run_id>/repro`) is mounted. The path is strictly validated: symlinks are forbidden, and paths that resolve outside `runs/<run_id>/repro` are rejected with `ValueError`. The host filesystem, `.env`, `.git/`, and root directories are never mounted. |
| **Ephemeral Memory-Only Scratch** | `tmpfs={'/tmp': 'rw,noexec,nosuid,size=64m'}` | Temporary storage uses bounded RAM-backed tmpfs mounted with `noexec` and `nosuid` flags, preventing binary execution from `/tmp`. |
| **Resource Caps (CPU/RAM/PIDs)** | `nano_cpus=1_000_000_000`<br>`mem_limit='512m'` or `'1g'`<br>`pids_limit=128` or `256` | Prevents CPU starvation, memory exhaustion OOM crashes on the host, and fork bombs. |
| **Zombie Process Management** | `init=True` | Integrates a lightweight init process (e.g. `tini`) inside each container to ensure signals (`SIGTERM`, `SIGKILL`) are properly reaped and orphaned processes are terminated. |
| **Container Disposability** | `container.remove(force=True)` | Containers are completely destroyed immediately after command execution in a `finally` block. State never persists between runs. |
| **Execution Timeouts** | Maximum 60s per command | Hard wall-clock limits enforce termination via `container.kill()` for hung tests, infinite loops, or deadlocks. |
| **Log Bomb Defense** | Truncated to 32KB (16KB head + 16KB tail) | Prevents host disk fill or memory exhaustion from tests generating endless stdout/stderr streams. |

---

## 3. Trusted Build vs. Untrusted Execution Separation

Environment setup (`src/repro/envbuilder.py`) is decoupled from reproduction execution:
1. **Build Phase (Network Allowed, Read-Only Checkout)**:
   - Git shallow clones and dependency resolution (`pip install`) execute in a sandboxed bridge container with `user='65534:65534'`, `cap_drop=['ALL']`, and memory/CPU limits.
   - Built virtual environments are committed to isolated local Docker image tags (`issue-repro-env:<digest>`).
2. **Reproduction Phase (Network Prohibited)**:
   - Once the environment image is built, all subsequent agent commands, exploration steps, and reproduction tests run exclusively with `network_mode='none'`.

---

## 4. Credential Protection & Redaction

1. **Host-Only Secret Confinement**:
   - Secrets (`META_MODEL_API_KEY`, `GITHUB_TOKEN`) reside exclusively on the host system within `.env`.
   - **Zero credentials are injected into Docker containers**. Container environment variables are sanitized to:
     ```python
     environment = {
         'HOME': '/tmp',
         'TMPDIR': '/tmp',
         'PYTHONDONTWRITEBYTECODE': '1',
         'PATH': '/var/tmp/repro/venv/bin:/usr/local/bin:/usr/bin:/bin'
     }
     ```
2. **Trace Log Redaction**:
   - All HTTP interaction logs, model request payloads, and audit traces (`trace.jsonl`, `trace.jsonl.model`, and SQLite ledger `runs/spend.sqlite`) automatically redact Bearer tokens, API keys, and authorization headers before serialization.
3. **Git History Hygiene**:
   - Regular automated pre-commit secret scanning checks the repository history to ensure no API keys or access tokens are ever committed.

---

## 5. Strict Prohibition on Automatic GitHub Mutation

To prevent spam, unauthorized modifications, or unintended reputational impact:
- **No GitHub Mutation Tools**: The agent does not possess tools or API integrations to post comments to GitHub, open pull requests, merge code, close issues, or delete branches.
- **Read-Only GitHub Access**: If a `GITHUB_TOKEN` is configured, it is utilized solely for authenticated GET requests against the public GitHub REST API to avoid rate-limiting when resolving commit SHAs and release tarballs.
- **Human-in-the-Loop Review**: All generated responses, verified reproduction scripts, and triage recommendations are written locally to `runs/<id>/comment.md` for human maintainer review.

---

## 6. Financial & Resource Exhaustion Protection

The agent enforces strict accounting via an ACID SQLite ledger (`runs/spend.sqlite`) with thread-safe reservations:
- **Per-Run Cost Cap**: Maximum $1.00 USD per issue reproduction run.
- **Daily Spend Ceiling**: Maximum $10.00 USD per calendar day.
- **Project Spend Ceiling**: Maximum $120.00 USD total hackathon budget cap.
- **Step Limit**: Maximum 25 tool execution steps per run.
- **Timeout Limit**: Maximum 900 seconds total wall-clock execution per issue.

If any threshold is exceeded, the agent immediately terminates with status `limit_hit`, preserving all artifacts up to that point.

---

## 7. Reporting a Vulnerability

If you discover a security vulnerability in this repository, please do not file a public GitHub issue. Contact the project maintainers directly or submit a private security advisory via GitHub Security Advisories.
