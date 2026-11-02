<p align="center"><img src="assets/banner.png" alt="CapyMatch: a capybara in scrubs holding a clipboard" width="820"></p>

# CapyMatch

**Clinical-trial pre-screening with a fine-tuned NVIDIA Nemotron on Fireworks.**
CapyMatch reads a patient note and a ClinicalTrials.gov record and says whether the patient is
**eligible**, **excluded**, or **not relevant**, the way a research coordinator pre-screens charts.
We fine-tuned NVIDIA Nemotron 3.5 Super VL with LoRA on Fireworks serverless training and compared it with
OpenAI's flagship and low-cost models on the same held-out patients.

<!-- RESULTS -->

## Project overview

| | |
|---|---|
| **Task** | Patient–trial eligibility: given a patient description and a trial record, label the pair `eligible`, `excluded`, or `not_relevant` (TREC Clinical Trials definitions). |
| **Intended user** | Research coordinators at hospitals, trial sites, and CROs who pre-screen patient charts against long eligibility lists; patient-matching services. |
| **Why it matters** | Most clinical trials miss their enrollment targets, and screening is manual: every patient has to be checked against hundreds of trials, each with dozens of criteria. A screener that is accurate *and* cheap enough to run on every patient–trial pair changes what is feasible. |
| **Approach** | LoRA SFT of **NVIDIA Nemotron 3.5 Super VL (120B MoE, 12B active)** on 3,000 expert-judged patient–trial pairs, trained and sampled on **Fireworks serverless training**. **Nemotron 3 Ultra** on Fireworks serverless writes a one-line, criterion-citing explanation for the coordinator. |

## How it works

```
patient note ─┐
              ├─► CapyMatch screener ─────────────► eligible / excluded / not_relevant
trial record ─┘   Nemotron 3.5 Super VL + LoRA          │
                  (Fireworks serverless training)       ▼
                                              Nemotron 3 Ultra (Fireworks serverless)
                                              "Excluded: trial requires age ≤ 24; patient is 34."
```

- **Prompt:** every system, ours and baselines, gets the identical system prompt and input (`capymatch/prompts.py`).
- **Fine-tuning:** 2 epochs, LoRA rank 16, batch 32, peak LR 1e-4 with cosine decay. Loss only on the answer tokens.
  The prompt is rendered with the model's official chat template with thinking disabled (`capymatch/nemotron.py`).
- **Checkpoint choice:** made on a dev split of 5 held-out 2021 patients, never on test.

## Evaluation method

- **Data:** [TREC Clinical Trials](https://www.trec-cds.org/) 2021 and 2022. Synthetic patient descriptions written by
  clinicians, real ClinicalTrials.gov records (2021-04-27 snapshot), and expert relevance judgments
  (2 = eligible, 1 = excluded, 0 = not relevant).
- **Splits (no patient overlap):**
  - train: 3,000 pairs from 70 TREC 2021 patients
  - dev: 120 pairs from 5 other 2021 patients
  - **test: 900 pairs from all 50 TREC 2022 patients**, label-balanced (300 per class), spread round-robin across patients
- **Metrics:** accuracy, macro-F1, and precision/recall on `eligible`; cost per 1,000 screenings at list price from
  measured tokens; client-side latency.
- **Uncertainty:** 95% confidence intervals from a **patient-clustered bootstrap** (2,000 draws over the 50 test
  patients, since pairs from one patient are correlated). Paired differences use the same draws.
  **Exact McNemar tests** on per-pair correctness.
- **Baselines:** **GPT-6.1 Sol** (OpenAI's flagship), **GPT-6 Luna** (OpenAI's low-cost tier), **Nemotron 3 Ultra**
  zero-shot (Fireworks serverless), and **Nemotron 3.5 Super VL** zero-shot (the same model before fine-tuning).
  OpenAI models run with their default reasoning settings.

## Reproduce

```bash
git clone <this repo> && cd hack-fireworks
cp .env.example .env              # add FIREWORKS_API_KEY, OPENAI_API_KEY (ELEVENLABS_API_KEY only for the video)
make setup                        # venv + CPU torch + fireworks-ai[training]
make data                         # TREC topics/judgments + ClinicalTrials.gov snapshot (~1.8 GB), builds data/*.jsonl
make baselines                    # GPT-6.1 Sol, GPT-6 Luna, Nemotron 3 Ultra, Super VL zero-shot
make finetune                     # LoRA SFT on Fireworks serverless training (~15 min)
make eval-tuned evaluate          # dev checkpoint choice, test predictions, metrics, CIs, chart
make demo                         # demo/examples.json from real predictions; open demo/index.html
```

All predictions are committed in `results/preds/`, so `make evaluate` reproduces every number above without any API calls.

## Repository layout

| Path | What |
|---|---|
| `capymatch/data.py` | builds train/dev/test pairs from TREC + ClinicalTrials.gov |
| `capymatch/prompts.py` | shared prompt and label parser |
| `capymatch/run_chat.py` | OpenAI / Fireworks chat-completions runner (resumable, logs tokens and latency) |
| `capymatch/finetune.py`, `capymatch/nemotron.py` | LoRA SFT on Fireworks serverless training |
| `capymatch/run_sampler.py` | scores base and fine-tuned checkpoints through serverless sampling |
| `capymatch/evaluate.py` | metrics, clustered bootstrap CIs, McNemar, cost, chart |
| `capymatch/explain.py` | Nemotron 3 Ultra explanations for coordinators |
| `demo/` | static demo page (`index.html` + `examples.json`) |
| `video/` | narrated demo video pipeline (HTML scenes, ElevenLabs narration, ffmpeg) |
| `assets/` | the CapyMatch capybara (original SVG art) |

## Limitations

- **Labels are expert judgments with known noise.** TREC assessors' "excluded" vs. "not relevant" calls are not
  always crisp, and a fine-tuned model partly learns those conventions. That is useful for matching TREC, but
  it is not the same as clinical ground truth.
- **Synthetic patient notes.** TREC topics are written by clinicians, not taken from real EHRs. Real charts are longer and messier.
- **Balanced test set.** Real screening is dominated by `not_relevant` pairs. We report eligible precision and recall
  so the screening tradeoff is visible.
- **Serving cost.** The tuned LoRA is priced at Fireworks' serverless-training sampling rate, which includes a
  limited-time 50% discount. Production serving would use a dedicated deployment billed per GPU-hour, so cost per
  screening then depends on utilization.
- **Decision support, not diagnosis.** CapyMatch flags candidates for a human coordinator; it does not decide enrollment.

## Credits

Data: TREC Clinical Trials 2021/2022 (NIST) and ClinicalTrials.gov (U.S. National Library of Medicine).
Models: NVIDIA Nemotron 3.5 Super VL and Nemotron 3 Ultra served and fine-tuned on Fireworks AI, and OpenAI GPT-6.1 Sol and GPT-6 Luna as baselines.
Mascot and banner: original artwork made for this project.
