"""CLI for the causal FP&A agent."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from fpa_agent.agent.pipeline import analyze, load_tables
from fpa_agent.env import repo_root

app = typer.Typer(add_completion=False, no_args_is_help=True, invoke_without_command=False)
console = Console()


def _resolve_path(path: Path) -> Path:
    """Resolve relative paths against the repo root (not CWD)."""
    if path.is_absolute():
        return path
    return (repo_root() / path).resolve()


@app.command("explain")
def explain_cmd(
    data_dir: Path = typer.Option(Path("data/given"), help="Directory with given CSVs"),
    company: str = typer.Option("Alphabet", help="Company key in the CSVs"),
    period: str = typer.Option("2026-Q2", help="Analysis period YYYY-Qn"),
    prior_period: str = typer.Option("2026-Q1", help="Comparison period YYYY-Qn"),
    materiality: float = typer.Option(0.08, help="Min |share of parent delta| to keep"),
    z: float = typer.Option(1.5, help="|Z-score| materiality threshold"),
    json_out: Path | None = typer.Option(None, help="Optional path to write full JSON evidence"),
    validate: bool = typer.Option(
        False,
        "--validate/--no-validate",
        help="Run one-shot validation (legacy). Prefer --agent-loop for write↔validate loop.",
    ),
    rewrite_on_fail: bool = typer.Option(
        True,
        "--rewrite/--no-rewrite",
        help="When using --validate, auto-rewrite once on failure",
    ),
    agent_loop: bool = typer.Option(
        False,
        "--agent-loop/--no-agent-loop",
        help="LangChain writer↔validator loop; succeeds ONLY if validation agent passes",
    ),
    max_loop_rounds: int = typer.Option(3, help="Max write/validate rounds for --agent-loop"),
) -> None:
    """Top-down revenue causal explanation: analytics → LLM (+ optional LangChain agent loop)."""
    data_dir = _resolve_path(data_dir)
    tables = load_tables(data_dir)
    result = analyze(
        tables,
        company=company,
        period=period,
        prior_period=prior_period,
        materiality_share=materiality,
        material_z=z,
        validate=validate and not agent_loop,
        rewrite_on_fail=rewrite_on_fail,
        agent_loop=agent_loop,
        max_loop_rounds=max_loop_rounds,
    )

    rs = result.revenue_stat
    console.print(
        Panel.fit(
            f"[bold]{result.company}[/bold]  {result.prior_period} → {result.period}\n"
            f"Revenue Δ = {rs.get('delta'):,.2f} ({_pct(rs.get('pct_change'))})  "
            f"z = {_num(rs.get('z_score'))}",
            title="North star",
        )
    )

    table = Table(title="Driver clusters")
    table.add_column("Cluster")
    table.add_column("Δ", justify="right")
    table.add_column("mean z", justify="right")
    table.add_column("dims")
    table.add_column("top drivers")
    for c in result.clusters:
        top = ", ".join(d.label for d in c.drivers[:3])
        table.add_row(
            c.label,
            f"{c.total_delta:,.1f}",
            f"{c.mean_z:.2f}",
            ",".join(c.dimensions),
            top,
        )
    console.print(table)
    console.print(Panel(result.summary, title="Executive revenue brief"))

    if agent_loop:
        loop = result.agent_loop or {}
        status = "PASS" if result.passed else "FAIL"
        color = "green" if result.passed else "red"
        v = result.validation or {}
        issues = v.get("issues") or []
        errors = [i for i in issues if i.get("severity") == "error"]
        lines = [
            f"Loop status: {status}  (passes ONLY if validation agent succeeds)",
            f"Rounds: {loop.get('rounds')} / max",
            f"History: {loop.get('history')}",
            f"Validation errors: {len(errors)}",
        ]
        for i in errors[:6]:
            lines.append(f"- {i.get('code')}: {i.get('message')}")
        console.print(Panel("\n".join(lines), title=f"[{color}]LangChain agent loop[/{color}]"))
        if not result.passed:
            raise typer.Exit(code=2)

    elif validate:
        v = result.validation or {}
        if v:
            status = "PASS" if v.get("passed") else "FAIL"
            color = "green" if v.get("passed") else "red"
            issues = v.get("issues") or []
            errors = [i for i in issues if i.get("severity") == "error"]
            warnings = [i for i in issues if i.get("severity") == "warning"]
            lines = [
                f"Status: {status}",
                f"Rewritten: {v.get('rewritten')}",
                f"Errors: {len(errors)}  Warnings: {len(warnings)}",
            ]
            for i in (errors + warnings)[:8]:
                lines.append(f"- [{i.get('severity')}] {i.get('code')}: {i.get('message')}")
            console.print(Panel("\n".join(lines), title=f"[{color}]Validation[/{color}]"))
            if not v.get("passed"):
                raise typer.Exit(code=2)

    if json_out:
        out = _resolve_path(json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result.to_json())
        console.print(f"[green]Wrote evidence → {out}[/green]")


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.1%}"


def _num(x: float | None) -> str:
    return "n/a" if x is None else f"{x:.2f}"


def main() -> None:
    app()


if __name__ == "__main__":
    main()
