"""Save a previously harness-confirmed candidate without calling a model."""
from __future__ import annotations

import argparse
import json
from dataclasses import fields, replace
from pathlib import Path

from repro.agent import AgentResult
from repro.matcher import DeterministicSymptomChecker
from repro.parser import IssueRecord
from repro.result_writer import ArtifactError, write_run_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_folder', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads((args.run_folder / 'result.json').read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            raise TypeError('Invalid result')
        names = {field.name for field in fields(AgentResult)}
        result = AgentResult(**{key: value for key, value in data.items() if key in names})
        if result.outcome != 'candidate_found' or result.verdict not in ('exact', 'partial'):
            raise ValueError('Run has no confirmed candidate')
        parser_events = [json.loads(line) for line in
                         (args.run_folder / 'parser_trace.jsonl').read_text(encoding='utf-8').splitlines()]
        parsed = [event for event in parser_events if event.get('event') == 'parser_result']
        if not parsed or parsed[-1].get('fallback') is not False:
            raise ValueError('Run lacks a validated issue record')
        issue = IssueRecord.model_validate(parsed[-1]['record'])
        events = [json.loads(line) for line in
                  (args.run_folder / 'trace.jsonl').read_text(encoding='utf-8').splitlines()]
        submissions = [event for event in events if event.get('tool') == 'submit_repro' and
                       isinstance(event.get('arguments'), dict) and
                       event['arguments'].get('path') == result.repro_path]
        if not submissions or not isinstance(submissions[-1].get('output'), str):
            raise ValueError('Run lacks matching submission output')
        match = DeterministicSymptomChecker().check(issue, submissions[-1]['output'])
        if match.verdict not in ('exact', 'partial'):
            raise ValueError('Saved submission no longer matches the issue')
        result = replace(result, verdict=match.verdict)
        written = write_run_artifacts(args.run_folder, result)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, ArtifactError) as exc:
        print(f'Could not save candidate: {type(exc).__name__}')
        return 1
    print(f'Saved test: {args.run_folder / written["test_file"]}')
    print(f'Status: {written["status"]}; verification: {written["verification"]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
