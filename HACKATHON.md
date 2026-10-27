# Hackathon build log

- Event: Meta Global AI Hackathon
- Track: Indie — Build for Your World
- Event start date: **October 27, 2026**

## Work built during the event

- October 27, 2026 — Step 0: repository and development setup; starting commit tagged `hackathon-start`.
- October 27, 2026 — Step 1: model layer, fake provider, preflight accounting, budget ledger and tests. A real Muse call was verified by the project owner. The documented provider-side billing limitation remains.
- October 27, 2026 — Step 2: GitHub issue fetcher, paginated comments, JSON cache and unit tests. Five-repository live test passed as reported by the project owner; linked URLs are listed but their contents are not fetched.
- October 27, 2026 — Step 3: disposable resource-limited, non-root Docker sandbox, offline execution, trusted networked setup, unit tests and opt-in Docker integration tests. All Docker integration tests passed on Windows, as reported by the project owner.
- October 27, 2026 — Step 4: version resolution, containerized environment building, image caching, environment metadata and offline test command. Three-library live checks passed.
- October 28, 2026 — Switched Step 4 to a commit-verified Git checkout and recorded reported v0.1 evidence; live verification passed on three libraries as reported by the project owner.

- October 28, 2026 — Step 5: structured issue parser and deterministic hints. The project owner reported 10/10 correct versions, 9/10 correct symptoms and 9/10 correct on both; vague-issue missing fields matched exactly on 1/3, with extra missing items on two cases.

- October 28, 2026 — Step 6: the project owner reported a successful boltons 23.0.0 candidate and an independently failing test; conservative recorded cost was $0.03205825. Docker isolation checks passed on Windows.
- October 28, 2026 — Step 7: deterministic symptom matcher passed 15 saved simulated-output cases, including a shortened trace based on the manual boltons repro.
- October 28, 2026 — Step 8: the project owner reported that the saved test failed independently with the reported exception. Step 9 verification and confidence remain pending. The original successful agent trace and a reproduction example are saved under `examples/v0.2-boltons`.
