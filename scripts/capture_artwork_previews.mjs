#!/usr/bin/env node
/** Capture archive previews for Granted Hours live artworks.
 *
 * Requirements: Node.js, Playwright, ffmpeg.
 * Usage:
 *   node scripts/capture_artwork_previews.mjs --all
 *   node scripts/capture_artwork_previews.mjs --date 2026-05-11
 *   node scripts/capture_artwork_previews.mjs --all --visual-only
 */
import { chromium } from 'playwright';
import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const getArg = (name) => {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : null;
};
const all = args.includes('--all');
const visualOnly = args.includes('--visual-only');
const missingOnly = args.includes('--missing');
const dateFilter = getArg('--date');
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

async function captureEntry(browser, entryDir) {
  const live = path.join(entryDir, 'live', 'index.html');
  const assets = path.join(entryDir, 'assets');
  fs.mkdirSync(assets, { recursive: true });
  const url = pathToFileURL(live).href;

  // Full-frame still: large landscape viewport, full visible page. This avoids the old half-window thumbnails.
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 }, deviceScaleFactor: 1 });
  await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
  const info = await waitForCanvas(page);
  await primeInteraction(page, 1600, 900);
  await page.screenshot({ path: path.join(assets, 'preview.png'), fullPage: false });
  await page.close();

  // GIF: smaller viewport, 4 seconds at 12fps to keep repo size reasonable.
  // Frames are streamed directly to ffmpeg so no temp frame directory needs deletion.
  const gifPage = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 1 });
  await gifPage.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
  await waitForCanvas(gifPage);
  await primeInteraction(gifPage, 960, 540);
  const gifPath = path.join(assets, 'preview.gif');
  const ff = spawn('ffmpeg', ['-y', '-v', 'error', '-f', 'image2pipe', '-framerate', '12', '-i', '-', '-vf', 'fps=12,scale=720:-1:flags=lanczos', '-loop', '0', gifPath], { stdio: ['pipe', 'pipe', 'pipe'] });
  let ffmpegErr = '';
  ff.stderr.on('data', d => { ffmpegErr += d.toString(); });
  const total = 48;
  for (let i = 0; i < total; i++) {
    await movePreviewMouse(gifPage, i, total, 960, 540);
    ff.stdin.write(await gifPage.screenshot({ fullPage: false }));
    await gifPage.waitForTimeout(1000 / 12);
  }
  ff.stdin.end();
  await new Promise((resolve, reject) => {
    ff.on('close', code => code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}: ${ffmpegErr}`)));
    ff.on('error', reject);
  });
  await gifPage.close();

  // Mirror assets into root archive if matching path exists.
  const rel = path.relative(path.join(ROOT, 'docs'), entryDir);
  const rootAssets = path.join(ROOT, rel, 'assets');
  if (fs.existsSync(path.dirname(rootAssets))) {
    fs.mkdirSync(rootAssets, { recursive: true });
    fs.copyFileSync(path.join(assets, 'preview.png'), path.join(rootAssets, 'preview.png'));
    fs.copyFileSync(path.join(assets, 'preview.gif'), path.join(rootAssets, 'preview.gif'));
  }

  console.log(`${path.basename(entryDir)} canvas ${info.w}x${info.h} -> preview.png + preview.gif`);
}

async function captureVisualPreview(browser, entryDir, sharedContext = null) {
  const live = path.join(entryDir, 'live', 'index.html');
  const assets = path.join(entryDir, 'assets');
  fs.mkdirSync(assets, { recursive: true });
  const page = sharedContext
    ? await sharedContext.newPage()
    : await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
  await suppressCanvasText(page);
  await page.goto(pathToFileURL(live).href, { waitUntil: 'domcontentloaded', timeout: 45000 });
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
  const entries = listEntries();
  if (!entries.length) throw new Error('No matching live entries found.');
  const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  const launchOptions = fs.existsSync(chromePath)
    ? { headless: true, executablePath: chromePath, args: ['--disable-gpu'] }
    : { headless: true };
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
              .map((entry) => captureVisualPreview(browser, entry, context)),
          );
        }
      } finally {
        await context.close();
      }
    } else {
      for (const entry of entries) {
        await captureEntry(browser, entry);
        await captureVisualPreview(browser, entry);
      }
    }
  } finally {
    await browser.close();
  }
}

main().catch(err => { console.error(err.stack || err.message); process.exit(1); });
