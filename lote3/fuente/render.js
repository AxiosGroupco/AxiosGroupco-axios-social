// Video vertical con la mascota narrando: dibuja cada cuadro de video.html y lo une con el audio.
// Uso: node render.js tiempos.json audio.(wav|m4a) salida.mp4 [segundo1 segundo2 ...]
// Con segundos al final solo guarda esos cuadros como PNG (vista previa). Con audio "-" el video sale sin sonido.
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');

const FPS = 30;

(async () => {
  const [tiemposPath, audio, out, ...vista] = process.argv.slice(2);
  const escenas = JSON.parse(fs.readFileSync(path.join(__dirname, 'escenas.json'), 'utf8'));
  const tiempos = JSON.parse(fs.readFileSync(tiemposPath, 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 } });
  page.on('pageerror', e => console.error('error en la página:', e.message));
  await page.goto('file://' + path.resolve(__dirname, 'video.html'));
  await page.waitForFunction(() => window.READY === true);
  await page.evaluate(() => Promise.all([document.fonts.ready, ...[...document.images].map(i => i.decode().catch(() => {}))]));
  await page.evaluate(([e, t]) => window.setup(e, t), [escenas, tiempos]);

  if (vista.length) {
    for (const s of vista) {
      await page.evaluate(t => window.render(t), +s);
      await page.screenshot({ path: `${out}_${s}.png` });
    }
    await browser.close();
    return;
  }

  const args = ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-i', '-'];
  if (audio !== '-') args.push('-i', audio);
  args.push('-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20', '-preset', 'medium');
  if (audio !== '-') args.push('-c:a', 'aac', '-b:a', '192k', '-shortest');
  args.push('-movflags', '+faststart', out);
  const ffmpeg = spawn('ffmpeg', args, { stdio: ['pipe', 'inherit', 'inherit'] });

  const cuadros = Math.round(tiempos.duracion * FPS);
  for (let i = 0; i < cuadros; i++) {
    await page.evaluate(t => window.render(t), i / FPS);
    const buf = await page.screenshot({ type: 'jpeg', quality: 92 });
    if (!ffmpeg.stdin.write(buf)) await new Promise(r => ffmpeg.stdin.once('drain', r));
  }
  ffmpeg.stdin.end();
  await new Promise((res, rej) => ffmpeg.on('close', c => (c === 0 ? res() : rej(new Error('ffmpeg ' + c)))));
  await browser.close();
  console.log(out, cuadros, 'cuadros');
})();
