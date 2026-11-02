"""Screen a patient against live ClinicalTrials.gov records with the fine-tuned CapyMatch model.

Usage:
  python -m capymatch.screen --patient-file note.txt --nct NCT03898388 NCT04280705
  python -m capymatch.screen --patient "A 62-year-old woman with ..." --nct NCT... --no-explain

Fetches each trial from the ClinicalTrials.gov API (v2), renders it exactly like the training data,
labels it with the fine-tuned Nemotron 3.5 Super VL checkpoint (Fireworks serverless sampling), and asks
Nemotron 3 Ultra for a one-line, criterion-citing explanation.
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

from capymatch.data import format_trial
from capymatch.nemotron import prompt_ids, service_client, tokenizer
from capymatch.prompts import parse_label

FIELDS = ",".join([
    "protocolSection.identificationModule", "protocolSection.conditionsModule",
    "protocolSection.armsInterventionsModule.interventions", "protocolSection.designModule.phases",
    "protocolSection.descriptionModule.briefSummary", "protocolSection.eligibilityModule",
])
PHASES = {"EARLY_PHASE1": "Early Phase 1", "PHASE1": "Phase 1", "PHASE2": "Phase 2", "PHASE3": "Phase 3", "PHASE4": "Phase 4", "NA": "N/A"}


def fetch_trial(nct: str) -> dict:
    url = f"https://clinicaltrials.gov/api/v2/studies/{nct}?fields={FIELDS}"
    with urllib.request.urlopen(url, timeout=30) as r:
        ps = json.loads(r.read())["protocolSection"]
    ident, elig = ps.get("identificationModule", {}), ps.get("eligibilityModule", {})
    criteria = elig.get("eligibilityCriteria", "")
    criteria = re.sub(r"^(\s*)\* ", r"\1- ", criteria, flags=re.M).replace("\\", "")
    hv = elig.get("healthyVolunteers")
    return {
        "nct_id": ident.get("nctId", nct),
        "title": ident.get("briefTitle", ""),
        "conditions": ps.get("conditionsModule", {}).get("conditions", []),
        "interventions": [i.get("name", "") for i in ps.get("armsInterventionsModule", {}).get("interventions", [])],
        "phase": "/".join(PHASES.get(p, p) for p in ps.get("designModule", {}).get("phases", [])),
        "summary": ps.get("descriptionModule", {}).get("briefSummary", ""),
        "criteria": criteria,
        "gender": {"ALL": "All", "FEMALE": "Female", "MALE": "Male"}.get(elig.get("sex", ""), ""),
        "min_age": elig.get("minimumAge", ""),
        "max_age": elig.get("maximumAge", ""),
        "healthy_volunteers": "" if hv is None else ("Accepts Healthy Volunteers" if hv else "No"),
    }


def chosen_checkpoint() -> str:
    ckpts = json.loads(Path("results/checkpoints.json").read_text())
    choice = json.loads(Path("results/checkpoint_choice.json").read_text())["chosen"]
    return ckpts[f"capy-{choice}"]["path"]


def main() -> None:
    from fireworks.training import sdk

    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--patient")
    g.add_argument("--patient-file")
    ap.add_argument("--nct", nargs="+", required=True)
    ap.add_argument("--checkpoint", default=None, help="sampler checkpoint path (default: the dev-chosen CapyMatch checkpoint)")
    ap.add_argument("--no-explain", action="store_true")
    args = ap.parse_args()

    patient = args.patient or Path(args.patient_file).read_text().strip()
    tok = tokenizer()
    sampler = service_client().create_sampling_client(model_path=args.checkpoint or chosen_checkpoint(), tokenizer=tok)
    params = sdk.SamplingParams(max_tokens=24, temperature=0.0, stop=[tok.convert_tokens_to_ids("<|im_end|>")])
    for nct in args.nct:
        trial = fetch_trial(nct)
        rec = {"patient": patient, "trial": format_trial(trial)}
        res = sampler.sample(prompt=sdk.ModelInput.from_ints(prompt_ids(rec)), num_samples=1, sampling_params=params).result()
        label = parse_label(tok.decode(list(res.sequences[0].tokens), skip_special_tokens=True))
        line = f"{trial['nct_id']}  {label or 'unparsed':<13} {trial['title'][:70]}"
        if not args.no_explain and label:
            from capymatch.explain import explain

            line += f"\n    why: {explain(rec, label)}"
        print(line, flush=True)
    sampler.close()


if __name__ == "__main__":
    main()
