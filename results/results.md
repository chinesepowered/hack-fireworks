| System | Type | Accuracy (95% CI) | Macro-F1 (95% CI) | Eligible P / R | $ per 1k screens | p50 latency |
|---|---|---|---|---|---|---|
| **Nemotron 3.5 Super VL, zero-shot** | open, Fireworks serverless sampling | **69.3%** (65.7–72.7) | 69.5 (65.8–72.9) | 83% / 58% | $0.47 | 0.9s |
| GPT-6.1 Sol | closed frontier (OpenAI) | 72.1% (68.1–75.6) | 71.7 (67.7–75.2) | 79% / 72% | $1.80 | 1.4s |
| GPT-6 Luna | closed, low-cost tier (OpenAI) | 70.8% (66.5–74.5) | 70.3 (65.8–74.1) | 82% / 69% | $0.13 | 1.6s |
| Nemotron 3 Ultra, zero-shot | open, Fireworks serverless | 68.4% (64.5–72.2) | 67.7 (63.6–71.5) | 81% / 65% | $1.78 | 4.0s |

| Ours vs | Accuracy Δ (95% CI) | Macro-F1 Δ (95% CI) | McNemar p | Cost ratio (baseline ÷ ours) |
|---|---|---|---|---|
| GPT-6.1 Sol | -2.8 pts (-5.3 to +0.0) | -2.2 (-4.9 to +0.6) | 0.061 | 3.8× |
| GPT-6 Luna | -1.4 pts (-4.1 to +1.3) | -0.8 (-3.6 to +2.1) | 0.38 | 0.3× |
| Nemotron 3 Ultra, zero-shot | +0.9 pts (-1.9 to +3.5) | +1.8 (-1.0 to +4.6) | 0.6 | 3.8× |
