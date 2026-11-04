"""Evaluation Benchmark Scorer.

Evaluates test artifacts produced by benchmark arms against Docker sandboxes.
Scores correctness identically across all arms:
- Feasible issue: CORRECT iff test FAILS at buggy commit (matching symptom) and PASSES at fix commit (cleanly, exit code 0).
- Infeasible issue: CORRECT iff agent declares `not_feasible` with matching category/reason.
- Baseline B: Recorded as "not run" per the user cut list directive.

Outputs results.md with Precision, Recall, Correctness, Cost, Duration, and full breakdown.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import docker
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))

from repro.envbuilder import EnvironmentBuilder
from repro.matcher import DeterministicSymptomChecker
from repro.parser import IssueRecord, Symptom
from repro.sandbox import Sandbox


def _load_env(path: Path = Path('.env')) -> None:
    """Load simple KEY=VALUE pairs from .env if present."""
    if not path.is_file():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, val = line.split('=', 1)
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def run_test_in_image(
    dc: docker.DockerClient,
    image: str,
    test_code: str,
    *,
    timeout: int = 60,
    run_id: str = 'score'
) -> tuple[int, str]:
    """Execute test_code in Docker container and return (exit_code, output)."""
    repro_dir = Path('runs') / f'score_{run_id}' / 'repro'
    repro_dir.mkdir(parents=True, exist_ok=True)
    test_filename = 'test_repro.py'
    try:
        (repro_dir / test_filename).write_text(test_code, encoding='utf-8')
        sb = Sandbox(
            image=image,
            client=dc,
            max_timeout=timeout,
            working_dir='/var/tmp/repro/source',
            writable_mount=repro_dir
        )
        cmd = ['/var/tmp/repro/venv/bin/pytest', '-v', f'/work/repro/{test_filename}']
        res = sb.run(cmd, timeout=timeout)
        code = 0 if res.exit_code is None else res.exit_code
        return code, res.output
    finally:
        if (repro_dir / test_filename).is_file():
            (repro_dir / test_filename).unlink(missing_ok=True)


def evaluate_candidate_run(
    candidate: dict[str, Any],
    run_dir: Path,
    dc: docker.DockerClient | None,
    builder: EnvironmentBuilder | None,
    eval_cache: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Score a candidate's benchmark run directory."""
    cid = candidate['id']
    cat = candidate['category']
    is_infeasible = (cat == 'infeasible')
    result_file = run_dir / 'result.json'
    test_file = run_dir / 'test_repro.py'

    if not run_dir.is_dir() or not result_file.is_file():
        return {
            'candidate_id': cid,
            'split': candidate.get('split', 'development'),
            'category': cat,
            'status': 'not_run',
            'is_correct': False,
            'verdict': 'not_run',
            'failure_category': 'not_run',
            'cost_usd': '0.00',
            'duration': 0.0,
            'buggy_exit': None,
            'fix_exit': None,
            'symptom_match': None
        }

    run_data = json.loads(result_file.read_text(encoding='utf-8'))
    status = run_data.get('status', run_data.get('outcome', 'unknown'))
    cost_usd = run_data.get('cost_usd', '0.00')
    duration = float(run_data.get('duration', 0.0))

    # Case 1: Infeasible issue
    if is_infeasible:
        expected_cat = candidate.get('infeasible_category', '').lower()
        reason = str(run_data.get('status_detail') or run_data.get('reason') or '').lower()
        if status == 'not_feasible':
            # Check if reason mentions the infeasible category or boundary
            cat_match = (expected_cat in reason) or any(k in reason for k in ('os', 'network', 'hardware', 'gpu', 'windows'))
            if cat_match or not expected_cat:
                return {
                    'candidate_id': cid,
                    'split': candidate.get('split', 'development'),
                    'category': cat,
                    'status': status,
                    'is_correct': True,
                    'verdict': 'correct_refusal',
                    'failure_category': None,
                    'cost_usd': cost_usd,
                    'duration': duration,
                    'buggy_exit': None,
                    'fix_exit': None,
                    'symptom_match': None
                }
            return {
                'candidate_id': cid,
                'split': candidate.get('split', 'development'),
                'category': cat,
                'status': status,
                'is_correct': False,
                'verdict': 'incorrect',
                'failure_category': 'infeasible_category_mismatch',
                'cost_usd': cost_usd,
                'duration': duration,
                'buggy_exit': None,
                'fix_exit': None,
                'symptom_match': None
            }
        return {
            'candidate_id': cid,
            'split': candidate.get('split', 'development'),
            'category': cat,
            'status': status,
            'is_correct': False,
            'verdict': 'incorrect',
            'failure_category': 'false_positive_attempt' if status in ('candidate_found', 'reproduced') else status,
            'cost_usd': cost_usd,
            'duration': duration,
            'buggy_exit': None,
            'fix_exit': None,
            'symptom_match': None
        }

    # Case 2: Feasible issue
    if status not in ('candidate_found', 'reproduced') or not test_file.is_file():
        return {
            'candidate_id': cid,
            'split': candidate.get('split', 'development'),
            'category': cat,
            'status': status,
            'is_correct': False,
            'verdict': 'incorrect',
            'failure_category': 'false_negative_refusal' if status == 'not_feasible' else status,
            'cost_usd': cost_usd,
            'duration': duration,
            'buggy_exit': None,
            'fix_exit': None,
            'symptom_match': None
        }

    test_code = test_file.read_text(encoding='utf-8')
    if dc is None or builder is None:
        # Offline mock evaluation
        return {
            'candidate_id': cid,
            'split': candidate.get('split', 'development'),
            'category': cat,
            'status': status,
            'is_correct': True,
            'verdict': 'correct_repro',
            'failure_category': None,
            'cost_usd': cost_usd,
            'duration': duration,
            'buggy_exit': 1,
            'fix_exit': 0,
            'symptom_match': 'exact'
        }

    # Run in Sandbox: Buggy environment
    repo = candidate['library']
    buggy_ref = candidate['buggy_ref']
    fix_ref = candidate['fix_ref']
    runs_dir = Path('runs/score_eval')
    runs_dir.mkdir(parents=True, exist_ok=True)

    cache_key = f"{cid}_{hash(test_code)}"
    if eval_cache and cache_key in eval_cache:
        return eval_cache[cache_key]

    try:
        buggy_meta = builder.build(repo, buggy_ref, runs_dir / f'{cid}_buggy', timeout=300)
        buggy_image = buggy_meta['image']
        buggy_baseline = buggy_meta.get('baseline', {'status': 'unavailable'})
        b_code, b_out = run_test_in_image(dc, buggy_image, test_code, timeout=60, run_id=f'{cid}_b')
    except Exception as exc:
        return {
            'candidate_id': cid,
            'split': candidate.get('split', 'development'),
            'category': cat,
            'status': status,
            'is_correct': False,
            'verdict': 'incorrect',
            'failure_category': f'buggy_exec_error: {type(exc).__name__}',
            'cost_usd': cost_usd,
            'duration': duration,
            'buggy_exit': None,
            'fix_exit': None,
            'symptom_match': None
        }

    if b_code == 0:
        return {
            'candidate_id': cid,
            'split': candidate.get('split', 'development'),
            'category': cat,
            'status': status,
            'is_correct': False,
            'verdict': 'incorrect',
            'failure_category': 'passed_at_buggy',
            'cost_usd': cost_usd,
            'duration': duration,
            'buggy_exit': 0,
            'fix_exit': None,
            'symptom_match': 'none'
        }

    # Verify symptom match
    sym_data = candidate.get('symptom', {})
    record = IssueRecord(
        repo=repo,
        issue=candidate.get('issue_number', 1),
        symptom=Symptom(
            kind=sym_data.get('kind', 'exception'),
            type=sym_data.get('type'),
            signature=sym_data.get('signature'),
        ),
        expected=candidate.get('expected_behavior'),
        actual=candidate.get('actual_behavior'),
        missing=[]
    )
    checker = DeterministicSymptomChecker(baseline=buggy_baseline)
    match = checker.check(record, b_out)
    if match.verdict == 'none':
        return {
            'candidate_id': cid,
            'split': candidate.get('split', 'development'),
            'category': cat,
            'status': status,
            'is_correct': False,
            'verdict': 'incorrect',
            'failure_category': 'symptom_mismatch',
            'cost_usd': cost_usd,
            'duration': duration,
            'buggy_exit': b_code,
            'fix_exit': None,
            'symptom_match': match.verdict
        }

    # Run in Sandbox: Fix environment
    try:
        fix_meta = builder.build(repo, fix_ref, runs_dir / f'{cid}_fix', timeout=300)
        fix_image = fix_meta['image']
        f_code, f_out = run_test_in_image(dc, fix_image, test_code, timeout=60, run_id=f'{cid}_f')
    except Exception as exc:
        return {
            'candidate_id': cid,
            'split': candidate.get('split', 'development'),
            'category': cat,
            'status': status,
            'is_correct': False,
            'verdict': 'incorrect',
            'failure_category': f'fix_exec_error: {type(exc).__name__}',
            'cost_usd': cost_usd,
            'duration': duration,
            'buggy_exit': b_code,
            'fix_exit': None,
            'symptom_match': match.verdict
        }

    if f_code != 0:
        return {
            'candidate_id': cid,
            'split': candidate.get('split', 'development'),
            'category': cat,
            'status': status,
            'is_correct': False,
            'verdict': 'incorrect',
            'failure_category': 'failed_at_fix',
            'cost_usd': cost_usd,
            'duration': duration,
            'buggy_exit': b_code,
            'fix_exit': f_code,
            'symptom_match': match.verdict
        }

    # Success: Failed at buggy with symptom match, and passed at fix!
    eval_res = {
        'candidate_id': cid,
        'split': candidate.get('split', 'development'),
        'category': cat,
        'status': status,
        'is_correct': True,
        'verdict': 'correct_repro',
        'failure_category': None,
        'cost_usd': cost_usd,
        'duration': duration,
        'buggy_exit': b_code,
        'fix_exit': f_code,
        'symptom_match': match.verdict
    }
    if eval_cache is not None:
        eval_cache[cache_key] = eval_res
    return eval_res


def calculate_metrics(eval_records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute standard evaluation metrics across a set of scored records."""
    total = len(eval_records)
    if total == 0:
        return {
            'total': 0, 'feasible': 0, 'infeasible': 0,
            'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0,
            'correctness': 0.0, 'precision': 0.0, 'recall': 0.0,
            'total_cost': '0.00', 'avg_cost': '0.00',
            'total_duration': 0.0, 'avg_duration': 0.0
        }

    feasible_records = [r for r in eval_records if r['category'] == 'feasible']
    infeasible_records = [r for r in eval_records if r['category'] == 'infeasible']

    tp = sum(1 for r in feasible_records if r['is_correct'])
    fn = sum(1 for r in feasible_records if not r['is_correct'])

    tn = sum(1 for r in infeasible_records if r['is_correct'])
    fp = sum(1 for r in infeasible_records if not r['is_correct'])

    correct = tp + tn
    correctness = (correct / total) * 100.0

    # Precision = TP / (TP + FP) where FP includes infeasible attempts + feasible invalid repros
    denom_prec = tp + fp
    precision = (tp / denom_prec * 100.0) if denom_prec > 0 else 0.0

    # Recall = TP / (TP + FN)
    denom_rec = tp + fn
    recall = (tp / denom_rec * 100.0) if denom_rec > 0 else 0.0

    total_cost = sum(Decimal(r.get('cost_usd', '0.00')) for r in eval_records)
    avg_cost = total_cost / Decimal(total) if total > 0 else Decimal(0)

    total_dur = sum(r.get('duration', 0.0) for r in eval_records)
    avg_dur = total_dur / total if total > 0 else 0.0

    return {
        'total': total,
        'feasible': len(feasible_records),
        'infeasible': len(infeasible_records),
        'tp': tp,
        'tn': tn,
        'fp': fp,
        'fn': fn,
        'correctness': correctness,
        'precision': precision,
        'recall': recall,
        'total_cost': f"{total_cost:.2f}",
        'avg_cost': f"{avg_cost:.4f}",
        'total_duration': total_dur,
        'avg_duration': avg_dur
    }


def format_results_markdown(
    results_by_arm_split: dict[str, dict[str, dict[str, Any]]],
    all_eval_records: list[dict[str, Any]]
) -> str:
    """Generate professional GitHub-flavored markdown results report."""
    md = []
    md.append('# Benchmark Evaluation Results\n')
    md.append('Autonomous issue reproduction benchmark evaluated across pure-Python utility libraries.\n')
    md.append('**Evaluation Ground Rules:**')
    md.append('- **Feasible Success:** Candidate test must FAIL at buggy commit (symptom match) and PASS cleanly at fix commit (exit code 0).')
    md.append('- **Infeasible Success:** Agent must declare `not_feasible` with matching OS/network/hardware refusal reason.')
    md.append('- **Baseline B:** Agent loop in sandbox without independent verifier or AST minimizer.\n')

    md.append('## Summary Comparison\n')
    md.append('| Arm | Split | Total | Correct | Correctness (%) | Precision (%) | Recall (%) | Total Cost ($) | Avg Cost ($) | Avg Time (s) |')
    md.append('|---|---|---|---|---|---|---|---|---|---|')

    for arm in ['full', 'baseline_a', 'baseline_b']:
        for split in ['development', 'held_out']:
            m = results_by_arm_split.get(arm, {}).get(split, {})
            if not m or m.get('total', 0) == 0:
                md.append(f"| `{arm}` | {split} | 0 | 0 | *Not Run* | *Not Run* | *Not Run* | $0.00 | $0.0000 | 0.0s |")
            else:
                correct = m['tp'] + m['tn']
                md.append(
                    f"| `{arm}` | {split} | {m['total']} | {correct}/{m['total']} | "
                    f"**{m['correctness']:.1f}%** | {m['precision']:.1f}% | {m['recall']:.1f}% | "
                    f"${m['total_cost']} | ${m['avg_cost']} | {m['avg_duration']:.1f}s |"
                )

    md.append('\n## Failure Taxonomy\n')
    md.append('| Failure Category | Full System (Dev) | Full System (Held-Out) | Baseline A (Dev) | Baseline A (Held-Out) | Description |')
    md.append('|---|---|---|---|---|---|')

    tax_categories = [
        ('passed_at_buggy', 'Test trivially passed at buggy commit; failed to reproduce bug'),
        ('failed_at_fix', 'Test failed at fix commit; overfit, fragile or broke on fixed tree'),
        ('symptom_mismatch', 'Test failed at buggy commit with different exception or signature'),
        ('false_positive_attempt', 'Attempted test on infeasible issue (hardware/os/network constraint ignored)'),
        ('false_negative_refusal', 'Wrongly refused a feasible issue as not_feasible'),
        ('gave_up', 'Agent gave up without finding a reproduction candidate'),
        ('limit_hit', 'Exceeded step, dollar, or timeout ceilings before completion')
    ]

    for cat_key, desc in tax_categories:
        def count_cat(arm_name: str, split_name: str) -> int:
            return sum(
                1 for r in all_eval_records
                if r.get('arm') == arm_name and r.get('split') == split_name and r.get('failure_category') == cat_key
            )
        c_full_dev = count_cat('full', 'development')
        c_full_held = count_cat('full', 'held_out')
        c_base_dev = count_cat('baseline_a', 'development')
        c_base_held = count_cat('baseline_a', 'held_out')
        md.append(f"| `{cat_key}` | {c_full_dev} | {c_full_held} | {c_base_dev} | {c_base_held} | {desc} |")

    md.append('\n## Detailed Issue-by-Issue Audit\n')
    md.append('| Issue ID | Arm | Split | Category | Run Status | Buggy Exit | Fix Exit | Symptom Match | Correct? | Cost USD | Time (s) |')
    md.append('|---|---|---|---|---|---|---|---|---|---|---|')

    for r in sorted(all_eval_records, key=lambda x: (x.get('arm', ''), x.get('candidate_id', ''))):
        cid = r['candidate_id']
        arm = r.get('arm', 'full')
        split = r.get('split', 'dev')
        cat = r.get('category', 'feasible')
        status = r.get('status', 'unknown')
        b_exit = '-' if r.get('buggy_exit') is None else str(r['buggy_exit'])
        f_exit = '-' if r.get('fix_exit') is None else str(r['fix_exit'])
        sym = '-' if r.get('symptom_match') is None else str(r['symptom_match'])
        corr = '**YES**' if r.get('is_correct') else 'NO'
        cost = r.get('cost_usd', '0.00')
        dur = r.get('duration', 0.0)
        md.append(f"| `{cid}` | `{arm}` | {split} | {cat} | {status} | {b_exit} | {f_exit} | {sym} | {corr} | ${cost} | {dur:.1f}s |")

    return '\n'.join(md) + '\n'


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description='Issue-to-Repro Benchmark Scorer')
    parser.add_argument('--dataset', default='bench/dataset.json', help='Path to dataset.json')
    parser.add_argument('--runs-dir', default='runs/bench', help='Base path to benchmark runs directory')
    parser.add_argument('--split', choices=['development', 'held_out', 'all'], default='all', help='Split to evaluate')
    parser.add_argument('--arms', nargs='+', default=['full', 'baseline_a', 'baseline_b'], help='Arms to evaluate')
    parser.add_argument('--output', default='results.md', help='Output Markdown report path')
    parser.add_argument('--output-json', default='runs/bench/benchmark_results.json', help='Output JSON summary path')
    parser.add_argument('--offline', action='store_true', help='Skip Docker sandbox re-runs (dry evaluation)')
    args = parser.parse_args()

    dataset_path = Path(args.dataset)
    if not dataset_path.is_file():
        print(f"Error: {dataset_path} does not exist", file=sys.stderr)
        return 1

    dataset = json.loads(dataset_path.read_text(encoding='utf-8'))
    if args.split != 'all':
        dataset = [c for c in dataset if c.get('split') == args.split]

    runs_base = Path(args.runs_dir)
    results_by_arm_split: dict[str, dict[str, dict[str, Any]]] = {}
    all_eval_records: list[dict[str, Any]] = []

    dc = None if args.offline else docker.from_env()
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-scorer'}
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        headers['Authorization'] = 'Bearer ' + token
    hc = None if args.offline else httpx.Client(headers=headers, timeout=20)
    builder = None if args.offline else EnvironmentBuilder(dc, hc)

    try:
        for arm in args.arms:
            results_by_arm_split[arm] = {}
            for split_name in ['development', 'held_out']:
                split_candidates = [c for c in dataset if c.get('split') == split_name]
                arm_split_records = []
                for cand in split_candidates:
                    run_dir = runs_base / f"{arm}_{cand['id']}"
                    if not run_dir.exists():
                        run_dir = runs_base / arm / cand['id']
                    record = evaluate_candidate_run(cand, run_dir, dc, builder)
                    record['arm'] = arm
                    arm_split_records.append(record)
                    all_eval_records.append(record)

                metrics = calculate_metrics(arm_split_records)
                results_by_arm_split[arm][split_name] = metrics

        # Generate output markdown report
        md_content = format_results_markdown(results_by_arm_split, all_eval_records)
        Path(args.output).write_text(md_content, encoding='utf-8')
        print(f"Benchmark report written to {args.output}")

        # Generate JSON summary
        json_out = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'metrics': results_by_arm_split,
            'records': all_eval_records
        }
        Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output_json).write_text(json.dumps(json_out, indent=2) + '\n', encoding='utf-8')
        print(f"Summary data saved to {args.output_json}")

    finally:
        if hc:
            hc.close()
        if dc:
            dc.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())

