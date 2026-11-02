# Demo video pipeline

The demo video is generated from code, so it always matches the numbers in `results/summary.json`.

```
python3 video/build.py                 # final: reads results/summary.json -> video/build/capymatch_demo.mp4 (+ captions.srt)
python3 video/build.py --dry-run       # print the narration (and its character count) without calling any API
python3 video/build.py --preview       # one still per scene -> video/build/preview_*.png (no TTS)
```

How it works:

1. **Narration** is written by `narration()` in `build.py`. The results line is conditional on the
   numbers (a win is only claimed when the 95% confidence interval for the accuracy difference is above zero).
2. **Voice**: ElevenLabs text-to-speech, voice *Jessica* (`cgSgspJ2msm6clMCkdW9`, young American female),
   model `eleven_v4`. Each line is cached in `video/build/audio/` by a hash of voice, model, settings and text,
   so rebuilding after a results change only re-synthesizes the changed line. A character ledger caps spend
   (`CAPY_TTS_BUDGET`, default 4000 characters). Needs `ELEVENLABS_API_KEY` for uncached lines.
3. **Scenes** are HTML pages (1920x1080) with CSS animations; the demo scene is `demo/index.html` itself, fed with
   `demo/examples.json`. `video/render_frames.js` opens each page in headless Chromium (Playwright), pauses every
   animation, and seeks it frame by frame at 30 fps, piping JPEG frames into ffmpeg. Output is deterministic.
4. **Assembly**: per-scene clips and narration (with a short lead-in and tail) are concatenated and muxed to
   H.264 + AAC with `+faststart`; captions are written as SRT and a thumbnail PNG is extracted.

Requirements: Python 3, Node with `playwright` (Chromium), ffmpeg/ffprobe. Fonts (Fredoka, Nunito; SIL OFL)
are downloaded from Google Fonts into `video/build/fonts/` on first run.
