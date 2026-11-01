// Exporta cada <section class="slide"> como PNG de 1080x1350, con el id como nombre.
// Uso: node lote4/fuente/render.js lote4/fuente/noviembre.html lote4
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const [html, outDir] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1350 } });
  await page.goto('file://' + path.resolve(html));
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(300);
  const slides = await page.$$('section.slide');
  for (const slide of slides) {
    const id = await slide.getAttribute('id');
    // Avisa si algún elemento se sale del área de la pieza
    const over = await slide.evaluate(s => {
      const r = s.getBoundingClientRect();
      return [...s.querySelectorAll('*')].filter(e => !e.closest('.deco') && !e.classList.contains('photo') && !e.classList.contains('photo-fade') && !e.closest('svg'))
        .some(e => { const b = e.getBoundingClientRect(); return b.height > 0 && (b.bottom > r.bottom - 40 || b.right > r.right + 1); });
    });
    const file = path.join(outDir, `${id}.png`);
    await slide.screenshot({ path: file });
    console.log(file, over ? '  <-- REVISAR: contenido cerca del borde' : '');
  }
  await browser.close();
})();
