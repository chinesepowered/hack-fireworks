# CapyMatch pipeline. Keys are read from .env (see .env.example).
-include .env
export
PY ?= .venv/bin/python

.PHONY: setup data baselines finetune eval-tuned evaluate demo video all

setup:
	python3 -m venv .venv
	.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cpu
	.venv/bin/pip install -r requirements.txt

data:  ## TREC Clinical Trials 2021/2022 topics, judgments, and the 2021-04-27 ClinicalTrials.gov snapshot (~1.8 GB)
	mkdir -p data/raw
	cd data/raw && curl -sSLO https://www.trec-cds.org/topics2021.xml -O https://www.trec-cds.org/topics2022.xml \
	  -O https://trec.nist.gov/data/trials/qrels2021.txt -O https://trec.nist.gov/data/trials/qrels2022.txt
	cd data/raw && for i in 1 2 3 4 5; do curl -sSL -C - -o ClinicalTrials.part$$i.zip https://www.trec-cds.org/2021_data/ClinicalTrials.2021-04-27.part$$i.zip; done
	$(PY) -m capymatch.data
	$(PY) -m capymatch.data --train-only --train-per-label 3000 --train-out train_9k

baselines:  ## closed + open zero-shot baselines on the frozen test set
	$(PY) -m capymatch.run_chat --system gpt-6-luna --split test
	$(PY) -m capymatch.run_chat --system gpt-6.1-sol --split test
	$(PY) -m capymatch.run_chat --system nemotron-3-ultra --split test
	$(PY) -m capymatch.run_sampler --system super-vl-base --split test

finetune:  ## LoRA SFT of Nemotron 3.5 Super VL on Fireworks serverless training (two runs)
	$(PY) -m capymatch.finetune --epochs 2 --batch-size 32 --lr 1e-4 --rank 16 --tag capy
	$(PY) -m capymatch.finetune --train-file data/train_9k.jsonl --epochs 1 --batch-size 32 --lr 1e-4 --rank 16 --tag c9k

eval-tuned:  ## pick the checkpoint on dev, then score only that one on test (+ the 3k-pair ablation)
	$(PY) -m capymatch.choose --tags capy-e1 capy-e2 c9k-e1
	$(PY) -m capymatch.run_sampler --system capymatch-3k --checkpoint capy-e1 --split test

evaluate:
	$(PY) -m capymatch.evaluate --ours capymatch

demo:
	$(PY) -m capymatch.demo_examples
	@echo "serve the repo root: python3 -m http.server 8000, then open http://localhost:8000/demo/"

video:
	python3 video/build.py

all: data baselines finetune eval-tuned evaluate demo video
