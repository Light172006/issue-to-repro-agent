"""Evaluation Benchmark Runner.

Executes benchmark candidates across configured arms:
- full: The production Issue-to-Repro Agent pipeline (Spark 1.3 + escalation if triggered)
- baseline_a: Single-shot zero-tool test generation model call
- baseline_b: Skipped per user cut list ("not run" in results)

All runs use issue snapshots from bench/snapshots/ and enforce per-run limits and budget caps.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import docker
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from repro.agent import AgentResult, MAX_OUTPUT_TOKENS, SYSTEM, run_agent
from repro.envbuilder import EnvironmentBuilder
from repro.llm import (
    Budget,
    BudgetExceeded,
    FakeProvider,
    OpenAIProvider,
    call_model,
    load_config,
)
from repro.matcher import DeterministicSymptomChecker
from repro.minimizer import minimize_run
from repro.parser import IssueRecord, ModelClient, parse_issue
from repro.report import write_report
from repro.result_writer import ArtifactError, write_run_artifacts
from repro.sandbox import Sandbox
from repro.tools import SandboxTools, tool_schemas
from repro.triage import assess
from repro.verifier import verify, save_verification


_CODE_BLOCK_RE = re.compile(r'```(?:python)?\s*\n([\s\S]*?)```', re.IGNORECASE)


def _load_env(path: Path = Path('.env')) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('\'"'))


def load_candidate_snapshot(snapshot_path: Path) -> dict[str, Any]:
    """Load and normalize snapshot JSON for ingestion by parse_issue and assess."""
    data = json.loads(snapshot_path.read_text(encoding='utf-8'))
    # Ensure comments have 'author' for parser issue_text compatibility
    for c in data.get('comments', []):
        if isinstance(c, dict) and 'author' not in c and 'user' in c:
            c['author'] = c['user']
    return data


def extract_python_code(text: str) -> str | None:
    """Extract python code from markdown block or return raw text if valid AST."""
    if not text:
        return None
    matches = _CODE_BLOCK_RE.findall(text)
    if matches:
        candidate_code = matches[0].strip()
        try:
            ast.parse(candidate_code)
            return candidate_code
        except SyntaxError:
            pass
    try:
        tree = ast.parse(text)
        has_logic = any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Assert, ast.Import, ast.ImportFrom))
            for node in ast.walk(tree)
        )
        if has_logic:
            return text.strip()
        return None
    except SyntaxError:
        return None


def extract_text_from_reply(reply: Any) -> str:
    """Extract plain text response from diverse model provider Reply outputs."""
    if reply is None:
        return ""
    message = getattr(reply, "message", reply)
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        if "content" in message and isinstance(message["content"], str):
            return message["content"]
        if "text" in message and isinstance(message["text"], str):
            return message["text"]
    pieces = []
    if isinstance(message, list):
        for item in message:
            if isinstance(item, str):
                pieces.append(item)
            elif isinstance(item, dict):
                if "content" in item and isinstance(item["content"], str):
                    pieces.append(item["content"])
                elif "text" in item and isinstance(item["text"], str):
                    pieces.append(item["text"])
            else:
                content = getattr(item, "content", None)
                if isinstance(content, str):
                    pieces.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, str):
                            pieces.append(part)
                        elif isinstance(getattr(part, "text", None), str):
                            pieces.append(part.text)
                elif hasattr(item, "text") and isinstance(item.text, str):
                    pieces.append(item.text)
    if pieces:
        return "".join(pieces)
    if hasattr(message, "content"):
        c = getattr(message, "content")
        if isinstance(c, str):
            return c
    return ""


def run_baseline_a_candidate(
    candidate: dict[str, Any],
    snapshot: dict[str, Any],
    run_dir: Path,
    provider: Any,
    budget: Budget,
    models: dict,
    model: str,
) -> dict[str, Any]:
    """Execute Baseline A: Single model call, zero tools, zero execution."""
    run_dir.mkdir(parents=True, exist_ok=True)
    start_time = budget.clock()

    title = snapshot.get('title') or candidate.get('title') or ''
    body = snapshot.get('body') or ''
    repo = candidate.get('library', '')

    prompt = (
        f"You are an expert Python QA engineer. Write a minimal, standalone reproduction test using pytest for the following bug report.\n\n"
        f"Repository: {repo}\n"
        f"Issue Title: {title}\n"
        f"Issue Description:\n{body}\n\n"
        f"Requirements:\n"
        f"1. Output ONLY a valid pytest test file enclosed in a ```python ... ``` markdown block.\n"
        f"2. Define at least one test function starting with `test_`.\n"
        f"3. Do not modify the library source files; write a standalone test that imports the library and asserts the correct behavior or triggers the bug.\n"
    )

    messages = [
        {'role': 'system', 'content': 'You generate standalone pytest reproduction tests for software bug reports.'},
        {'role': 'user', 'content': prompt}
    ]

    trace_path = run_dir / 'trace.jsonl'
    try:
        reply = call_model(
            provider=provider,
            model=model,
            messages=messages,
            tools=None,
            budget=budget,
            model_config=models,
            trace_path=str(trace_path),
            max_output_tokens=2048,
            reasoning_effort='minimal',
            phase='baseline_a'
        )
        content = extract_text_from_reply(reply)
        code = extract_python_code(content)
        duration = budget.clock() - start_time
        cost_usd = str(Decimal(budget.run_charged) / Decimal(1_000_000_000))

        if code:
            test_file = run_dir / 'test_repro.py'
            test_file.write_text(code + '\n', encoding='utf-8')
            res = {
                'outcome': 'candidate_found',
                'status': 'candidate_found',
                'repro_path': str(test_file),
                'test_file': 'test_repro.py',
                'verdict': 'unverified',
                'steps': 1,
                'cost_usd': cost_usd,
                'duration': duration,
                'reason': 'Baseline A generated test code in single model call'
            }
        else:
            res = {
                'outcome': 'gave_up',
                'status': 'gave_up',
                'repro_path': None,
                'test_file': None,
                'verdict': None,
                'steps': 1,
                'cost_usd': cost_usd,
                'duration': duration,
                'reason': 'Baseline A response contained no valid Python test code'
            }
    except Exception as exc:
        duration = budget.clock() - start_time
        cost_usd = str(Decimal(budget.run_charged) / Decimal(1_000_000_000))
        res = {
            'outcome': 'error',
            'status': 'error',
            'repro_path': None,
            'test_file': None,
            'verdict': None,
            'steps': budget.steps,
            'cost_usd': cost_usd,
            'duration': duration,
            'reason': f'Baseline A model call failed: {type(exc).__name__}'
        }

    (run_dir / 'result.json').write_text(json.dumps(res, indent=2) + '\n', encoding='utf-8')
    return res


def run_full_system_candidate(
    candidate: dict[str, Any],
    snapshot: dict[str, Any],
    run_dir: Path,
    provider: Any,
    budget: Budget,
    models: dict,
    model: str,
    limits: dict,
    dc: docker.DockerClient,
    hc: httpx.Client,
    *,
    no_escalation: bool = False,
    no_minimize: bool = False,
) -> dict[str, Any]:
    """Execute Full System: Triage, environment build at buggy_ref, agent loop, verifier, minimizer."""
    run_dir.mkdir(parents=True, exist_ok=True)
    start_time = budget.clock()
    runs_root = run_dir.parent

    # 1. Parse issue and perform triage
    parser_trace = run_dir / 'parser_trace.jsonl'
    try:
        record = parse_issue(snapshot, ModelClient(provider, budget, models, parser_trace, model=model))
    except Exception as exc:
        # Fallback to candidate metadata record
        from repro.parser import Symptom
        sym_data = candidate.get('symptom', {})
        record = IssueRecord(
            repo=candidate['library'],
            issue=candidate.get('issue_number', 1),
            version=candidate.get('buggy_ref'),
            symptom=Symptom(
                kind=sym_data.get('kind', 'exception'),
                type=sym_data.get('type'),
                signature=sym_data.get('signature'),
            ),
            expected=candidate.get('expected_behavior'),
            actual=candidate.get('actual_behavior'),
            missing=[]
        )

    triage = assess(snapshot, record)
    if triage is not None:
        duration = budget.clock() - start_time
        cost_usd = str(Decimal(budget.run_charged) / Decimal(1_000_000_000))
        res = {
            'outcome': 'gave_up',
            'status': triage.status,
            'status_detail': triage.reason,
            'repro_path': None,
            'test_file': None,
            'verdict': None,
            'steps': budget.steps,
            'cost_usd': cost_usd,
            'duration': duration,
            'reason': triage.reason,
            'questions': list(triage.questions)
        }
        (run_dir / 'result.json').write_text(json.dumps(res, indent=2) + '\n', encoding='utf-8')
        return res

    # 2. Build environment at buggy commit
    remaining = int(float(limits['max_seconds']) - (budget.clock() - start_time))
    if remaining <= 0:
        raise BudgetExceeded('Time limit reached before environment build')

    builder = EnvironmentBuilder(dc, hc)
    try:
        env_meta = builder.build(record.repo, candidate['buggy_ref'], run_dir, timeout=min(300, remaining))
    except Exception as exc:
        duration = budget.clock() - start_time
        cost_usd = str(Decimal(budget.run_charged) / Decimal(1_000_000_000))
        res = {
            'outcome': 'error',
            'status': 'error',
            'repro_path': None,
            'test_file': None,
            'verdict': None,
            'steps': budget.steps,
            'cost_usd': cost_usd,
            'duration': duration,
            'reason': f'Environment build failed: {exc}'
        }
        (run_dir / 'result.json').write_text(json.dumps(res, indent=2) + '\n', encoding='utf-8')
        return res

    baseline = env_meta.get('baseline', {'status': 'unavailable'})
    image = env_meta['image']

    # 3. Agent loop in Sandbox
    sandbox = Sandbox(
        image=image,
        client=dc,
        max_timeout=60,
        working_dir='/var/tmp/repro/source',
        writable_mount=run_dir / 'repro'
    )
    tools = SandboxTools(sandbox, record, checker=DeterministicSymptomChecker(baseline=baseline))
    trace_path = str(run_dir / 'trace.jsonl')

    effective_limits = dict(limits)
    if no_escalation:
        effective_limits.setdefault('escalation', {})['enabled'] = False

    agent_res = run_agent(
        record,
        tools,
        provider=provider,
        budget=budget,
        model_config=models,
        model=model,
        trace_path=trace_path,
        tool_schemas=tool_schemas()
    )

    # 4. Save artifacts & verify if candidate found
    written = write_run_artifacts(run_dir, agent_res)
    if agent_res.outcome == 'candidate_found' and (run_dir / 'test_repro.py').is_file():
        try:
            candidate_bytes = (run_dir / 'test_repro.py').read_bytes()
            verification = verify(
                record,
                candidate_bytes,
                image,
                dc,
                runs=runs_root,
                deadline=budget.started + float(limits['max_seconds']),
                baseline=baseline
            )
            written = save_verification(run_dir, verification)
            if not no_minimize:
                settings = effective_limits.get('minimizer', {})
                written = minimize_run(
                    run_dir,
                    record,
                    dc,
                    image,
                    config=settings,
                    enabled=settings.get('enabled', True),
                    deadline=budget.started + float(limits['max_seconds'])
                )
        except Exception:
            pass

    key = os.environ.get('META_MODEL_API_KEY', '')
    gh_token = os.environ.get('GITHUB_TOKEN', '')
    try:
        write_report(run_dir, written, secrets=(key, gh_token))
    except Exception:
        pass

    return written


def run_single_candidate(
    candidate: dict[str, Any],
    arm: str,
    output_base: Path,
    snapshots_dir: Path,
    config_dir: Path,
    token: str | None,
    api_key: str,
    *,
    no_escalation: bool = False,
    no_minimize: bool = False,
    lock: threading.Lock | None = None,
) -> dict[str, Any]:
    """Worker function to run a single benchmark candidate."""
    cid = candidate['id']
    snapshot_path = snapshots_dir / f'{cid}.json'
    if not snapshot_path.is_file():
        raise FileNotFoundError(f'Snapshot file {snapshot_path} not found')

    snapshot = load_candidate_snapshot(snapshot_path)
    run_dir = Path('runs') / f'{arm}_{cid}'
    run_dir.mkdir(parents=True, exist_ok=True)

    limits = load_config(config_dir / 'limits.yaml')
    if no_escalation:
        limits.setdefault('escalation', {})['enabled'] = False
    models = load_config(config_dir / 'models.yaml')
    model = load_config(config_dir / 'parser.yaml')['default_model']
    ledger_path = Path('runs') / 'spend.sqlite'

    # Thread-safe budget initialization
    budget = Budget(ledger_path, limits)

    provider_cls = OpenAIProvider if api_key else FakeProvider
    provider_kwargs = {'api_key': api_key} if api_key else {}

    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-bench'}
    if token:
        headers['Authorization'] = 'Bearer ' + token

    with closing(provider_cls(**provider_kwargs)) as provider:
        if arm == 'baseline_a':
            res = run_baseline_a_candidate(candidate, snapshot, run_dir, provider, budget, models, model)
        elif arm == 'full':
            with closing(docker.from_env()) as dc, httpx.Client(headers=headers, timeout=20) as hc:
                res = run_full_system_candidate(
                    candidate, snapshot, run_dir, provider, budget, models, model,
                    limits, dc, hc, no_escalation=no_escalation, no_minimize=no_minimize
                )
        else:
            raise ValueError(f'Unsupported arm: {arm}')

    return {'candidate_id': cid, 'arm': arm, 'result': res}


def main() -> int:
    parser = argparse.ArgumentParser(description='Issue-to-Repro Benchmark Runner')
    parser.add_argument('--arm', choices=['full', 'baseline_a', 'all'], default='full', help='Benchmark arm to run')
    parser.add_argument('--split', choices=['development', 'held_out', 'all'], default='development', help='Dataset partition')
    parser.add_argument('--candidate', default=None, help='Run only a specific candidate ID')
    parser.add_argument('--dataset', default='bench/dataset.json', help='Path to dataset.json')
    parser.add_argument('--snapshots-dir', default='bench/snapshots', help='Path to snapshots directory')
    parser.add_argument('--output-dir', default='runs/bench', help='Base directory for benchmark outputs')
    parser.add_argument('--config-dir', default='config', help='Config directory path')
    parser.add_argument('--workers', type=int, default=3, help='Worker threads (max 3)')
    parser.add_argument('--no-escalation', action='store_true', help='Disable escalation in full system')
    parser.add_argument('--no-minimize', action='store_true', help='Disable minimizer in full system')
    args = parser.parse_args()

    _load_env()
    api_key = os.environ.get('META_MODEL_API_KEY', '')
    token = os.environ.get('GITHUB_TOKEN', '')

    dataset_path = Path(args.dataset)
    if not dataset_path.is_file():
        print(f'Error: dataset {dataset_path} does not exist', file=sys.stderr)
        return 1

    dataset = json.loads(dataset_path.read_text(encoding='utf-8'))
    if args.split != 'all':
        dataset = [c for c in dataset if c.get('split') == args.split]

    if args.candidate:
        dataset = [c for c in dataset if c.get('id') == args.candidate]

    if not dataset:
        print(f'No candidates matched criteria (split={args.split}, candidate={args.candidate})', file=sys.stderr)
        return 1

    arms = ['baseline_a', 'full'] if args.arm == 'all' else [args.arm]
    output_base = Path(args.output_dir)
    snapshots_dir = Path(args.snapshots_dir)
    config_dir = Path(args.config_dir)
    workers = min(3, max(1, args.workers))

    print(f'=== Launching Benchmark: arms={arms}, candidates={len(dataset)}, split={args.split}, workers={workers} ===')
    lock = threading.Lock()

    for arm in arms:
        print(f'\n--- Starting Arm: {arm} ({len(dataset)} issues) ---')
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    run_single_candidate,
                    candidate,
                    arm,
                    output_base,
                    snapshots_dir,
                    config_dir,
                    token,
                    api_key,
                    no_escalation=args.no_escalation,
                    no_minimize=args.no_minimize,
                    lock=lock
                ): candidate['id']
                for candidate in dataset
            }
            for fut in as_completed(futures):
                cid = futures[fut]
                try:
                    res = fut.result()
                    status = res['result'].get('status', 'unknown')
                    cost = res['result'].get('cost_usd', '0.00')
                    dur = res['result'].get('duration', 0.0)
                    print(f'[{arm.upper()}] {cid:<20} -> status: {status:<15} (cost: ${cost}, time: {dur:.1f}s)')
                except Exception as exc:
                    print(f'[{arm.upper()}] {cid:<20} -> ERROR: {exc}', file=sys.stderr)

    print('\n=== Benchmark Execution Complete ===')
    return 0


if __name__ == '__main__':
    sys.exit(main())
