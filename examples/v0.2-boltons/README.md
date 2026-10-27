# v0.2 example: boltons issue 337

- Issue: https://github.com/mahmoud/boltons/issues/337
- Reported version and tag: `23.0.0`
- Checked-out commit: `2adf15c735396b10e5050072babba0c319766726`
- Model: Muse Spark 1.3
- Conservatively recorded run cost: USD 0.03205825
- Run ID: `766a1a5dcba844ffb3dcf1de38e5b8d9`

The test, result fields and pytest excerpt are transcribed from the project
owner's reported successful run and independent check. The test fails with the
reported `AttributeError` at `dictutils.py:_insert`. The full successful agent
trace is not yet included; it remains on the project owner's machine.

The Step 7 deterministic matcher rated the saved submission `exact`. This is a
candidate, not Step 9 verification: repeated-run and fixed-version checks are
pending and confidence remains null. The older agent's initial verdict was
`partial`; the reported result above reflects the later Step 7 recheck.
