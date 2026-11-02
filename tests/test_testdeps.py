from repro.testdeps import discover_test_dependencies


def test_no_declarations_is_empty():
    plan = discover_test_dependencies({})
    assert plan.extras == plan.requirements == plan.plugins == plan.warnings == ()


def test_pyproject_extras_groups_and_pytest_coverage():
    plan = discover_test_dependencies({'pyproject.toml': '''
[project.optional-dependencies]
test = ["pytest<8"]
[dependency-groups]
dev = ["pytest<8", "hypothesis"]
[tool.pytest.ini_options]
addopts = "--cov=thing --cov-report=term"
'''})
    assert plan.extras == ('test',)
    assert plan.requirements == ('pytest<8', 'hypothesis')
    assert plan.plugins == ('pytest-cov',)


def test_tox_setup_cfg_and_requirements_are_data():
    plan = discover_test_dependencies({
        'setup.cfg': '[options.extras_require]\ntests =\n pytest\n',
        'tox.ini': '[testenv]\ndeps =\n pytest<8\n freezegun\n[pytest]\naddopts = --cov thing\n',
        'requirements-test.txt': 'hypothesis\n-r ../outside\n',
    })
    assert plan.extras == ('tests',)
    assert plan.requirements == ('pytest<8', 'freezegun', 'hypothesis')
    assert plan.plugins == ('pytest-cov',)
    assert any('unsupported' in warning for warning in plan.warnings)


def test_nox_is_parsed_never_executed(tmp_path):
    payload = f"open({str(tmp_path / 'danger')!r}, 'w').write('bad')\nsession.install('pytest<8', runtime_name)"
    plan = discover_test_dependencies({'noxfile.py': payload})
    assert plan.requirements == ('pytest<8',)
    assert plan.warnings == ('noxfile.py: dynamic or non-string dependency',)
    assert not (tmp_path / 'danger').exists()


def test_invalid_and_huge_inputs_are_handled():
    plan = discover_test_dependencies({'pyproject.toml': '!', 'requirements-test.txt': 'x' * 10000})
    assert any('invalid' in warning for warning in plan.warnings)
    assert discover_test_dependencies({'noxfile.py': 'not python !'}).warnings


def test_same_input_gives_same_plan():
    files = {'tox.ini': '[testenv]\ndeps =\n pytest<8\n', 'requirements-dev.txt': 'freezegun\n'}
    assert discover_test_dependencies(files) == discover_test_dependencies(dict(reversed(list(files.items()))))


def test_tox_ignores_py2_and_skips_duplicate_package_pins():
    files = {
        'tox.ini': '[testenv]\ndeps =\n    pytest==7.2.0\n    pytest-cov==4.0.0\n[testenv:py27]\ndeps =\n    pytest==4.6.11\n    pytest-cov==2.12\n[testenv:lint]\ndeps =\n    flake8\n',
    }
    plan = discover_test_dependencies(files)
    assert plan.requirements == ('pytest==7.2.0', 'pytest-cov==4.0.0')
    assert 'flake8' not in plan.requirements
