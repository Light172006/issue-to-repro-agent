"""Command-line orchestration for the current reproduction pipeline."""
from __future__ import annotations

import json
import os
import uuid
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

import docker
import httpx
import typer

from repro.agent import run_agent
from repro.envbuilder import EnvironmentBuilder
from repro.github import fetch_issue
from repro.llm import Budget, BudgetExceeded, OpenAIProvider, load_config
from repro.parser import ModelClient, parse_issue
from repro.sandbox import Sandbox
from repro.tools import SandboxTools, tool_schemas

app = typer.Typer(add_completion=False)


@app.command()
def main(issue_url: str) -> None:
    """Fetch ISSUE_URL and attempt an offline reproduction."""
    key = os.environ.get('META_MODEL_API_KEY')
    if not key:
        raise typer.BadParameter('Set META_MODEL_API_KEY in your environment')
    root = Path.cwd()
    config = root / 'config'
    runs = root / 'runs'
    folder = runs / uuid.uuid4().hex
    folder.mkdir(parents=True)
    limits = load_config(config / 'limits.yaml')
    models = load_config(config / 'models.yaml')
    model = load_config(config / 'parser.yaml')['default_model']
    budget = Budget(runs / 'spend.sqlite', limits)
    try:
        with closing(OpenAIProvider(api_key=key)) as provider:
            issue, _ = fetch_issue(issue_url, token=os.environ.get('GITHUB_TOKEN'))
            record = parse_issue(issue, ModelClient(provider, budget, models,
                                 folder / 'parser_trace.jsonl', model=model))
            headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-agent'}
            token = os.environ.get('GITHUB_TOKEN')
            if token:
                headers['Authorization'] = 'Bearer ' + token
            with closing(docker.from_env()) as dc, httpx.Client(headers=headers, timeout=20) as hc:
                remaining = int(float(limits['max_seconds']) - (budget.clock() - budget.started))
                if remaining <= 0:
                    raise BudgetExceeded('Time limit reached before environment build')
                environment = EnvironmentBuilder(dc, hc).build(record.repo, record.version, folder,
                                                               timeout=min(600, remaining))
                sandbox = Sandbox(image=environment['image'], client=dc, max_timeout=60,
                                  working_dir='/var/tmp/repro/source',
                                  writable_mount=folder / 'repro')
                tools = SandboxTools(sandbox, record)
                result = run_agent(record, tools, provider=provider, budget=budget,
                                   model_config=models, model=model,
                                   trace_path=str(folder / 'trace.jsonl'),
                                   tool_schemas=tool_schemas())
            (folder / 'result.json').write_text(json.dumps(asdict(result), indent=2), encoding='utf-8')
            typer.echo(f'Outcome: {result.outcome}\nReason: {result.reason or "none"}\n'
                       f'Verdict: {result.verdict or "none"}\n'
                       f'Conservative cost USD: {result.cost_usd}\nRun folder: {folder}')
    finally:
        budget.close()


if __name__ == '__main__':
    app()
