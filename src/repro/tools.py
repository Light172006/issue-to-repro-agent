"""Step 6 symptom-checking interface; execution tools are not implemented yet."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

from repro.parser import IssueRecord

Verdict = Literal['exact', 'partial', 'none']


@dataclass(frozen=True)
class SymptomMatch:
    verdict: Verdict
    reason: str


class SymptomChecker(Protocol):
    def check(self, issue: IssueRecord, output: str) -> SymptomMatch: ...


class NaiveSymptomChecker:
    """Temporary Step 6 stub, not verification; Step 7 must replace it."""

    def check(self, issue: IssueRecord, output: str) -> SymptomMatch:
        symptom = issue.symptom
        if symptom.kind != 'exception':
            return SymptomMatch('none', 'Non-exception symptoms are not supported until Step 7')
        exception = symptom.type
        if not exception or not re.search(rf'(?<![\w.]){re.escape(exception)}(?!\w)', output):
            return SymptomMatch('none', 'Expected exception type was not found')
        frame = re.search(r' @ [^\s:]+:([^\s:]+)$', symptom.signature or '')
        if frame and re.search(rf'\bin\s+{re.escape(frame.group(1))}\b', output):
            return SymptomMatch('exact', 'Exception type and frame function both appear')
        return SymptomMatch('partial', 'Exception type appears; frame function was not matched')

# All file resolution and I/O occurs inside the disposable container.  The
# source and image root are read-only; only /work/repro is a writable mount.
_FILE_OP = r'''
import base64, os, pathlib, sys
op, name = sys.argv[1:3]
roots = [pathlib.Path('/work/repro').resolve(), pathlib.Path('/var/tmp/repro/source').resolve()]
p = pathlib.Path(name)
if not p.is_absolute(): p = roots[0] / p
p = p.resolve()
allowed = roots[:1] if op == 'write' else roots
if not any(p == root or root in p.parents for root in allowed):
    raise SystemExit('Error: path outside allowed roots')
if op == 'write':
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode('' if sys.argv[3] == '-' else sys.argv[3], validate=True))
    print('File written')
else:
    with p.open('rb') as f: data = f.read(65537)
    if len(data) > 65536: raise SystemExit('Error: file exceeds 65536 bytes')
    lines = data.decode('utf-8', 'replace').splitlines(keepends=True)
    start, end = int(sys.argv[3]), int(sys.argv[4])
    sys.stdout.write(''.join(lines[start-1:end]))
'''


def _path(path: object) -> str:
    from pathlib import PurePosixPath

    if not isinstance(path, str) or not path or '\x00' in path:
        raise ValueError('Invalid path')
    parts = PurePosixPath(path).parts
    if '..' in parts:
        raise ValueError('Path traversal is not allowed')
    return path


class SandboxTools:
    """Host-side dispatch only; each operation executes in an isolated container."""

    def __init__(self, sandbox, issue: IssueRecord, checker: SymptomChecker | None = None,
                 timeout: float = 30):
        self.sandbox = sandbox
        self.issue = issue
        self.checker = checker or NaiveSymptomChecker()
        self.timeout = timeout

    def close(self):
        self.sandbox.close()

    def execute(self, name: str, args: dict) -> dict:
        import base64

        if name == 'give_up':
            if set(args) != {'reason'} or not isinstance(args['reason'], str):
                return {'output': 'Error: reason must be a string'}
            return {'output': args['reason'], 'outcome': 'gave_up'}
        try:
            if name == 'run_shell':
                if set(args) != {'command'} or not isinstance(args['command'], str) or not args['command'].strip():
                    raise ValueError('command must be a nonempty string')
                command = args['command']
                if re.search(r'\b(?:pip\s+install|pip3\s+install|curl|wget)\b', command, re.IGNORECASE):
                    raise ValueError('Packages must already be installed in the environment')
                result = self.sandbox.run(['sh', '-c', command], timeout=self.timeout)
            elif name in ('read_file', 'write_file'):
                path = _path(args.get('path'))
                if name == 'write_file':
                    if set(args) != {'path', 'content'} or not isinstance(args['content'], str):
                        raise ValueError('Expected path and string content')
                    raw = args['content'].encode('utf-8')
                    if len(raw) > 65536:
                        raise ValueError('Content exceeds 65536 bytes')
                    payload = base64.b64encode(raw).decode() or '-'
                    command = ['/usr/local/bin/python', '-c', _FILE_OP, 'write', path, payload]
                else:
                    if not set(args).issubset({'path', 'start_line', 'end_line'}):
                        raise ValueError('Unknown read_file arguments')
                    start = args.get('start_line', 1)
                    end = args.get('end_line', 10000)
                    if type(start) is not int or type(end) is not int or start < 1 or end < start:
                        raise ValueError('Invalid line range')
                    command = ['/usr/local/bin/python', '-c', _FILE_OP, 'read', path, str(start), str(end)]
                result = self.sandbox.run(command, timeout=self.timeout)
            elif name in ('run_pytest', 'submit_repro'):
                key = 'path' if name == 'submit_repro' else 'args'
                if set(args) != {key}:
                    raise ValueError(f'Expected {key}')
                values = [args[key]] if name == 'submit_repro' else args[key]
                if not isinstance(values, list) or len(values) != 1:
                    raise ValueError('Provide exactly one repro test path')
                path = _path(values[0])
                if not path.startswith('/work/repro/'):
                    raise ValueError('pytest path must be under /work/repro/')
                # Resolve symlinks in the container before invoking pytest.
                check = self.sandbox.run(['/usr/local/bin/python', '-c',
                    ('import os,sys; p=os.path.realpath(sys.argv[1]); '
                    "sys.exit(0 if p.startswith('/work/repro/') else 1)"), path], timeout=self.timeout)
                if check.exit_code != 0 or check.timed_out:
                    raise ValueError('Invalid or escaped test path')
                result = self.sandbox.run(['/var/tmp/repro/venv/bin/python', '-m', 'pytest',
                                           '-p', 'no:cacheprovider', path], timeout=self.timeout)
                if name == 'submit_repro' and result.exit_code == 1 and not result.timed_out:
                    match = self.checker.check(self.issue, result.output)
                    if match.verdict in ('exact', 'partial'):
                        return {'output': result.output, 'outcome': 'candidate_found',
                                'path': path, 'verdict': match.verdict}
                    return {'output': result.output + '\nSymptom not matched: ' + match.reason}
            else:
                return {'output': f'Error: unknown tool {name}'}
            return {'output': result.output + ('\nError: command timed out' if result.timed_out else ''),
                    'exit_code': result.exit_code}
        except (ValueError, TypeError, OSError) as exc:
            return {'output': f'Error: {exc}'}


def tool_schemas() -> list[dict]:
    """OpenAI Responses function schemas, with no model-controlled execution."""
    definitions = [
        ('run_shell', 'Run a command in the offline sandbox.', {'command': {'type': 'string'}}),
        ('read_file', 'Read a file from the repro or library source.', {'path': {'type': 'string'}}),
        ('write_file', 'Write a file under /work/repro.', {'path': {'type': 'string'}, 'content': {'type': 'string'}}),
        ('run_pytest', 'Run pytest on one file under /work/repro.', {'args': {'type': 'array', 'items': {'type': 'string'}}}),
        ('submit_repro', 'Request harness verification of a failing repro.', {'path': {'type': 'string'}}),
        ('give_up', 'Stop when reproduction is not possible.', {'reason': {'type': 'string'}}),
    ]
    return [{'type': 'function', 'name': name, 'description': description,
             'parameters': {'type': 'object', 'properties': properties,
                            'required': list(properties), 'additionalProperties': False},
             'strict': True} for name, description, properties in definitions]
