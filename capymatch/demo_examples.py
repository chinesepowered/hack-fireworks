"""Build demo/examples.json from real test-set predictions (one illustrative 2022 patient).

Usage: python -m capymatch.demo_examples [--topic 12]

Without --topic, picks a patient whose sampled trials cover all three labels and where systems
disagree, so the demo shows real differences. The aggregate results are reported separately;
this file is illustrative only. Explanations are written by Nemotron 3 Ultra for the gold label.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from capymatch.evaluate import SYSTEMS, load_preds
from capymatch.explain import explain

SHOW = ["gpt-6.1-sol", "gpt-6-luna", "nemotron-3-ultra", "capymatch"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--topic", default=None)
    ap.add_argument("--max-trials", type=int, default=6)
    args = ap.parse_args()

    test = [json.loads(line) for line in open("data/test.jsonl")]
    preds = {k: load_preds(k, "test") for k in SHOW}
    preds = {k: v for k, v in preds.items() if len(v) == len(test)}
    by_topic = defaultdict(list)
    for r in test:
        by_topic[r["topic"]].append(r)

    def score(topic: str) -> tuple:
        rows = by_topic[topic]
        labels = {r["label"] for r in rows}
        ours = sum(preds["capymatch"][r["id"]]["pred"] == r["label"] for r in rows) / len(rows)
        others = [sum(preds[k][r["id"]]["pred"] == r["label"] for r in rows) / len(rows) for k in preds if k != "capymatch"]
        return (len(labels) == 3, ours - (max(others) if others else 0), ours, len(rows))

    topic = args.topic or max(by_topic, key=score)
    rows = by_topic[topic]
    # Keep a mix of labels, correct ones first.
    rows.sort(key=lambda r: (preds["capymatch"][r["id"]]["pred"] != r["label"], r["label"]))
    picked, seen = [], defaultdict(int)
    for r in rows:
        if seen[r["label"]] < 2 and len(picked) < args.max_trials:
            picked.append(r)
            seen[r["label"]] += 1
    trials = []
    for r in picked:
        trials.append({
            "nct_id": r["nct_id"],
            "title": r["trial_title"],
            "gold": r["label"],
            "preds": {SYSTEMS[k][0]: preds[k][r["id"]]["pred"] for k in preds},
            "why": explain(r, r["label"]),
        })
        print(r["nct_id"], r["label"], {k: preds[k][r["id"]]["pred"] for k in preds})
    out = {"placeholder": False,
           "systems": [SYSTEMS[k][0] for k in SHOW if k in preds],
           "patient": {"id": f"2022-{topic}", "text": rows[0]["patient"]}, "trials": trials,
           "note": "Illustrative patient from the held-out TREC 2022 test set; aggregate metrics are in results/."}
    Path("demo").mkdir(exist_ok=True)
    Path("demo/examples.json").write_text(json.dumps(out, indent=2))
    print(f"wrote demo/examples.json for patient 2022-{topic} ({len(trials)} trials)")


if __name__ == "__main__":
    main()
