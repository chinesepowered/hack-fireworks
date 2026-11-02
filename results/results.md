| System | Type | Accuracy (95% CI) | Macro-F1 (95% CI) | Eligible P / R | $ per 1k screens | p50 latency |
|---|---|---|---|---|---|---|
| **CapyMatch (Super VL + LoRA, ours)** | open + fine-tuned on Fireworks | **74.1%** (70.8–77.4) | 73.9 (70.6–77.2) | 72% / 79% | $0.47 | 4.5s |
| CapyMatch, 3k-pair LoRA (ablation) | open + fine-tuned on Fireworks | 73.1% (69.3–76.8) | 72.8 (68.8–76.5) | 72% / 78% | $0.47 | 3.7s |
| GPT-6.1 Sol | closed frontier (OpenAI) | 72.1% (68.1–75.6) | 71.7 (67.7–75.2) | 79% / 72% | $1.80 | 1.4s |
| GPT-6 Luna | closed, low-cost tier (OpenAI) | 70.8% (66.5–74.5) | 70.3 (65.8–74.1) | 82% / 69% | $0.13 | 1.6s |
| Nemotron 3.5 Super VL, zero-shot | open, Fireworks serverless sampling | 69.3% (65.7–72.7) | 69.5 (65.8–72.9) | 83% / 58% | $0.47 | 0.9s |
| Nemotron 3 Ultra, zero-shot | open, Fireworks serverless | 68.4% (64.5–72.2) | 67.7 (63.6–71.5) | 81% / 65% | $1.78 | 4.0s |

| Ours vs | Accuracy Δ (95% CI) | Macro-F1 Δ (95% CI) | McNemar p | Cost ratio (baseline ÷ ours) |
|---|---|---|---|---|
| GPT-6.1 Sol | +2.0 pts (-1.0 to +5.2) | +2.1 (-0.9 to +5.5) | 0.19 | 3.8× |
| GPT-6 Luna | +3.3 pts (+0.7 to +6.5) | +3.6 (+0.8 to +6.9) | 0.022 | 0.3× |
| Nemotron 3 Ultra, zero-shot | +5.7 pts (+2.7 to +8.8) | +6.2 (+3.0 to +9.4) | 0.00014 | 3.8× |
| Nemotron 3.5 Super VL, zero-shot | +4.8 pts (+2.9 to +6.7) | +4.4 (+2.3 to +6.4) | 0.00075 | 1.0× |
| CapyMatch, 3k-pair LoRA (ablation) | +1.0 pts (-0.2 to +2.2) | +1.1 (-0.2 to +2.4) | 0.22 | 1.0× |

**Selective screening** (CapyMatch auto-screens confident pairs; the rest go to GPT-6.1 Sol):

| Auto-screened share | CapyMatch accuracy on auto-screened | Overall accuracy with escalation | $ per 1k screens |
|---|---|---|---|
| 100% | 74.1% | 74.1% | $0.47 |
| 90% | 77.2% | 73.6% | $0.65 |
| 80% | 79.2% | 73.3% | $0.83 |
| 70% | 82.1% | 73.4% | $1.01 |
| 60% | 83.9% | 72.2% | $1.19 |
| 50% | 87.1% | 72.4% | $1.37 |

With the confidence threshold fixed on dev (keep 80% of dev pairs): 73% of test pairs auto-screened at 81.2% accuracy; overall 73.8% (95% CI 69.9–77.4), +1.7 pts vs GPT-6.1 Sol alone (95% CI +0.0 to +3.3, McNemar p=0.063) at $0.96 per 1k screens.
