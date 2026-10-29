"""Conservative, deterministic early decisions based on reporter-provided facts."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from repro.parser import IssueRecord, issue_text

Status = Literal['not_feasible', 'needs_info']


@dataclass(frozen=True)
class Triage:
    status: Status
    reason: str
    questions: tuple[str, ...] = ()


# Require explicit dependency language; a mention of a GPU alone is not proof
# that one is required. Never access links or follow instructions in the issue.
_REQUIREMENT = re.compile(
    r'\b(?:requires?|needs?|must have|only (?:works|runs) (?:on|with)|'
    r'cannot (?:run|reproduce) without|can(?:not|\'t) (?:run|reproduce) without)\s+'
    r'(?:an? |the |access to |a working )?'
    r'(gpu|cuda|tpu|physical hardware|special hardware|private (?:server|service)|'
    r'credentials|api (?:key|token)|internet access|network access|windows|macos)\b',
    re.IGNORECASE)
_NEGATION = re.compile(r'\b(?:no|not|never|without|does not|doesn\'t)\s+(?:\w+\s+){0,2}$', re.IGNORECASE)

QUESTIONS = {
    'version': 'Which version of the library shows the problem?',
    'python version': 'Which Python version are you using?',
    'os': 'Which operating system and version are you using?',
    'steps': 'What exact steps reproduce the problem?',
    'expected behavior': 'What behavior did you expect?',
    'actual behavior': 'What happened instead? Please include the exact output or error.',
    'traceback': 'If an exception occurred, could you share the complete traceback?',
    'minimal code': 'Could you share a minimal runnable code example?',
    'input data': 'What minimal input data triggers the problem?',
    'config': 'Are there any configuration settings needed to reproduce it?',
}


def assess(issue: dict, record: IssueRecord) -> Triage | None:
    text = issue_text(issue)
    for match in _REQUIREMENT.finditer(text):
        if _NEGATION.search(text[max(0, match.start() - 30):match.start()]):
            continue
        return Triage('not_feasible', f"The report explicitly requires {match.group(1)}, which this sandbox does not provide.")
    missing = set(record.missing)
    if {'steps', 'actual behavior', 'minimal code'} <= missing:
        return Triage('needs_info', 'The report lacks reproduction steps, observed behavior, and runnable code.',
                      tuple(QUESTIONS[name] for name in QUESTIONS if name in missing))
    return None
