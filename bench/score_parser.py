"""Score hand-labelled issues. Network/API use is explicit via --run."""
from __future__ import annotations

import argparse
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from repro.llm import Budget, OpenAIProvider, load_config
from repro.parser import MISSING, ModelClient, parse_issue


def norm(version: str | None) -> str | None:
    return version.lower().removeprefix('v') if version else None


def main() -> int:
    parser = argparse.ArgumentParser(description='Score the labelled parser gold set')
    parser.add_argument('--gold', default='bench/parser_gold.json')
    parser.add_argument('--run', action='store_true', help='Permit real API calls')
    args = parser.parse_args()
    data = json.loads(Path(args.gold).read_text(encoding='utf-8'))
    entries = data['issues']
    categories = [item.get('category') for item in entries if isinstance(item, dict)]
    def valid(item: dict) -> bool:
        expected = item.get('expected')
        if item.get('status') != 'labelled' or not item.get('url') or not isinstance(expected, dict):
            return False
        symptom = expected.get('symptom')
        return ('version' in expected and isinstance(symptom, dict) and
                symptom.get('kind') in ('exception', 'wrong_output', 'regression', 'crash', 'performance', 'other') and
                (symptom.get('kind') != 'exception' or isinstance(symptom.get('type'), str)) and
                isinstance(expected.get('missing'), list) and set(expected['missing']) <= set(MISSING))
    if (len(entries) != 10 or categories.count('clear') != 5 or categories.count('vague') != 3 or
            categories.count('messy') != 2 or not all(isinstance(item, dict) and valid(item) for item in entries)):

        print('Gold set incomplete: label all 10 issues before running. No API calls made.')
        return 2
    snapshots = []
    for item in entries:
        try:
            issue = json.loads(Path(item['snapshot']).read_text(encoding='utf-8'))
            if issue.get('repo', '').lower() != item['repo'].lower() or issue.get('number') != item['issue']:
                raise ValueError('Snapshot identity mismatch')
            snapshots.append(issue)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print(f'Invalid or missing snapshot for {item.get("url")}: {exc}', file=sys.stderr)
            return 2
    print('Estimate: about $0.05 for 10 calls at 2,000 input and 500 output tokens each; retries and larger inputs cost more.')
    if not args.run:
        print('Pass --run to allow real API calls. No API calls made.')
        return 0
    key = os.getenv('META_MODEL_API_KEY')
    if not key:
        print('Set META_MODEL_API_KEY in your environment.', file=sys.stderr)
        return 2
    provider = OpenAIProvider(api_key=key)
    config, limits = load_config('config/models.yaml'), load_config('config/limits.yaml')
    selected = load_config('config/parser.yaml')['default_model']
    total = Decimal(0)
    version_correct = symptom_correct = both_correct = vague_correct = vague_count = 0
    print('issue | version | symptom | both | vague missing')
    try:
        for item, issue in zip(entries, snapshots, strict=True):
            budget = Budget('budget.sqlite3', limits)
            try:
                client = ModelClient(provider, budget, config, 'trace.jsonl', model=selected)
                result = parse_issue(issue, client)
                total += Decimal(budget.run_charged) / Decimal(1_000_000_000)
            finally:
                budget.close()
            expected = item['expected']
            v = norm(result.version) == norm(expected['version'])
            symptom = result.symptom.kind == expected['symptom']['kind'] and (result.symptom.kind != 'exception' or result.symptom.type == expected['symptom']['type'])
            vague = item.get('category') == 'vague'
            m = set(result.missing) == set(expected['missing']) if vague else None
            version_correct += v
            symptom_correct += symptom
            both_correct += v and symptom
            vague_count += vague
            vague_correct += m is True
            print(f"{item['url']} | {v} | {symptom} | {v and symptom} | {m if vague else '-'}")
    finally:
        provider.close()
    print(f'Version: {version_correct}/10; symptom: {symptom_correct}/10; both: {both_correct}/10')
    print(f'Vague missing exact match: {vague_correct}/{vague_count}; review sensibility manually.')
    print(f'Total conservative cost USD: {total}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
