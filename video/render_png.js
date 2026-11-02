// Render SVG/HTML files to PNG with headless Chromium.
// usage: node video/render_png.js <input.svg|html> <output.png> <width> <height> [transparent=1]
const { chromium } = require('playwright');
const fs = require('fs');
const os = require('os');
const path = require('path');

(async () => {
  const [input, output, w, h, transparent = '1'] = process.argv.slice(2);
  const width = parseInt(w, 10), height = parseInt(h, 10);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 });
  let target = path.resolve(input);
  let tmp = null;
  if (input.endsWith('.svg')) {
    // A file:// page may load file:// images, so wrap the SVG in a temporary HTML file.
    tmp = path.join(os.tmpdir(), `render-${process.pid}-${Date.now()}.html`);
    fs.writeFileSync(tmp, `<!doctype html><html><body style="margin:0;background:transparent">
      <img src="file://${target}" style="width:${width}px;height:${height}px;display:block"></body></html>`);
    target = tmp;
  }
  await page.goto('file://' + target);
  await page.waitForLoadState('networkidle');
  await page.evaluate(async () => { if (document.fonts) await document.fonts.ready; });
  await page.screenshot({ path: output, omitBackground: transparent === '1' });
  await browser.close();
  if (tmp) fs.unlinkSync(tmp);
})();
