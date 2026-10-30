// Video de la mascota: dibuja cada cuadro de mascota.html y lo une con la voz.
// Uso: node render.js guion.json <dir con voz.wav y tiempos.json> salida.mp4 [segundo1 segundo2 ...]
// Con segundos al final, solo guarda esos cuadros como PNG (vista previa).
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');

const FPS = 30;

(async () => {
  const [guionPath, vozDir, out, ...preview] = process.argv.slice(2);
  const guion = JSON.parse(fs.readFileSync(guionPath, 'utf8'));
  const tiempos = JSON.parse(fs.readFileSync(path.join(vozDir, 'tiempos.json'), 'utf8'));

  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('pageerror', e => console.error('page error:', e.message));
  await page.goto('file://' + path.resolve(__dirname, 'mascota.html'));
  await page.waitForFunction(() => window.READY === true, null, { timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(([g, t]) => window.setup(g, t), [guion, tiempos]);

  if (preview.length) {
    for (const s of preview) {
      await page.evaluate(t => window.render(t), +s);
      await page.screenshot({ path: `${out}_${s}.png` });
    }
    await browser.close();
    return;
  }

  const ffmpeg = spawn('ffmpeg', [
    '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-',
    '-i', path.join(vozDir, 'voz.wav'),
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '19', '-preset', 'medium',
    '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', out,
  ], { stdio: ['pipe', 'inherit', 'inherit'] });

  const frames = Math.round(tiempos.duracion * FPS);
  for (let i = 0; i < frames; i++) {
    await page.evaluate(t => window.render(t), i / FPS);
    const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
    if (!ffmpeg.stdin.write(buf)) await new Promise(r => ffmpeg.stdin.once('drain', r));
  }
  ffmpeg.stdin.end();
  await new Promise((res, rej) => ffmpeg.on('close', c => (c === 0 ? res() : rej(new Error('ffmpeg ' + c)))));
  await browser.close();
  console.log(out, frames, 'cuadros');
})();
