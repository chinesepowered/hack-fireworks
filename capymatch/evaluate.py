"""Score every system on the same frozen test set, with uncertainty.

Usage:  python -m capymatch.evaluate [--split test] [--ours capymatch]

Outputs:
  results/metrics.json   full metrics per system + paired comparisons
  results/summary.json   compact numbers consumed by the README table and the demo video
  results/results.md     markdown results table
  results/chart.png      accuracy (95% CI) and cost per 1,000 screenings

Statistics:
  * 95% CIs from a patient-clustered bootstrap (resample the 50 test patients, 2,000 draws),
    because pairs from the same patient are correlated.
  * Paired differences (ours - baseline) use the same bootstrap draws.
  * Exact McNemar test on per-pair correctness (ours vs each baseline).
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from capymatch import LABELS
from capymatch.config import MODELS

PRED_DIR = Path("results/preds")
OUT = Path("results")

SYSTEMS = {
    # key: (display name, kind, price key in config.MODELS)
    "gpt-6.1-sol": ("GPT-6.1 Sol", "closed frontier (OpenAI)", "gpt-6.1-sol"),
    "gpt-6-luna": ("GPT-6 Luna", "closed, low-cost tier (OpenAI)", "gpt-6-luna"),
    "nemotron-3-ultra": ("Nemotron 3 Ultra, zero-shot", "open, Fireworks serverless", "nemotron-3-ultra"),
    "nemotron-3.5-lightning": ("Nemotron 3.5 Lightning, zero-shot", "open, Fireworks serverless", "nemotron-3.5-lightning"),
    "super-vl-base": ("Nemotron 3.5 Super VL, zero-shot", "open, Fireworks serverless sampling", "nemotron-3.5-super-vl"),
    "capymatch": ("CapyMatch (Super VL + LoRA, ours)", "open + fine-tuned on Fireworks", "nemotron-3.5-super-vl"),
}


def load_preds(system: str, split: str) -> dict[str, dict]:
    path = PRED_DIR / f"{system}__{split}.jsonl"
    if not path.exists():
        return {}
    rows = {}
    for line in open(path):
        r = json.loads(line)
        rows[r["id"]] = r
    return rows


def macro_f1(gold: np.ndarray, pred: np.ndarray) -> float:
    f1s = []
    for k in range(len(LABELS)):
        tp = np.sum((pred == k) & (gold == k))
        fp = np.sum((pred == k) & (gold != k))
        fn = np.sum((pred != k) & (gold == k))
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        f1s.append(2 * p * r / (p + r) if p + r else 0.0)
    return float(np.mean(f1s))


def per_class(gold: np.ndarray, pred: np.ndarray) -> dict:
    out = {}
    for k, name in enumerate(LABELS):
        tp = int(np.sum((pred == k) & (gold == k)))
        fp = int(np.sum((pred == k) & (gold != k)))
        fn = int(np.sum((pred != k) & (gold == k)))
        p = tp / (tp + fp) if tp + fp else 0.0
        r = tp / (tp + fn) if tp + fn else 0.0
        out[name] = {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0, "support": tp + fn}
    return out


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value (binomial on discordant pairs)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2**n
    return min(1.0, 2 * tail)


def cost_usd(rows: list[dict], price_key: str) -> float:
    price = MODELS[price_key]["price"]
    total = 0.0
    for r in rows:
        u = r.get("usage") or {}
        prompt = u.get("prompt_tokens", 0) or 0
        cached = ((u.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
        out = u.get("completion_tokens", 0) or 0
        total += ((prompt - cached) * price["in"] + cached * price["cached"] + out * price["out"]) / 1e6
    return total


def cascade_analysis(ours, present, ids, correct, metrics, draws, ci) -> dict | None:
    """Selective screening: CapyMatch auto-screens confident pairs, escalates the rest to the best closed model.

    The confidence threshold is fixed on the dev split (keep 80% of dev pairs), then applied to test.
    """
    if ours not in present or any(present[ours][i].get("confidence") is None for i in ids):
        return None
    closed = [k for k in present if k != ours and MODELS[SYSTEMS[k][2]]["provider"] == "openai"]
    if not closed:
        return None
    esc = max(closed, key=lambda k: metrics[k]["accuracy"])
    conf = np.array([present[ours][i]["confidence"] for i in ids])

    sweep = []
    for cov in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5):
        t = np.quantile(conf, 1 - cov) if cov < 1 else -1.0
        keep = conf >= t if cov < 1 else np.ones_like(conf, dtype=bool)
        combined = np.where(keep, correct[ours], correct[esc])
        sweep.append({
            "coverage": float(keep.mean()),
            "auto_accuracy": float(correct[ours][keep].mean()) if keep.any() else None,
            "cascade_accuracy": float(combined.mean()),
            "cost_per_1k_usd": metrics[ours]["cost_per_1k_usd"] + (1 - keep.mean()) * metrics[esc]["cost_per_1k_usd"],
        })

    out = {"escalate_to": esc, "escalate_name": metrics[esc]["name"], "sweep_on_test": sweep}
    choice_path = Path("results/checkpoint_choice.json")
    if choice_path.exists():
        chosen = json.loads(choice_path.read_text())["chosen"]
        dev = [json.loads(line) for line in open(PRED_DIR / f"capymatch-{chosen}__dev.jsonl")]
        dev_conf = np.array([r.get("confidence") or 0.0 for r in dev])
        t = float(np.quantile(dev_conf, 0.2))  # keep the most confident 80% of dev pairs
        keep = conf >= t
        combined = np.where(keep, correct[ours], correct[esc])
        b = [combined[d].mean() for d in draws]
        delta = [combined[d].mean() - correct[esc][d].mean() for d in draws]
        bb = int(np.sum((combined == 1) & (correct[esc] == 0)))
        cc = int(np.sum((combined == 0) & (correct[esc] == 1)))
        cost = metrics[ours]["cost_per_1k_usd"] + (1 - keep.mean()) * metrics[esc]["cost_per_1k_usd"]
        out["dev_threshold"] = {
            "threshold": t,
            "test_coverage": float(keep.mean()),
            "auto_accuracy": float(correct[ours][keep].mean()),
            "escalated_accuracy_esc": float(correct[esc][~keep].mean()) if (~keep).any() else None,
            "escalated_accuracy_ours": float(correct[ours][~keep].mean()) if (~keep).any() else None,
            "cascade_accuracy": float(combined.mean()),
            "cascade_accuracy_ci": ci(b),
            "delta_vs_escalation_model": float(combined.mean() - correct[esc].mean()),
            "delta_ci": ci(delta),
            "mcnemar_p_vs_escalation_model": mcnemar_exact(bb, cc),
            "cost_per_1k_usd": cost,
            "cost_ratio_vs_escalation_model": metrics[esc]["cost_per_1k_usd"] / cost,
        }
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--ours", default="capymatch")
    ap.add_argument("--n-boot", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    test = [json.loads(line) for line in open(f"data/{args.split}.jsonl")]
    ids = [r["id"] for r in test]
    topics = np.array([r["topic"] for r in test])
    lab_idx = {name: i for i, name in enumerate(LABELS)}
    gold = np.array([lab_idx[r["label"]] for r in test])

    present = {}
    for key in SYSTEMS:
        p = load_preds(key, args.split)
        if len(p) == len(ids):
            present[key] = p
        elif p:
            print(f"skipping {key}: {len(p)}/{len(ids)} predictions")
    if not present:
        raise SystemExit("no complete prediction files")

    preds = {k: np.array([lab_idx.get(present[k][i]["pred"], -1) for i in ids]) for k in present}
    correct = {k: (preds[k] == gold).astype(float) for k in present}

    # Patient-clustered bootstrap: one set of draws shared by all systems (paired).
    rng = np.random.default_rng(args.seed)
    uniq = np.unique(topics)
    idx_by_topic = {t: np.where(topics == t)[0] for t in uniq}
    draws = []
    for _ in range(args.n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        draws.append(np.concatenate([idx_by_topic[t] for t in pick]))

    def ci(values):
        lo, hi = np.percentile(values, [2.5, 97.5])
        return [float(lo), float(hi)]

    metrics = {}
    for k in present:
        rows = [present[k][i] for i in ids]
        acc_b = [correct[k][d].mean() for d in draws]
        f1_b = [macro_f1(gold[d], preds[k][d]) for d in draws]
        lat = np.array([r["latency_s"] for r in rows])
        name, kind, price_key = SYSTEMS[k]
        cost = cost_usd(rows, price_key)
        pc = per_class(gold, preds[k])
        metrics[k] = {
            "name": name,
            "kind": kind,
            "n": len(rows),
            "accuracy": float(correct[k].mean()),
            "accuracy_ci": ci(acc_b),
            "macro_f1": macro_f1(gold, preds[k]),
            "macro_f1_ci": ci(f1_b),
            "per_class": pc,
            # rows = gold label, columns = predicted label (+ unparsed), in LABELS order
            "confusion": [[int(np.sum((gold == g) & (preds[k] == p))) for p in list(range(len(LABELS))) + [-1]]
                          for g in range(len(LABELS))],
            "eligible_precision": pc["eligible"]["precision"],
            "eligible_recall": pc["eligible"]["recall"],
            "unparsed": int(np.sum(preds[k] == -1)),
            "cost_usd_total": cost,
            "cost_per_1k_usd": cost / len(rows) * 1000,
            "latency_p50_s": float(np.percentile(lat, 50)),
            "latency_p95_s": float(np.percentile(lat, 95)),
            "mean_prompt_tokens": float(np.mean([(r.get("usage") or {}).get("prompt_tokens", 0) for r in rows])),
            "mean_output_tokens": float(np.mean([(r.get("usage") or {}).get("completion_tokens", 0) for r in rows])),
        }

    comparisons = {}
    if args.ours in present:
        for k in present:
            if k == args.ours:
                continue
            b = int(np.sum((correct[args.ours] == 1) & (correct[k] == 0)))
            c = int(np.sum((correct[args.ours] == 0) & (correct[k] == 1)))
            d_acc = [correct[args.ours][d].mean() - correct[k][d].mean() for d in draws]
            d_f1 = [macro_f1(gold[d], preds[args.ours][d]) - macro_f1(gold[d], preds[k][d]) for d in draws]
            comparisons[k] = {
                "acc_delta": metrics[args.ours]["accuracy"] - metrics[k]["accuracy"],
                "acc_delta_ci": ci(d_acc),
                "macro_f1_delta": metrics[args.ours]["macro_f1"] - metrics[k]["macro_f1"],
                "macro_f1_delta_ci": ci(d_f1),
                "ours_right_base_wrong": b,
                "ours_wrong_base_right": c,
                "mcnemar_p": mcnemar_exact(b, c),
                "cost_ratio": (metrics[k]["cost_per_1k_usd"] / metrics[args.ours]["cost_per_1k_usd"])
                if metrics[args.ours]["cost_per_1k_usd"] > 0 else None,
            }

    cascade = cascade_analysis(args.ours, present, ids, correct, metrics, draws, ci)

    OUT.mkdir(exist_ok=True)
    (OUT / "metrics.json").write_text(json.dumps({"split": args.split, "n_pairs": len(ids),
                                                    "n_patients": int(len(uniq)), "systems": metrics,
                                                    "ours": args.ours, "comparisons": comparisons,
                                                    "cascade": cascade}, indent=2))

    # Headline: compare against the strongest closed (OpenAI) baseline that was run.
    closed = [k for k in comparisons if MODELS[SYSTEMS[k][2]]["provider"] == "openai"]
    vs = max(closed, key=lambda k: metrics[k]["accuracy"]) if closed else (max(comparisons, key=lambda k: metrics[k]["accuracy"]) if comparisons else None)
    order = sorted(metrics, key=lambda k: (k != args.ours, -metrics[k]["accuracy"]))
    summary = {
        "placeholder": False,
        "test_pairs": len(ids),
        "test_patients": int(len(uniq)),
        "train_pairs": sum(1 for _ in open("data/train.jsonl")),
        "systems": [
            {"key": k, **{f: metrics[k][f] for f in ("name", "kind", "accuracy", "accuracy_ci", "macro_f1", "macro_f1_ci",
                                                  "eligible_precision", "eligible_recall", "cost_per_1k_usd",
                                                  "latency_p50_s", "unparsed")}}
            for k in order
        ],
        "headline": ({"ours": args.ours, "vs": vs, **comparisons[vs]} if vs else None),
        "comparisons": comparisons,
        "notes": [
            "Test set: 900 label-balanced pairs from 50 TREC 2022 patients never seen in training (train: 70 TREC 2021 patients).",
            "95% CIs: patient-clustered bootstrap, 2,000 draws. p-values: exact McNemar on per-pair correctness.",
            "Cost: list price x measured tokens (reasoning tokens included). Super VL priced at Fireworks serverless-training sampling rates.",
            "Latency is client-side wall time; the Super VL rows use the training sampler, not a production deployment.",
        ],
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))

    # Markdown table
    lines = ["| System | Type | Accuracy (95% CI) | Macro-F1 (95% CI) | Eligible P / R | $ per 1k screens | p50 latency |",
             "|---|---|---|---|---|---|---|"]
    for k in order:
        m = metrics[k]
        bold = "**" if k == args.ours else ""
        lines.append(
            f"| {bold}{m['name']}{bold} | {m['kind']} | {bold}{m['accuracy']*100:.1f}%{bold} ({m['accuracy_ci'][0]*100:.1f}–{m['accuracy_ci'][1]*100:.1f}) "
            f"| {m['macro_f1']*100:.1f} ({m['macro_f1_ci'][0]*100:.1f}–{m['macro_f1_ci'][1]*100:.1f}) "
            f"| {m['eligible_precision']*100:.0f}% / {m['eligible_recall']*100:.0f}% | ${m['cost_per_1k_usd']:.2f} | {m['latency_p50_s']:.1f}s |"
        )
    if comparisons:
        lines += ["", "| Ours vs | Accuracy Δ (95% CI) | Macro-F1 Δ (95% CI) | McNemar p | Cost ratio (baseline ÷ ours) |", "|---|---|---|---|---|"]
        for k, c in comparisons.items():
            ratio = f"{c['cost_ratio']:.1f}×" if c["cost_ratio"] else "n/a"
            lines.append(
                f"| {metrics[k]['name']} | {c['acc_delta']*100:+.1f} pts ({c['acc_delta_ci'][0]*100:+.1f} to {c['acc_delta_ci'][1]*100:+.1f}) "
                f"| {c['macro_f1_delta']*100:+.1f} ({c['macro_f1_delta_ci'][0]*100:+.1f} to {c['macro_f1_delta_ci'][1]*100:+.1f}) "
                f"| {c['mcnemar_p']:.2g} | {ratio} |"
            )
    if cascade:
        summary["cascade"] = cascade
        lines += ["", f"**Selective screening** (CapyMatch auto-screens confident pairs; the rest go to {cascade['escalate_name']}):", "",
                  "| Auto-screened share | CapyMatch accuracy on auto-screened | Overall accuracy with escalation | $ per 1k screens |", "|---|---|---|---|"]
        for s in cascade["sweep_on_test"]:
            lines.append(f"| {s['coverage']*100:.0f}% | {s['auto_accuracy']*100:.1f}% | {s['cascade_accuracy']*100:.1f}% | ${s['cost_per_1k_usd']:.2f} |")
        if "dev_threshold" in cascade:
            d = cascade["dev_threshold"]
            lines += ["", f"With the confidence threshold fixed on dev (keep 80% of dev pairs): {d['test_coverage']*100:.0f}% of test pairs auto-screened at "
                      f"{d['auto_accuracy']*100:.1f}% accuracy; overall {d['cascade_accuracy']*100:.1f}% "
                      f"(95% CI {d['cascade_accuracy_ci'][0]*100:.1f}–{d['cascade_accuracy_ci'][1]*100:.1f}), "
                      f"{d['delta_vs_escalation_model']*100:+.1f} pts vs {cascade['escalate_name']} alone "
                      f"(95% CI {d['delta_ci'][0]*100:+.1f} to {d['delta_ci'][1]*100:+.1f}, McNemar p={d['mcnemar_p_vs_escalation_model']:.2g}) "
                      f"at ${d['cost_per_1k_usd']:.2f} per 1k screens."]
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    (OUT / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    plot(metrics, order, args.ours)


def plot(metrics: dict, order: list[str], ours: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, ink2, grid = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
    hi, base = "#2a78d6", "#b9b7b0"
    names = [metrics[k]["name"] for k in order][::-1]
    keys = order[::-1]
    y = np.arange(len(keys))
    colors = [hi if k == ours else base for k in keys]

    fig, axes = plt.subplots(1, 2, figsize=(13, 0.62 * len(keys) + 1.9), dpi=200,
                             gridspec_kw={"width_ratios": [1.35, 1]})
    fig.patch.set_facecolor(surface)
    for ax in axes:
        ax.set_facecolor(surface)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color(grid)
        ax.tick_params(colors=ink2, labelsize=10, length=0)
        ax.xaxis.grid(True, color=grid, linewidth=0.8)
        ax.set_axisbelow(True)

    acc = np.array([metrics[k]["accuracy"] * 100 for k in keys])
    lo = np.array([metrics[k]["accuracy_ci"][0] * 100 for k in keys])
    hi_ci = np.array([metrics[k]["accuracy_ci"][1] * 100 for k in keys])
    ax = axes[0]
    ax.barh(y, acc, height=0.52, color=colors, zorder=2)
    ax.errorbar(acc, y, xerr=[acc - lo, hi_ci - acc], fmt="none", ecolor=ink2, elinewidth=1.2, capsize=3, zorder=3)
    for yi, (a, h, k) in enumerate(zip(acc, hi_ci, keys)):
        ax.text(h + 1.0, yi, f"{a:.1f}%", va="center", ha="left", fontsize=10.5,
                color=ink, fontweight="bold" if k == ours else "normal")
    ax.set_yticks(y, names, fontsize=10.5, color=ink)
    for lbl, k in zip(ax.get_yticklabels(), keys):
        if k == ours:
            lbl.set_fontweight("bold")
    ax.axvline(100 / 3, color=ink2, linestyle=(0, (2, 3)), linewidth=1)
    ax.text(100 / 3 + 0.6, len(keys) - 0.45, "chance (33%)", fontsize=8.5, color=ink2, va="bottom")
    ax.set_xlim(0, 100)
    ax.set_xlabel("Accuracy on 900 held-out patient–trial pairs (95% CI)", color=ink2, fontsize=10)

    cost = np.array([metrics[k]["cost_per_1k_usd"] for k in keys])
    ax = axes[1]
    ax.barh(y, cost, height=0.52, color=colors, zorder=2)
    ax.set_xscale("log")
    ax.set_yticks(y, [""] * len(keys))
    for yi, (c, k) in enumerate(zip(cost, keys)):
        ax.text(c * 1.12, yi, f"${c:.2f}", va="center", ha="left", fontsize=10.5,
                color=ink, fontweight="bold" if k == ours else "normal")
    ax.set_xlim(min(cost) / 2.5, max(cost) * 6)
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

    ticks = [t for t in (0.03, 0.1, 0.3, 1, 3, 10, 30) if min(cost) / 2.5 <= t <= max(cost) * 6]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:g}"))
    ax.set_xlabel("Cost per 1,000 screenings, USD (log scale)", color=ink2, fontsize=10)

    fig.suptitle("CapyMatch: clinical-trial eligibility screening (TREC Clinical Trials 2022)",
                 x=0.01, ha="left", fontsize=13.5, color=ink, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(OUT / "chart.png", facecolor=surface)
    print(f"wrote {OUT / 'chart.png'}")


if __name__ == "__main__":
    main()
