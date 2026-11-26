"""Check the exact application package set in a clean virtual environment."""
from importlib.metadata import distributions
from pathlib import Path
import re
import sys


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


def main():
    expected = {}
    for line in (Path(__file__).resolve().parents[1] / "requirements.lock.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9.]+)", line)
        if not match or normalize(match[1]) in expected:
            raise SystemExit("Invalid or duplicate lock entry.")
        expected[normalize(match[1])] = match[2]
    installed = {}
    for dist in distributions():
        name = normalize(dist.metadata["Name"])
        if name in installed:
            raise SystemExit("Duplicate installed distribution.")
        installed[name] = dist.version
    for name in ("pip", "setuptools", "wheel"):
        if name not in expected:
            installed.pop(name, None)
    if expected != installed:
        for name in sorted(expected.keys() | installed.keys()):
            if expected.get(name) != installed.get(name):
                print(f"{name}: expected {expected.get(name)}, installed {installed.get(name)}", file=sys.stderr)
        raise SystemExit("Installed application differs from lock.")
    print(f"Verified {len(expected)} exact application dependency versions.")


if __name__ == "__main__":
    main()
