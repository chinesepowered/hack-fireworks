"""Evaluate Nemotron 3.5 Super VL (base or LoRA checkpoint) via Fireworks serverless sampling.

Usage:
  python -m capymatch.run_sampler --system super-vl-base --split test
  python -m capymatch.run_sampler --system capymatch --checkpoint capy-e2 --split test

Greedy decoding, thinking disabled, same prompt as every other system.
Writes results/preds/<system>__<split>.jsonl in the same format as run_chat.py.
"""

from __future__ import annotations

import argparse
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from capymatch.nemotron import BASE_MODEL, prompt_ids, service_client, tokenizer
from capymatch.prompts import parse_label

PRED_DIR = Path("results/preds")


def label_confidence(tok, ids: list[int], logprobs) -> float | None:
    """Probability of the label-deciding token ('el' / 'ex' / 'not' right after '{"label": "')."""
    if not logprobs:
        return None
    text = ""
    for i, t in enumerate(ids):
        if text.endswith('"label": "') or text.endswith('"label":"'):
            return float(math.exp(logprobs[i]))
        text += tok.decode([t])
    return None


def main() -> None:
    from fireworks.training import sdk

    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True, help="super-vl-base or a name for the tuned run, e.g. capymatch")
    ap.add_argument("--checkpoint", default=None, help="key in results/checkpoints.json or a full sampler path")
    ap.add_argument("--split", default="test")
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    tok = tokenizer()
    service = service_client()
    if args.checkpoint:
        ck = json.loads(Path("results/checkpoints.json").read_text()).get(args.checkpoint, {}).get("path", args.checkpoint)
        sampler = service.create_sampling_client(model_path=ck, tokenizer=tok)
        print(f"sampling checkpoint {ck}", flush=True)
    else:
        sampler = service.create_sampling_client(base_model=BASE_MODEL, tokenizer=tok)
        print(f"sampling base model {BASE_MODEL}", flush=True)
    params = sdk.SamplingParams(max_tokens=24, temperature=0.0, stop=[tok.convert_tokens_to_ids("<|im_end|>")])

    rows = [json.loads(line) for line in open(f"data/{args.split}.jsonl")]
    if args.limit:
        rows = rows[: args.limit]
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    out = PRED_DIR / f"{args.system}__{args.split}.jsonl"
    done = {json.loads(line)["id"] for line in open(out)} if out.exists() else set()
    todo = [r for r in rows if r["id"] not in done]
    print(f"{args.system} on {args.split}: {len(rows)} rows, {len(done)} done, {len(todo)} to run", flush=True)
    lock = threading.Lock()

    def work(rec: dict) -> dict:
        ids = prompt_ids(rec)
        for attempt in range(6):
            t0 = time.perf_counter()
            try:
                res = sampler.sample(prompt=sdk.ModelInput.from_ints(ids), num_samples=1, sampling_params=params).result()
                break
            except Exception as e:  # transient capacity errors: back off and retry
                if attempt == 5:
                    raise
                time.sleep(2 ** attempt)
        latency = time.perf_counter() - t0
        seq = res.sequences[0]
        out_ids = list(seq.tokens)
        text = tok.decode(out_ids, skip_special_tokens=True)
        lps = list(seq.logprobs) if getattr(seq, "logprobs", None) is not None else None
        return {
            "id": rec["id"],
            "gold": rec["label"],
            "pred": parse_label(text),
            "confidence": label_confidence(tok, out_ids, lps),
            "finish_reason": str(getattr(seq, "stop_reason", "")),
            "usage": {"prompt_tokens": len(ids), "completion_tokens": len(out_ids)},
            "latency_s": round(latency, 3),
            "server_ms": None,
            "raw": text[-400:],
        }

    n_err = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool, open(out, "a") as f:
        futures = {pool.submit(work, r): r for r in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                row = fut.result()
            except Exception as e:
                n_err += 1
                print(f"error on {futures[fut]['id']}: {e!r}"[:300], flush=True)
                continue
            with lock:
                f.write(json.dumps(row) + "\n")
                f.flush()
            if i % 100 == 0:
                print(f"  {i}/{len(todo)} done ({n_err} errors)", flush=True)
    sampler.close()
    print(f"finished {args.system}/{args.split}: errors={n_err} -> {out}", flush=True)


if __name__ == "__main__":
    main()
