from unittest.mock import Mock
import pytest
from repro.sandbox import Sandbox

def test_reuse_closed_sandbox_rejected():
    c = Mock(); box = Sandbox(client=c); box.close()
    with pytest.raises(RuntimeError, match='closed'): box.run(['true'])
    c.containers.create.assert_not_called()

def test_failed_start_always_removed():
    c=Mock(); container=c.containers.create.return_value; container.start.side_effect=KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt): Sandbox(client=c).run(['true'])
    container.remove.assert_called_once_with(force=True)

def test_invalid_utf8_is_decoded():
    c=Mock(); container=c.containers.create.return_value; container.wait.return_value={'StatusCode':1}; container.logs.return_value=b'\xffx'
    result=Sandbox(client=c).run(['false'])
    assert result.exit_code == 1 and result.output == '\ufffdx'

def test_large_log_is_streamed_with_bounded_output():
    c=Mock(); container=c.containers.create.return_value; container.wait.return_value={'StatusCode':0}
    container.logs.return_value=iter([b'a'*20000 for _ in range(20)] + [b'END'])
    result=Sandbox(client=c).run(['echo','large'])
    assert len(result.output) <= 32100
    assert 'output truncated' in result.output and result.output.endswith('END')
    assert container.logs.call_args.kwargs['stream'] is True
