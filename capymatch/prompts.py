"""Shared prompt + label parsing. Every system (frontier, open zero-shot, fine-tuned) sees the same text."""

from __future__ import annotations

import json
import re

from capymatch import LABELS

SYSTEM_PROMPT = """You are a clinical research coordinator pre-screening patients for clinical trials.
Read the patient description and the trial record, then assign exactly one label:
- eligible: the trial studies this patient's condition and the patient would be eligible to enroll (meets the inclusion criteria and no exclusion criterion applies).
- excluded: the trial targets the patient's condition, but the eligibility criteria make the patient ineligible.
- not_relevant: the trial is not relevant to this patient (for example it studies a different condition or population).
Judge from the information given; do not reject a patient only because the description is silent on a criterion.
Respond with only a JSON object: {"label": "eligible" | "excluded" | "not_relevant"}"""


def user_prompt(rec: dict) -> str:
    return f"Patient:\n{rec['patient']}\n\n{rec['trial']}"


def messages(rec: dict) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt(rec)},
    ]


def target(rec: dict) -> str:
    """Training target for the fine-tuned model (label only, no rationale)."""
    return json.dumps({"label": rec["label"]})


_LABEL_RE = re.compile(r"\b(not[ _-]?relevant|eligible|excluded)\b", re.I)


def parse_label(text: str | None) -> str | None:
    """Return a label from model output, or None if it cannot be parsed."""
    if not text:
        return None
    text = text.strip()
    # Strip any leaked reasoning block; the answer follows it.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    for m in re.finditer(r"\{[^{}]*\}", text):
        try:
            lab = str(json.loads(m.group(0)).get("label", "")).strip().lower().replace(" ", "_").replace("-", "_")
        except (json.JSONDecodeError, AttributeError):
            continue
        if lab in LABELS:
            return lab
    hits = _LABEL_RE.findall(text)
    if hits:
        lab = hits[-1].lower().replace(" ", "_").replace("-", "_")
        lab = "not_relevant" if lab.startswith("not") else lab
        return lab if lab in LABELS else None
    return None
