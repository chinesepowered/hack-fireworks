"""Run a chat-completions model (OpenAI or Fireworks serverless) over a split.

Usage:
  python -m capymatch.run_chat --system gpt-6-luna --split test
  python -m capymatch.run_chat --system nemotron-3-ultra --split test --workers 8

Writes results/preds/<system>__<split>.jsonl (resumable: finished ids are skipped).
Each row: id, gold, pred, usage, latency_s, server_ms, raw (answer text only).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from capymatch.config import ENDPOINTS, KEY_ENV, MODELS
from capymatch.prompts import messages, parse_label

PRED_DIR = Path("results/preds")


def call_chat(system: str, msgs: list[dict], max_tokens: int, timeout: float = 300.0) -> dict:
    spec = MODELS[system]
    provider = spec["provider"]
    body = {"model": spec["model"], "messages": msgs}
    if provider == "openai":
        body["max_completion_tokens"] = max_tokens
    else:
        body["max_tokens"] = max_tokens
    data = json.dumps(body).encode()
    headers = {"Authorization": f"Bearer {os.environ[KEY_ENV[provider]]}", "Content-Type": "application/json"}
    last_err = None
    for attempt in range(8):
        req = urllib.request.Request(ENDPOINTS[provider], data=data, headers=headers, method="POST")
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read())
                latency = time.perf_counter() - t0
                server_ms = resp.headers.get("fireworks-server-processing-time") or resp.headers.get("openai-processing-ms")
                return {"payload": payload, "latency_s": latency, "server_ms": server_ms}
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read()[:300]!r}"
            if e.code not in (408, 409, 429, 500, 502, 503, 504):
                raise RuntimeError(last_err) from e
            retry_after = e.headers.get("Retry-After") if e.headers else None
            wait = float(retry_after) if retry_after and retry_after.replace(".", "").isdigit() else min(60, 2**attempt)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = repr(e)
            wait = min(60, 2**attempt)
        time.sleep(wait + random.random())
    raise RuntimeError(f"gave up after retries: {last_err}")


def run(system: str, split: str, workers: int, max_tokens: int, limit: int | None) -> Path:
    rows = [json.loads(line) for line in open(f"data/{split}.jsonl")]
    if limit:
        rows = rows[:limit]
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    out = PRED_DIR / f"{system}__{split}.jsonl"
    done = set()
    if out.exists():
        done = {json.loads(line)["id"] for line in open(out)}
    todo = [r for r in rows if r["id"] not in done]
    print(f"{system} on {split}: {len(rows)} rows, {len(done)} done, {len(todo)} to run", flush=True)
    lock = threading.Lock()
    n_ok = n_err = 0

    def work(rec: dict) -> dict:
        res = call_chat(system, messages(rec), max_tokens)
        choice = res["payload"]["choices"][0]
        content = choice["message"].get("content") or ""
        return {
            "id": rec["id"],
            "gold": rec["label"],
            "pred": parse_label(content),
            "finish_reason": choice.get("finish_reason"),
            "usage": res["payload"].get("usage", {}),
            "latency_s": round(res["latency_s"], 3),
            "server_ms": res["server_ms"],
            "raw": content[-400:],
        }

    with ThreadPoolExecutor(max_workers=workers) as pool, open(out, "a") as f:
        futures = {pool.submit(work, r): r for r in todo}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                row = fut.result()
                n_ok += 1
            except Exception as e:  # keep going; failures are reported and can be re-run (resumable)
                n_err += 1
                print(f"error on {futures[fut]['id']}: {e}", flush=True)
                continue
            with lock:
                f.write(json.dumps(row) + "\n")
                f.flush()
            if i % 50 == 0:
                print(f"  {i}/{len(todo)} done ({n_err} errors)", flush=True)
    print(f"finished {system}/{split}: ok={n_ok} errors={n_err} -> {out}", flush=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True, choices=[k for k, v in MODELS.items() if v["provider"] != "fw-sampler"])
    ap.add_argument("--split", default="test")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-tokens", type=int, default=6000)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    run(args.system, args.split, args.workers, args.max_tokens, args.limit)


if __name__ == "__main__":
    main()
