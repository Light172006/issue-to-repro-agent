# Step 11: feasibility and reporter questions

The CLI parses the issue, then checks its body and up to ten original-reporter
comments before building an environment. Explicitly stated needs for supported
hardware, credentials, private services, external network, Windows or macOS
produce `not_feasible`. An issue missing steps, actual behavior and minimal
code produces `needs_info` with questions based on its missing fields. Other
issues continue to the agent. This conservative rule can miss less explicit
requirements and does not guarantee that every runnable issue will be recognized.

The CLI saves `result.json` and drafts `comment.md`. Reports are not posted.
Only a verified reproduction includes the saved test, which is the minimized
one if minimization succeeded. Confidence is read from verifier checks. The
standalone `scripts/check_step11.py` uses fictional inputs and no model calls.
