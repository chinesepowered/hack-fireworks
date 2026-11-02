"""CapyMatch: clinical-trial eligibility screening with fine-tuned open models on Fireworks."""

LABELS = ("eligible", "excluded", "not_relevant")
# TREC Clinical Trials qrels encoding -> label name
QREL_TO_LABEL = {"2": "eligible", "1": "excluded", "0": "not_relevant"}
