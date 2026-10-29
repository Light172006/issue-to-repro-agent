# v0.3 checkpoint evidence reported by the project owner

The owner ran the verifier on Windows with Docker. The five cases were boltons
#337 and pydash #153, #147, #142 and #236. All five failed consistently on the
buggy reference and passed on the fixed reference. Four were manually written
pydash tests; #147 had a partial symptom match and low confidence. The boltons
case was agent-generated and had an exact symptom match and high confidence.

The owner reported the boltons test shrank from seven to six non-blank,
non-comment lines in 27 runs. They supplied the minimized test and result as
chat text; `result.json` preserves the reported fields and `test_repro.py` has
been byte-checked against its recorded SHA-256. `test_repro.orig.py` contains
the prior test. The owner also reported all offline and Docker tests passed,
including the bloated boltons fixture. The original agent trace is in
`examples/v0.2-boltons/trace.jsonl`.

This is a transcription from the owner's output, not a direct copy of the files
from their machine. See `reported-result.json` for the fixed commit, which was
present in the owner's earlier Step 9 output but omitted by Step 10's result.
