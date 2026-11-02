"""Build assets/banner.svg (self-contained) and an HTML wrapper used to render banner.png with web fonts.

  python3 assets/make_banner.py
  node video/render_png.js video/build/banner_render.html assets/banner.png 1600 500 0
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
BUILD = ROOT / "video" / "build"

FONT_STACK_DISPLAY = "Fredoka, 'Baloo 2', 'Nunito', 'Arial Rounded MT Bold', 'Segoe UI', Arial, sans-serif"
FONT_STACK_BODY = "Nunito, 'Segoe UI', Roboto, Arial, sans-serif"


def mascot_inner(name: str = "capy.svg") -> str:
    svg = (ASSETS / name).read_text()
    inner = re.sub(r"^.*?<svg[^>]*>", "", svg, count=1, flags=re.S)
    inner = inner.rsplit("</svg>", 1)[0]
    return re.sub(r"<title>.*?</title>", "", inner, flags=re.S)


def banner_svg() -> str:
    deco = """
    <g opacity="0.9">
      <circle cx="300" cy="250" r="230" fill="#DDF4EF"/>
      <circle cx="300" cy="250" r="230" fill="none" stroke="#C3EAE2" stroke-width="6" stroke-dasharray="2 18" stroke-linecap="round"/>
      <g fill="#FFC7CF"><circle cx="92" cy="86" r="9"/><circle cx="560" cy="442" r="7"/><circle cx="1500" cy="70" r="8"/></g>
      <g fill="#BFE7DF"><circle cx="1452" cy="420" r="11"/><circle cx="700" cy="60" r="6"/></g>
      <g stroke="#7FD3C5" stroke-width="9" stroke-linecap="round">
        <path d="M86 380 v32 M70 396 h32"/>
        <path d="M1530 230 v26 M1517 243 h26"/>
      </g>
      <g stroke="#FFB9A2" stroke-width="8" stroke-linecap="round">
        <path d="M540 70 v24 M528 82 h24"/>
      </g>
    </g>"""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 500" width="1600" height="500" role="img" aria-label="CapyMatch banner">
  <title>CapyMatch: matching patients to clinical trials with fine-tuned open models on Fireworks</title>
  <rect x="0" y="0" width="1600" height="500" rx="36" fill="#FFF6EA"/>{deco}
  <svg x="70" y="24" width="460" height="460" viewBox="0 0 512 512">{mascot_inner()}</svg>
  <text x="600" y="232" font-family="{FONT_STACK_DISPLAY}" font-size="150" font-weight="700" letter-spacing="-2">
    <tspan fill="#5B3A26">Capy</tspan><tspan fill="#2FA595">Match</tspan>
  </text>
  <text x="606" y="304" font-family="{FONT_STACK_BODY}" font-size="35" font-weight="700" fill="#6B5040">Matching patients to clinical trials</text>
  <text x="606" y="350" font-family="{FONT_STACK_BODY}" font-size="35" font-weight="700" fill="#6B5040">with fine-tuned open models on Fireworks</text>
  <g font-family="{FONT_STACK_BODY}" font-size="24" font-weight="800">
    <rect x="606" y="384" width="290" height="50" rx="25" fill="#5B3A26"/>
    <text x="751" y="417" text-anchor="middle" fill="#FFF6EA">NVIDIA Nemotron</text>
    <rect x="912" y="384" width="236" height="50" rx="25" fill="#2FA595"/>
    <text x="1030" y="417" text-anchor="middle" fill="#FFFFFF">Fireworks AI</text>
    <rect x="1164" y="384" width="270" height="50" rx="25" fill="#FFE2C2"/>
    <text x="1299" y="417" text-anchor="middle" fill="#8A4B1F">TREC Clinical Trials</text>
  </g>
</svg>
"""


def font_faces() -> str:
    fonts = BUILD / "fonts"
    return f"""
@font-face {{ font-family: 'Fredoka'; src: url('file://{fonts / "fredoka-latin.woff2"}') format('woff2'); font-weight: 300 700; }}
@font-face {{ font-family: 'Nunito'; src: url('file://{fonts / "nunito-latin.woff2"}') format('woff2'); font-weight: 200 1000; }}"""


if __name__ == "__main__":
    svg = banner_svg()
    (ASSETS / "banner.svg").write_text(svg)
    BUILD.mkdir(parents=True, exist_ok=True)
    (BUILD / "banner_render.html").write_text(
        f"<!doctype html><html><head><style>{font_faces()}\nbody{{margin:0;background:transparent}}</style></head>"
        f"<body>{svg}</body></html>"
    )
    print("wrote assets/banner.svg and video/build/banner_render.html")
