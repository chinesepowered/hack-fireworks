#!/usr/bin/env python3
"""Build the CapyMatch demo video (narrated, 1920x1080, H.264 + AAC).

    python3 video/build.py                 # uses results/summary.json, else video/summary.placeholder.json
    python3 video/build.py --summary path/to/summary.json --out video/build/capymatch_demo.mp4

Pipeline
  1. Narration lines are generated from summary.json (results lines are conditional on the numbers).
  2. ElevenLabs TTS per scene (cached by sha1(voice, model, settings, text) in video/build/audio/;
     a character ledger enforces a budget, CAPY_TTS_BUDGET, default 4000 chars).
  3. Each scene is an HTML page with CSS animations; video/render_frames.js seeks the animations
     frame by frame in headless Chromium and pipes JPEG frames to ffmpeg (deterministic output).
  4. Clips + padded narration are concatenated and muxed; captions.srt is written alongside.

Requires: python3, node + playwright (chromium), ffmpeg/ffprobe, ELEVENLABS_API_KEY in the environment
(only for lines that are not cached yet).
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VID = ROOT / "video"
BUILD = VID / "build"
AUDIO = BUILD / "audio"
SCENES = BUILD / "scenes"
CLIPS = BUILD / "clips"
FONTS = BUILD / "fonts"
ASSETS = ROOT / "assets"

VOICE_ID = "cgSgspJ2msm6clMCkdW9"  # "Jessica" (ElevenLabs premade): young American female, bright and warm
VOICE_NAME = "Jessica"
MODEL_ID = "eleven_v4"
VOICE_SETTINGS = {"stability": 0.5, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True, "speed": 1.06}
LEAD, TAIL, LAST_TAIL, FPS = 0.35, 0.6, 1.7, 30
REPO_URL = "github.com/chinesepowered/hack-fireworks"


# ----------------------------------------------------------------------------- helpers
def sh(cmd: list[str], **kw) -> str:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw).stdout


def duration_of(path: Path) -> float:
    return float(sh(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)]).strip())


def ensure_fonts() -> None:
    FONTS.mkdir(parents=True, exist_ok=True)
    need = {"Fredoka": FONTS / "fredoka-latin.woff2", "Nunito": FONTS / "nunito-latin.woff2"}
    if all(p.exists() for p in need.values()):
        return
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    url = "https://fonts.googleapis.com/css2?family=Fredoka:wght@400..700&family=Nunito:wght@400..900&display=swap"
    css = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": ua})).read().decode()
    for subset, body in re.findall(r"/\* (\S+) \*/\s*@font-face \{(.*?)\}", css, re.S):
        fam = re.search(r"font-family: '([^']+)'", body).group(1)
        if subset == "latin" and fam in need:
            urllib.request.urlretrieve(re.search(r"url\((https://[^)]+)\)", body).group(1), need[fam])


def pct(x: float) -> str:
    return f"{100 * x:.0f}"


def money_text(x: float) -> str:
    return "<$0.01" if x < 0.01 else f"${x:.2f}"


def money_spoken(x: float) -> str:
    if x < 0.01:
        return "less than a cent"
    if x < 1:
        c = round(x * 100)
        return f"{c} cent{'s' if c != 1 else ''}"
    return f"{x:.2f} dollars"


def p_text(p: float | None) -> str:
    if p is None:
        return ""
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


# ----------------------------------------------------------------------------- narration
def results_story(s: dict) -> dict:
    """Numbers-driven results text. Only states what summary.json supports."""
    sysmap = {x["key"]: x for x in s["systems"]}
    h = s["headline"]
    ours, vs = sysmap[h["ours"]], sysmap[h["vs"]]
    lo, hi = h["acc_delta_ci"]
    d = round(100 * h["acc_delta"])
    spoken, callout = [], []
    base = sysmap.get("super-vl-base")
    if base and base is not ours:
        b, o = pct(base["accuracy"]), pct(ours["accuracy"])
        if int(o) > int(b):
            spoken.append(f"Fine-tuning lifted Nemotron Super VL from {b} to {o} percent accuracy.")
        elif int(o) < int(b):
            spoken.append(f"Fine-tuning lowered Nemotron Super VL from {b} to {o} percent accuracy.")
        else:
            spoken.append(f"Fine-tuning kept Nemotron Super VL at about {o} percent accuracy.")
    else:
        spoken.append(f"CapyMatch reached {pct(ours['accuracy'])} percent accuracy.")
    if lo > 0:
        win = "win"
        spoken.append(f"That's about {d} points more accurate than {vs['name']}, and the 95 percent confidence interval stays above zero.")
        callout.append(f"+{d} pts accuracy vs {vs['name']}")
    elif hi < 0:
        win = "loss"
        spoken.append(f"That's about {abs(d)} points below {vs['name']}, so on accuracy this run is not a win.")
        callout.append(f"{d} pts accuracy vs {vs['name']}")
    else:
        win = "tie"
        spoken.append(f"That's statistically tied with {vs['name']}: the 95 percent confidence interval includes zero.")
        callout.append(f"Tied with {vs['name']} on accuracy")
    callout.append(f"95% CI {100 * lo:+.0f} to {100 * hi:+.0f} pts" + (f" · McNemar {p_text(h.get('mcnemar_p'))}" if h.get("mcnemar_p") is not None else ""))
    co, cv = ours["cost_per_1k_usd"], vs["cost_per_1k_usd"]
    if co < cv * 0.95:
        r = cv / co if co > 0 else float("inf")
        spoken.append(f"And it costs about {money_spoken(co)} per thousand screenings, roughly {r:.0f} times less than {vs['name']}." if r >= 2
                      else f"And it costs about {money_spoken(co)} per thousand screenings, less than {vs['name']}.")
    elif co > cv * 1.05:
        spoken.append(f"It costs about {money_spoken(co)} per thousand screenings, versus {money_spoken(cv)} for {vs['name']}.")
    else:
        spoken.append(f"It costs about the same, around {money_spoken(co)} per thousand screenings.")
    sol = sysmap.get("gpt-6.1-sol")
    if sol and h["vs"] != "gpt-6.1-sol":
        spoken.append(f"For reference, GPT-6.1 Sol scored {pct(sol['accuracy'])} percent at {money_spoken(sol['cost_per_1k_usd'])} per thousand.")
    return {"spoken": " ".join(spoken), "callout": callout, "win": win}


def narration(s: dict) -> list[dict]:
    rs = results_story(s)
    lines = [
        ("title", "Meet CapyMatch: a calm little capybara that helps match patients to clinical trials."),
        ("problem", "Most clinical trials miss their enrollment targets. Coordinators still screen patient charts by hand, "
                    "against long lists of eligibility criteria."),
        ("approach", f"On the Trek Clinical Trials benchmark, we fine-tuned NVIDIA's Nemotron 3.5 Super VL with LoRA on Fireworks "
                     f"serverless training, using {s['train_pairs']:,} expert-labeled patient-trial pairs, then tested on "
                     f"{s['test_pairs']} pairs from {s['test_patients']} new patients."),
        ("demo", "Here's a held-out test patient. For each trial, CapyMatch says eligible, excluded, or not relevant, "
                 "and we check it against the expert's label."),
        ("results", rs["spoken"]),
        ("close", "Caveats: expert labels are noisy, patient notes are synthetic, and this is decision support, not a diagnosis. "
                  "CapyMatch: fine-tuned open models on Fireworks, helping patients find trials."),
    ]
    caption = lambda t: t.replace("Trek Clinical", "TREC Clinical")
    return [{"id": k, "spoken": t, "caption": caption(t)} for k, t in lines]


# ----------------------------------------------------------------------------- TTS
def tts(text: str, budget: int) -> Path:
    AUDIO.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha1(json.dumps([VOICE_ID, MODEL_ID, VOICE_SETTINGS, text]).encode()).hexdigest()[:16]
    out = AUDIO / f"{key}.mp3"
    if out.exists():
        return out
    ledger_p = AUDIO / "ledger.json"
    ledger = json.loads(ledger_p.read_text()) if ledger_p.exists() else {"chars": 0, "calls": []}
    if ledger["chars"] + len(text) > budget:
        sys.exit(f"TTS budget exceeded ({ledger['chars']} + {len(text)} > {budget}); set CAPY_TTS_BUDGET to allow more.")
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("ELEVENLABS_API_KEY is not set (needed for uncached narration lines).")
    body = json.dumps({"text": text, "model_id": MODEL_ID, "voice_settings": VOICE_SETTINGS}).encode()
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format=mp3_44100_128",
        data=body, headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}, method="POST")
    try:
        audio = urllib.request.urlopen(req, timeout=180).read()
    except urllib.error.HTTPError as e:
        sys.exit(f"ElevenLabs error {e.code}: {e.read()[:300]!r}")
    out.write_bytes(audio)
    ledger["chars"] += len(text)
    ledger["calls"].append({"file": out.name, "chars": len(text)})
    ledger_p.write_text(json.dumps(ledger, indent=1))
    print(f"  tts: {len(text)} chars -> {out.name} (ledger {ledger['chars']}/{budget})")
    return out


# ----------------------------------------------------------------------------- scenes
CSS = r"""
__FONTFACE__
* { box-sizing: border-box; }
html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #FFF6EA; color: #4A3326;
  font-family: Nunito, "Segoe UI", Arial, sans-serif; }
.stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; }
.dot { position: absolute; border-radius: 50%; }
.plus { position: absolute; font: 900 54px Nunito; }
.kicker { font-weight: 800; font-size: 28px; letter-spacing: .14em; text-transform: uppercase; color: #2FA595; }
.h1 { font-family: Fredoka, Nunito, sans-serif; font-weight: 700; font-size: 86px; line-height: 1.04; letter-spacing: -1.5px; margin: 10px 0 0; }
.h2 { font-family: Fredoka, Nunito, sans-serif; font-weight: 600; font-size: 46px; line-height: 1.1; margin: 0; }
.card { background: #fff; border-radius: 30px; box-shadow: 0 8px 0 #F0E2CF, 0 24px 50px rgba(122, 82, 48, .10); }
.chip { display: inline-flex; align-items: center; border-radius: 999px; padding: 12px 26px; font-weight: 800; font-size: 28px; white-space: nowrap; }
.c-brown { background: #5B3A26; color: #FFF6EA; } .c-teal { background: #2FA595; color: #fff; } .c-peach { background: #FFE2C2; color: #8A4B1F; }
.c-elig { background: #DCF5E6; color: #23935A; } .c-excl { background: #FFE7D6; color: #C8602A; } .c-nr { background: #ECEFF3; color: #5F6B7A; }
.tag-ph { position: absolute; right: 30px; top: 24px; background: #D64545; color: #fff; font-weight: 900; font-size: 22px; padding: 8px 16px; border-radius: 10px; letter-spacing: .06em; }
.wm { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%) rotate(-12deg); font: 900 120px Nunito; color: rgba(214, 69, 69, .14); white-space: nowrap; pointer-events: none; }

@keyframes rise { from { opacity: 0; transform: translateY(34px); } to { opacity: 1; transform: none; } }
@keyframes pop { 0% { opacity: 0; transform: scale(.5); } 70% { opacity: 1; transform: scale(1.07); } 100% { opacity: 1; transform: scale(1); } }
@keyframes fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes bob { 0%, 100% { transform: translateY(0) rotate(-2deg); } 50% { transform: translateY(-14px) rotate(2deg); } }
@keyframes floaty { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-20px); } }
@keyframes grow { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes scrollup { from { transform: translateY(0); } to { transform: translateY(-560px); } }
@keyframes slide { from { opacity: 0; transform: translateX(-40px); } to { opacity: 1; transform: none; } }
.rise { animation: rise .7s cubic-bezier(.2, .8, .2, 1) both; }
.pop { animation: pop .6s cubic-bezier(.2, .8, .2, 1) both; }
.fade { animation: fade .6s ease both; }
.slide { animation: slide .6s cubic-bezier(.2, .8, .2, 1) both; }
.bob { animation: bob 2.8s ease-in-out infinite; }
.floaty { animation: floaty 4.5s ease-in-out infinite; }
"""


def font_face() -> str:
    return (f"@font-face {{ font-family: 'Fredoka'; src: url('file://{FONTS / 'fredoka-latin.woff2'}') format('woff2'); font-weight: 300 700; }}\n"
            f"@font-face {{ font-family: 'Nunito'; src: url('file://{FONTS / 'nunito-latin.woff2'}') format('woff2'); font-weight: 200 1000; }}")


def page(body: str, placeholder: bool) -> str:
    ph = '<div class="tag-ph">PLACEHOLDER NUMBERS</div>' if placeholder else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS.replace('__FONTFACE__', font_face())}</style></head>"
            f"<body><div class='stage'>{body}{ph}</div><script>window.CAPY_READY = true;</script></body></html>")


def capy(name: str) -> str:
    return f"file://{ASSETS / name}"


def deco() -> str:
    dots = [(120, 140, 26, "#FFC7CF"), (1780, 120, 20, "#BFE7DF"), (1700, 930, 34, "#FFE2C2"), (220, 950, 22, "#BFE7DF"), (980, 70, 14, "#FFC7CF")]
    out = "".join(f'<div class="dot floaty" style="left:{x}px;top:{y}px;width:{2*r}px;height:{2*r}px;background:{c};animation-delay:-{i*0.9:.1f}s"></div>'
                  for i, (x, y, r, c) in enumerate(dots))
    out += '<div class="plus floaty" style="left:1830px;top:500px;color:#7FD3C5;animation-delay:-1.3s">+</div>'
    out += '<div class="plus floaty" style="left:50px;top:540px;color:#FFB9A2;animation-delay:-2.2s">+</div>'
    return out


def scene_title(s: dict) -> str:
    return deco() + f"""
<div style="position:absolute;left:170px;top:170px;width:700px;height:700px;border-radius:50%;background:#DDF4EF" class="pop"></div>
<div class="pop" style="position:absolute;left:190px;top:150px;animation-delay:.15s"><img class="bob" src="{capy('capy.svg')}" style="width:680px;height:680px"></div>
<div style="position:absolute;left:960px;top:300px;width:900px">
  <div class="rise" style="font-family:Fredoka;font-weight:700;font-size:168px;letter-spacing:-3px;line-height:1;animation-delay:.45s">
    <span style="color:#5B3A26">Capy</span><span style="color:#2FA595">Match</span></div>
  <div class="rise h2" style="margin-top:26px;color:#6B5040;font-family:Nunito;font-weight:800;font-size:46px;animation-delay:.8s">
    Matching patients to clinical trials<br>with fine-tuned open models</div>
  <div style="display:flex;gap:18px;margin-top:40px">
    <span class="chip c-brown pop" style="animation-delay:1.2s">NVIDIA Nemotron</span>
    <span class="chip c-teal pop" style="animation-delay:1.35s">Fireworks AI</span>
    <span class="chip c-peach pop" style="animation-delay:1.5s">TREC Clinical Trials</span>
  </div>
</div>"""


def scene_problem(s: dict) -> str:
    lines = "".join(
        f'<div style="display:flex;gap:16px;align-items:center;margin:14px 0"><div style="width:30px;height:30px;border-radius:8px;border:4px solid #CDBBA6;flex:none"></div>'
        f'<div style="height:16px;border-radius:8px;background:#EFE4D6;width:{w}px"></div></div>'
        for w in [420, 360, 470, 300, 410, 380, 450, 330, 400, 460, 310, 390, 440, 350, 420, 300, 470, 380, 410, 360, 450, 330, 400, 380, 420, 360]
    )
    bullets = [("Coordinators screen charts by hand", ".9s"), ("Dozens of inclusion & exclusion criteria per trial", "1.5s"), ("Every patient × every candidate trial", "2.1s")]
    blist = "".join(f'<div class="slide card" style="animation-delay:{d};padding:26px 34px;margin-top:22px;font-size:38px;font-weight:800">{html.escape(b)}</div>' for b, d in bullets)
    return deco() + f"""
<div style="position:absolute;left:130px;top:140px;width:960px">
  <div class="kicker rise">The problem</div>
  <div class="h1 rise" style="animation-delay:.2s">Most clinical trials miss their enrollment targets</div>
  {blist}
</div>
<div class="card pop" style="position:absolute;left:1180px;top:150px;width:600px;height:760px;overflow:hidden;animation-delay:.3s">
  <div style="position:relative;z-index:2;background:#fff;padding:34px 40px 16px;border-bottom:3px solid #F3E8DA">
    <div style="font-family:Fredoka;font-weight:600;font-size:38px">Eligibility criteria</div>
    <div style="font-size:24px;font-weight:700;color:#9A8273">Inclusion · Exclusion · page 1 of 4</div>
  </div>
  <div style="position:absolute;left:0;right:0;top:134px;bottom:0;overflow:hidden">
    <div style="padding:14px 40px;animation:scrollup 14s linear both;animation-delay:.6s">{lines}</div>
  </div>
</div>
<div class="pop" style="position:absolute;left:1040px;top:640px;animation-delay:1.1s"><img class="bob" src="{capy('capy-thinking.svg')}" style="width:330px;height:330px"></div>"""


def scene_approach(s: dict) -> str:
    box = lambda x, d, kick, title, sub, color: f"""
<div class="card rise" style="position:absolute;left:{x}px;top:300px;width:500px;height:380px;padding:38px;animation-delay:{d}s">
  <div class="kicker" style="color:{color}">{kick}</div>
  <div style="font-family:Fredoka;font-weight:700;font-size:52px;line-height:1.05;margin:14px 0 18px">{title}</div>
  <div style="font-size:30px;font-weight:700;color:#7A6152;line-height:1.35">{sub}</div>
</div>"""
    arrow = lambda x, d: (f'<svg class="pop" style="position:absolute;left:{x}px;top:466px;animation-delay:{d}s" width="52" height="48" viewBox="0 0 52 48">'
                          '<path d="M4 24 H40 M28 10 L44 24 L28 38" fill="none" stroke="#2FA595" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></svg>')
    chips = f"""
<div style="position:absolute;left:150px;top:760px;display:flex;gap:22px;align-items:center">
  <div class="fade" style="font-size:32px;font-weight:800;color:#7A6152;animation-delay:3.2s">Every patient-trial pair gets one label:</div>
  <span class="chip c-elig pop" style="animation-delay:3.5s">Eligible</span>
  <span class="chip c-excl pop" style="animation-delay:3.7s">Excluded</span>
  <span class="chip c-nr pop" style="animation-delay:3.9s">Not relevant</span>
</div>"""
    return deco() + f"""
<div style="position:absolute;left:150px;top:110px"><div class="kicker rise">How CapyMatch works</div>
<div class="h1 rise" style="animation-delay:.15s;font-size:76px">Fine-tune an open model on expert labels</div></div>
{box(150, .5, "1 · Train data", "TREC Clinical Trials 2021", f"{s['train_pairs']:,} expert-labeled<br>patient-trial pairs", "#C8602A")}
{arrow(654, 1.2)}
{box(710, 1.4, "2 · Fine-tune", "Nemotron 3.5 Super VL + LoRA", "NVIDIA open model on<br>Fireworks serverless training", "#2FA595")}
{arrow(1214, 2.1)}
{box(1270, 2.3, "3 · Held-out test", f"{s['test_pairs']} pairs", f"{s['test_patients']} new patients<br>from TREC 2022", "#5B3A26")}
{chips}"""


def scene_results(s: dict) -> str:
    rs = results_story(s)
    systems = s["systems"]
    ours_key = s["headline"]["ours"]
    n = len(systems)
    row_h, x0, width = min(112, int(560 / max(n, 1))), 560, 640
    rows = []
    for i, x in enumerate(systems):
        y = 40 + i * row_h
        ours = x["key"] == ours_key
        lo, hi = x.get("accuracy_ci", [x["accuracy"], x["accuracy"]])
        bar_w = width * x["accuracy"]
        color = "#2FA595" if ours else "#D9C3A9"
        d = 0.6 + i * 0.35
        rows.append(f"""
  <text x="{x0 - 24}" y="{y + 50}" text-anchor="end" font-family="Nunito" font-weight="{900 if ours else 800}" font-size="{min(30, 520 / (0.55 * max(len(x['name']), 1))):.1f}" fill="{'#2FA595' if ours else '#4A3326'}">{html.escape(x['name'])}</text>
  <text x="{x0 - 24}" y="{y + 82}" text-anchor="end" font-family="Nunito" font-weight="700" font-size="21" fill="#9A8273">{html.escape(x.get('kind', ''))}</text>
  <rect x="{x0}" y="{y + 18}" width="{bar_w:.1f}" height="64" rx="14" fill="{color}" style="transform-box:fill-box;transform-origin:left center;animation:grow .9s cubic-bezier(.2,.8,.2,1) both;animation-delay:{d:.2f}s"/>
  <g class="fade" style="animation-delay:{d + 0.8:.2f}s">
    <line x1="{x0 + width * lo:.1f}" x2="{x0 + width * hi:.1f}" y1="{y + 50}" y2="{y + 50}" stroke="#4A3326" stroke-width="4"/>
    <line x1="{x0 + width * lo:.1f}" x2="{x0 + width * lo:.1f}" y1="{y + 36}" y2="{y + 64}" stroke="#4A3326" stroke-width="4"/>
    <line x1="{x0 + width * hi:.1f}" x2="{x0 + width * hi:.1f}" y1="{y + 36}" y2="{y + 64}" stroke="#4A3326" stroke-width="4"/>
    <text x="{x0 + width * max(hi, x['accuracy']) + 18:.1f}" y="{y + 61}" font-family="Fredoka" font-weight="700" font-size="36" fill="{'#2FA595' if ours else '#4A3326'}">{pct(x['accuracy'])}%</text>
  </g>""")
    chance = x0 + width / 3
    chart_h = 40 + n * row_h + 30
    ticks = "".join(f'<line x1="{x0 + width * t}" x2="{x0 + width * t}" y1="20" y2="{chart_h - 20}" stroke="#EADBC8" stroke-width="2"/>'
                    f'<text x="{x0 + width * t}" y="{chart_h + 8}" text-anchor="middle" font-family="Nunito" font-weight="700" font-size="20" fill="#9A8273">{int(t * 100)}%</text>'
                    for t in (0, .25, .5, .75, 1))
    chart = f"""<svg width="1300" height="{chart_h + 20}" viewBox="0 0 1300 {chart_h + 20}" style="overflow:visible">
  {ticks}
  <line x1="{chance:.1f}" x2="{chance:.1f}" y1="20" y2="{chart_h - 20}" stroke="#D64545" stroke-width="3" stroke-dasharray="8 8" opacity=".55"/>
  <text x="{chance + 8:.1f}" y="{chart_h - 26}" font-family="Nunito" font-weight="800" font-size="19" fill="#D64545" opacity=".75">chance</text>
  {''.join(rows)}
</svg>"""
    costs = "".join(
        f'<div class="slide" style="display:flex;justify-content:space-between;gap:20px;padding:12px 0;border-bottom:2px solid #F3E8DA;animation-delay:{2.2 + i * 0.15:.2f}s;'
        f'font-size:27px;font-weight:{900 if x["key"] == ours_key else 700};color:{"#2FA595" if x["key"] == ours_key else "#4A3326"}">'
        f'<span>{html.escape(x["name"])}</span><span>{money_text(x["cost_per_1k_usd"])}</span></div>'
        for i, x in enumerate(systems))
    mascot = "capy-happy.svg" if rs["win"] == "win" else ("capy.svg" if rs["win"] == "tie" else "capy-oops.svg")
    call = "".join(f'<div style="font-size:{34 if i == 0 else 25}px;font-weight:{900 if i == 0 else 700};margin-top:{0 if i == 0 else 8}px">{html.escape(c)}</div>'
                   for i, c in enumerate(rs["callout"]))
    wm = '<div class="wm">PLACEHOLDER NUMBERS</div>' if s.get("placeholder") else ""
    return deco() + f"""
<div style="position:absolute;left:110px;top:70px"><div class="kicker rise">Results · held-out test set</div>
<div class="h1 rise" style="animation-delay:.15s;font-size:68px">Accuracy on {s['test_pairs']} pairs from {s['test_patients']} new patients</div>
<div class="fade" style="animation-delay:.3s;font-size:25px;font-weight:700;color:#9A8273;margin-top:8px">Bars: accuracy · whiskers: 95% bootstrap confidence interval · balanced 3-way labels (chance = 33%)</div></div>
<div style="position:absolute;left:40px;top:280px">{chart}</div>
<div class="card rise" style="position:absolute;left:1400px;top:280px;width:450px;padding:28px 32px;animation-delay:2s">
  <div style="font-family:Fredoka;font-weight:700;font-size:34px;margin-bottom:8px">Cost per 1,000 screenings</div>{costs}
  <div style="font-size:18px;font-weight:700;color:#9A8273;margin-top:12px">List price × measured tokens</div>
</div>
<div class="card pop" style="position:absolute;left:{x0 + 40}px;top:{min(280 + chart_h + 24, 940)}px;padding:22px 34px;background:#2FA595;color:#fff;animation-delay:3.3s;max-width:820px">{call}</div>
<div class="pop" style="position:absolute;left:1520px;top:760px;animation-delay:3.6s"><img class="bob" src="{capy(mascot)}" style="width:290px;height:290px"></div>
{wm}"""


def scene_close(s: dict) -> str:
    items = ["Expert labels are noisy judgments", "Patient notes are synthetic (TREC)", "Decision support, not a diagnosis"]
    lis = "".join(f'<div class="slide card" style="padding:24px 32px;margin-top:20px;font-size:36px;font-weight:800;animation-delay:{0.5 + i * 0.45:.2f}s">{html.escape(t)}</div>'
                  for i, t in enumerate(items))
    return deco() + f"""
<div style="position:absolute;left:130px;top:150px;width:880px">
  <div class="kicker rise">Honest tradeoffs</div>
  <div class="h1 rise" style="animation-delay:.15s;font-size:76px">Good to know</div>
  {lis}
</div>
<div style="position:absolute;left:1110px;top:120px;width:680px;text-align:center">
  <div class="pop" style="animation-delay:2.4s"><img class="bob" src="{capy('capy-happy.svg')}" style="width:520px;height:520px"></div>
  <div class="rise" style="font-family:Fredoka;font-weight:700;font-size:118px;letter-spacing:-2px;line-height:1;animation-delay:2.8s">
    <span style="color:#5B3A26">Capy</span><span style="color:#2FA595">Match</span></div>
  <div class="rise" style="font-size:30px;font-weight:800;color:#7A6152;margin-top:16px;animation-delay:3.1s">{REPO_URL}</div>
</div>"""


SCENE_BUILDERS = {"title": scene_title, "problem": scene_problem, "approach": scene_approach,
                  "results": scene_results, "close": scene_close}


# ----------------------------------------------------------------------------- assembly
def render_clip(scene_id: str, url: str, html_text: str, duration: float, inject: Path | None) -> Path:
    CLIPS.mkdir(parents=True, exist_ok=True)
    extra = inject.read_text() if inject else ""
    assets_sig = "".join(p.read_text() for p in sorted(ASSETS.glob("capy*.svg")))
    key = hashlib.sha1(f"{html_text}|{extra}|{assets_sig}|{duration:.3f}|{FPS}".encode()).hexdigest()[:16]
    clip = CLIPS / f"{scene_id}_{key}.mp4"
    if clip.exists():
        return clip
    cmd = ["node", str(VID / "render_frames.js"), "--url", url, "--out", str(clip), "--duration", f"{duration:.3f}",
           "--fps", str(FPS), "--fonts", str(FONTS)]
    if inject:
        cmd += ["--inject-json", str(inject)]
    print(f"  rendering {scene_id} ({duration:.1f}s)...", flush=True)
    subprocess.run(cmd, check=True)
    return clip


def srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default=None)
    ap.add_argument("--examples", default=str(ROOT / "demo" / "examples.json"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--dry-run", action="store_true", help="print narration and character counts only")
    ap.add_argument("--preview", action="store_true", help="render one still per scene (no TTS) to video/build/preview_*.png")
    args = ap.parse_args()

    sp = Path(args.summary) if args.summary else (ROOT / "results" / "summary.json")
    if not sp.exists():
        sp = VID / "summary.placeholder.json"
    s = json.loads(sp.read_text())
    placeholder = bool(s.get("placeholder"))
    out = Path(args.out) if args.out else BUILD / ("capymatch_demo_draft.mp4" if placeholder else "capymatch_demo.mp4")
    print(f"summary: {sp} (placeholder={placeholder}) -> {out}")

    lines = narration(s)
    total_chars = sum(len(l["spoken"]) for l in lines)
    for l in lines:
        print(f"[{l['id']}] ({len(l['spoken'])} chars) {l['spoken']}")
    print(f"total narration chars: {total_chars}")
    if args.dry_run:
        return
    if args.preview:
        ensure_fonts()
        SCENES.mkdir(parents=True, exist_ok=True)
        for idx, l in enumerate(lines):
            if l["id"] == "demo":
                url, inject = f"file://{ROOT / 'demo' / 'index.html'}?video=1", ["--inject-json", args.examples]
            else:
                sp_html = SCENES / f"{idx}_{l['id']}.html"
                sp_html.write_text(page(SCENE_BUILDERS[l["id"]](s), placeholder))
                url, inject = f"file://{sp_html}", []
            subprocess.run(["node", str(VID / "render_frames.js"), "--url", url, "--out", str(BUILD / f"preview_{idx}_{l['id']}.png"),
                            "--duration", "1", "--still", "8", "--fonts", str(FONTS), *inject], check=True)
        return

    ensure_fonts()
    SCENES.mkdir(parents=True, exist_ok=True)
    budget = int(os.environ.get("CAPY_TTS_BUDGET", "4000"))
    t, video_list, audio_list, srt = 0.0, [], [], []
    for idx, l in enumerate(lines):
        mp3 = tts(l["spoken"], budget)
        a = duration_of(mp3)
        dur = LEAD + a + (LAST_TAIL if idx == len(lines) - 1 else TAIL)
        if l["id"] == "demo":
            url = f"file://{ROOT / 'demo' / 'index.html'}?video=1"
            html_text = (ROOT / "demo" / "index.html").read_text()
            clip = render_clip(l["id"], url, html_text, dur, Path(args.examples))
        else:
            html_text = page(SCENE_BUILDERS[l["id"]](s), placeholder)
            sp_html = SCENES / f"{idx}_{l['id']}.html"
            sp_html.write_text(html_text)
            clip = render_clip(l["id"], f"file://{sp_html}", html_text, dur, None)
        wav = BUILD / f"audio_{idx}.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp3), "-af", f"adelay={int(LEAD * 1000)}:all=1,apad",
                        "-t", f"{dur:.3f}", "-ar", "48000", "-ac", "2", str(wav)], check=True)
        video_list.append(clip)
        audio_list.append(wav)
        # captions: split into sentences, time proportional to length
        sents = [x for x in re.split(r"(?<=[.!?])\s+", l["caption"]) if x]
        start = t + LEAD
        total = sum(len(x) for x in sents)
        for sent in sents:
            seg = a * len(sent) / total
            srt.append((start, start + seg, sent))
            start += seg
        t += dur

    vlist, alist = BUILD / "video_list.txt", BUILD / "audio_list.txt"
    vlist.write_text("".join(f"file '{p}'\n" for p in video_list))
    alist.write_text("".join(f"file '{p}'\n" for p in audio_list))
    vcat, acat = BUILD / "video_concat.mp4", BUILD / "audio_concat.wav"
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(vlist), "-c", "copy", str(vcat)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(alist), "-c", "copy", str(acat)], check=True)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(vcat), "-i", str(acat), "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-shortest", "-movflags", "+faststart", str(out)], check=True)
    (out.with_suffix(".srt") if out.name != "capymatch_demo.mp4" else BUILD / "captions.srt").write_text(
        "".join(f"{i}\n{srt_time(a)} --> {srt_time(b)}\n{txt}\n\n" for i, (a, b, txt) in enumerate(srt, 1)))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", "2.2", "-i", str(out), "-frames:v", "1", str(out.with_name(out.stem + "_thumb.png"))], check=True)
    total = duration_of(out)
    print(f"done: {out} ({total:.1f}s){'  WARNING: over 110s' if total > 110 else ''}")


if __name__ == "__main__":
    main()
