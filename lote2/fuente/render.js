// Exporta cada <section class="slide"> de un HTML como PNG de 1080x1350.
// Uso: node lote2/fuente/render.js lote2/fuente/renta-2027.html lote2 renta2027
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const [html, outDir, prefix] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  await page.goto('file://' + path.resolve(html));
  await page.evaluate(() => document.fonts.ready);
  const slides = await page.$$('section.slide');
  for (const [i, slide] of slides.entries()) {
    const file = path.join(outDir, `${prefix}_s${i + 1}.png`);
    await slide.screenshot({ path: file });
    console.log(file);
  }
  await browser.close();
})();
