// Deterministically render an HTML scene to an H.264 clip by seeking its animations frame by frame.
// usage: node video/render_frames.js --url <file-or-http-url> --out <clip.mp4> --duration <sec> [--fps 30]
//                                   [--inject-json <file.json>]   (sets window.CAPY_EXAMPLES before load)
//                                   [--fonts <dir with fredoka-latin.woff2, nunito-latin.woff2>]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

function arg(name, def) {
  const i = process.argv.indexOf('--' + name);
  return i > -1 ? process.argv[i + 1] : def;
}

(async () => {
  const url = arg('url');
  const out = arg('out');
  const duration = parseFloat(arg('duration'));
  const fps = parseInt(arg('fps', '30'), 10);
  const injectJson = arg('inject-json');
  const fonts = arg('fonts');
  const nFrames = Math.round(duration * fps);

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.addInitScript(json => {
    window.CAPY_VIDEO = true;
    if (json) window.CAPY_EXAMPLES = JSON.parse(json);
  }, injectJson ? fs.readFileSync(injectJson, 'utf8') : null);
  await page.goto(url);
  if (fonts) {
    await page.addStyleTag({ content: `
      @font-face { font-family: 'Fredoka'; src: url('file://${path.resolve(fonts, 'fredoka-latin.woff2')}') format('woff2'); font-weight: 300 700; }
      @font-face { font-family: 'Nunito'; src: url('file://${path.resolve(fonts, 'nunito-latin.woff2')}') format('woff2'); font-weight: 200 1000; }` });
  }
  await page.waitForFunction(() => window.CAPY_READY === true, null, { timeout: 15000 })
    .catch(() => console.error('warning: page never set window.CAPY_READY; rendering anyway'));
  await page.waitForLoadState('networkidle').catch(() => {});
  await page.evaluate(async () => {
    if (document.fonts) await document.fonts.ready;
    await Promise.all([...document.images].map(img => img.complete ? null : new Promise(r => { img.onload = img.onerror = r; })));
  });
  // Freeze every animation; we drive time ourselves.
  await page.evaluate(() => { document.getAnimations().forEach(a => a.pause()); });

  const still = arg('still');
  if (still !== undefined) {   // single PNG at time <still> seconds (layout previews)
    await page.evaluate(ms => { document.getAnimations().forEach(a => { a.pause(); a.currentTime = ms; }); }, parseFloat(still) * 1000);
    await page.screenshot({ path: out, type: 'png' });
    await browser.close();
    console.log(`still @${still}s -> ${out}`);
    return;
  }

  const ff = spawn('ffmpeg', ['-loglevel', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', String(fps), out], { stdio: ['pipe', 'inherit', 'inherit'] });
  const write = buf => new Promise(res => (ff.stdin.write(buf) ? res() : ff.stdin.once('drain', res)));

  for (let f = 0; f < nFrames; f++) {
    const t = (f * 1000) / fps;
    await page.evaluate(ms => {
      document.getAnimations().forEach(a => { a.pause(); a.currentTime = ms; });
    }, t);
    const buf = await page.screenshot({ type: 'jpeg', quality: 93 });
    await write(buf);
  }
  ff.stdin.end();
  await new Promise((res, rej) => ff.on('close', code => (code === 0 ? res() : rej(new Error('ffmpeg exit ' + code)))));
  await browser.close();
  console.log(`rendered ${nFrames} frames -> ${out}`);
})().catch(e => { console.error(e); process.exit(1); });
