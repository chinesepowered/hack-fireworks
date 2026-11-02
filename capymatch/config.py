"""Model registry and list prices (USD per 1M tokens) used for cost reporting.

Prices were read from the providers' public pricing pages on 2026-11-02:
  Fireworks serverless: https://docs.fireworks.ai/serverless/pricing
  Fireworks serverless training (sampling): https://docs.fireworks.ai/fine-tuning/training-api/serverless
  OpenAI: https://developers.openai.com/api/docs/pricing (Standard tier)
"""

MODELS = {
    # Closed frontier baselines (OpenAI)
    "gpt-6.1-sol": {"provider": "openai", "model": "gpt-6.1-sol", "price": {"in": 2.00, "cached": 0.10, "out": 10.00}},
    "gpt-6-luna": {"provider": "openai", "model": "gpt-6-luna", "price": {"in": 0.10, "cached": 0.01, "out": 0.50}},
    # Open models on Fireworks serverless (NVIDIA Nemotron)
    "nemotron-3-ultra": {
        "provider": "fireworks",
        "model": "accounts/fireworks/models/nemotron-3-ultra-nvfp4",
        "price": {"in": 0.60, "cached": 0.12, "out": 2.40},
    },
    "nemotron-3.5-lightning": {
        "provider": "fireworks",
        "model": "accounts/fireworks/models/nemotron-lightning-3p5-30b-a3b",
        "price": {"in": 0.05, "cached": 0.01, "out": 0.20},
    },
    # Nemotron 3.5 Super VL sampled through Fireworks serverless training (base and LoRA-tuned).
    # Rate shown is the serverless-training sampler card (includes a limited-time 50% discount).
    "nemotron-3.5-super-vl": {
        "provider": "fw-sampler",
        "model": "accounts/fireworks/models/nvidia-nemotron-3p5-super-vl-120b-a12b-bf16",
        "price": {"in": 0.57, "cached": 0.114, "out": 1.44},
    },
}

ENDPOINTS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "fireworks": "https://api.fireworks.ai/inference/v1/chat/completions",
}
KEY_ENV = {"openai": "OPENAI_API_KEY", "fireworks": "FIREWORKS_API_KEY"}
