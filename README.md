# Issue-to-Repro Agent

A Python tool under development that aims to turn GitHub bug reports into verified, minimal failing tests, or explain why a bug could not be reproduced. Built for the Meta Global AI Hackathon, indie track, Build for Your World.

## Status

Step 0 setup is complete as reported by the project owner. Step 1 has a tested fake model provider, usage accounting, a persistent budget ledger, and JSONL call metadata. **Step 1 is not complete:** real API calls are disabled because a strict pre-billing prompt-token ceiling is not yet enforceable; no real model call has been verified. No reproduction or sandbox functionality has been implemented.

## Windows development setup

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest
```

Check Docker separately with `docker run hello-world`. Keep API keys in the environment, never in source control or containers.

## Model layer

`config/models.yaml` and `config/limits.yaml` contain JSON (a YAML 1.2 subset). Prices are the planning figures from the architecture document and must be verified before use. The Muse model names are placeholders, not verified API identifiers. A sample fake call:

```python
from repro.llm import Budget, FakeProvider, call_model, load_config

limits = load_config('config/limits.yaml')
models = load_config('config/models.yaml')
budget = Budget('budget.sqlite3', limits)
try:
    reply = call_model(provider=FakeProvider(), model='fake', messages=[], tools=None,
                       budget=budget, model_config=models, trace_path='trace.jsonl')
    print(reply.message, 'cost USD:', reply.cost_usd)
finally:
    budget.close()
```

Each attempt reserves its configured maximum cost before execution; reservations are retained even after success or an error. The ledger's daily limit uses UTC days and its total limit applies to all calls sharing that ledger. Use one persistent ledger for the project. Removing or changing it resets its accounting. Trace records contain model metadata and costs, not prompts, responses, secrets, or tool output. The reservation only protects a real request if the provider enforces the configured input and output token bounds and the pricing is accurate. Real calls are deliberately blocked until this is established. The model-layer time check and API timeout do not yet enforce a deadline across future non-model steps.
