# Example: status = not_reproduced

This example illustrates an authentic held-out run (`tabulate-410` on `astable/tabulate`) where the agent explored the codebase in an isolated Docker container but honestly reported that it could not reproduce the bug:

1. **Exploration**: The agent executed 16 steps inside the Linux sandbox trying to trigger the reported issue.
2. **Escalation**: When repeated test errors occurred at step 6, the runner triggered an automatic semantic escalation from Muse Spark 1.3 to Muse Wonder 1.0.
3. **Honest Refusal**: Because the test output did not consistently match the reported symptom signature within the bounded exploration ceiling (10 Wonder steps), the agent refused to fabricate a claim, returning `status: not_reproduced` with total cost $0.277 USD.
4. **Draft Comment**: Emitted a draft `comment.md` explaining why reproduction was not found, without attempting to post to GitHub.
