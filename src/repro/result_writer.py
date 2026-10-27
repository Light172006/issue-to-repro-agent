"""Save accepted candidate tests and honest, machine-readable run results."""
from __future__ import annotations

import ast
import json
import os
import stat
import tempfile
from dataclasses import asdict
from pathlib import Path, PurePosixPath

from repro.agent import AgentResult

_MAX_TEST_BYTES = 65536


class ArtifactError(RuntimeError):
    """The candidate cannot safely be saved as a test artifact."""


def _atomic_write(destination: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _read_candidate(run_folder: Path, container_path: str) -> bytes:
    if not isinstance(container_path, str) or '\x00' in container_path:
        raise ArtifactError('Invalid candidate path')
    path = PurePosixPath(container_path)
    root = PurePosixPath('/work/repro')
    try:
        relative = path.relative_to(root)
    except ValueError:
        raise ArtifactError('Candidate must be under /work/repro') from None
    if not relative.parts or any(part in ('.', '..') for part in relative.parts):
        raise ArtifactError('Invalid candidate path')
    if relative.suffix != '.py':
        raise ArtifactError('Candidate must be a Python file')
    directory = run_folder / 'repro'
    if directory.is_symlink():
        raise ArtifactError('Repro directory must not be a symlink')
    current = directory
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ArtifactError('Candidate path must not contain symlinks')
    try:
        resolved_root = directory.resolve(strict=True)
        resolved = current.resolve(strict=True)
        resolved.relative_to(resolved_root)
        flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        flags |= getattr(os, 'O_NONBLOCK', 0)
        descriptor = os.open(resolved, flags)
        with os.fdopen(descriptor, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ArtifactError('Candidate must be a regular file')
            content = stream.read(_MAX_TEST_BYTES + 1)
    except (OSError, ValueError):
        raise ArtifactError('Candidate file is missing or inaccessible') from None
    if len(content) > _MAX_TEST_BYTES:
        raise ArtifactError('Candidate file is too large')
    try:
        tree = ast.parse(content.decode('utf-8'))
    except (UnicodeDecodeError, SyntaxError, ValueError):
        raise ArtifactError('Candidate is not valid UTF-8 Python') from None
    if not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith('test_')
               for node in ast.walk(tree)):
        raise ArtifactError('Candidate does not contain a pytest-style test function')
    return content


def write_run_artifacts(run_folder: str | Path, result: AgentResult) -> dict:
    """Write an accepted test and result without claiming verifier success."""
    folder = Path(run_folder)
    folder.mkdir(parents=True, exist_ok=True)
    data = asdict(result)
    data.update({'status': 'not_reproduced', 'confidence': None,
                 'checks': {'symptom_match': result.verdict if result.outcome == 'candidate_found' else None,
                            'repeated_runs': None, 'fixed_version': None},
                 'verification': 'pending' if result.outcome == 'candidate_found' else 'not_run',
                 'status_detail': ('Candidate awaits independent verification' if result.outcome == 'candidate_found'
                                   else 'No verified reproduction'), 'test_file': None})
    if result.outcome == 'candidate_found':
        if result.verdict not in ('exact', 'partial') or not result.repro_path:
            raise ArtifactError('Candidate lacks a confirmed symptom match or path')
        content = _read_candidate(folder, result.repro_path)
        _atomic_write(folder / 'test_repro.py', content)
        data['test_file'] = 'test_repro.py'
    _atomic_write(folder / 'result.json', (json.dumps(data, indent=2) + '\n').encode('utf-8'))
    return data
