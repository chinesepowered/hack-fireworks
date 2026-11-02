"""Pick the fine-tuned checkpoint on dev, then score only that checkpoint on test.

Usage: python -m capymatch.choose --tags capy-e1 capy-e2 c9k-e1

Each tag is a key in results/checkpoints.json. Dev predictions go to results/preds/<tag>__dev.jsonl,
the choice to results/checkpoint_choice.json, and the chosen checkpoint's test predictions to
results/preds/capymatch__test.jsonl. The test set is touched once, by the dev-chosen checkpoint
(ties go to the later tag in the list).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def dev_accuracy(tag: str) -> float:
    rows = [json.loads(line) for line in open(f"results/preds/{tag}__dev.jsonl")]
    return sum(r["pred"] == r["gold"] for r in rows) / len(rows)


def run(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "capymatch.run_sampler", *args], check=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", nargs="+", default=["capy-e1", "capy-e2", "c9k-e1"])
    ap.add_argument("--skip-test", action="store_true")
    args = ap.parse_args()
    ckpts = json.loads(Path("results/checkpoints.json").read_text())
    acc = {}
    for tag in args.tags:
        run("--system", tag, "--checkpoint", tag, "--split", "dev")
        acc[tag] = dev_accuracy(tag)
    best = max(reversed(args.tags), key=lambda t: acc[t])
    choice = {
        "candidates": {t: {"dev_accuracy": acc[t], "train_rows": ckpts[t].get("train_rows"), "epoch": ckpts[t].get("epoch")}
                       for t in args.tags},
        "chosen": best,
    }
    Path("results/checkpoint_choice.json").write_text(json.dumps(choice, indent=2))
    print(f"dev accuracy {acc} -> chosen {best}")
    if not args.skip_test:
        run("--system", "capymatch", "--checkpoint", best, "--split", "test")


if __name__ == "__main__":
    main()
