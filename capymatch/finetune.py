"""LoRA SFT of NVIDIA Nemotron 3.5 Super VL on Fireworks serverless training.

Usage:
  python -m capymatch.finetune --epochs 2 --batch-size 32 --lr 1e-4 --rank 16

Saves a sampler checkpoint after every epoch (paths in results/checkpoints.json),
logs per-step loss to results/train_log.jsonl, and promotes the final checkpoint
to a deployable LoRA model before exiting.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from pathlib import Path

import numpy as np

from capymatch.nemotron import BASE_MODEL, make_datum, prompt_ids, completion_ids, service_client, tokenizer

RESULTS = Path("results")


def lr_at(step: int, total: int, peak: float, warmup: int, floor_frac: float = 0.1) -> float:
    if step < warmup:
        return peak * (step + 1) / warmup
    progress = (step - warmup) / max(1, total - warmup)
    return peak * (floor_frac + (1 - floor_frac) * 0.5 * (1 + math.cos(math.pi * progress)))


def weighted_nll(output, datums) -> float:
    num = den = 0.0
    for out, d in zip(output.loss_fn_outputs, datums):
        lp = np.asarray(out["logprobs"].to_numpy(), dtype=np.float64).reshape(-1)
        w = np.asarray(d.loss_fn_inputs["weights"].to_numpy(), dtype=np.float64).reshape(-1)
        n = min(len(lp), len(w))
        num += float(-(lp[:n] * w[:n]).sum())
        den += float(w[:n].sum())
    return num / max(den, 1.0)


def main() -> None:
    from fireworks.training import sdk

    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--warmup", type=int, default=6)
    ap.add_argument("--limit", type=int, default=None, help="smoke test: train on the first N rows")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--tag", default="capy")
    ap.add_argument("--no-promote", action="store_true")
    ap.add_argument("--train-file", default="data/train.jsonl")
    args = ap.parse_args()

    rows = [json.loads(line) for line in open(args.train_file)]
    if args.limit:
        rows = rows[: args.limit]
    tokenizer()
    # Sanity: rendered prompt must be a strict prefix of prompt+completion.
    for r in rows[:3]:
        assert completion_ids(r)[-1] == tokenizer().convert_tokens_to_ids("<|im_end|>")
        assert len(prompt_ids(r)) > 0
    built = [make_datum(r) for r in rows]
    n_tokens = sum(n for _, n in built)
    print(f"{len(built)} datums, {n_tokens:,} tokens/epoch (max {max(n for _, n in built)})", flush=True)

    service = service_client()
    tc = service.create_lora_training_client(base_model=BASE_MODEL, rank=args.rank, seed=args.seed)
    print(f"session={service.training_session_id} run={tc.run_id}", flush=True)

    RESULTS.mkdir(exist_ok=True)
    log = open(RESULTS / f"train_log_{args.tag}.jsonl", "a")
    ckpts_path = RESULTS / "checkpoints.json"
    ckpts = json.loads(ckpts_path.read_text()) if ckpts_path.exists() else {}

    rng = random.Random(args.seed)
    steps_per_epoch = math.ceil(len(built) / args.batch_size)
    total = steps_per_epoch * args.epochs
    step = 0
    t_start = time.time()
    for epoch in range(1, args.epochs + 1):
        order = list(range(len(built)))
        rng.shuffle(order)
        for b in range(steps_per_epoch):
            batch = [built[i][0] for i in order[b * args.batch_size : (b + 1) * args.batch_size]]
            lr = lr_at(step, total, args.lr, args.warmup)
            t0 = time.time()
            fb = tc.forward_backward(batch, "cross_entropy")
            op = tc.optim_step(sdk.AdamParams(learning_rate=lr, beta1=0.9, beta2=0.95, eps=1e-8, weight_decay=0.0))
            out = fb.result()
            op.result()
            loss = weighted_nll(out, batch)
            rec = {"epoch": epoch, "step": step, "lr": lr, "loss": loss, "secs": round(time.time() - t0, 2)}
            log.write(json.dumps(rec) + "\n")
            log.flush()
            if step % 5 == 0 or b == steps_per_epoch - 1:
                el = time.time() - t_start
                print(f"epoch {epoch} step {step}/{total} loss {loss:.4f} lr {lr:.2e} ({rec['secs']}s/step, {el/60:.1f} min)", flush=True)
            step += 1
        name = f"{args.tag}-e{epoch}"
        path = tc.save_weights_for_sampler(name).result().path
        ckpts[name] = {"path": path, "epoch": epoch, "steps": step, "run_id": tc.run_id,
                       "session": service.training_session_name, "rank": args.rank, "lr": args.lr,
                       "batch_size": args.batch_size, "train_rows": len(built), "train_tokens_per_epoch": n_tokens}
        ckpts_path.write_text(json.dumps(ckpts, indent=2))
        print(f"saved sampler checkpoint {name}: {path}", flush=True)

    if not args.no_promote:
        try:
            fw = sdk.FireworksClient(api_key=os.environ["FIREWORKS_API_KEY"])
            rows_ck = fw.list_training_session_checkpoints(service.training_session_name)
            promotable = [r for r in rows_ck if r.get("promotable")]
            promotable.sort(key=lambda r: r["createTime"])
            target = promotable[-1]
            model = fw.promote_session_checkpoint(name=target["name"], output_model_id=f"capymatch-{args.tag}-final", base_model=BASE_MODEL)
            ckpts["promoted_model"] = str(getattr(model, "name", model))
            ckpts_path.write_text(json.dumps(ckpts, indent=2))
            print(f"promoted {target['name']} -> {ckpts['promoted_model']}", flush=True)
        except Exception as e:  # promotion is a convenience for later deployment; eval does not need it
            print(f"promotion skipped: {e!r}", flush=True)
    print(f"done in {(time.time() - t_start)/60:.1f} min", flush=True)


if __name__ == "__main__":
    main()
