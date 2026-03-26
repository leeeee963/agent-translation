"""CLI entry point for the translation agent.

Usage:
    python -m src.main translate <file> --target <language>
    python -m src.main styles [--detail <key>]
    python -m src.main styles-add <key>
    python -m src.main languages
    python -m src.main eval-history

Examples:
    python -m src.main translate presentation.pptx --target ja
    python -m src.main styles --detail technical
    python -m src.main styles-add marketing
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler

from src.orchestrator.agent import Orchestrator

console = Console()

LANG_HELP = (
    "目标语言代码。常用: zh-CN, zh-TW, en, ja, ko, mn, th, vi, id, kk, "
    "fr, de, es, pt, ru"
)


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


@click.group()
def cli() -> None:
    """多语种翻译 Agent 系统"""


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--target", "-t",
    "targets",
    required=True,
    multiple=True,
    help=LANG_HELP,
)
@click.option("--output", "-o", default=None, help="输出目录（多语言时生效）")
@click.option("--verbose", "-v", is_flag=True, help="显示详细日志")
def translate(
    file: str,
    targets: tuple[str, ...],
    output: str | None,
    verbose: bool,
) -> None:
    """翻译文件。支持多目标语言：--target zh-CN --target vi

    支持格式: .pptx, .srt, .vtt, .ass
    """
    _setup_logging(verbose)

    target_list = list(targets)
    lang_display = ", ".join(target_list)
    console.print(
        f"\n[bold]🌐 多语种翻译 Agent[/bold]\n"
        f"  文件: [cyan]{file}[/cyan]\n"
        f"  目标语言: [cyan]{lang_display}[/cyan]\n"
    )

    orchestrator = Orchestrator()

    if len(target_list) == 1:
        task = asyncio.run(
            orchestrator.run(
                source_file=file,
                target_language=target_list[0],
                output_file=output,
            )
        )
        if task.error_message:
            sys.exit(1)
    else:
        output_dir = output if output else str(Path(file).parent)
        tasks = asyncio.run(
            orchestrator.run_multi(
                source_file=file,
                target_languages=target_list,
                output_dir=output_dir,
                quiet=False,
            )
        )
        failed = [t for t in tasks.language_runs if t.error_message]
        if failed:
            sys.exit(1)


@cli.command("eval-history")
def eval_history() -> None:
    """查看历次质量评测结果和对比。"""
    from rich.table import Table
    from src.quality.regression import RegressionTracker

    tracker = RegressionTracker()
    runs = tracker.load_runs()

    if not runs:
        console.print("[yellow]暂无评测记录。翻译文件后会自动产生评测数据。[/yellow]")
        return

    table = Table(title="质量评测历史", show_lines=True)
    table.add_column("Run ID", style="cyan")
    table.add_column("时间", style="dim")
    table.add_column("文件数", justify="right")
    table.add_column("平均分", justify="right", style="bold")
    table.add_column("备注")

    for run in runs[-10:]:
        table.add_row(
            run.run_id,
            run.timestamp[:19],
            str(len(run.results)),
            f"{run.average_overall:.1f}",
            run.notes or "-",
        )
    console.print(table)

    comparison = tracker.compare_latest()
    if comparison:
        delta = comparison["delta"]
        color = "green" if delta >= 0 else "red"
        arrow = "↑" if delta >= 0 else "↓"
        console.print(
            f"\n  最近变化: [{color}]{arrow} {abs(delta):.1f} 分[/{color}] "
            f"({comparison['previous']['average']:.1f} → {comparison['current']['average']:.1f})"
        )
        if comparison.get("regressed"):
            console.print(
                "[bold red]  ⚠ 检测到质量回归（下降超过 2 分），请检查最近的改动！[/bold red]"
            )


@cli.command()
def languages() -> None:
    """列出支持的语言。"""
    from rich.table import Table

    table = Table(title="支持的语言")
    table.add_column("代码", style="cyan")
    table.add_column("名称", style="green")

    from src.utils.language_detect import LANGUAGE_NAMES
    for code, name in LANGUAGE_NAMES.items():
        table.add_row(code, name)
    console.print(table)


@cli.command()
@click.option("--detail", "-d", default=None, help="查看某个风格的详细配置（如 --detail technical）")
def styles(detail: str | None) -> None:
    """列出支持的翻译风格，或查看某个风格的详细配置。"""
    from rich.panel import Panel
    from rich.table import Table
    from src.utils.style_loader import list_styles, get_style, build_style_prompt, get_style_file_path

    if detail:
        cfg = get_style(detail)
        if not cfg:
            console.print(f"[red]风格 '{detail}' 不存在。[/red]")
            return

        name = cfg.get("name", detail)
        desc = cfg.get("description", "")
        console.print(f"\n[bold cyan]{name}[/bold cyan]  ({detail})")
        console.print(f"  {desc}\n")

        if cfg.get("guidelines"):
            console.print(Panel(cfg["guidelines"].strip(), title="翻译指南", border_style="green"))

        examples = cfg.get("examples", [])
        if examples:
            t = Table(title="翻译示例", show_lines=True)
            t.add_column("原文", style="dim")
            t.add_column("译文", style="green")
            t.add_column("说明", style="yellow")
            for ex in examples:
                t.add_row(ex.get("source", ""), ex.get("target", ""), ex.get("note", ""))
            console.print(t)

        avoid = cfg.get("avoid", [])
        if avoid:
            console.print("\n[bold red]禁忌：[/bold red]")
            for item in avoid:
                console.print(f"  [red]✗[/red] {item}")

        file_path = get_style_file_path(detail)
        console.print(f"\n  配置文件: [dim]{file_path}[/dim]")
        console.print(f"  [dim]直接编辑此文件即可修改风格[/dim]\n")
        return

    all_styles = list_styles()
    if not all_styles:
        console.print("[yellow]未找到风格配置。请检查 config/styles/ 目录。[/yellow]")
        return

    table = Table(title="翻译风格预设")
    table.add_column("Key", style="cyan")
    table.add_column("名称", style="bold")
    table.add_column("描述", style="green")
    table.add_column("配置项", justify="right", style="dim")
    for key, cfg in all_styles.items():
        field_count = sum(1 for k in cfg if k not in ("name", "description") and cfg[k])
        table.add_row(
            key,
            cfg.get("name", key),
            cfg.get("description", ""),
            str(field_count),
        )
    console.print(table)
    console.print("\n  [dim]使用 --detail <key> 查看详细配置[/dim]")
    console.print("  [dim]使用 styles-add 创建新风格[/dim]")
    console.print(f"  [dim]风格文件目录: config/styles/[/dim]\n")


@cli.command("styles-add")
@click.argument("key")
def styles_add(key: str) -> None:
    """交互式创建新的翻译风格。

    KEY 是风格标识符（如 marketing），会用作 --style 参数的值。
    """
    from src.utils.style_loader import get_style, save_style, get_style_file_path

    existing = get_style(key)
    if existing:
        if not click.confirm(f"风格 '{key}' 已存在，是否覆盖？"):
            return

    console.print(f"\n[bold]创建翻译风格: [cyan]{key}[/cyan][/bold]\n")

    name = click.prompt("  显示名称", default=key)
    description = click.prompt("  一句话描述")

    console.print("\n  [dim]输入翻译指南（每行一条规则，空行结束）：[/dim]")
    guideline_lines: list[str] = []
    while True:
        line = click.prompt("  ", default="", show_default=False)
        if not line:
            break
        guideline_lines.append(f"- {line}" if not line.startswith("-") else line)

    examples: list[dict[str, str]] = []
    if click.confirm("\n  是否添加翻译示例？", default=False):
        while True:
            source = click.prompt("    原文 (空行结束)", default="", show_default=False)
            if not source:
                break
            target = click.prompt("    译文")
            note = click.prompt("    说明 (可选)", default="", show_default=False)
            ex: dict[str, str] = {"source": source, "target": target}
            if note:
                ex["note"] = note
            examples.append(ex)

    avoid: list[str] = []
    if click.confirm("\n  是否添加禁忌规则？", default=False):
        console.print("  [dim]每行一条，空行结束：[/dim]")
        while True:
            line = click.prompt("  ", default="", show_default=False)
            if not line:
                break
            avoid.append(line)

    config: dict = {"name": name, "description": description}
    if guideline_lines:
        config["guidelines"] = "\n".join(guideline_lines) + "\n"
    if examples:
        config["examples"] = examples
    if avoid:
        config["avoid"] = avoid

    path = save_style(key, config)
    console.print(f"\n[green]风格 '{key}' 已保存到: {path}[/green]")
    console.print(f"[dim]使用方式: python -m src.main translate <file> --target <lang> --style {key}[/dim]")
    console.print(f"[dim]后续可直接编辑 {path} 来调整风格[/dim]\n")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
