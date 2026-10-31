"""Read static test-dependency declarations as data; never execute target code."""
from __future__ import annotations

import ast
import configparser
import re
import tomllib
from dataclasses import dataclass


@dataclass(frozen=True)
class DependencyPlan:
    extras: tuple[str, ...]
    requirements: tuple[str, ...]
    plugins: tuple[str, ...]
    warnings: tuple[str, ...]


_EXTRAS = ('test', 'tests', 'testing', 'dev')
_SIMPLE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?(?:\s*(?:[<>=!~]=?|===)\s*[A-Za-z0-9.*+_-]+(?:\s*,\s*(?:[<>=!~]=?|===)\s*[A-Za-z0-9.*+_-]+)*)?$')


def discover_test_dependencies(files: dict[str, str]) -> DependencyPlan:
    """Derive a deterministic conservative plan from already-read text files."""
    extras: list[str] = []
    requirements: list[str] = []
    warnings: list[str] = []
    configs: list[str] = []

    def add(requirement: object, origin: str) -> None:
        if not isinstance(requirement, str):
            warnings.append(f'{origin}: dynamic or non-string dependency')
            return
        requirement = requirement.strip()
        if _SIMPLE.fullmatch(requirement):
            if requirement not in requirements:
                requirements.append(requirement)
        elif requirement:
            warnings.append(f'{origin}: unsupported dependency declaration')

    pyproject = files.get('pyproject.toml')
    if pyproject is not None:
        try:
            data = tomllib.loads(pyproject)
            groups = data.get('dependency-groups', {})
            options = data.get('project', {}).get('optional-dependencies', {})
            poetry = data.get('tool', {}).get('poetry', {})
            for name in _EXTRAS:
                if name in options:
                    extras.append(name)
                group = groups.get(name, [])
                if isinstance(group, list):
                    for value in group:
                        add(value, f'dependency-groups.{name}')
                if name in poetry.get('group', {}):
                    warnings.append(f'poetry group {name}: static conversion not supported')
            pytest_config = data.get('tool', {}).get('pytest', {}).get('ini_options', {})
            configs.append(str(pytest_config.get('addopts', '')))
        except (tomllib.TOMLDecodeError, AttributeError, TypeError):
            warnings.append('pyproject.toml: invalid or unsupported configuration')

    for name in ('setup.cfg', 'tox.ini', 'pytest.ini'):
        if name not in files:
            continue
        config = configparser.ConfigParser(interpolation=None, strict=False)
        try:
            config.read_string(files[name])
            if config.has_section('options.extras_require'):
                extras.extend(x for x in _EXTRAS if config.has_option('options.extras_require', x) and x not in extras)
            for section in config.sections():
                if section.startswith('testenv') and config.has_option(section, 'deps'):
                    for dep in config.get(section, 'deps').splitlines():
                        add(dep, f'{name}:{section}')
                if section in ('pytest', 'tool:pytest') and config.has_option(section, 'addopts'):
                    configs.append(config.get(section, 'addopts'))
        except configparser.Error:
            warnings.append(f'{name}: invalid configuration')

    for name in sorted(files):
        if re.fullmatch(r'(?:.*/)?requirements[^/]*(?:test|dev)[^/]*\.txt', name, re.IGNORECASE):
            for line in files[name].splitlines():
                add(line.split('#', 1)[0], name)

    if 'noxfile.py' in files:
        try:
            tree = ast.parse(files['noxfile.py'])
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
                        node.func.attr == 'install'):
                    for arg in node.args:
                        add(arg.value if isinstance(arg, ast.Constant) else None, 'noxfile.py')
        except SyntaxError:
            warnings.append('noxfile.py: invalid syntax')

    plugins: list[str] = []
    if any(re.search(r'(^|\s)--cov(?:[=\s-]|$)', text) for text in configs):
        plugins.append('pytest-cov')
    return DependencyPlan(tuple(extras), tuple(requirements), tuple(plugins), tuple(warnings))
