# CapyMatch: submission notes

Paste-ready text for the Fireworks: Deploy submission form. All numbers come from `results/metrics.json`.

**Project name:** CapyMatch

**One-liner:** Clinical-trial pre-screening with a fine-tuned NVIDIA Nemotron on Fireworks that matches GPT-6.1 Sol's
accuracy at about a quarter of the cost.

## Project overview

- **Task:** given a patient description and a ClinicalTrials.gov record, label the pair `eligible`, `excluded`, or
  `not_relevant`. This is the pre-screening step research coordinators do by hand.
- **Intended user:** research coordinators at hospitals, trial sites, and CROs, and patient-matching services.
- **Approach:**
  - LoRA fine-tune of NVIDIA Nemotron 3.5 Super VL (120B MoE, 12B active) on 3,000 expert-judged patient–trial pairs
    (TREC Clinical Trials 2021), trained and sampled on Fireworks serverless training.
  - Nemotron 3 Ultra on Fireworks serverless writes a one-line, criterion-citing explanation for each call.
  - A CLI screens a patient against live ClinicalTrials.gov records.
- **Why it matters:** most trials miss enrollment targets, and every patient has to be checked against hundreds of
  trials with dozens of criteria each. A screener that is as accurate as a frontier model at a fraction of the cost
  can run on every patient–trial pair.

## Before and after

- **Evaluation set:** 900 label-balanced patient–trial pairs from all 50 TREC Clinical Trials 2022 patients, none seen
  in training. The trials come from the ClinicalTrials.gov snapshot used by TREC.
- **Metric:** accuracy, plus macro-F1 and eligible precision/recall. 95% CIs come from a patient-clustered bootstrap
  (2,000 draws); significance from exact McNemar tests.
- **Baselines:** GPT-6.1 Sol (OpenAI flagship), GPT-6 Luna (OpenAI low-cost), Nemotron 3 Ultra zero-shot, and the same
  Nemotron 3.5 Super VL before fine-tuning.

| System | Accuracy (95% CI) | $ per 1k screens |
|---|---|---|
| **CapyMatch (Super VL + LoRA)** | **73.1% (69.3–76.8)** | **$0.47** |
| GPT-6.1 Sol | 72.1% (68.1–75.6) | $1.80 |
| GPT-6 Luna | 70.8% (66.5–74.5) | $0.13 |
| Nemotron 3.5 Super VL, zero-shot | 69.3% (65.7–72.7) | $0.47 |
| Nemotron 3 Ultra, zero-shot | 68.4% (64.5–72.2) | $1.78 |

**What improved:**
- Fine-tuning added +3.8 pts over the same model zero-shot (95% CI +1.6 to +5.9, p = 0.01).
- CapyMatch matches GPT-6.1 Sol (+1.0 pts, CI −2.1 to +4.2, p = 0.53) at 3.8× lower cost.
- It has the highest eligible recall of any system: 78% vs 72% for Sol.
- On its 70% most-confident pairs it is 82.9% accurate.

**Tradeoffs:**
- GPT-6 Luna is cheaper ($0.13/1k) and 2.3 pts less accurate (not significant).
- CapyMatch's eligible precision is lower (72% vs 79% for Sol).
- Latency was measured through Fireworks' shared training sampler, not a production deployment.
- TREC labels are noisy expert judgments on synthetic patient notes.
- This is decision support, not diagnosis.

## Links

- **Repo:** https://github.com/chinesepowered/hack-fireworks (setup and reproduction steps in the README; all
  predictions committed, so `make evaluate` reproduces every number offline).
- **Demo video:** `video/capymatch_demo.mp4` in the repo (upload to YouTube or Drive for the form).
- **Fireworks model:** `accounts/clai74-1172e7/models/capymatch-nemotron-e1` (promoted LoRA, deployable).
