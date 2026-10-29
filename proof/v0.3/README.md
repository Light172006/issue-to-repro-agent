# v0.3 checkpoint evidence reported by the project owner

The owner ran the verifier on Windows with Docker. The five cases were boltons
#337 and pydash #153, #147, #142 and #236. All five failed consistently on the
buggy reference and passed on the fixed reference. Four were manually written
pydash tests; #147 had a partial symptom match and low confidence. The boltons
case was agent-generated and had an exact symptom match and high confidence.

The owner reported that Step 10 minimized the boltons test from seven to six
non-blank, non-comment lines in 27 runs, and the minimized result passed all
four displayed checkpoint conditions. The original test is included here. The
actual minimized test and original machine-generated result.json have not yet
been supplied to this workspace; the JSON file here is a transcription of the
reported evidence, not an original run artifact. The owner also reported that
all offline and Docker tests passed, including the bloated boltons fixture.

Before tagging, save the actual `test_repro.py` and `result.json` from the
owner's `runs/766a1a5dcba844ffb3dcf1de38e5b8d9` directory and check that the
file's SHA-256 equals the recorded value. Do not add credentials or local paths.
