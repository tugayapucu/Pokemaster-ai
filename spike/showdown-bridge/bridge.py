"""Spike: prove Python can drive the Node/Showdown battle process and parse
its protocol output. Not the real bridge design -- just confirms the
subprocess + line protocol approach is viable before building on it.
"""
import subprocess
from pathlib import Path

SPIKE_DIR = Path(__file__).parent


def run_battle() -> list[str]:
    proc = subprocess.run(
        ["node", str(SPIKE_DIR / "run-battle.js")],
        cwd=SPIKE_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return proc.stdout.splitlines()


def summarize(lines: list[str]) -> None:
    turn = 0
    winner = None
    faints = []
    for line in lines:
        parts = line.split("|")
        if len(parts) < 2:
            continue
        tag = parts[1]
        if tag == "turn":
            turn = int(parts[2])
        elif tag == "win":
            winner = parts[2]
        elif tag == "faint":
            faints.append(parts[2])

    print(f"parsed {len(lines)} protocol lines")
    print(f"battle reached turn {turn}")
    print(f"fainted: {faints}")
    print(f"winner: {winner}")


if __name__ == "__main__":
    lines = run_battle()
    summarize(lines)
