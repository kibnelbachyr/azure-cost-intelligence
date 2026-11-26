"""CLI for independent, advisory-only questions."""
from __future__ import annotations

import argparse
import logging

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from .agent.runner import AgentRunner, OrchestrationError

console = Console()
logging.basicConfig(level=logging.WARNING)


def show(runner, query):
    try:
        with console.status("Analysing…"):
            answer = runner.chat(query)
    except OrchestrationError as exc:
        console.print(str(exc), markup=False, style="red")
        return False
    console.print(Panel(Markdown(answer), title="AI-generated advisory narrative", subtitle="Verify against source evidence; not execution authority"))
    return True


def main():
    parser = argparse.ArgumentParser(description="Azure Cost Intelligence — advisory only")
    parser.add_argument("query", nargs="?")
    parser.add_argument("-i", "--interactive", action="store_true", help="Ask independent questions; restate scope each time")
    parser.add_argument("--allow-live", action="store_true", help="Explicitly permit Azure/Foundry requests and possible charges")
    args = parser.parse_args()
    if not args.allow_live:
        parser.error("Live execution is disabled by default. Review the README before using --allow-live.")
    try:
        with AgentRunner() as runner:
            if args.interactive or not args.query:
                console.print("Each question is independent; restate scope. Type exit to quit.")
                while True:
                    try:
                        question = Prompt.ask("You")
                    except (KeyboardInterrupt, EOFError):
                        break
                    if question.strip().lower() in ("exit", "quit", ""):
                        break
                    show(runner, question)
            elif not show(runner, args.query):
                raise SystemExit(1)
    except (KeyboardInterrupt, EOFError):
        raise SystemExit(130)
    except Exception:
        console.print("Could not initialize or close the live client. Verify authorized configuration.", style="red")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
