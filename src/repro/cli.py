"""Command-line orchestration for the current reproduction pipeline."""
from __future__ import annotations

import json
import os
import uuid
from contextlib import closing
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import docker
import httpx
import typer

from repro.agent import AgentResult, run_agent
from repro.envbuilder import EnvironmentBuilder
from repro.github import fetch_issue
from repro.llm import Budget, BudgetExceeded, OpenAIProvider, load_config
from repro.minimizer import minimize_run
from repro.parser import ModelClient, parse_issue
from repro.report import write_report
from repro.result_writer import ArtifactError, _atomic_write, write_run_artifacts
from repro.sandbox import Sandbox
from repro.tools import SandboxTools, tool_schemas
from repro.triage import assess
from repro.verifier import save_verification, verify

app = typer.Typer(add_completion=False)


def _parser_fell_back(trace_path: Path) -> bool:
    """Fail closed when the parser could not produce a validated record."""
    try:
        events = [json.loads(line) for line in trace_path.read_text(encoding='utf-8').splitlines()]
        results = [event for event in events if event.get('event') == 'parser_result']
        return not results or results[-1].get('fallback') is not False
    except (OSError, ValueError, AttributeError):
        return True


def _failed_result(budget: Budget | None, outcome: str, reason: str) -> AgentResult:
    if budget is None:
        return AgentResult(outcome, None, None, 0, '0', 0, reason=reason)
    return AgentResult(outcome, None, None, budget.steps,
                       str(Decimal(budget.run_charged) / Decimal(1_000_000_000)),
                       budget.clock() - budget.started, reason=reason)


@app.command()
def main(issue_url: str, no_minimize: bool = typer.Option(False, '--no-minimize'),
         no_escalation: bool = typer.Option(False, '--no-escalation'),
         force_escalate_at_step: int | None = typer.Option(None, '--force-escalate-at-step', hidden=True, min=1)) -> None:
    """Fetch ISSUE_URL and attempt an offline reproduction."""
    key = os.environ.get('META_MODEL_API_KEY')
    if not key:
        raise typer.BadParameter('Set META_MODEL_API_KEY in your environment')
    root = Path.cwd()
    config = root / 'config'
    runs = root / 'runs'
    folder = runs / uuid.uuid4().hex
    folder.mkdir(parents=True)
    budget = None
    try:
        limits = load_config(config / 'limits.yaml')
        if no_escalation:
            limits.setdefault('escalation', {})['enabled'] = False
        models = load_config(config / 'models.yaml')
        model = load_config(config / 'parser.yaml')['default_model']
        budget = Budget(runs / 'spend.sqlite', limits)
        with closing(OpenAIProvider(api_key=key)) as provider:
            issue, _ = fetch_issue(issue_url, token=os.environ.get('GITHUB_TOKEN'))
            parser_trace = folder / 'parser_trace.jsonl'
            record = parse_issue(issue, ModelClient(provider, budget, models, parser_trace, model=model))
            if _parser_fell_back(parser_trace):
                result = AgentResult('error', None, None, budget.steps,
                                     str(Decimal(budget.run_charged) / Decimal(1_000_000_000)),
                                     budget.clock() - budget.started,
                                     reason='Parser output failed validation; environment was not built')
                written = write_run_artifacts(folder, result)
                write_report(folder, written, secrets=(key, os.environ.get('GITHUB_TOKEN', '')))
                typer.echo(f'Outcome: {result.outcome}\nReason: {result.reason}\n'
                           f'Conservative cost USD: {result.cost_usd}\nRun folder: {folder}')
                raise typer.Exit(code=1)
            triage = assess(issue, record)
            if triage is not None:
                stopped = _failed_result(budget, 'gave_up', triage.reason)
                written = write_run_artifacts(folder, stopped)
                written.update({'status': triage.status, 'status_detail': triage.reason,
                                'questions': list(triage.questions)})
                _atomic_write(folder / 'result.json', (json.dumps(written, indent=2) + '\n').encode('utf-8'))
                write_report(folder, written, questions=triage.questions,
                             secrets=(key, os.environ.get('GITHUB_TOKEN', '')))
                typer.echo(f'Status: {triage.status}\nReason: {triage.reason}\nRun folder: {folder}')
                return
            typer.echo(f'Parsed version: {record.version or "not stated (default branch)"}')
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
                typer.echo(f'Environment ref: {environment["selected_ref"]}\n'
                           f'Environment commit: {environment["commit"]}')
                sandbox = Sandbox(image=environment['image'], client=dc, max_timeout=60,
                                  working_dir='/var/tmp/repro/source',
                                  writable_mount=folder / 'repro')
                tools = SandboxTools(sandbox, record)
                result = run_agent(record, tools, provider=provider, budget=budget,
                                   model_config=models, model=model,
                                   trace_path=str(folder / 'trace.jsonl'),
                                   tool_schemas=tool_schemas(),
                                   force_escalate_at_step=force_escalate_at_step)
            result = replace(result, duration=budget.clock() - budget.started)
            try:
                written = write_run_artifacts(folder, result)
            except (ArtifactError, OSError) as exc:
                failed = replace(result, outcome='error', repro_path=None, verdict=None,
                                 reason=f'Unable to save candidate: {type(exc).__name__}')
                written = write_run_artifacts(folder, failed)
                write_report(folder, written, secrets=(key, os.environ.get('GITHUB_TOKEN', '')))
                typer.echo(f'Outcome: error\nReason: {failed.reason}\nRun folder: {folder}')
                raise typer.Exit(code=1) from None
            if result.outcome == 'candidate_found':
                try:
                    with closing(docker.from_env()) as verify_client:
                        verification = verify(record, (folder / 'test_repro.py').read_bytes(),
                                              environment['image'], verify_client, runs=runs,
                                              deadline=budget.started + float(limits['max_seconds']))
                    written = save_verification(folder, verification)
                    typer.echo(f'Verification: {written["status"]}; confidence: {written["confidence"]}')
                    settings = limits.get('minimizer', {})
                    with closing(docker.from_env()) as minimize_client:
                        written = minimize_run(folder, record, minimize_client, environment['image'],
                            config=settings, enabled=settings.get('enabled', True) and not no_minimize,
                            deadline=budget.started + float(limits['max_seconds']))
                    typer.echo(f'Minimization: {written["minimization"]["status"]}')
                except Exception as exc:  # noqa: BLE001 - keep the saved candidate on verifier errors.
                    typer.echo(f'Verification could not run: {type(exc).__name__}; candidate remains pending')
            write_report(folder, written, secrets=(key, os.environ.get('GITHUB_TOKEN', '')))
            typer.echo(f'Outcome: {result.outcome}\nReason: {result.reason or "none"}\n'
                       f'Verdict: {result.verdict or "none"}\n'
                       f'Conservative cost USD: {result.cost_usd}\nRun folder: {folder}\n'
                       f'Saved test: {written["test_file"] or "none"}')
    except typer.Exit:
        raise
    except KeyboardInterrupt:
        interrupted = _failed_result(budget, 'error', 'Interrupted by user')
        written = write_run_artifacts(folder, interrupted)
        write_report(folder, written, secrets=(key, os.environ.get('GITHUB_TOKEN', '')))
        typer.echo(f'Outcome: error\nReason: Interrupted by user\nRun folder: {folder}')
        raise typer.Exit(code=130) from None
    except Exception as exc:  # noqa: BLE001 - persist a sanitized result at the CLI boundary.
        outcome = 'error'
        if isinstance(exc, BudgetExceeded):
            detail = str(exc).lower()
            outcome = ('limit_hit:time' if 'time' in detail else
                       'limit_hit:steps' if 'step' in detail else 'limit_hit:dollars')
        failed = _failed_result(budget, outcome, f'Pipeline failed: {type(exc).__name__}')
        written = write_run_artifacts(folder, failed)
        write_report(folder, written, secrets=(key, os.environ.get('GITHUB_TOKEN', '')))
        typer.echo(f'Outcome: {failed.outcome}\nReason: {failed.reason}\n'
                   f'Conservative cost USD: {failed.cost_usd}\nRun folder: {folder}')
        raise typer.Exit(code=1) from None
    finally:
        if budget is not None:
            budget.close()


if __name__ == '__main__':
    app()
