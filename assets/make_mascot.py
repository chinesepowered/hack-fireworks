"""Generate the CapyMatch mascot SVGs (original artwork).

  python3 assets/make_mascot.py        -> assets/capy.svg, capy-happy.svg, capy-thinking.svg, capy-oops.svg

All four share one body; only the face and the little extras change.
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).resolve().parent

INK = "#5B3A26"          # outline
FUR = "#C99263"          # caramel
FUR_SHADE = "#B27C4E"
FUR_LIGHT = "#E2B486"
MUZZLE = "#A9724A"
MUZZLE_LIGHT = "#BD8758"
EAR_IN = "#8E5C3A"
SCRUB = "#5FC9B9"
SCRUB_SHADE = "#45B2A2"
SCRUB_LIGHT = "#8EDDD0"
BLUSH = "#FF8FA0"
YUZU = "#FFB23F"
YUZU_LIGHT = "#FFD58A"
LEAF = "#69C46B"
STETH = "#3E4C5E"
STEEL = "#CCD6E0"
BOARD = "#D99A5B"
PAPER = "#FFFDF7"
CHECK = "#3DB862"
SW = 7  # stroke width

DEFS = f"""
  <defs>
    <radialGradient id="g-head" cx="45%" cy="35%" r="70%">
      <stop offset="0%" stop-color="{FUR_LIGHT}"/>
      <stop offset="55%" stop-color="{FUR}"/>
      <stop offset="100%" stop-color="{FUR_SHADE}"/>
    </radialGradient>
    <radialGradient id="g-muzzle" cx="50%" cy="30%" r="75%">
      <stop offset="0%" stop-color="{MUZZLE_LIGHT}"/>
      <stop offset="100%" stop-color="{MUZZLE}"/>
    </radialGradient>
    <linearGradient id="g-scrub" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="{SCRUB_LIGHT}"/>
      <stop offset="45%" stop-color="{SCRUB}"/>
      <stop offset="100%" stop-color="{SCRUB_SHADE}"/>
    </linearGradient>
    <radialGradient id="g-yuzu" cx="38%" cy="32%" r="70%">
      <stop offset="0%" stop-color="{YUZU_LIGHT}"/>
      <stop offset="60%" stop-color="{YUZU}"/>
      <stop offset="100%" stop-color="#F29A2A"/>
    </radialGradient>
  </defs>"""


def body() -> str:
    return f"""
  <!-- soft ground shadow -->
  <ellipse cx="256" cy="488" rx="140" ry="13" fill="#000" opacity="0.08"/>
  <!-- feet -->
  <ellipse cx="200" cy="470" rx="36" ry="19" fill="{MUZZLE}" stroke="{INK}" stroke-width="{SW}"/>
  <ellipse cx="312" cy="470" rx="36" ry="19" fill="{MUZZLE}" stroke="{INK}" stroke-width="{SW}"/>
  <!-- chubby barrel body in scrubs -->
  <path d="M150 334 C 124 384, 128 452, 180 468 L 332 468 C 384 452, 388 384, 362 334 C 332 302, 180 302, 150 334 Z"
        fill="url(#g-scrub)" stroke="{INK}" stroke-width="{SW}" stroke-linejoin="round"/>
  <path d="M172 444 Q 256 456 340 444" fill="none" stroke="{SCRUB_SHADE}" stroke-width="4" stroke-linecap="round"/>
  <!-- V-neck showing fur -->
  <path d="M216 312 L 256 360 L 296 312 Z" fill="{FUR}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>
  <!-- stethoscope draped around the neck -->
  <path d="M206 318 C 190 344, 192 372, 214 386" fill="none" stroke="{STETH}" stroke-width="7" stroke-linecap="round"/>
  <path d="M306 318 C 322 344, 320 372, 298 386" fill="none" stroke="{STETH}" stroke-width="7" stroke-linecap="round"/>"""


def clipboard() -> str:
    return f"""
  <!-- clipboard hugged to the chest -->
  <g transform="rotate(-5 256 412)">
    <rect x="200" y="356" width="112" height="112" rx="14" fill="{BOARD}" stroke="{INK}" stroke-width="{SW}" stroke-linejoin="round"/>
    <rect x="212" y="370" width="88" height="88" rx="7" fill="{PAPER}" stroke="{INK}" stroke-width="3.5"/>
    <rect x="234" y="346" width="44" height="22" rx="8" fill="{STEEL}" stroke="{INK}" stroke-width="5"/>
    <path d="M222 392 l7 7 l12 -14" fill="none" stroke="{CHECK}" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M248 392 h38" stroke="#CFC5B8" stroke-width="5" stroke-linecap="round"/>
    <path d="M222 416 l7 7 l12 -14" fill="none" stroke="{CHECK}" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M248 416 h30" stroke="#CFC5B8" stroke-width="5" stroke-linecap="round"/>
    <path d="M222 440 l7 7 l12 -14" fill="none" stroke="{CHECK}" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M248 440 h24" stroke="#CFC5B8" stroke-width="5" stroke-linecap="round"/>
  </g>
  <!-- stethoscope chest piece peeking out -->
  <circle cx="318" cy="388" r="12" fill="{STEEL}" stroke="{STETH}" stroke-width="5"/>
  <circle cx="318" cy="388" r="4" fill="#FFFFFF"/>
  <!-- stubby arms + paws holding the clipboard -->
  <path d="M170 352 C 174 386, 186 404, 204 410" fill="none" stroke="{INK}" stroke-width="27" stroke-linecap="round"/>
  <path d="M170 352 C 174 386, 186 404, 204 410" fill="none" stroke="{SCRUB}" stroke-width="15" stroke-linecap="round"/>
  <circle cx="208" cy="410" r="16" fill="{FUR}" stroke="{INK}" stroke-width="{SW}"/>
  <path d="M342 352 C 338 386, 326 404, 308 410" fill="none" stroke="{INK}" stroke-width="27" stroke-linecap="round"/>
  <path d="M342 352 C 338 386, 326 404, 308 410" fill="none" stroke="{SCRUB}" stroke-width="15" stroke-linecap="round"/>
  <circle cx="304" cy="410" r="16" fill="{FUR}" stroke="{INK}" stroke-width="{SW}"/>"""


def head() -> str:
    return f"""
  <!-- small rounded side ears -->
  <ellipse cx="152" cy="112" rx="19" ry="14" transform="rotate(-32 152 112)" fill="{FUR}" stroke="{INK}" stroke-width="{SW}"/>
  <ellipse cx="154" cy="114" rx="8" ry="5.5" transform="rotate(-32 154 114)" fill="{EAR_IN}"/>
  <ellipse cx="360" cy="112" rx="19" ry="14" transform="rotate(32 360 112)" fill="{FUR}" stroke="{INK}" stroke-width="{SW}"/>
  <ellipse cx="358" cy="114" rx="8" ry="5.5" transform="rotate(32 358 114)" fill="{EAR_IN}"/>
  <!-- tall, soft, boxy capybara head -->
  <path d="M256 88 C 330 88, 370 98, 374 158 C 378 220, 394 292, 302 316 C 282 320, 230 320, 210 316 C 118 292, 134 220, 138 158 C 142 98, 182 88, 256 88 Z"
        fill="url(#g-head)" stroke="{INK}" stroke-width="{SW}" stroke-linejoin="round"/>
  <!-- tuft -->
  <path d="M240 90 q 8 -13 16 0 q 8 -13 16 0" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
  <!-- nose bridge highlight -->
  <ellipse cx="256" cy="170" rx="30" ry="52" fill="{FUR_LIGHT}" opacity="0.45"/>
  <!-- broad, flat-topped capybara muzzle -->
  <path d="M256 200 C 320 200, 358 208, 360 246 C 362 288, 322 310, 256 310 C 190 310, 150 288, 152 246 C 154 208, 192 200, 256 200 Z"
        fill="url(#g-muzzle)" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>
  <!-- big dark nose -->
  <path d="M220 222 Q 256 206 292 222 Q 302 236 286 246 Q 256 256 226 246 Q 210 236 220 222 Z" fill="{INK}"/>
  <ellipse cx="242" cy="222" rx="10" ry="4.5" fill="#fff" opacity="0.55"/>
  <!-- blush -->
  <ellipse cx="164" cy="226" rx="20" ry="11" fill="{BLUSH}" opacity="0.62"/>
  <ellipse cx="348" cy="226" rx="20" ry="11" fill="{BLUSH}" opacity="0.62"/>"""


def mouth_rodent(teeth: bool = True) -> str:
    t = (f'<rect x="248" y="268" width="7.5" height="11" rx="2.5" fill="#FFFFFF" stroke="{INK}" stroke-width="2.6"/>'
         f'<rect x="256.5" y="268" width="7.5" height="11" rx="2.5" fill="#FFFFFF" stroke="{INK}" stroke-width="2.6"/>') if teeth else ""
    return f"""
  <!-- rodent mouth -->
  <path d="M256 251 L 256 262" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
  {t}
  <path d="M236 262 Q 246 274 256 262 Q 266 274 276 262" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>"""


def yuzu() -> str:
    return f"""
  <!-- yuzu on head -->
  <g>
    <circle cx="256" cy="60" r="30" fill="url(#g-yuzu)" stroke="{INK}" stroke-width="{SW}"/>
    <circle cx="246" cy="50" r="2.4" fill="#F29A2A" opacity="0.7"/>
    <circle cx="266" cy="66" r="2.4" fill="#F29A2A" opacity="0.7"/>
    <circle cx="254" cy="72" r="2.0" fill="#F29A2A" opacity="0.7"/>
    <ellipse cx="244" cy="48" rx="8" ry="5" fill="#FFF3D6" opacity="0.85" transform="rotate(-30 244 48)"/>
    <path d="M256 31 q -2 -10 4 -14" fill="none" stroke="{INK}" stroke-width="4.5" stroke-linecap="round"/>
    <path d="M260 22 C 272 6, 296 10, 300 20 C 286 30, 268 30, 260 22 Z" fill="{LEAF}" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>
    <path d="M266 22 C 276 18, 286 18, 294 20" fill="none" stroke="#4FA352" stroke-width="2.5" stroke-linecap="round"/>
  </g>"""


def sparkly_eyes(dy: int = 0) -> str:
    return f"""
  <g transform="translate(0 {dy})">
    <ellipse cx="180" cy="164" rx="17" ry="20" fill="{INK}"/>
    <ellipse cx="332" cy="164" rx="17" ry="20" fill="{INK}"/>
    <circle cx="187" cy="156" r="6.5" fill="#fff"/>
    <circle cx="339" cy="156" r="6.5" fill="#fff"/>
    <circle cx="174" cy="173" r="3.2" fill="#fff"/>
    <circle cx="326" cy="173" r="3.2" fill="#fff"/>
  </g>"""


def eyes_content() -> str:
    return sparkly_eyes() + mouth_rodent()


def eyes_happy() -> str:
    return f"""
  <path d="M162 170 Q 180 146 198 170" fill="none" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>
  <path d="M314 170 Q 332 146 350 170" fill="none" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>
  <!-- open happy mouth -->
  <path d="M238 258 Q 256 290 274 258 Z" fill="#E8546B" stroke="{INK}" stroke-width="5" stroke-linejoin="round"/>
  <path d="M246 270 Q 256 280 266 270" fill="#FF9AAE" stroke="none"/>
  <!-- sparkles + hearts -->
  <g fill="#FFD23F" stroke="{INK}" stroke-width="3" stroke-linejoin="round">
    <path d="M86 132 l6 -16 l6 16 l16 6 l-16 6 l-6 16 l-6 -16 l-16 -6 z"/>
    <path d="M428 96 l4 -11 l4 11 l11 4 l-11 4 l-4 11 l-4 -11 l-11 -4 z"/>
  </g>
  <g fill="#FF6F8A" stroke="{INK}" stroke-width="3.5" stroke-linejoin="round">
    <path d="M430 168 c -10 -14 -32 -2 -20 14 l 20 18 l 20 -18 c 12 -16 -10 -28 -20 -14 z"/>
    <path d="M78 214 c -7 -10 -22 -1 -14 10 l 14 12 l 14 -12 c 8 -11 -7 -20 -14 -10 z"/>
  </g>"""


def eyes_thinking() -> str:
    return f"""
  <g>
    <ellipse cx="178" cy="168" rx="15" ry="17" fill="{INK}"/>
    <ellipse cx="334" cy="168" rx="15" ry="17" fill="{INK}"/>
    <circle cx="182" cy="158" r="6" fill="#fff"/>
    <circle cx="338" cy="158" r="6" fill="#fff"/>
  </g>
  <!-- one eyebrow raised -->
  <path d="M312 132 q 22 -12 42 0" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
  <path d="M158 140 q 20 -6 40 0" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
  <!-- small 'o' mouth -->
  <ellipse cx="256" cy="270" rx="8" ry="9" fill="#8C3B3B" stroke="{INK}" stroke-width="4"/>
  <!-- thought dots -->
  <g fill="#FFFFFF" stroke="{INK}" stroke-width="4">
    <circle cx="400" cy="70" r="9"/>
    <circle cx="428" cy="44" r="13"/>
    <circle cx="466" cy="22" r="17"/>
  </g>"""


def eyes_oops() -> str:
    return f"""
  <g>
    <ellipse cx="178" cy="170" rx="13" ry="15" fill="{INK}"/>
    <ellipse cx="334" cy="170" rx="13" ry="15" fill="{INK}"/>
    <circle cx="182" cy="164" r="4.5" fill="#fff"/>
    <circle cx="338" cy="164" r="4.5" fill="#fff"/>
  </g>
  <!-- worried brows -->
  <path d="M156 142 L 196 132" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
  <path d="M356 142 L 316 132" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
  <!-- wobbly flat mouth -->
  <path d="M238 270 q 6 -6 12 0 q 6 6 12 0 q 6 -6 12 0" fill="none" stroke="{INK}" stroke-width="5" stroke-linecap="round"/>
  <!-- sweat drop -->
  <path d="M392 138 C 380 158, 382 176, 396 178 C 410 176, 412 158, 400 138 C 398 134, 394 134, 392 138 Z"
        fill="#9FD8FF" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>
  <ellipse cx="392" cy="166" rx="3" ry="5" fill="#fff" opacity="0.9"/>"""


def svg(face: str, title: str) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" aria-label="{title}">
  <title>{title}</title>{DEFS}{body()}{clipboard()}{head()}{face}{yuzu()}
</svg>
"""


VARIANTS = {
    "capy.svg": (eyes_content, "CapyMatch mascot: a calm capybara in scrubs with a clipboard"),
    "capy-happy.svg": (eyes_happy, "CapyMatch mascot, happy: eligible match"),
    "capy-thinking.svg": (eyes_thinking, "CapyMatch mascot, thinking: screening"),
    "capy-oops.svg": (eyes_oops, "CapyMatch mascot, oops: not a match"),
}

if __name__ == "__main__":
    for name, (face, title) in VARIANTS.items():
        (OUT / name).write_text(svg(face(), title))
        print("wrote", OUT / name)
