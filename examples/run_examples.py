"""Examples explicitly opt into live Azure/Foundry requests."""
import argparse

from src.agent.runner import AgentRunner, OrchestrationError

QUERIES = [
    "Give me a breakdown of the last 30 days of spend by service.",
    "Review cost opportunities with evidence, risk and unknown savings.",
    "List unattached resources for owner review; do not recommend execution.",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live", action="store_true")
    args = parser.parse_args()
    if not args.allow_live:
        parser.error("Live calls are disabled by default. Review the README first.")
    with AgentRunner() as runner:
        for question in QUERIES:
            print(question)
            try:
                print(runner.chat(question))
            except OrchestrationError as exc:
                print(exc)
                raise SystemExit(1) from None


if __name__ == "__main__":
    main()
