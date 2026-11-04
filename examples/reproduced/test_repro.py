# Minimized from test_repro.orig.py
import humanize
def test_metric_zero_does_not_crash():
    assert humanize.metric(0) == ''
