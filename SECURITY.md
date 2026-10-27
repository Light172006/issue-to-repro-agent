# Security design

The following controls are planned and are not implemented in the Step 0 setup:

- Run untrusted code in Docker as a non-root user with CPU, memory, process and time limits. Install dependencies with network access, then run tests with networking disabled; mount only the run output folder.
- Treat issue text, comments and code as untrusted data. Expose only container tools to the model; do not give it tools to post, delete, or read host files.
- Keep API keys on the host, out of container environments, and redact secrets from traces.
- Enforce step, cost and wall-clock limits through the model layer.
- Match reported symptoms deterministically first; verify repeated runs and derive confidence from checks.
- Draft issue comments for a human to review; do not post automatically.
- Use public, permissively licensed repositories, credit them, and use a read-only GitHub token.
