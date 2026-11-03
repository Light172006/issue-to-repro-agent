"""Tests for dataset validation and infeasible category classification."""
from __future__ import annotations

from scripts.validate_dataset import VALID_INFEASIBLE_CATEGORIES, validate_infeasible


def test_valid_infeasible_categories_set():
    assert VALID_INFEASIBLE_CATEGORIES == {'hardware', 'os', 'network', 'credentials', 'external_service'}


def test_validate_infeasible_explicit_category():
    candidate = {
        'id': 'test-explicit-net',
        'category': 'infeasible',
        'infeasible_category': 'network',
        'infeasible_reason': 'Requires external live internet DNS resolution.',
        'infeasible_evidence': 'socket.gethostbyname raises OSError in sandbox.'
    }
    ok, msg = validate_infeasible(candidate)
    assert ok is True
    assert 'category: network' in msg


def test_validate_infeasible_inferred_network():
    candidate = {
        'id': 'validators-dns',
        'category': 'infeasible',
        'title': 'domain validator fails when resolving external internationalized domain names (IDN)',
        'infeasible_reason': 'Requires external live internet DNS network resolution and network connectivity, which is blocked by the --network none sandbox boundary.',
        'test_code': 'assert domain("example.com", resolve=True)'
    }
    ok, msg = validate_infeasible(candidate)
    assert ok is True
    assert 'category: network' in msg


def test_validate_infeasible_inferred_os():
    candidate = {
        'id': 'colorama-110',
        'category': 'infeasible',
        'title': 'AnsiToWin32 raises OSError on Windows when handle is redirected to character device',
        'infeasible_reason': 'Requires Windows kernel32 Win32 Console API (kernel32.GetConsoleMode), which is unavailable in the Linux execution sandbox.',
        'test_code': 'AnsiToWin32(sys.stdout)'
    }
    ok, msg = validate_infeasible(candidate)
    assert ok is True
    assert 'category: os' in msg


def test_validate_infeasible_inferred_hardware():
    candidate = {
        'id': 'gpustat-cuda',
        'category': 'infeasible',
        'title': 'gpustat crashes when NVIDIA NVML driver library is missing',
        'infeasible_reason': 'Requires physical NVIDIA GPU hardware and proprietary NVIDIA NVML/CUDA drivers (/dev/nvidia* and libnvidia-ml.so), which are absent in standard CI and container sandboxes.',
        'test_code': 'gpustat.new_query()'
    }
    ok, msg = validate_infeasible(candidate)
    assert ok is True
    assert 'category: hardware' in msg


def test_validate_infeasible_rejects_non_infeasible():
    candidate = {'id': 'feasible-issue', 'category': 'feasible'}
    ok, msg = validate_infeasible(candidate)
    assert ok is False
    assert 'Category is not infeasible' in msg


def test_validate_infeasible_rejects_missing_reason():
    candidate = {
        'id': 'no-reason',
        'category': 'infeasible',
        'infeasible_category': 'network',
        'infeasible_reason': 'short'
    }
    ok, msg = validate_infeasible(candidate)
    assert ok is False
    assert 'too short' in msg.lower()


def test_validate_infeasible_rejects_unknown_category():
    candidate = {
        'id': 'unknown-cat',
        'category': 'infeasible',
        'infeasible_category': 'quantum_computer',
        'infeasible_reason': 'Requires a quantum computer to run factorization.',
        'infeasible_evidence': 'QPU not available.'
    }
    ok, msg = validate_infeasible(candidate)
    assert ok is False
    assert 'Invalid infeasible category' in msg
