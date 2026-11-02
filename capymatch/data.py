"""Build CapyMatch train/dev/test pairs from TREC Clinical Trials 2021 + 2022.

Inputs (downloaded by `make data`, see README):
  data/raw/topics2021.xml, topics2022.xml   synthetic patient descriptions
  data/raw/qrels2021.txt,  qrels2022.txt    expert judgments: 2 eligible, 1 excluded, 0 not relevant
  data/raw/ClinicalTrials.part{1..5}.zip    ClinicalTrials.gov snapshot (2021-04-27) used by both tracks

Split design (no patient appears in more than one split):
  train: TREC 2021 topics 1-70     dev: TREC 2021 topics 71-75     test: TREC 2022 topics 1-50
Each split is sampled label-balanced and spread round-robin across patients.
"""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

from capymatch import QREL_TO_LABEL

RAW = Path("data/raw")
OUT = Path("data")
MAX_CRITERIA_CHARS = 7000
MAX_SUMMARY_CHARS = 700


def load_topics(path: Path) -> dict[str, str]:
    root = ET.parse(path).getroot()
    return {t.get("number"): re.sub(r"\s+", " ", (t.text or "")).strip() for t in root.iter("topic")}


def load_qrels(path: Path) -> list[tuple[str, str, str]]:
    rows = []
    for line in path.read_text().splitlines():
        topic, _, nct, rel = line.split()
        rows.append((topic, nct, QREL_TO_LABEL[rel]))
    return rows


def _text(node: ET.Element | None, path: str) -> str:
    if node is None:
        return ""
    el = node.find(path)
    if el is None:
        return ""
    return "".join(el.itertext())


def _clean(s: str) -> str:
    s = html.unescape(s).replace("\r", "")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in s.split("\n")]
    out, blank = [], False
    for ln in lines:
        if not ln:
            if not blank and out:
                out.append("")
            blank = True
            continue
        out.append(ln)
        blank = False
    return "\n".join(out).strip()


def parse_trial(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    elig = root.find("eligibility")
    return {
        "nct_id": _text(root, "id_info/nct_id").strip(),
        "title": _clean(_text(root, "brief_title")),
        "official_title": _clean(_text(root, "official_title")),
        "conditions": [_clean("".join(c.itertext())) for c in root.findall("condition")],
        "interventions": [_clean(_text(i, "intervention_name")) for i in root.findall("intervention")],
        "phase": _clean(_text(root, "phase")),
        "summary": _clean(_text(root, "brief_summary/textblock")),
        "criteria": _clean(_text(elig, "criteria/textblock")),
        "gender": _clean(_text(elig, "gender")),
        "min_age": _clean(_text(elig, "minimum_age")),
        "max_age": _clean(_text(elig, "maximum_age")),
        "healthy_volunteers": _clean(_text(elig, "healthy_volunteers")),
    }


def load_trials(needed: set[str]) -> dict[str, dict]:
    trials: dict[str, dict] = {}
    for i in range(1, 6):
        with zipfile.ZipFile(RAW / f"ClinicalTrials.part{i}.zip") as z:
            for name in z.namelist():
                if not name.endswith(".xml"):
                    continue
                nct = name.rsplit("/", 1)[-1][:-4]
                if nct in needed:
                    trials[nct] = parse_trial(z.read(name))
    return trials


def format_trial(t: dict) -> str:
    """Render a trial for the prompt. Criteria are kept nearly whole; summary is trimmed."""
    criteria = t["criteria"]
    if len(criteria) > MAX_CRITERIA_CHARS:
        criteria = criteria[:MAX_CRITERIA_CHARS].rsplit("\n", 1)[0] + "\n[... criteria truncated ...]"
    summary = t["summary"]
    if len(summary) > MAX_SUMMARY_CHARS:
        summary = summary[:MAX_SUMMARY_CHARS].rsplit(" ", 1)[0] + " ..."
    ages = f"{t['min_age'] or 'N/A'} to {t['max_age'] or 'N/A'}"
    parts = [
        f"Trial: {t['nct_id']}",
        f"Title: {t['title']}",
        f"Conditions: {'; '.join(c for c in t['conditions'] if c) or 'N/A'}",
    ]
    if any(t["interventions"]):
        parts.append(f"Interventions: {'; '.join(i for i in t['interventions'] if i)}")
    if t["phase"]:
        parts.append(f"Phase: {t['phase']}")
    parts.append(f"Summary: {summary or 'N/A'}")
    parts.append(
        f"Eligibility: sex {t['gender'] or 'All'}; age {ages}; "
        f"healthy volunteers {t['healthy_volunteers'] or 'N/A'}"
    )
    parts.append(f"Criteria:\n{criteria or 'N/A'}")
    return "\n".join(parts)


def balanced_sample(rows, topics_ok, per_label: dict[str, int], seed: int):
    """Pick per_label[label] pairs per label, round-robin across patients so each patient is represented."""
    rng = random.Random(seed)
    by_label_topic: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for topic, nct, label in rows:
        if topic in topics_ok:
            by_label_topic[label][topic].append((topic, nct, label))
    picked = []
    for label, n in per_label.items():
        pools = by_label_topic[label]
        topic_ids = sorted(pools, key=int)
        for tid in topic_ids:
            rng.shuffle(pools[tid])
        take, idx = [], {tid: 0 for tid in topic_ids}
        while len(take) < n and any(idx[t] < len(pools[t]) for t in topic_ids):
            for tid in topic_ids:
                if len(take) >= n:
                    break
                if idx[tid] < len(pools[tid]):
                    take.append(pools[tid][idx[tid]])
                    idx[tid] += 1
        picked.extend(take)
    rng.shuffle(picked)
    return picked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-per-label", type=int, default=1000)
    ap.add_argument("--dev-per-label", type=int, default=40)
    ap.add_argument("--test-per-label", type=int, default=300)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--train-only", action="store_true", help="only (re)build the training split")
    ap.add_argument("--train-out", default="train", help="file stem for the training split (e.g. train_9k)")
    args = ap.parse_args()

    topics21, topics22 = load_topics(RAW / "topics2021.xml"), load_topics(RAW / "topics2022.xml")
    q21, q22 = load_qrels(RAW / "qrels2021.txt"), load_qrels(RAW / "qrels2022.txt")

    train_topics = {str(i) for i in range(1, 71)}
    dev_topics = {str(i) for i in range(71, 76)}
    test_topics = set(topics22)

    splits = {
        "train": (balanced_sample(q21, train_topics, dict.fromkeys(["eligible", "excluded", "not_relevant"], args.train_per_label), args.seed), topics21, "2021"),
        "dev": (balanced_sample(q21, dev_topics, dict.fromkeys(["eligible", "excluded", "not_relevant"], args.dev_per_label), args.seed), topics21, "2021"),
        "test": (balanced_sample(q22, test_topics, dict.fromkeys(["eligible", "excluded", "not_relevant"], args.test_per_label), args.seed), topics22, "2022"),
    }
    if args.train_only:
        splits = {args.train_out: splits["train"]}
    elif args.train_out != "train":
        splits[args.train_out] = splits.pop("train")
    needed = {nct for rows, _, _ in splits.values() for _, nct, _ in rows}
    print(f"loading {len(needed)} trials from the 2021-04-27 ClinicalTrials.gov snapshot ...")
    trials = load_trials(needed)
    missing = needed - set(trials)
    print(f"parsed {len(trials)} trials; missing {len(missing)}")

    OUT.mkdir(exist_ok=True)
    for split, (rows, topics, year) in splits.items():
        n_written, counts = 0, defaultdict(int)
        with open(OUT / f"{split}.jsonl", "w") as f:
            for topic, nct, label in rows:
                if nct not in trials:
                    continue
                rec = {
                    "id": f"{year}-{topic}-{nct}",
                    "year": year,
                    "topic": topic,
                    "nct_id": nct,
                    "patient": topics[topic],
                    "trial": format_trial(trials[nct]),
                    "trial_title": trials[nct]["title"],
                    "label": label,
                }
                f.write(json.dumps(rec) + "\n")
                n_written += 1
                counts[label] += 1
        print(f"{split}: {n_written} pairs {dict(counts)} from {len({r[0] for r in rows})} patients")


if __name__ == "__main__":
    main()
