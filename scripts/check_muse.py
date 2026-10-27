"""One small Meta API integration check; run from the repository root."""
import os
from decimal import Decimal

from repro.llm import Budget, OpenAIProvider, call_model, load_config

key = os.environ.get('META_MODEL_API_KEY')
if not key:
    raise SystemExit('Set META_MODEL_API_KEY in your shell before running this script.')
provider = OpenAIProvider(api_key=key)
budget = Budget('budget.sqlite3', load_config('config/limits.yaml'))
try:
    reply = call_model(provider=provider, model='muse-spark-1.3',
                       messages=[{'role': 'user', 'content': 'Reply with hello.'}], tools=None,
                       budget=budget, model_config=load_config('config/models.yaml'),
                       trace_path='trace.jsonl', max_output_tokens=128)
    print('Response:', reply.message)
    print('Input tokens:', reply.input_tokens, 'Output tokens:', reply.output_tokens)
    print('Call cost USD (uncached-rate upper estimate):', reply.cost_usd)
    print('Run total USD:', Decimal(budget.run_charged) / Decimal(1_000_000_000))
finally:
    budget.close()
    provider.close()
