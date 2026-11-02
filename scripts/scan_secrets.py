"""Scan git repository history and tracked files for secrets."""
from __future__ import annotations

import re
import subprocess
import sys

PATTERNS = [
    re.compile(r'ghp_[a-zA-Z0-9]{20,}'),
    re.compile(r'github_pat_[a-zA-Z0-9_]{20,}'),
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),
    re.compile(r'(?i)(?:api_key|apikey|meta_model_api_key)\s*[:=]\s*["\']([a-zA-Z0-9_\-]{16,})["\']'),
    re.compile(r'(?i)bearer\s+([a-zA-Z0-9_\-\.]{25,})'),
]

IGNORE_STRINGS = {
    'isolation-secret-sentinel',
    'your-api-key-here',
    'YOUR_API_KEY_HERE',
}

def scan_text(text: str, context: str) -> list[str]:
    findings = []
    for pattern in PATTERNS:
        for match in pattern.finditer(text):
            val = match.group(0)
            if any(ign in val for ign in IGNORE_STRINGS):
                continue
            findings.append(f'{context}: {val[:50]}')
    return findings

def main() -> int:
    findings = []
    # 1. Full git log patch
    git_log = subprocess.check_output(['git', 'log', '-p'], text=True, errors='replace')
    findings.extend(scan_text(git_log, 'git-history'))

    # 2. Tracked files
    files = subprocess.check_output(['git', 'ls-files'], text=True).splitlines()
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8', errors='replace') as fp:
                findings.extend(scan_text(fp.read(), f'tracked:{f}'))
        except OSError:
            pass

    print(f'Total secret findings: {len(findings)}')
    for f in findings:
        print('  FINDING:', f)
    return 1 if findings else 0

if __name__ == '__main__':
    sys.exit(main())
