"""
Entry point for the Azure Cost Optimization Agent CLI.

Usage:
    # Single query
    python -m src.main "Where am I overspending this month?"

    # Interactive chat session
    python -m src.main --interactive
"""
from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

load_dotenv()  # must be before importing settings

from .agent.runner import AgentRunner  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Quiet noisy SDK loggers
logging.getLogger("azure").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

console = Console()

WELCOME = """
# Azure Cost Optimization Agent

Type your question in plain English.  Examples:
- "Where am I overspending this month?"
- "Top 5 cost optimisation opportunities in my production subscription"
- "Show me idle or underutilised resources in West Europe"
- "What are the quick wins to reduce my Azure bill?"

Type **exit** or **quit** to end the session.
"""


def run_single_query(query: str) -> None:
    with console.status("[bold green]Initialising agent…"):
        runner = AgentRunner()
    thread = runner.create_thread()

    with console.status("[bold cyan]Thinking…"):
        response = runner.chat(query, thread_id=thread.id)

    console.print(Panel(Markdown(response), title="Azure Cost Advisor", border_style="green"))


def run_interactive() -> None:
    console.print(Markdown(WELCOME))

    with console.status("[bold green]Initialising agent…"):
        runner = AgentRunner()
    thread = runner.create_thread()
    console.print("[dim]Agent ready.  Thread ID:[/dim]", thread.id)

    while True:
        try:
            user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if user_input.lower().strip() in ("exit", "quit", ""):
            console.print("[dim]Goodbye![/dim]")
            break

        with console.status("[bold cyan]Thinking…"):
            response = runner.chat(user_input, thread_id=thread.id)

        console.print(
            Panel(
                Markdown(response),
                title="[green]Azure Cost Advisor[/green]",
                border_style="green",
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Azure Cost Optimization AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Single natural-language question to ask the agent.",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Start an interactive multi-turn chat session.",
    )

    args = parser.parse_args()

    if args.interactive or not args.query:
        run_interactive()
    else:
        run_single_query(args.query)


if __name__ == "__main__":
    main()
