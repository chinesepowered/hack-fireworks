"""Coordinator-facing explanations, written by Nemotron 3 Ultra (Fireworks serverless).

The fine-tuned screener outputs only a label (that is what we score). For the demo and the
product flow, Nemotron 3 Ultra turns (patient, trial, label) into one sentence that cites the
deciding criterion, so a coordinator can verify the call quickly. Explanations are not scored.
"""

from __future__ import annotations

import json

from capymatch.run_chat import call_chat

EXPLAIN_SYSTEM = """You help clinical research coordinators review automated trial pre-screening.
Given a patient description, a trial record, and the screening label, write ONE short sentence
(max 30 words) explaining the label by citing the specific criterion or condition that decides it.
Plain language, no preamble, no hedging words like "likely"."""


def explain(rec: dict, label: str) -> str:
    msgs = [
        {"role": "system", "content": EXPLAIN_SYSTEM},
        {"role": "user", "content": f"Label: {label}\n\nPatient:\n{rec['patient']}\n\n{rec['trial']}"},
    ]
    res = call_chat("nemotron-3-ultra", msgs, max_tokens=4000)
    text = (res["payload"]["choices"][0]["message"].get("content") or "").strip()
    return text.split("\n")[0].strip()


if __name__ == "__main__":
    rec = json.loads(open("data/dev.jsonl").readline())
    print(rec["label"], "->", explain(rec, rec["label"]))
