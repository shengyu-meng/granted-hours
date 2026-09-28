#!/usr/bin/env node
/** Generate text-free animated GIF thumbnails for every Granted Hours artwork.
 *
 * Record the live artwork, including pointer gestures. Never animate a still.
 * Each date runs in an isolated process with a 90-second deadline. A failure
 * preserves the previous asset and must be repaired before publication.
 *
 * Usage:
 *   node scripts/capture_visual_preview_gifs.mjs --all
 *   node scripts/capture_visual_preview_gifs.mjs --date 2026-07-26
 *   node scripts/capture_visual_preview_gifs.mjs --all --resume --jobs 1
 */
import { chromium } from "playwright";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import { createHash } from "node:crypto";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Artwork pixels do not depend on remote interface fonts.
process.env.PW_TEST_SCREENSHOT_NO_FONTS_READY = "1";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const all = args.includes("--all");
const missingOnly = args.includes("--missing");
const resume = args.includes("--resume");
const dateIndex = args.indexOf("--date");
const dateFilter = dateIndex >= 0 ? args[dateIndex + 1] : null;
const jobsIndex = args.indexOf("--jobs");
const jobCount = jobsIndex >= 0 ? Number(args[jobsIndex + 1]) : 1;
const FPS = 8;
const FRAME_COUNT = 24;
const WIDTH = 400;
const HEIGHT = 225;
const MAX_BYTES = 700 * 1024;
const TARGET_BYTES = 450 * 1024;
const MIN_MOTION_YAVG = 0.04;


function fail(message) {
  throw new Error(message);
}

function run(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    encoding: "utf8",
    timeout: 20000,
    stdio: "pipe",
    ...options,
  });
  if (result.status !== 0) {
    fail(`${command} failed (${result.status})\n${result.stderr || result.stdout}`);
  }
  return result;
}

function startStaticServer() {
  const mimeTypes = {
    ".css": "text/css; charset=utf-8",
    ".gif": "image/gif",
    ".html": "text/html; charset=utf-8",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".mp3": "audio/mpeg",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
  };
  const server = http.createServer((request, response) => {
    let pathname;
    try {
      pathname = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
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
      if (fs.statSync(filePath).isDirectory()) filePath = path.join(filePath, "index.html");
      const stat = fs.statSync(filePath);
      response.writeHead(200, {
        "Content-Length": stat.size,
        "Content-Type": mimeTypes[path.extname(filePath).toLowerCase()] || "application/octet-stream",
        "Cache-Control": "no-store",
      });
      fs.createReadStream(filePath).pipe(response);
    } catch {
      response.writeHead(404).end();
    }
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      resolve({
        baseUrl: `http://127.0.0.1:${address.port}`,
        close: () => new Promise((done) => server.close(done)),
      });
    });
  });
}

function listEntries() {
  const archiveRoot = path.join(ROOT, "docs", "archive");
  const entries = [];
  for (const year of fs.readdirSync(archiveRoot).filter((value) => /^\d{4}$/.test(value))) {
    for (const month of fs.readdirSync(path.join(archiveRoot, year)).filter((value) => /^\d{2}$/.test(value))) {
      const monthRoot = path.join(archiveRoot, year, month);
      for (const day of fs.readdirSync(monthRoot).filter((value) => /^\d{4}-\d{2}-\d{2}$/.test(value))) {
        if (dateFilter && day !== dateFilter) continue;
        const entry = path.join(monthRoot, day);
        const output = path.join(entry, "assets", "visual-preview.gif");
        if (missingOnly && fs.existsSync(output)) continue;
        if (resume) {
          try {
            const receipt = JSON.parse(fs.readFileSync(path.join(entry, 'assets/visual-preview.capture.json')));
            const digest = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
            if (receipt.timing === 'browser-clock-8fps' && receipt.compositing === 'browser-native-raf' && receipt.gifSha256 === digest(output) && receipt.sourceSha256 === digest(path.join(entry, 'live/index.html')) && receipt.duration <= 4) continue;
          } catch {}
        }
        if (fs.existsSync(path.join(entry, "live", "index.html"))) entries.push(entry);
      }
    }
  }
  return entries.sort();
}

async function suppressText(page) {
  await page.addInitScript(() => {
    window.__GRANTED_HOURS_VISUAL_PREVIEW__ = true;
    const noText = () => {};
    for (const name of ["fillText", "strokeText"]) {
      Object.defineProperty(CanvasRenderingContext2D.prototype, name, {
        configurable: true,
        value: noText,
        writable: true,
      });
    }
    if (window.OffscreenCanvasRenderingContext2D) {
      for (const name of ["fillText", "strokeText"]) {
        Object.defineProperty(OffscreenCanvasRenderingContext2D.prototype, name, {
          configurable: true,
          value: noText,
          writable: true,
        });
      }
    }
  });
}

async function markAndIsolateLargestCanvas(page) {
  try {
    await page.waitForSelector("canvas", { timeout: 3500 });
  } catch {
    return null;
  }
  return page.evaluate(() => {
    const candidates = [...document.querySelectorAll("canvas")]
      .filter((canvas) => {
        const rect = canvas.getBoundingClientRect();
        const style = getComputedStyle(canvas);
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 4 && rect.height > 4 && rect.right > 0 && rect.bottom > 0 && rect.left < innerWidth && rect.top < innerHeight;
      })
      .sort((left, right) => {
        const a = left.getBoundingClientRect();
        const b = right.getBoundingClientRect();
        return b.width * b.height - a.width * a.height;
      });
    const canvas = candidates[0];
    if (!canvas) return null;
    canvas.dataset.grantedHoursGifCanvas = "true";
    for (const element of document.body.querySelectorAll("*")) {
      if (candidates.some(layer => element === layer || element.contains(layer))) continue;
      element.style.setProperty("visibility", "hidden", "important");
      element.style.setProperty("opacity", "0", "important");
      element.style.setProperty("pointer-events", "none", "important");
    }
    const style = document.createElement("style");
    style.textContent = `
      body { overflow: hidden !important; }
      body *:not(canvas):not(:has(canvas))::before,
      body *:not(canvas):not(:has(canvas))::after {
        visibility: hidden !important;
        opacity: 0 !important;
      }
    `;
    document.head.append(style);
    const rect = canvas.getBoundingClientRect();
    return { width: rect.width, height: rect.height, count: candidates.length };
  });
}

function gifFilter() {
  const base = [
    `fps=${FPS}`,
    `scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos`,
    `crop=${WIDTH}:${HEIGHT}`,
  ].join(",");
  return `${base},split[gifbase][palettebase];`
    + "[palettebase]palettegen=max_colors=64:stats_mode=diff[palette];"
    + "[gifbase][palette]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle";
}

async function streamLiveGif(page, outputPath, entryDir) {
  const encoder = spawn("ffmpeg", [
    "-y", "-v", "error", "-threads", "1", "-filter_complex_threads", "1", "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-filter_complex", gifFilter(), "-threads", "1", "-loop", "0", outputPath,
  ], { stdio: ["pipe", "ignore", "pipe"] });
  let stderr = "";
  encoder.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
  encoder.stdin.on("error", () => {});
  const completed = new Promise((resolve, reject) => {
    encoder.on("close", code => code === 0 ? resolve() : reject(new Error(`ffmpeg ${code}: ${stderr}`)));
    encoder.on("error", reject);
  });
  completed.catch(() => {});
  const date = path.basename(entryDir);
  const frameStart = Date.now();
  // This artwork is a local form. Show its actual filing transition, with
  // authored demonstration text; never capture private user input.
  const form = date === "2026-07-06";
  const ambient = ['2026-05-13', '2026-06-06', '2026-06-12', '2026-07-08'].includes(date);
  if (form) {
    await page.locator('#f-request').fill('Time to reconsider.');
    await page.locator('#f-ground').fill('A decision can leave room for an answer.');
    await page.locator('#f-return').fill('The right to return remains.');
    await page.locator('#f-name').fill('Visitor');
    await page.locator('#submit-btn').scrollIntoViewIfNeeded();
    await page.addStyleTag({content:'body * { color:transparent !important; text-shadow:none !important; caret-color:transparent !important; }'});
  }
  // Capture the browser composite: transparent paint needs its authored background.
  // Normalized hit targets from each work's authored layout. These are
  // gestures through the live controls, never substitutes for its animation.
  const targets = {
    '2026-07-25': [0.3515, 0.3176], '2026-08-30': [0.50, 0.37],
    '2026-09-04': [0.27, 0.38], '2026-09-05': [0.483, 0.34],
    '2026-09-11': [0.72, 0.46], '2026-09-12': [0.63, 0.50],
    '2026-09-13': [0.25, 0.46], '2026-09-14': [0.5, 0.17],
    '2026-09-15': [0.65, 0.50], '2026-09-16': [0.59, 0.455],
    '2026-09-17': [0.74, 0.43], '2026-09-18': [0.75, 0.49],
    '2026-09-19': [0.75, 0.69], '2026-09-20': [0.66, 0.36],
    '2026-09-21': [0.50, 0.40], '2026-09-22': [0.50, 0.413],
    '2026-09-23': [0.50, 0.814], '2026-09-24': [0.50, 0.44],
    '2026-09-25': [0.37, 0.56], '2026-09-26': [0.50, 0.56],
    '2026-09-29': [0.40, 0.46],
  };
  const target = targets[date] || [0.50, 0.50];
  let anchor = { x: 960 * target[0], y: 540 * target[1] };
  const compositor = await page.context().newCDPSession(page);
  // Read the work's own public debug geometry where the gesture must begin
  // on a small handle. Input still goes through the original pointer events.
  if (date === "2026-09-27") {
    anchor = await page.evaluate(() => window.__slackProbe?.().bead || {x:480,y:270});
  }
  try {
    for (let frame = 0; frame < FRAME_COUNT; frame += 1) {
      if (frame % 8 === 0) console.error(`${date} frame ${frame}/${FRAME_COUNT} at ${Date.now() - frameStart}ms`);
      const phase = frame / FRAME_COUNT * Math.PI * 2;
      if (!form && !ambient) {
        if (frame === 0) { await page.mouse.move(anchor.x, anchor.y); await page.mouse.down(); }
        if (date !== '2026-08-30') await page.mouse.move(anchor.x + Math.sin(phase) * 170, anchor.y + Math.sin(phase / 2) * 125);
        if (frame === 14) await page.mouse.up();
        if (frame === 19) await page.mouse.click(550, 310);
      } else if (form && frame === 5) {
        await page.locator('#submit-btn').click();
      }
      await page.clock.runFor(1000 / FPS);
      // Browser screenshots preserve WebGL, CSS/SVG layers and compositing.
      // toDataURL may be blank when a WebGL drawing buffer has been cleared.
      const png = Buffer.from((await compositor.send('Page.captureScreenshot', {format:'png', fromSurface:true, captureBeyondViewport:false})).data, 'base64');
      if (!encoder.stdin.write(png)) await new Promise(resolve => encoder.stdin.once('drain', resolve));

    }
    await page.mouse.up();
    encoder.stdin.end();
    await completed;
  } catch (error) {
    encoder.stdin.destroy(); encoder.kill("SIGKILL"); throw error;
  }
}

function inspectMotion(gifPath, threshold = MIN_MOTION_YAVG) {
  const result = run("ffmpeg", [
    "-v", "error", "-threads", "1", "-filter_threads", "1", "-i", gifPath,
    "-vf", "tblend=all_mode=difference,signalstats,metadata=print:file=-",
    "-f", "null", "-",
  ]);
  const values = [...result.stdout.matchAll(/lavfi\.signalstats\.YAVG=([0-9.]+)/g)]
    .map((match) => Number(match[1]))
    .filter(Number.isFinite);
  return {
    changedFrames: values.filter((value) => value >= threshold).length,
    averageYavg: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0,
    maximumYavg: values.length ? Math.max(...values) : 0,
  };
}

function probeGif(gifPath) {
  const result = run("ffprobe", [
    "-v", "error", "-count_frames", "-select_streams", "v:0",
    "-show_entries", "stream=width,height,nb_read_frames,duration:format=duration,size",
    "-of", "json", gifPath,
  ]);
  const probe = JSON.parse(result.stdout);
  return {
    width: Number(probe.streams?.[0]?.width),
    height: Number(probe.streams?.[0]?.height),
    frames: Number(probe.streams?.[0]?.nb_read_frames),
    duration: Number(probe.format?.duration || probe.streams?.[0]?.duration),
    bytes: Number(probe.format?.size),
  };
}

function compressGif(sourcePath, outputPath, compact = false) {
  const filter = `fps=${compact ? 4 : 6},split[gifbase][palettebase];`
    + `[palettebase]palettegen=max_colors=${compact ? 32 : 48}:stats_mode=diff[palette];`
    + "[gifbase][palette]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle";
  run("ffmpeg", [
    "-y", "-v", "error", "-threads", "1", "-filter_complex_threads", "1", "-i", sourcePath,
    "-filter_complex", filter, "-threads", "1", "-loop", "0", outputPath,
  ]);
}

function mirror(entryDir, source) {
  const relative = path.relative(path.join(ROOT, "docs"), entryDir);
  const rootAssets = path.join(ROOT, relative, "assets");
  fs.mkdirSync(rootAssets, { recursive: true });
  fs.copyFileSync(source, path.join(rootAssets, "visual-preview.gif"));
}

async function captureEntry(browser, entryDir, serverBaseUrl) {
  const startedAt = Date.now();
  const assets = path.join(entryDir, "assets");
  const output = path.join(assets, "visual-preview.gif");
  const partial = path.join(assets, "visual-preview.partial.gif");
  const compressed = path.join(assets, "visual-preview.compressed.gif");
  const still = path.join(assets, "visual-preview.webp");
  if (!fs.existsSync(still)) fail(`${path.basename(entryDir)} is missing audited visual-preview.webp`);
  fs.mkdirSync(assets, { recursive: true });
  const rasterScale = ['2026-06-12', '2026-06-17', '2026-07-08'].includes(path.basename(entryDir)) ? 0.5 : 1;
  const page = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: rasterScale });
  await suppressText(page);
  // The text-free preview must not wait on remote interface font services.
  await page.route('https://fonts.googleapis.com/**', route => route.fulfill({contentType:'text/css', body:''}));
  // Advance the browser clock by the GIF frame interval. IPC/readback latency
  // must not speed up the artwork in the exported loop.
  const epoch = new Date(`${path.basename(entryDir)}T03:17:00+08:00`);
  await page.clock.install({time:epoch});
  await page.clock.pauseAt(new Date(epoch.getTime() + 1000));
  let mode = "live-browser";
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    const relativeLive = path.relative(ROOT, path.join(entryDir, "live")).split(path.sep).join("/");
    // These works limit their interactions in compact embeds; record the full live work.
    const query = ['2026-07-06', '2026-08-13', '2026-08-14', '2026-08-15'].includes(path.basename(entryDir)) ? '' : '?embed=calendar';
    await page.goto(`${serverBaseUrl}/${relativeLive}/${query}`, {
      waitUntil: "load", timeout: 20000,
    });
    console.error(`${path.basename(entryDir)} loaded at ${Date.now() - startedAt}ms`);
    await page.clock.runFor(500);
    if (path.basename(entryDir) === '2026-07-25') {
      // Its desktop side essay makes the stage taller than the viewport.
      // Fit the authored responsive stage before interacting and recording.
      await page.addStyleTag({content:'.stage {position:fixed!important;inset:0!important;width:100vw!important;height:100vh!important;min-height:0!important;} canvas {width:100vw!important;height:100vh!important;}'});
      await page.evaluate(() => dispatchEvent(new Event('resize')));
    }
    const canvas = await markAndIsolateLargestCanvas(page);
    if (!canvas && path.basename(entryDir) !== '2026-07-06') {
      // A p5/WebGL library failing to load is not a DOM artwork.
      const source = fs.readFileSync(path.join(entryDir, 'live/index.html'), 'utf8');
      if (/createCanvas\(|new THREE\.WebGLRenderer|<canvas\b/.test(source)) {
        fail(`Expected live canvas did not initialize: ${errors.join('; ')}`);
      }
    }
    await page.addStyleTag({ content: `
      .gh-live-brief, .gh-work-note-trigger, .gh-calendar-return,
      .gh-embed-shortcuts, .gh-touch-shortcuts, .gh-media-unlock,
      #granted-hours-sound-toggle { visibility:hidden !important; }
    ` });
    await streamLiveGif(page, partial, entryDir);
    mode = canvas ? "live-canvas" : "live-dom";
    if (errors.length) fail(`Live artwork errors: ${errors.join('; ')}`);
  } finally {
    await page.close();
  }

  console.error(`${path.basename(entryDir)} pixels captured at ${Date.now() - startedAt}ms`);
  // This pale line drawing changes a small fraction of the thumbnail.
  const motionThreshold = path.basename(entryDir) === '2026-07-25' ? 0.02 : MIN_MOTION_YAVG;
  let motion = inspectMotion(partial, motionThreshold);
  // Quiet pauses are part of the work; require visible changes in at least two frames.
  if (motion.changedFrames < 2 || motion.maximumYavg < motionThreshold) {
    fail(`${path.basename(entryDir)} GIF has no visible motion: ${JSON.stringify(motion)}`);
  }

  let probe = probeGif(partial);
  if (probe.bytes > TARGET_BYTES) {
    compressGif(partial, compressed);
    fs.renameSync(compressed, partial);
    probe = probeGif(partial);
    motion = inspectMotion(partial, motionThreshold);
    mode += "-compressed";
  }
  if (probe.bytes > MAX_BYTES) {
    compressGif(partial, compressed, true);
    fs.renameSync(compressed, partial);
    probe = probeGif(partial);
    motion = inspectMotion(partial, motionThreshold);
  }
  if (motion.changedFrames < 2) fail(`${path.basename(entryDir)} compressed GIF lost visible motion`);
  const expectedWidth = WIDTH;
  const expectedHeight = HEIGHT;
  if (probe.width !== expectedWidth || probe.height !== expectedHeight || probe.frames < 12 || probe.duration < 2) {
    fail(`${path.basename(entryDir)} invalid GIF: ${JSON.stringify(probe)}`);
  }
  if (probe.bytes > MAX_BYTES) fail(`${path.basename(entryDir)} GIF exceeds ${MAX_BYTES} bytes`);
  const bytes = fs.readFileSync(partial);
  if (!["GIF87a", "GIF89a"].includes(bytes.subarray(0, 6).toString("ascii"))) {
    fail(`${path.basename(entryDir)} has an invalid GIF signature`);
  }
  if (!bytes.includes(Buffer.from("NETSCAPE2.0"))) fail(`${path.basename(entryDir)} GIF does not loop`);
  fs.renameSync(partial, output);
  mirror(entryDir, output);
  const result = { date: path.basename(entryDir), mode, ...probe, ...motion,
    captureMs: Date.now() - startedAt,
    timing: "browser-clock-8fps",
    compositing: "browser-native-raf",
    schema: "live-artwork-capture-v1",
    sourceSha256: createHash('sha256').update(fs.readFileSync(path.join(entryDir, 'live/index.html'))).digest('hex'),
    gifSha256: createHash('sha256').update(bytes).digest('hex'),
  };
  fs.writeFileSync(path.join(assets, 'visual-preview.capture.json'), JSON.stringify(result, null, 2) + '\n');
  const rootAssets = path.join(ROOT, path.relative(path.join(ROOT, 'docs'), entryDir), 'assets');
  fs.copyFileSync(path.join(assets, 'visual-preview.capture.json'), path.join(rootAssets, 'visual-preview.capture.json'));
  console.log(JSON.stringify(result));
  return result;
}

async function main() {
  if (!all && !dateFilter) fail("Pass --all or --date YYYY-MM-DD");
  if (!Number.isInteger(jobCount) || jobCount < 1 || jobCount > 4) fail("--jobs must be an integer from 1 to 4");
  run("ffmpeg", ["-version"]);
  run("ffprobe", ["-version"]);
  const entries = listEntries();
  if (!entries.length) {
    if (resume) { console.log(JSON.stringify({complete:true, count:0})); return; }
    fail("No matching live entries found");
  }
  if (all) {
    const results = [];
    const workflowDeadline = Date.now() + 60 * 60 * 1000;
    let next = 0;
    const worker = async () => {
      while (next < entries.length) {
        if (Date.now() >= workflowDeadline) fail("Capture batch exceeded one hour; resume verified dates with --resume");
        const entry = entries[next++];
        const date = path.basename(entry);
        results.push(await new Promise(resolve => {
          const child = spawn(process.execPath, [fileURLToPath(import.meta.url), '--date', date], {
            detached: true, stdio: ['ignore', 'pipe', 'pipe'],
          });
          let output = '';
          child.stdout.on('data', x => { output += x; });
          child.stderr.on('data', x => { output += x; });
          const deadline = setTimeout(() => {
            child.kill('SIGTERM');
            setTimeout(() => { try { process.kill(-child.pid, 'SIGKILL'); } catch {} }, 5000).unref();
          }, 90000);
          child.on('close', code => {
            clearTimeout(deadline);
            console.log(JSON.stringify({date, ok:code === 0, output:output.trim()}));
            resolve({date, ok:code === 0});
          });
        }));
      }
    };
    await Promise.all(Array.from({length: Math.min(jobCount, entries.length)}, worker));
    const failures = results.filter(x => !x.ok);
    console.log(JSON.stringify({complete:!failures.length, count:results.length, failures}));
    if (failures.length) process.exitCode = 1;
    return;
  }
  const server = await startStaticServer();
  const chromePath = process.env.CHROME_PATH || "";
  const browserServer = await chromium.launchServer(fs.existsSync(chromePath)
    ? { headless: true, executablePath: chromePath }
    : { headless: true });
  const browser = await chromium.connect(browserServer.wsEndpoint());
  const deadline = setTimeout(() => { browserServer.kill(); }, 80000);
  process.once("SIGTERM", async () => { await browserServer.kill(); process.exit(124); });
  try {
    await captureEntry(browser, entries[0], server.baseUrl);
  } finally {
    clearTimeout(deadline);
    await browser.close().catch(() => {});
    await browserServer.kill();
    await server.close();
  }
}

await main();
