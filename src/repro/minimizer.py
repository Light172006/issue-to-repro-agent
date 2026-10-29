"""Syntax-aware source ranges for deterministic reproduction reduction."""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    start: int
    end: int
    replacement: str = ''


def units(source: str, *, top_level: bool) -> list[Unit]:
    """Return removable statement line ranges without regenerating source."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    result = []
    bodies = [tree.body] if top_level else [node.body for node in ast.walk(tree)
              if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
    for body in bodies:
        for statement in body:
            start = min([statement.lineno] + [d.lineno for d in getattr(statement, 'decorator_list', [])])
            end = statement.end_lineno or statement.lineno
            replacement = ''
            if len(body) == 1 and not top_level:
                indent = lines[statement.lineno - 1][:statement.col_offset]
                newline = '\r\n' if lines[statement.lineno - 1].endswith('\r\n') else '\n'
                replacement = indent + 'pass' + newline
            result.append(Unit(start, end, replacement))
    return sorted(result, key=lambda u: (u.start, u.end))


def remove_units(source: str, selected: list[Unit]) -> str:
    lines = source.splitlines(keepends=True)
    for unit in sorted(selected, key=lambda u: u.start, reverse=True):
        lines[unit.start - 1:unit.end] = [unit.replacement] if unit.replacement else []
    return ''.join(lines)
