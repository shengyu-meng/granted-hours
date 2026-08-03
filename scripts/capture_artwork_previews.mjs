#!/usr/bin/env node
/** Capture archive previews for Granted Hours live artworks.
 *
 * Requirements: Node.js, Playwright, ffmpeg.
 * Usage:
 *   node scripts/capture_artwork_previews.mjs --all
 *   node scripts/capture_artwork_previews.mjs --date 2026-05-11
 *   node scripts/capture_artwork_previews.mjs --all --visual-only
 *   node scripts/capture_artwork_previews.mjs --date 2026-07-31 --archive-only
 *   node scripts/capture_artwork_previews.mjs --date 2026-07-31 --deterministic-gif
 */
import { chromium } from 'playwright';
import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const getArg = (name) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : null;
};
const all = args.includes('--all');
const visualOnly = args.includes('--visual-only');
const archiveOnly = args.includes('--archive-only');
const deterministicGif = args.includes('--deterministic-gif');
const missingOnly = args.includes('--missing');
const dateFilter = getArg('--date');
const PREVIEW_SPECS = Object.freeze({
  'preview.png': { width: 1600, height: 900 },
  'preview.gif': { width: 720, height: 405 },
  'visual-preview.webp': { width: 960, height: 540 },
});
const displayAllowances = JSON.parse(
  fs.readFileSync(path.join(ROOT, 'metadata', 'artwork-display-allowances.json'), 'utf8'),
).days;

function listEntries() {
  const archiveRoot = path.join(ROOT, 'docs', 'archive');
  const entries = [];
  if (!fs.existsSync(archiveRoot)) return entries;
  for (const year of fs.readdirSync(archiveRoot).filter(d => /^\d{4}$/.test(d))) {
    const yearDir = path.join(archiveRoot, year);
    for (const month of fs.readdirSync(yearDir).filter(d => /^\d{2}$/.test(d))) {
      const monthDir = path.join(yearDir, month);
      for (const day of fs.readdirSync(monthDir).filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d))) {
        if (dateFilter && day !== dateFilter) continue;
        const entryDir = path.join(monthDir, day);
        if (missingOnly && fs.existsSync(path.join(entryDir, 'assets', 'visual-preview.webp'))) continue;
        if (fs.existsSync(path.join(entryDir, 'live', 'index.html'))) entries.push(entryDir);
      }
    }
  }
  return entries.sort();
}

function run(cmd, cmdArgs, opts = {}) {
  const res = spawnSync(cmd, cmdArgs, { encoding: 'utf-8', stdio: 'pipe', ...opts });
  if (res.status !== 0) {
    throw new Error(`${cmd} ${cmdArgs.join(' ')} failed\nSTDOUT:\n${res.stdout}\nSTDERR:\n${res.stderr}`);
  }
  return res;
}

function probeVisual(filePath) {
  const result = run('ffprobe', [
    '-v', 'error', '-select_streams', 'v:0',
    '-show_entries', 'stream=width,height',
    '-of', 'json', filePath,
  ]);
  const stream = JSON.parse(result.stdout).streams?.[0] || {};
  return { width: Number(stream.width), height: Number(stream.height) };
}

function assertPreviewSpec(filePath, assetName) {
  const expected = PREVIEW_SPECS[assetName];
  const actual = probeVisual(filePath);
  if (actual.width !== expected.width || actual.height !== expected.height) {
    throw new Error(
      `${path.basename(path.dirname(path.dirname(filePath)))} ${assetName} must be `
      + `${expected.width}x${expected.height} landscape; got ${actual.width}x${actual.height}`,
    );
  }
}

function animateFullFrameStill(stillPath, outputPath) {
  const motion = [
    "scale=736:414:flags=lanczos",
    "zoompan=z='1+0.012*sin(on*PI/47)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=48:s=720x405:fps=12",
  ].join(',');
  const filter = `${motion},split[gifbase][palettebase];`
    + '[palettebase]palettegen=max_colors=128:stats_mode=full[palette];'
    + '[gifbase][palette]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle';
  run('ffmpeg', [
    '-y', '-v', 'error', '-i', stillPath,
    '-filter_complex', filter,
    '-frames:v', '48', '-loop', '0', outputPath,
  ]);
}

function startStaticServer() {
  const mimeTypes = {
    '.css': 'text/css; charset=utf-8',
    '.gif': 'image/gif',
    '.html': 'text/html; charset=utf-8',
    '.jpeg': 'image/jpeg',
    '.jpg': 'image/jpeg',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.mp3': 'audio/mpeg',
    '.png': 'image/png',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
  };
  const server = http.createServer((request, response) => {
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(request.url, 'http://127.0.0.1').pathname);
    } catch {
      response.writeHead(400).end();
      return;
    }
    const requested = path.resolve(ROOT, `.${pathname}`);
    if (requested !== ROOT && !requested.startsWith(`${ROOT}${path.sep}`)) {
      response.writeHead(403).end();
      return;
    }
    let filePath = requested;
    try {
      if (fs.statSync(filePath).isDirectory()) filePath = path.join(filePath, 'index.html');
      const stat = fs.statSync(filePath);
      if (!stat.isFile()) throw new Error('not a file');
      response.writeHead(200, {
        'Cache-Control': 'no-store',
        'Content-Length': stat.size,
        'Content-Type': mimeTypes[path.extname(filePath).toLowerCase()] || 'application/octet-stream',
      });
      fs.createReadStream(filePath).pipe(response);
    } catch {
      // Never expose a directory index: a missing index.html is a hard 404.
      response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Not found');
    }
  });
  return new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const address = server.address();
      resolve({
        baseUrl: `http://127.0.0.1:${address.port}`,
        close: () => new Promise((done) => server.close(done)),
      });
    });
  });
}

function artworkUrl(entryDir, serverBaseUrl) {
  const live = path.join(entryDir, 'live', 'index.html');
  const relative = path.relative(ROOT, live).split(path.sep).join('/');
  if (relative.startsWith('../')) throw new Error(`Artwork left repository root: ${entryDir}`);
  return `${serverBaseUrl}/${relative}`;
}

async function openLiveArtwork(page, entryDir, serverBaseUrl, waitUntil = 'networkidle') {
  const expectedUrl = artworkUrl(entryDir, serverBaseUrl);
  const response = await page.goto(expectedUrl, { waitUntil, timeout: 45000 });
  const contentType = response?.headers()['content-type'] || '';
  if (!response?.ok() || !contentType.startsWith('text/html')) {
    throw new Error(
      `${path.basename(entryDir)} live route returned ${response?.status()} ${contentType || 'without content type'}`,
    );
  }
  const state = await page.evaluate(() => ({
    href: window.location.href,
    canvasCount: document.querySelectorAll('canvas').length,
    directoryIndex: /(?:Index of|Directory listing for|\[上级目录\])/i.test(document.body.innerText),
  }));
  if (state.href !== expectedUrl || state.directoryIndex) {
    throw new Error(`${path.basename(entryDir)} resolved outside its live artwork: ${JSON.stringify(state)}`);
  }
  return expectedUrl;
}

async function waitForCanvas(page, settleMs = 1800, timeout = 20000) {
  await page.waitForSelector('canvas', { timeout });
  await page.waitForTimeout(settleMs);
  const info = await page.evaluate(() => {
    const canvases = [...document.querySelectorAll('canvas')];
    const c = canvases
      .filter((canvas) => {
        const rect = canvas.getBoundingClientRect();
        const style = getComputedStyle(canvas);
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 1 && rect.height > 1;
      })
      .sort((a, b) => {
        const ar = a.getBoundingClientRect();
        const br = b.getBoundingClientRect();
        return br.width * br.height - ar.width * ar.height;
      })[0];
    if (c) c.dataset.grantedHoursVisualCanvas = 'true';
    const rect = c?.getBoundingClientRect();
    return {
      count: canvases.length,
      w: c?.width,
      h: c?.height,
      cssWidth: rect?.width,
      cssHeight: rect?.height,
    };
  });
  if (!info.count || !info.w || !info.h || !info.cssWidth || !info.cssHeight) {
    throw new Error(`Canvas did not initialize: ${JSON.stringify(info)}`);
  }
  return info;
}

async function suppressCanvasText(page) {
  await page.addInitScript(() => {
    window.__GRANTED_HOURS_VISUAL_PREVIEW__ = true;
    const noText = () => {};
    for (const name of ['fillText', 'strokeText']) {
      Object.defineProperty(CanvasRenderingContext2D.prototype, name, {
        configurable: true,
        value: noText,
        writable: true,
      });
    }
    if (window.OffscreenCanvasRenderingContext2D) {
      for (const name of ['fillText', 'strokeText']) {
        Object.defineProperty(OffscreenCanvasRenderingContext2D.prototype, name, {
          configurable: true,
          value: noText,
          writable: true,
        });
      }
    }
  });
}

async function isolateVisualCanvas(page) {
  await page.evaluate(() => {
    const canvas = document.querySelector('canvas[data-granted-hours-visual-canvas="true"]');
    if (!canvas) throw new Error('Visual canvas marker is missing');
    for (const element of document.body.querySelectorAll('*')) {
      if (element === canvas || element.contains(canvas)) continue;
      element.style.setProperty('visibility', 'hidden', 'important');
      element.style.setProperty('opacity', '0', 'important');
      element.style.setProperty('pointer-events', 'none', 'important');
    }
    const isolation = document.createElement('style');
    isolation.textContent = `
      body *:not(canvas):not(:has(canvas))::before,
      body *:not(canvas):not(:has(canvas))::after {
        visibility: hidden !important;
        opacity: 0 !important;
      }
    `;
    document.head.append(isolation);
  });
}

async function primeInteraction(page, width, height, settleMs = 900) {
  // Some works intentionally reveal more under a human gesture.
  // For archive previews, capture the artwork in an activated/exhibited state,
  // not as a cold untouched browser frame.
  await page.mouse.move(width * 0.52, height * 0.52, { steps: 18 });
  await page.mouse.click(width * 0.52, height * 0.52);
  await page.waitForTimeout(settleMs);
}

async function movePreviewMouse(page, frame, total, width, height) {
  const t = frame / Math.max(1, total - 1);
  const x = width * (0.18 + 0.64 * (0.5 + 0.5 * Math.sin(t * Math.PI * 2)));
  const y = height * (0.22 + 0.56 * (0.5 + 0.5 * Math.sin(t * Math.PI * 2 * 1.37 + 1.1)));
  await page.mouse.move(x, y, { steps: 2 });
  if (frame === 4 || frame === Math.floor(total / 2)) await page.mouse.click(x, y);
}

async function captureEntry(browser, entryDir, serverBaseUrl) {
  const assets = path.join(entryDir, 'assets');
  fs.mkdirSync(assets, { recursive: true });

  // Full-frame still: large landscape viewport, full visible page. This avoids the old half-window thumbnails.
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  await openLiveArtwork(page, entryDir, serverBaseUrl);
  const info = await waitForCanvas(page);
  await primeInteraction(page, 1600, 900);
  const previewPng = path.join(assets, 'preview.png');
  await page.screenshot({ path: previewPng, fullPage: false });
  assertPreviewSpec(previewPng, 'preview.png');
  await page.close();

  // GIF: smaller viewport, 4 seconds at 12fps to keep repo size reasonable.
  // Frames are streamed directly to ffmpeg so no temp frame directory needs deletion.
  const gifPath = path.join(assets, 'preview.gif');
  const partialGifPath = path.join(assets, '.preview.partial.gif');
  let gifMode = 'deterministic-full-frame';
  if (deterministicGif) {
    animateFullFrameStill(previewPng, partialGifPath);
    fs.renameSync(partialGifPath, gifPath);
  } else {
    const gifPage = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 1 });
    const expectedUrl = await openLiveArtwork(gifPage, entryDir, serverBaseUrl);
    await waitForCanvas(gifPage);
    await primeInteraction(gifPage, 960, 540);
    const gifFilter = [
      'fps=12,scale=720:-1:flags=lanczos',
      'split[gif][paletteSource]',
      '[paletteSource]palettegen=max_colors=128:stats_mode=diff[palette]',
      '[gif][palette]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle',
    ].join(';');
    const ff = spawn('ffmpeg', [
      '-y', '-v', 'error',
      '-f', 'image2pipe', '-framerate', '12', '-i', '-',
      '-filter_complex', gifFilter,
      '-loop', '0', partialGifPath,
    ], { stdio: ['pipe', 'pipe', 'pipe'] });
    let ffmpegErr = '';
    ff.stderr.on('data', d => { ffmpegErr += d.toString(); });
    const total = 48;
    try {
      for (let i = 0; i < total; i++) {
        await movePreviewMouse(gifPage, i, total, 960, 540);
        const frameState = await gifPage.evaluate(() => ({
          href: window.location.href,
          visibleCanvas: [...document.querySelectorAll('canvas')].some((canvas) => {
            const rect = canvas.getBoundingClientRect();
            const style = getComputedStyle(canvas);
            return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 1 && rect.height > 1;
          }),
        }));
        if (frameState.href !== expectedUrl || !frameState.visibleCanvas) {
          throw new Error(
            `${path.basename(entryDir)} frame ${i} left the live artwork: ${JSON.stringify(frameState)}`,
          );
        }
        const bytes = await gifPage.screenshot({ fullPage: false, timeout: 1500 });
        if (!ff.stdin.write(bytes)) await once(ff.stdin, 'drain');
        await gifPage.waitForTimeout(1000 / 12);
      }
      ff.stdin.end();
      await new Promise((resolve, reject) => {
        ff.on('close', code => code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}: ${ffmpegErr}`)));
        ff.on('error', reject);
      });
      fs.renameSync(partialGifPath, gifPath);
      gifMode = 'dynamic-full-frame';
    } catch (error) {
      ff.stdin.destroy();
      ff.kill('SIGKILL');
      fs.rmSync(partialGifPath, { force: true });
      console.warn(`${path.basename(entryDir)} full-frame GIF fallback: ${error.message}`);
      animateFullFrameStill(previewPng, partialGifPath);
      fs.renameSync(partialGifPath, gifPath);
    } finally {
      await Promise.race([
        gifPage.close(),
        new Promise((resolve) => setTimeout(resolve, 2500)),
      ]);
    }
  }
  assertPreviewSpec(gifPath, 'preview.gif');

  // Mirror assets into root archive if matching path exists.
  const rel = path.relative(path.join(ROOT, 'docs'), entryDir);
  const rootAssets = path.join(ROOT, rel, 'assets');
  if (fs.existsSync(path.dirname(rootAssets))) {
    fs.mkdirSync(rootAssets, { recursive: true });
    fs.copyFileSync(path.join(assets, 'preview.png'), path.join(rootAssets, 'preview.png'));
    fs.copyFileSync(path.join(assets, 'preview.gif'), path.join(rootAssets, 'preview.gif'));
  }

  console.log(
    `${path.basename(entryDir)} canvas ${info.w}x${info.h} -> preview.png + preview.gif (${gifMode})`,
  );
}

async function captureVisualPreview(browser, entryDir, serverBaseUrl, sharedContext = null) {
  const assets = path.join(entryDir, 'assets');
  fs.mkdirSync(assets, { recursive: true });
  const page = sharedContext
    ? await sharedContext.newPage()
    : await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  await suppressCanvasText(page);
  await openLiveArtwork(page, entryDir, serverBaseUrl, 'domcontentloaded');
  const day = path.basename(entryDir);
  const allowance = displayAllowances[day];
  let info;
  try {
    info = await waitForCanvas(page, 650, allowance?.visual_mode === 'text_free_form_structure' ? 1200 : 20000);
  } catch (error) {
    if (allowance?.visual_mode !== 'text_free_form_structure') throw error;
    info = await page.evaluate(() => {
      document.documentElement.style.overflow = 'hidden';
      document.body.style.height = '100vh';
      document.body.style.overflow = 'hidden';
      const isolation = document.createElement('style');
      isolation.dataset.grantedHoursVisualFallback = 'true';
      isolation.textContent = `
        body, body * {
          color: transparent !important;
          caret-color: transparent !important;
          text-shadow: none !important;
          text-decoration-color: transparent !important;
          animation: none !important;
          transition: none !important;
        }
        body *::placeholder { color: transparent !important; }
        .field-group {
          opacity: 1 !important;
          transform: none !important;
        }
        .gh-fold-toggle, audio { display: none !important; }
      `;
      document.head.append(isolation);
      return { count: 0, w: innerWidth, h: innerHeight, cssWidth: innerWidth, cssHeight: innerHeight };
    });
  }
  const temporaryPng = path.join(assets, '.visual-preview-source.png');
  if (allowance?.visual_mode === 'text_free_form_structure' && info.count === 0) {
    await page.screenshot({
      path: temporaryPng,
      type: 'png',
      animations: 'disabled',
      fullPage: false,
    });
  } else {
    await isolateVisualCanvas(page);
    await primeInteraction(page, 1280, 720, 300);
    await page.locator('canvas[data-granted-hours-visual-canvas="true"]').screenshot({
      path: temporaryPng,
      type: 'png',
      animations: 'disabled',
    });
  }
  await page.close();

  const visualPreview = path.join(assets, 'visual-preview.webp');
  run('cwebp', [
    '-quiet',
    '-q', '78',
    '-m', '6',
    '-resize', '960', '0',
    temporaryPng,
    '-o', visualPreview,
  ]);
  assertPreviewSpec(visualPreview, 'visual-preview.webp');
  fs.unlinkSync(temporaryPng);

  const rel = path.relative(path.join(ROOT, 'docs'), entryDir);
  const rootAssets = path.join(ROOT, rel, 'assets');
  if (fs.existsSync(path.dirname(rootAssets))) {
    fs.mkdirSync(rootAssets, { recursive: true });
    fs.copyFileSync(visualPreview, path.join(rootAssets, 'visual-preview.webp'));
  }
  const size = fs.statSync(visualPreview).size;
  console.log(
    `${path.basename(entryDir)} ${info.count ? 'canvas-only' : 'background-region'} `
    + `${Math.round(info.cssWidth)}x${Math.round(info.cssHeight)} `
    + `-> visual-preview.webp ${Math.round(size / 1024)} KiB`,
  );
}

async function main() {
  if (!all && !dateFilter) {
    console.error('Pass --all or --date YYYY-MM-DD');
    process.exit(2);
  }
  if (visualOnly && archiveOnly) throw new Error('--visual-only and --archive-only are mutually exclusive');
  const entries = listEntries();
  if (!entries.length) throw new Error('No matching live entries found.');
  const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const launchOptions = fs.existsSync(chromePath)
    ? { headless: true, executablePath: chromePath, args: ['--disable-gpu'] }
    : { headless: true };
  const server = await startStaticServer();
  const browser = await chromium.launch(launchOptions);
  try {
    if (visualOnly) {
      const context = await browser.newContext({
        viewport: { width: 1280, height: 720 },
        deviceScaleFactor: 1,
      });
      try {
        const concurrency = 8;
        for (let index = 0; index < entries.length; index += concurrency) {
          await Promise.all(
            entries.slice(index, index + concurrency)
              .map((entry) => captureVisualPreview(browser, entry, server.baseUrl, context)),
          );
        }
      } finally {
        await context.close();
      }
    } else if (archiveOnly) {
      for (const entry of entries) await captureEntry(browser, entry, server.baseUrl);
    } else {
      for (const entry of entries) {
        await captureEntry(browser, entry, server.baseUrl);
        await captureVisualPreview(browser, entry, server.baseUrl);
      }
    }
  } finally {
    await browser.close();
    await server.close();
  }
}

main().catch(err => { console.error(err.stack || err.message); process.exit(1); });
