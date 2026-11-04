"""Unit tests for benchmark runner and scorer."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bench.run import (
    extract_python_code,
    load_candidate_snapshot,
    run_baseline_a_candidate,
)
from bench.score import (
    calculate_metrics,
    evaluate_candidate_run,
    format_results_markdown,
)
from repro.llm import Budget, Reply


def test_extract_python_code_markdown_block():
    text = "Here is the repro:\n```python\ndef test_something():\n    assert 1 == 2\n```\nDone."
    code = extract_python_code(text)
    assert code is not None
    assert "def test_something():" in code
    assert "assert 1 == 2" in code


def test_extract_python_code_raw_valid_python():
    text = "import pytest\ndef test_repro():\n    assert False\n"
    code = extract_python_code(text)
    assert code == text.strip()


def test_extract_python_code_invalid_syntax():
    text = "This is not python code at all, just a sentence."
    code = extract_python_code(text)
    assert code is None


def test_load_candidate_snapshot_normalizes_author(tmp_path: Path):
    snap_data = {
        "schema_version": 2,
        "repo": "test/repo",
        "number": 12,
        "body": "Bug report",
        "comments": [
            {"user": "alice", "body": "Comment 1"},
            {"author": "bob", "body": "Comment 2"}
        ]
    }
    p = tmp_path / "snap.json"
    p.write_text(json.dumps(snap_data), encoding="utf-8")
    loaded = load_candidate_snapshot(p)
    assert loaded["comments"][0]["author"] == "alice"
    assert loaded["comments"][1]["author"] == "bob"


def test_run_baseline_a_candidate_success(tmp_path: Path):
    candidate = {"id": "test-1", "library": "test/repo", "title": "Test Bug"}
    snapshot = {"title": "Test Bug", "body": "Some description"}
    run_dir = tmp_path / "run_1"

    provider = MagicMock()
    reply = Reply(
        message={"content": "```python\ndef test_repro():\n    assert 1 == 2\n```"},
        input_tokens=100,
        output_tokens=50,
        cost_usd=Decimal("0.005")
    )
    budget = MagicMock()
    budget.clock.return_value = 100.0
    budget.run_charged = 5000000  # 0.005 USD
    budget.steps = 1

    with patch("bench.run.call_model", return_value=reply):
        res = run_baseline_a_candidate(candidate, snapshot, run_dir, provider, budget, {"meta/test": {}}, "meta/test")

    assert res["status"] == "candidate_found"
    assert (run_dir / "test_repro.py").is_file()
    assert (run_dir / "result.json").is_file()
    saved = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    assert saved["status"] == "candidate_found"


def test_run_baseline_a_candidate_no_code(tmp_path: Path):
    candidate = {"id": "test-2", "library": "test/repo", "title": "Test Bug"}
    snapshot = {"title": "Test Bug", "body": "Some description"}
    run_dir = tmp_path / "run_2"

    provider = MagicMock()
    reply = Reply(
        message={"content": "I cannot reproduce this issue."},
        input_tokens=100,
        output_tokens=20,
        cost_usd=Decimal("0.002")
    )
    budget = MagicMock()
    budget.clock.return_value = 100.0
    budget.run_charged = 2000000
    budget.steps = 1

    with patch("bench.run.call_model", return_value=reply):
        res = run_baseline_a_candidate(candidate, snapshot, run_dir, provider, budget, {"meta/test": {}}, "meta/test")

    assert res["status"] == "gave_up"
    assert not (run_dir / "test_repro.py").is_file()


def test_score_infeasible_correct_refusal(tmp_path: Path):
    candidate = {
        "id": "validators-dns",
        "category": "infeasible",
        "infeasible_category": "network"
    }
    run_dir = tmp_path / "val_run"
    run_dir.mkdir()
    res_data = {
        "status": "not_feasible",
        "status_detail": "Requires external live internet DNS network resolution",
        "cost_usd": "0.00",
        "duration": 0.5
    }
    (run_dir / "result.json").write_text(json.dumps(res_data), encoding="utf-8")

    scored = evaluate_candidate_run(candidate, run_dir, None, None)
    assert scored["is_correct"] is True
    assert scored["verdict"] == "correct_refusal"
    assert scored["failure_category"] is None


def test_score_infeasible_false_attempt(tmp_path: Path):
    candidate = {
        "id": "colorama-110",
        "category": "infeasible",
        "infeasible_category": "os"
    }
    run_dir = tmp_path / "val_attempt"
    run_dir.mkdir()
    res_data = {
        "status": "candidate_found",
        "cost_usd": "0.02",
        "duration": 5.0
    }
    (run_dir / "result.json").write_text(json.dumps(res_data), encoding="utf-8")

    scored = evaluate_candidate_run(candidate, run_dir, None, None)
    assert scored["is_correct"] is False
    assert scored["failure_category"] == "false_positive_attempt"


def test_score_feasible_offline_unevaluated(tmp_path: Path):
    candidate = {
        "id": "parse-272",
        "category": "feasible",
        "library": "r1chardj0n3s/parse",
        "buggy_ref": "abc",
        "fix_ref": "def"
    }
    run_dir = tmp_path / "parse_run"
    run_dir.mkdir()
    res_data = {
        "status": "candidate_found",
        "cost_usd": "0.05",
        "duration": 12.0
    }
    (run_dir / "result.json").write_text(json.dumps(res_data), encoding="utf-8")
    (run_dir / "test_repro.py").write_text("def test_parse(): assert 1 == 2", encoding="utf-8")

    # In offline mode (dc=None, builder=None), it does not fabricate passes
    scored = evaluate_candidate_run(candidate, run_dir, None, None)
    assert scored["is_correct"] is False
    assert scored["verdict"] == "unevaluated"
    assert scored["failure_category"] == "offline_unevaluated"


def test_calculate_metrics_comprehensive():
    records = [
        {"category": "feasible", "is_correct": True, "cost_usd": "0.10", "duration": 10.0},
        {"category": "feasible", "is_correct": True, "cost_usd": "0.20", "duration": 20.0},
        {"category": "feasible", "is_correct": False, "cost_usd": "0.30", "duration": 30.0},
        {"category": "infeasible", "is_correct": True, "cost_usd": "0.00", "duration": 0.0},
        {"category": "infeasible", "is_correct": False, "cost_usd": "0.05", "duration": 5.0},
    ]
    m = calculate_metrics(records)
    assert m["total"] == 5
    assert m["feasible"] == 3
    assert m["infeasible"] == 2
    assert m["tp"] == 2
    assert m["fn"] == 1
    assert m["tn"] == 1
    assert m["fp"] == 1

    # Correctness = (2 + 1) / 5 = 60.0%
    assert m["correctness"] == 60.0
    # Precision = TP / (TP + FP) = 2 / (2 + 1) = 66.666...%
    assert abs(m["precision"] - 66.67) < 0.1
    # Recall = TP / (TP + FN) = 2 / (2 + 1) = 66.666...%
    assert abs(m["recall"] - 66.67) < 0.1

    assert m["total_cost"] == "0.65"
    assert m["avg_cost"] == "0.1300"
    assert m["total_duration"] == 65.0
    assert m["avg_duration"] == 13.0
    assert m["reproduction_rate"] == (2 / 3) * 100.0
    assert m["refusal_quality"] == (1 / 2) * 100.0


def test_baseline_a_metrics_rule():
    # Exactly matching the development distribution of Baseline A:
    # 9 feasible, 2 infeasible = 11 total.
    # Baseline A emits candidate_found for all 11:
    # 3 feasible correct, 6 feasible wrong, 2 infeasible wrong attempts.
    records = []
    # 3 correct feasible
    for _ in range(3):
        records.append({"category": "feasible", "status": "candidate_found", "is_claim": True, "is_correct": True, "fail_to_pass": True, "symptom_match": "partial"})
    # 6 wrong feasible
    for _ in range(6):
        records.append({"category": "feasible", "status": "candidate_found", "is_claim": True, "is_correct": False, "fail_to_pass": False, "symptom_match": "none"})
    # 2 wrong infeasible (attempted candidates)
    for _ in range(2):
        records.append({"category": "infeasible", "status": "candidate_found", "is_claim": True, "is_correct": False, "fail_to_pass": False, "symptom_match": None})

    m = calculate_metrics(records)
    assert m["total"] == 11
    assert m["feasible"] == 9
    assert m["infeasible"] == 2
    assert m["claims"] == 11
    assert m["correct_claims"] == 3
    assert m["wrong_claims"] == 8
    assert abs(m["wrong_claim_rate"] - (8 / 11 * 100.0)) < 1e-4
    assert abs(m["reproduction_rate"] - (3 / 9 * 100.0)) < 1e-4
    assert m["refusal_quality"] == 0.0
    assert m["fail_to_pass_count"] == 3
    assert m["symptom_match_count"] == 3


def test_format_results_markdown():
    metrics = {
        "full": {
            "development": {
                "total": 11, "tp": 6, "tn": 2, "fp": 1, "fn": 2,
                "correctness": 72.7, "precision": 85.7, "recall": 75.0,
                "total_cost": "2.40", "avg_cost": "0.2182", "avg_duration": 45.2
            },
            "held_out": {
                "total": 7, "tp": 4, "tn": 2, "fp": 0, "fn": 1,
                "correctness": 85.7, "precision": 100.0, "recall": 80.0,
                "total_cost": "1.50", "avg_cost": "0.2143", "avg_duration": 38.0
            }
        }
    }
    all_records = [
        {"arm": "full", "split": "development", "failure_category": "passed_at_buggy", "candidate_id": "c1", "is_correct": False},
        {"arm": "full", "split": "held_out", "failure_category": None, "candidate_id": "c2", "is_correct": True}
    ]
    md = format_results_markdown(metrics, all_records)
    assert "# Benchmark Evaluation Results" in md
    assert "72.7%" in md
    assert "85.7%" in md


def test_baseline_b_wiring(tmp_path: Path):
    """Verify that arm='baseline_b' calls run_full_system_candidate with no_verify=True and no_minimize=True."""
    from bench.run import run_single_candidate

    cand = {
        'id': 'test-cand',
        'library': 'test/lib',
        'buggy_ref': 'abc',
        'category': 'feasible',
        'split': 'development'
    }
    snap_dir = tmp_path / 'snaps'
    snap_dir.mkdir()
    (snap_dir / 'test-cand.json').write_text(json.dumps({'body': 'test'}), encoding='utf-8')
    with patch('bench.run.load_candidate_snapshot', return_value={'body': 'test'}), \
         patch('bench.run.run_full_system_candidate', return_value={'status': 'candidate_found'}) as mock_full, \
         patch('bench.run.docker.from_env'), \
         patch('bench.run.httpx.Client'):
        res = run_single_candidate(
            cand,
            'baseline_b',
            tmp_path / 'bench',
            snap_dir,
            Path('config'),
            token=None,
            api_key='',
            no_escalation=True,
            no_minimize=True,
        )
        assert res['arm'] == 'baseline_b'
        mock_full.assert_called_once()
        _, kwargs = mock_full.call_args
        assert kwargs['no_verify'] is True
        assert kwargs['no_minimize'] is True


