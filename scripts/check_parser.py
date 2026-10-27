"""Optional paid smoke test using a fictional report, not the gold set."""
import os
from decimal import Decimal

from repro.llm import Budget, OpenAIProvider, load_config
from repro.parser import ModelClient, parse_issue

key = os.getenv('META_MODEL_API_KEY')
if not key:
    raise SystemExit('Set META_MODEL_API_KEY before running this paid smoke test.')
print('Paid smoke test: one fictional issue, up to two calls if schema repair is needed.')
provider = OpenAIProvider(api_key=key)
budget = Budget('budget.sqlite3', load_config('config/limits.yaml'))
try:
    client = ModelClient(provider, budget, load_config('config/models.yaml'), 'trace.jsonl')
    issue = {'repo': 'example/fictional', 'number': 1,
             'body': 'Version: 1.2.3. Python 3.11. On Linux, calling add(2, 3) returns 8; expected 5.\n```python\nadd(2, 3)\n```'}
    record = parse_issue(issue, client)
    print('Smoke result:', record.model_dump_json())
    print('Conservative recorded cost USD:', Decimal(budget.run_charged) / Decimal(1_000_000_000))
    if record.version is None and len(record.missing) == 10:
        raise SystemExit('Smoke test failed: the parser returned its validation fallback.')
finally:
    budget.close()
    provider.close()
