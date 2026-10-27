# Parser notes

## First labelled gold run

The first gold evaluation reported version 5/10, symptom 9/10, both 5/10, and exact missing-set match 1/3 on vague issues. It cost $0.05793150 according to the run's conservative accounting. These are initial results, not a passing Step 5 score.

Version extraction previously accepted the first generic version-like string even if it referred to Python, a dependency, or an unrelated reference. The extractor now prefers unambiguous target-project labels, dependency pins including extras, and project-specific JSON version blocks. Ambiguous project versions are left to the model; `+` suffixes are retained. Regression tests use invented project names and data. The parser prompt and gold labels were not changed for this revision. A second evaluation is required to measure whether the changes improve the result.

One gold example labels a regression despite showing an exception traceback. The parser currently prioritizes the deterministic exception symptom as required by the design, while the scorer demands one exact kind. This is a labelling or taxonomy ambiguity requiring human review; neither label nor matcher was changed to force a pass.

Exact missing-list equality is only a proxy for whether questions are sensible. Review the actual lists for vague issues before changing the prompt or labels.

The parser logs the final record, so trace files can contain issue-derived data. Common key formats are redacted, but arbitrary secrets may not be recognized; do not publish traces without review. Prior cached issues lacking reporter identity are refreshed by the fetcher.
