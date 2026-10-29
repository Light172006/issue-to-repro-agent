import json
from pathlib import Path

from repro.stall import detect_stall


def step(tool='run_shell', arguments=None, output='Error: failed', error='Error: failed'):
    return {'tool': tool, 'arguments': arguments or {}, 'output': output, 'error': error}


def test_repeated_error_and_minimum():
    steps = [step(arguments={'command': str(i)}) for i in range(4)]
    assert not detect_stall(steps[:3], {}).stalled
    assert detect_stall(steps, {}).reason == 'repeated_error'


def test_repeated_calls_and_oscillation():
    repeated = [step(arguments={'command': 'x'}, output=str(i), error=None) for i in range(4)]
    assert detect_stall(repeated, {}).reason == 'repeated_tool_call'
    oscillation = [step(arguments={'command': x}, output=str(i), error=None) for i, x in enumerate('abab')]
    assert detect_stall(oscillation, {}).reason == 'oscillation'


def test_no_progress_and_new_file_hash():
    steps = [step(arguments={'command': str(i)}, output='same', error=None) for i in range(6)]
    assert detect_stall(steps, {}).reason == 'no_progress'
    steps[-1] = step('write_file', {'path': '/work/repro/a.py', 'content': 'new'}, 'same', None)
    assert not detect_stall(steps, {}).stalled


def test_infrastructure_errors_are_classified():
    steps = [step(arguments={'command': str(i)}, output='Error: cannot connect to docker daemon',
                  error='Error: cannot connect to docker daemon') for i in range(4)]
    result = detect_stall(steps, {})
    assert result.stalled and result.infrastructure


def test_successful_boltons_trace_does_not_stall():
    path = Path('examples/v0.2-boltons/trace.jsonl')
    steps = [json.loads(line) for line in path.read_text().splitlines()]
    for count in range(1, len(steps) + 1):
        assert not detect_stall(steps[:count], {}).stalled


def test_repeated_command_timeouts_are_infrastructure():
    steps = [step(arguments={'command': str(i)}, output='Error: command timed out', error=None) for i in range(4)]
    result = detect_stall(steps, {})
    assert result.infrastructure and result.reason == 'repeated_timeout'


def test_handoff_is_deterministic_and_bounded():
    from repro.stall import StallVerdict, handoff
    steps = [step(arguments={'command': 'cat test.py'}, output='hello', error=None)]
    verdict = StallVerdict(True, 'no_progress', ('5',))
    first = handoff('{"issue":1}', steps, verdict, 'def test_x(): pass', max_chars=400)
    assert first == handoff('{"issue":1}', steps, verdict, 'def test_x(): pass', max_chars=400)
    assert len(first) <= 400 and first.startswith('<untrusted_handoff>')
    assert 'cat test.py' in first
