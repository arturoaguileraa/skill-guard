"""skill-guard -- triage agent-facing artifacts with a System One model."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from rich.console import Console
from rich.table import Table

from skillguard._env import load_dotenv
from skillguard.bank import load_bank
from skillguard.engine import Engine
from skillguard.extract import extract_mcp_servers, extract_skill, find_skills
from skillguard.score import Decision, Thresholds, score

console = Console()

_STYLE = {Decision.ALLOW: "green", Decision.ESCALATE: "yellow", Decision.BLOCK: "bold red"}


def _make_engine(bank, use_fake: bool) -> Engine:
    if use_fake or not os.environ.get("TYPESAFE_API_KEY"):
        from skillguard.testing import FakeClient
        if not use_fake:
            console.print("[dim]No TYPESAFE_API_KEY set -- using heuristic fake client. "
                          "Set the key (or pass --real) for actual Jev readings.[/dim]")
        return Engine(bank, client=FakeClient())
    return Engine(bank)


def _collect(paths: list[Path]):
    artifacts = []
    for path in paths:
        if path.is_dir() and (path / "SKILL.md").exists():
            artifacts.append(extract_skill(path))
        elif path.is_dir():
            artifacts.extend(extract_skill(d) for d in find_skills(path))
        elif path.name.endswith(".json"):
            artifacts.extend(extract_mcp_servers(path))
        elif path.name == "SKILL.md":
            artifacts.append(extract_skill(path.parent))
    return artifacts


def cmd_scan(args) -> int:
    bank = load_bank(args.bank)
    engine = _make_engine(bank, args.fake)
    artifacts = _collect([Path(p).expanduser() for p in args.paths])
    if not artifacts:
        console.print("[red]No skills or MCP servers found at the given paths.[/red]")
        return 1

    th = Thresholds()
    verdicts = []
    total_cost = 0.0
    total_ms = 0.0
    for art in artifacts:
        reading = engine.read(art)
        total_cost += reading.cost_usd
        total_ms += reading.latency_ms
        verdicts.append((score(reading, bank, th), reading))

    verdicts.sort(key=lambda vr: vr[0].risk, reverse=True)

    table = Table(title=f"skill-guard scan -- {len(artifacts)} artifacts")
    table.add_column("risk", justify="right")
    table.add_column("decision")
    table.add_column("kind")
    table.add_column("identity")
    table.add_column("top signals")
    shown = verdicts if args.all else [vr for vr in verdicts if vr[0].decision is not Decision.ALLOW]
    for verdict, _ in shown:
        sig = ", ".join(f"{q}={v:.2f}" for q, v in verdict.top_signals[:3] if v > 0.3) or "-"
        flag = " ⚠" if verdict.integrity_warning else ""
        table.add_row(f"{verdict.risk:.2f}", f"[{_STYLE[verdict.decision]}]{verdict.decision.value}{flag}[/]",
                      verdict.kind, verdict.identity, sig)
    console.print(table)

    n_block = sum(1 for v, _ in verdicts if v.decision is Decision.BLOCK)
    n_esc = sum(1 for v, _ in verdicts if v.decision is Decision.ESCALATE)
    console.print(
        f"[dim]block={n_block}  escalate={n_esc}  allow={len(verdicts)-n_block-n_esc}  "
        f"| cost=${total_cost:.4f}  latency={total_ms:.0f}ms total "
        f"({total_ms/len(artifacts):.0f}ms/artifact)[/dim]"
    )
    if args.all:
        console.print("[dim](showing all; omit --all to hide allowed)[/dim]")
    return 0


def cmd_explain(args) -> int:
    bank = load_bank(args.bank)
    engine = _make_engine(bank, args.fake)
    arts = _collect([Path(args.path).expanduser()])
    if not arts:
        console.print("[red]No artifact found there.[/red]")
        return 1
    art = arts[0]
    reading = engine.read(art)
    verdict = score(reading, bank)

    console.print(f"[bold]{verdict.identity}[/bold]  ({verdict.kind})  from {art.source}")
    console.print(f"risk [bold]{verdict.risk:.3f}[/bold] -> [{_STYLE[verdict.decision]}]{verdict.decision.value}[/]  "
                  f"(mean confidence {verdict.mean_confidence:.2f})")
    if verdict.integrity_warning:
        console.print(f"[bold red]integrity:[/] {verdict.integrity_warning}")

    ft = Table(title="risk by family")
    ft.add_column("family"); ft.add_column("risk", justify="right"); ft.add_column("weight", justify="right")
    for fam, r in sorted(verdict.family_risk.items(), key=lambda kv: kv[1], reverse=True):
        w = bank.families.get(fam, {}).get("weight", 0)
        ft.add_row(fam, f"{r:.2f}", f"{w:.2f}")
    console.print(ft)

    qt = Table(title="per-question readings")
    qt.add_column("question"); qt.add_column("family"); qt.add_column("value", justify="right"); qt.add_column("conf", justify="right")
    for qid in sorted(reading.values, key=lambda q: reading.values[q], reverse=True):
        qt.add_row(qid, bank.specs[qid].family, f"{reading.values[qid]:.2f}", f"{reading.confidence.get(qid,0):.2f}")
    console.print(qt)
    console.print(f"[dim]request_id={reading.request_id}  input_tokens={reading.input_tokens}  "
                  f"cost=${reading.cost_usd:.5f}  latency={reading.latency_ms:.0f}ms[/dim]")
    return 0


def main(argv=None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="skill-guard", description=__doc__)
    parser.add_argument("--bank", default="skill_bank", help="question bank name (default: skill_bank)")
    parser.add_argument("--fake", action="store_true", help="force the heuristic fake client")
    parser.add_argument("--real", dest="fake", action="store_false", help="require the real Jev API")
    parser.set_defaults(fake=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("scan", help="triage many artifacts")
    ps.add_argument("paths", nargs="+")
    ps.add_argument("--all", action="store_true", help="show allowed artifacts too")
    ps.set_defaults(func=cmd_scan)

    pe = sub.add_parser("explain", help="full per-question breakdown for one artifact")
    pe.add_argument("path")
    pe.set_defaults(func=cmd_explain)

    args = parser.parse_args(argv)
    if args.fake is None:
        args.fake = not os.environ.get("TYPESAFE_API_KEY")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
