"""Append-only, immediately flushed JSONL agent traces."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_TOKEN = re.compile(r'(?i)\b(?:sk-[A-Za-z0-9_-]{12,}|gh[pousr]_[A-Za-z0-9_]{12,}|LLM_[A-Za-z0-9_]{12,}|bearer\s+[A-Za-z0-9._-]{12,})\b')


def redact(value: Any, secrets: tuple[str, ...] = ()) -> Any:
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[REDACTED]')
        return _TOKEN.sub('[REDACTED]', value)
    if isinstance(value, dict):
        return {str(k): redact(v, secrets) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, secrets) for v in value]
    return value


class TraceWriter:
    def __init__(self, path: str | Path, *, secrets: tuple[str, ...] = ()):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.secrets = secrets

    def write(self, event: dict) -> None:
        with self.path.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(redact(event, self.secrets), ensure_ascii=True) + '\n')
            stream.flush()
