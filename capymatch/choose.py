"""Pick the fine-tuned checkpoint on dev, then score only that checkpoint on test.

Usage: python -m capymatch.choose [--tags capy-e1 capy-e2]

Writes results/checkpoint_choice.json and results/preds/capymatch__test.jsonl.
The test set is touched once, by the dev-chosen checkpoint (ties go to the later epoch).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def dev_accuracy(system: str) -> float:
    rows = [json.loads(line) for line in open(f"results/preds/{system}__dev.jsonl")]
    return sum(r["pred"] == r["gold"] for r in rows) / len(rows)


def run(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "capymatch.run_sampler", *args], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", default=["capy-e1", "capy-e2"])
    args = ap.parse_args()
    acc = {}
    for tag in args.tags:
        epoch = tag.split("-")[-1]
        run("--system", f"capymatch-{epoch}", "--checkpoint", tag, "--split", "dev")
        acc[epoch] = dev_accuracy(f"capymatch-{epoch}")
    best = max(reversed(list(acc)), key=lambda e: acc[e])  # reversed: ties prefer the later epoch
    Path("results/checkpoint_choice.json").write_text(json.dumps({"dev_accuracy": acc, "chosen": best}, indent=2))
    print(f"dev accuracy {acc} -> chosen capy-{best}")
    run("--system", "capymatch", "--checkpoint", f"capy-{best}", "--split", "test")


if __name__ == "__main__":
    main()
