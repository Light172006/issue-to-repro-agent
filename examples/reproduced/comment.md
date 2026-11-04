## Reproduction status: reproduced

Independent verification passed

Confidence: **medium** (based on verification checks).



### Environment

- Repository: python-humanize/humanize
- Version or ref: 4.3.0
- Commit: dab62bfbc9ac4cd9e5d558b38723d31d453c37da
- Python: 3.11.18


### Reproduction test

```python
# Minimized from test_repro.orig.py
import humanize
def test_metric_zero_does_not_crash():
    assert humanize.metric(0) == ''

```


This is a draft; it has not been posted.
