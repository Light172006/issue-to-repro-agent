import concurrent.futures
import json
from decimal import Decimal
import pytest
from repro.llm import Budget, BudgetExceeded, FakeProvider, UsageUnavailable, call_model, cost_nanos

LIMITS = {'max_steps': 25, 'max_run_usd': '1', 'max_seconds': 900, 'max_daily_usd': '5', 'max_total_usd': '120'}
PRICES = {'fake': {'input_per_million': '1.25', 'output_per_million': '4.25', 'input_token_ceiling': 1000}}

def test_exact_limit_and_one_cent_over(tmp_path):
    b = Budget(tmp_path/'budget.db', LIMITS)
    try:
        b.reserve(1_000_000_000)
        with pytest.raises(BudgetExceeded): b.reserve(10_000_000)
    finally: b.close()

def test_single_call_over_budget_never_calls_provider(tmp_path):
    b = Budget(tmp_path/'budget.db', {**LIMITS, 'max_run_usd': '0.000001'})
    p = FakeProvider()
    try:
        with pytest.raises(BudgetExceeded):
            call_model(provider=p, model='fake', messages=[], tools=None, budget=b, model_config=PRICES, trace_path=tmp_path/'t')
        assert p.calls == 0
    finally: b.close()

@pytest.mark.parametrize('field,value', [('input_tokens', None), ('input_tokens', -1), ('output_tokens', -1), ('output_tokens', None)])
def test_invalid_usage_fails_closed(tmp_path, field, value):
    b = Budget(tmp_path/'b.db', LIMITS); p = FakeProvider(); setattr(p, field, value)
    try:
        with pytest.raises(UsageUnavailable):
            call_model(provider=p, model='fake', messages=[], tools=None, budget=b, model_config=PRICES, trace_path=tmp_path/'trace')
        assert b.run_charged > 0
    finally: b.close()

def test_zero_usage_and_unicode_trace_has_no_input(tmp_path):
    secret = 'sentinel-secret-🔑'
    b = Budget(tmp_path/'b.db', LIMITS)
    try:
        r = call_model(provider=FakeProvider(input_tokens=0,output_tokens=0), model='fake', messages=[{'role':'user','content':secret}], tools=None, budget=b, model_config=PRICES, trace_path=tmp_path/'trace')
        assert r.cost_usd == 0
        assert secret not in (tmp_path/'trace').read_text()
    finally: b.close()

def test_concurrent_same_budget_never_exceeds_step_cap(tmp_path):
    b = Budget(tmp_path/'b.db', {**LIMITS, 'max_steps': 5})
    def reserve():
        try: b.reserve(1); return 'ok'
        except BudgetExceeded: return 'limited'
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            results = list(pool.map(lambda _: reserve(), range(20)))
        assert results.count('ok') == 5
        assert results.count('limited') == 15
    finally: b.close()

def test_missing_model_is_clear(tmp_path):
    b = Budget(tmp_path/'b.db', LIMITS)
    try:
        with pytest.raises(ValueError, match='model'):
            call_model(provider=FakeProvider(),model='missing',messages=[],tools=None,budget=b,model_config=PRICES,trace_path=tmp_path/'trace')
    finally: b.close()

def test_cost_rounds_up_without_float_drift():
    assert sum(cost_nanos(1, 0, {'input_per_million':'0.0001','output_per_million':'0'}) for _ in range(10000)) == 10000

def _process_reserve(path):
    b = Budget(path, {**LIMITS, 'max_total_usd':'0.01'})
    try:
        try: b.reserve(5_000_000); return True
        except BudgetExceeded: return False
    finally: b.close()

def test_parallel_processes_share_total_limit(tmp_path):
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(_process_reserve, [str(tmp_path/'shared.db')]*8))
    assert sum(results) == 2

def test_provider_exception_must_not_expose_key(tmp_path, monkeypatch):
    key='fake-sentinel-api-key'
    b=Budget(tmp_path/'b.db', LIMITS); provider=FakeProvider()
    def fail(**kwargs): raise RuntimeError('transport failure '+key)
    monkeypatch.setattr(provider, 'complete', fail)
    try:
        with pytest.raises(Exception) as raised:
            call_model(provider=provider,model='fake',messages=[],tools=None,budget=b,model_config=PRICES,trace_path=tmp_path/'trace')
        import traceback
        assert key not in ''.join(traceback.format_exception(raised.value))
        assert key not in (tmp_path/'trace').read_text()
        assert b.run_charged > 0
    finally: b.close()

@pytest.mark.parametrize('kind,limit', [('run','max_run_usd'), ('daily','max_daily_usd'), ('total','max_total_usd')])
def test_each_money_limit_blocks_overage(tmp_path, kind, limit):
    b=Budget(tmp_path/'ledger', {**LIMITS, limit:'0.01'})
    try:
        b.reserve(10_000_000)
        with pytest.raises(BudgetExceeded): b.reserve(1)
    finally: b.close()

def test_daily_rollover_preserves_total(tmp_path, monkeypatch):
    import repro.llm as llm
    days=iter(['2026-10-27','2026-10-28'])
    monkeypatch.setattr(llm.time, 'strftime', lambda *args: next(days))
    b=Budget(tmp_path/'ledger', {**LIMITS,'max_daily_usd':'0.01','max_total_usd':'0.02'})
    try: b.reserve(10_000_000); b.reserve(10_000_000)
    finally: b.close()

@pytest.mark.parametrize('payload', ['','{', 'max_steps: 25'])
def test_invalid_config_is_rejected(tmp_path, payload):
    from repro.llm import load_config
    path=tmp_path/'limits.yaml'; path.write_text(payload)
    with pytest.raises(ValueError): load_config(path)


def test_overrun_records_actual_and_stops_run(tmp_path):
    import sqlite3
    b = Budget(tmp_path/'ledger', LIMITS)
    provider = FakeProvider(input_tokens=100000, output_tokens=5)
    try:
        with pytest.raises(UsageUnavailable, match='input=100000/1000'):
            call_model(provider=provider, model='fake', messages=[], tools=None, budget=b,
                       model_config=PRICES, trace_path=tmp_path/'trace', max_output_tokens=20)
        actual = cost_nanos(100000, 5, PRICES['fake'])
        assert b.run_charged == actual
        with pytest.raises(BudgetExceeded): b.reserve(1)
        event = json.loads((tmp_path/'trace').read_text().splitlines()[0])
        assert event['input_tokens'] == 100000 and event['input_ceiling'] == 1000
    finally: b.close()
    with sqlite3.connect(tmp_path/'ledger') as db:
        assert db.execute('select sum(amount) from charges').fetchone()[0] == actual


def test_count_receives_same_json_format_as_generation():
    import httpx
    from repro.llm import OpenAIProvider
    seen=[]
    def respond(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200,json={'input_tokens':42})
    provider=object.__new__(OpenAIProvider)
    provider.http=httpx.Client(base_url='https://api.meta.ai/v1',transport=httpx.MockTransport(respond))
    try:
        assert provider.count(model='muse-spark-1.3', messages=[], tools=None, timeout=5,
                              temperature=0, json_schema={'type':'object'}, reasoning_effort='minimal') == 42
        assert seen[0]['temperature'] == 0
        assert seen[0]['reasoning'] == {'effort': 'minimal'}
        assert seen[0]['text']['format']['schema'] == {'type':'object'}
    finally: provider.http.close()
