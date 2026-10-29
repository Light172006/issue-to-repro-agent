"""Create an unsent Markdown draft from checked run evidence."""
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, StrictUndefined

from repro.result_writer import _atomic_write
from repro.trace import redact

_TEMPLATE = '''## Reproduction status: {{ status }}

{{ detail }}
{% if confidence %}
Confidence: **{{ confidence }}** (based on verification checks).
{% endif %}
{% if questions %}
Could you provide the following details?
{% for question in questions %}
- {{ question }}
{% endfor %}
{% endif %}
{% if environment %}
### Environment

- Repository: {{ environment.repo }}
- Version or ref: {{ environment.selected_ref }}
- Commit: {{ environment.commit }}
- Python: {{ environment.python }}
{% endif %}
{% if code %}
### Reproduction test

{{ fence }}python
{{ code }}
{{ fence }}
{% endif %}

This is a draft; it has not been posted.
'''


def write_report(folder: str | Path, result: dict, *, questions=(), secrets=()) -> Path:
    """Write comment.md; include a test only for a verified reproduction."""
    folder = Path(folder)
    status = result.get('status', 'not_reproduced')
    allowed = {'reproduced', 'needs_info', 'not_feasible', 'not_reproduced'}
    if status not in allowed:
        raise ValueError('Unknown run status')
    code = None
    if status == 'reproduced' and result.get('verification') == 'completed':
        path = folder / 'test_repro.py'
        if not path.is_symlink() and path.is_file():
            code = path.read_text(encoding='utf-8')
    detail = result.get('status_detail') or 'No verified reproduction is available.'
    if status == 'reproduced' and code is None:
        status = 'not_reproduced'
        detail = 'The verified test artifact is missing or unavailable.'
    environment_data = None
    environment_path = folder / 'environment.json'
    if status == 'reproduced' and environment_path.is_file() and not environment_path.is_symlink():
        try:
            metadata = json.loads(environment_path.read_text(encoding='utf-8'))
            environment_data = {key: str(metadata.get(key) or 'unknown') for key in
                                ('repo', 'selected_ref', 'commit', 'python')}
        except (OSError, ValueError, AttributeError):
            pass
    fence = '```'
    while code and fence in code:
        fence += '`'
    environment = Environment(undefined=StrictUndefined, autoescape=False, keep_trailing_newline=True)
    rendered = environment.from_string(_TEMPLATE).render(
        status=status, detail=detail,
        confidence=result.get('confidence') if status == 'reproduced' else None,
        questions=questions, code=code, fence=fence, environment=environment_data)
    path = folder / 'comment.md'
    _atomic_write(path, redact(rendered, secrets=tuple(secrets)).encode('utf-8'))
    return path
