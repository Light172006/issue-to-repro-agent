import json

from repro.trace import TraceWriter


def test_jsonl_is_immediately_readable_and_redacts(tmp_path):
    path = tmp_path / 'trace.jsonl'
    writer = TraceWriter(path, secrets=('specific-secret',))
    writer.write({'output': 'specific-secret', 'arguments': {'key': 'ghp_12345678901234567890'}})
    event = json.loads(path.read_text())
    assert event['output'] == '[REDACTED]'
    assert event['arguments']['key'] == '[REDACTED]'
    writer.write({'event': 'final'})
    assert len(path.read_text().splitlines()) == 2
