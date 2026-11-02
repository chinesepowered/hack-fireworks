"""Nemotron 3.5 Super VL helpers for Fireworks serverless training and sampling.

Prompts are rendered with the model's official Hugging Face chat template with
thinking disabled, which yields:
  <|im_start|>system\n{system}<|im_end|>\n<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n<think></think>
The trained completion is the JSON label followed by <|im_end|>.
"""

from __future__ import annotations

import os
from functools import lru_cache

from capymatch.prompts import messages, target

BASE_MODEL = "accounts/fireworks/models/nvidia-nemotron-3p5-super-vl-120b-a12b-bf16"
TOKENIZER = "nvidia/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-BF16"
SERVERLESS_URL = "https://api.fireworks.ai/training/v1/serverless"
IM_END = "<|im_end|>"


@lru_cache(maxsize=1)
def tokenizer():
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(TOKENIZER)


def prompt_ids(rec: dict) -> list[int]:
    tok = tokenizer()
    text = tok.apply_chat_template(messages(rec), tokenize=False, add_generation_prompt=True, enable_thinking=False)
    return tok.encode(text, add_special_tokens=False)


def completion_ids(rec: dict) -> list[int]:
    return tokenizer().encode(target(rec) + IM_END, add_special_tokens=False)


def make_datum(rec: dict):
    """Next-token SFT datum: loss only on the assistant completion (label JSON + <|im_end|>)."""
    from fireworks.training import sdk

    p, c = prompt_ids(rec), completion_ids(rec)
    toks = p + c
    weights = [0.0] * len(p) + [1.0] * len(c)
    return sdk.Datum(
        model_input=sdk.ModelInput.from_ints(toks[:-1]),
        loss_fn_inputs={"target_tokens": toks[1:], "weights": weights[1:]},
    ), len(toks)


def service_client():
    from fireworks.training import sdk

    return sdk.FiretitanServiceClient(api_key=os.environ["FIREWORKS_API_KEY"], base_url=SERVERLESS_URL)
