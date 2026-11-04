"""Verify that benchmark snapshots contain untrusted reporter text without curator contamination."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

_CURATOR_KEYS = {'curator', 'fix_ref', 'buggy_ref', 'infeasible_evidence', 'test_code', 'ground_truth'}


def test_all_snapshots_clean_of_curator_content():
    snapshots = list(Path('bench/snapshots').glob('*.json'))
    assert len(snapshots) >= 18, f"Expected at least 18 snapshots, found {len(snapshots)}"

    for snap_path in snapshots:
        data = json.loads(snap_path.read_text(encoding='utf-8'))
        
        # Must conform to schema_version 2
        assert data.get('schema_version') == 2, f"{snap_path.name}: expected schema_version 2"
        assert 'repo' in data and data['repo'], f"{snap_path.name}: missing repo"
        assert isinstance(data.get('number'), int), f"{snap_path.name}: missing integer issue number"
        assert 'body' in data, f"{snap_path.name}: missing body"
        assert isinstance(data.get('comments'), list), f"{snap_path.name}: missing comments list"
        
        # Must not contain benchmark curator fields
        overlap = _CURATOR_KEYS.intersection(data.keys())
        assert not overlap, f"{snap_path.name} contains curator fields: {overlap}"
        
        # Body text must not contain curator leakage
        body = data.get('body') or ''
        for suspect in ('curator note', 'ground truth', 'benchmark solution', 'fix_ref', 'buggy_ref'):
            assert suspect not in body.lower(), f"{snap_path.name} body contains curator marker: {suspect}"
