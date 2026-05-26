"""
Runnable examples demonstrating the three core user queries.

Run:
    python examples/run_examples.py

Requires a valid .env file in the project root.
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule

from src.agent.runner import AgentRunner

console = Console()

QUERIES = [
    {
        "label": "Query 1 – Monthly overspend overview",
        "text": "Where am I overspending this month? Give me a breakdown by service.",
    },
    {
        "label": "Query 2 – Top optimisation opportunities",
        "text": (
            "Give me the top 5 cost optimisation opportunities in my subscription, "
            "including estimated monthly savings and effort for each."
        ),
    },
    {
        "label": "Query 3 – Idle and underutilised resources",
        "text": (
            "Show me idle or underutilised resources I should clean up. "
            "Focus on quick wins with low risk."
        ),
    },
]


def main():
    console.print(
        Panel(
            "[bold]Azure Cost Optimization Agent — Example Queries[/bold]",
            border_style="blue",
        )
    )

    with console.status("[bold green]Initialising agent…"):
        runner = AgentRunner()

    thread = runner.create_thread()
    console.print(f"[dim]Thread ID: {thread.id}[/dim]\n")

    for i, q in enumerate(QUERIES, start=1):
        console.print(Rule(f"[bold cyan]{q['label']}[/bold cyan]"))
        console.print(f"[bold blue]User:[/bold blue] {q['text']}\n")

        with console.status("[bold cyan]Agent thinking…"):
            response = runner.chat(q["text"], thread_id=thread.id)

        console.print(
            Panel(
                Markdown(response),
                title="[green]Azure Cost Advisor[/green]",
                border_style="green",
                padding=(1, 2),
            )
        )
        console.print()


if __name__ == "__main__":
    main()
