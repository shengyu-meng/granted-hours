#!/usr/bin/env node
/** Capture full-frame PNG stills and animated GIF previews for Granted Hours live artworks.
 *
 * Requirements: Node.js, Playwright, ffmpeg.
 * Usage:
 *   node scripts/capture_artwork_previews.mjs --all
 *   node scripts/capture_artwork_previews.mjs --date 2026-05-11
 */
import { chromium } from 'playwright';
import { spawnSync } from 'node:child_process';
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
const dateFilter = getArg('--date');

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

async function waitForCanvas(page) {
  await page.waitForSelector('canvas', { timeout: 20000 });
  await page.waitForTimeout(1800);
  const info = await page.evaluate(() => {
    const c = document.querySelector('canvas');
    return { count: document.querySelectorAll('canvas').length, w: c?.width, h: c?.height, text: document.body.innerText.slice(0, 300) };
  });
  if (!info.count || !info.w || !info.h) throw new Error(`Canvas did not initialize: ${JSON.stringify(info)}`);
  return info;
}

async function primeInteraction(page, width, height) {
  // Some works intentionally reveal more under a human gesture.
  // For archive previews, capture the artwork in an activated/exhibited state,
  // not as a cold untouched browser frame.
  await page.mouse.move(width * 0.52, height * 0.52, { steps: 18 });
  await page.mouse.click(width * 0.52, height * 0.52);
  await page.waitForTimeout(900);
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
  const framesDir = path.join(assets, '.gif-frames');
  fs.rmSync(framesDir, { recursive: true, force: true });
  fs.mkdirSync(framesDir, { recursive: true });
  const gifPage = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 1 });
  await gifPage.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
  await waitForCanvas(gifPage);
  await primeInteraction(gifPage, 960, 540);
  const total = 48;
  for (let i = 0; i < total; i++) {
    await movePreviewMouse(gifPage, i, total, 960, 540);
    await gifPage.screenshot({ path: path.join(framesDir, `frame-${String(i).padStart(4, '0')}.png`), fullPage: false });
    await gifPage.waitForTimeout(1000 / 12);
  }
  await gifPage.close();

  const palette = path.join(framesDir, 'palette.png');
  const input = path.join(framesDir, 'frame-%04d.png');
  run('ffmpeg', ['-y', '-v', 'error', '-framerate', '12', '-i', input, '-vf', 'fps=12,scale=720:-1:flags=lanczos,palettegen=max_colors=192', palette]);
  run('ffmpeg', ['-y', '-v', 'error', '-framerate', '12', '-i', input, '-i', palette, '-lavfi', 'fps=12,scale=720:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3', path.join(assets, 'preview.gif')]);
  fs.rmSync(framesDir, { recursive: true, force: true });

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
    for (const entry of entries) await captureEntry(browser, entry);
  } finally {
    await browser.close();
  }
}

main().catch(err => { console.error(err.stack || err.message); process.exit(1); });
