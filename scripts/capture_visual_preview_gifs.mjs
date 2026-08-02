#!/usr/bin/env node
/** Generate text-free animated GIF thumbnails for every Granted Hours artwork.
 *
 * Canvas/WebGL works are captured from the isolated visual canvas after canvas
 * text APIs are suppressed. Text-free DOM-only works, and canvases that do not
 * visibly move, fall back to a subtle animated crop of the already-audited
 * visual-preview.webp.
 *
 * Usage:
 *   node scripts/capture_visual_preview_gifs.mjs --all
 *   node scripts/capture_visual_preview_gifs.mjs --date 2026-07-26
 *   node scripts/capture_visual_preview_gifs.mjs --all --missing
 */
import { chromium } from "playwright";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const all = args.includes("--all");
const missingOnly = args.includes("--missing");
const dateIndex = args.indexOf("--date");
const dateFilter = dateIndex >= 0 ? args[dateIndex + 1] : null;
const jobsIndex = args.indexOf("--jobs");
const jobCount = jobsIndex >= 0 ? Number(args[jobsIndex + 1]) : (dateFilter ? 1 : 3);
const FPS = 8;
const FRAME_COUNT = 20;
const WIDTH = 400;
const HEIGHT = 225;
const FALLBACK_FPS = 5;
const FALLBACK_FRAME_COUNT = 12;
const FALLBACK_WIDTH = 360;
const FALLBACK_HEIGHT = 203;
const MAX_BYTES = 700 * 1024;
const MIN_MOTION_YAVG = 0.04;
const SCREENSHOT_TIMEOUT_MS = 2500;

function fail(message) {
  throw new Error(message);
}

function run(command, commandArgs, options = {}) {
  const result = spawnSync(command, commandArgs, {
    encoding: "utf8",
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
        return style.display !== "none" && style.visibility !== "hidden" && rect.width > 4 && rect.height > 4;
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
      if (element === canvas || element.contains(canvas)) continue;
      element.style.setProperty("visibility", "hidden", "important");
      element.style.setProperty("opacity", "0", "important");
      element.style.setProperty("pointer-events", "none", "important");
    }
    const style = document.createElement("style");
    style.textContent = `
      body { overflow: hidden !important; background: #03070b !important; }
      body *:not(canvas):not(:has(canvas))::before,
      body *:not(canvas):not(:has(canvas))::after {
        visibility: hidden !important;
        opacity: 0 !important;
      }
    `;
    document.head.append(style);
    const rect = canvas.getBoundingClientRect();
    return { width: rect.width, height: rect.height };
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

async function streamCanvasGif(page, outputPath) {
  const canvas = page.locator('canvas[data-granted-hours-gif-canvas="true"]');
  const process = spawn("ffmpeg", [
    "-y", "-v", "error",
    "-f", "image2pipe", "-framerate", String(FPS), "-i", "-",
    "-filter_complex", gifFilter(),
    "-loop", "0", outputPath,
  ], { stdio: ["pipe", "ignore", "pipe"] });
  let stderr = "";
  process.stderr.on("data", (chunk) => { stderr += chunk.toString(); });

  try {
    for (let frame = 0; frame < FRAME_COUNT; frame += 1) {
      const phase = frame / FRAME_COUNT * Math.PI * 2;
      const x = 480 + Math.sin(phase) * 210;
      const y = 270 + Math.cos(phase * 1.31) * 105;
      await page.mouse.move(x, y, { steps: 2 });
      if (frame === 3 || frame === 12) await page.mouse.click(x, y);
      const dataUrl = await Promise.race([
        canvas.evaluate((element) => element.toDataURL("image/png")),
        new Promise((_, reject) => {
          setTimeout(() => reject(new Error(`canvas pixel extraction exceeded ${SCREENSHOT_TIMEOUT_MS} ms`)), SCREENSHOT_TIMEOUT_MS);
        }),
      ]);
      if (!dataUrl.startsWith("data:image/png;base64,")) throw new Error("canvas did not return PNG pixels");
      const png = Buffer.from(dataUrl.slice(dataUrl.indexOf(",") + 1), "base64");
      if (!process.stdin.write(png)) await new Promise((resolve) => process.stdin.once("drain", resolve));
      await page.waitForTimeout(1000 / FPS);
    }
    process.stdin.end();
    await new Promise((resolve, reject) => {
      process.on("close", (code) => code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}: ${stderr}`)));
      process.on("error", reject);
    });
  } catch (error) {
    process.stdin.destroy();
    process.kill("SIGKILL");
    throw error;
  }
}

function animateStill(stillPath, outputPath) {
  const palettePath = `${outputPath}.palette.png`;
  const sourceCrop = [
    "scale=500:282:force_original_aspect_ratio=increase:flags=lanczos",
    "crop=500:282",
  ].join(",");
  const motionBase = [
    sourceCrop,
    `zoompan=z='1+0.042*sin(on*PI/${FALLBACK_FRAME_COUNT - 1})':x='iw/2-(iw/zoom/2)+6*sin(on*PI/7)':y='ih/2-(ih/zoom/2)+4*cos(on*PI/6)':d=${FALLBACK_FRAME_COUNT}:s=${FALLBACK_WIDTH}x${FALLBACK_HEIGHT}:fps=${FALLBACK_FPS}`,
  ].join(",");
  try {
    run("ffmpeg", [
      "-y", "-v", "error", "-i", stillPath,
      "-vf", `${sourceCrop},palettegen=max_colors=64:stats_mode=full`,
      "-frames:v", "1", palettePath,
    ]);
    run("ffmpeg", [
      "-y", "-v", "error",
      "-loop", "1", "-framerate", "1", "-t", "1", "-i", stillPath,
      "-i", palettePath,
      "-filter_complex", `[0:v]${motionBase}[motion];[motion][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle`,
      "-frames:v", String(FALLBACK_FRAME_COUNT), "-loop", "0", outputPath,
    ]);
  } finally {
    fs.rmSync(palettePath, { force: true });
  }
}

function inspectMotion(gifPath) {
  const result = run("ffmpeg", [
    "-v", "error", "-i", gifPath,
    "-vf", "tblend=all_mode=difference,signalstats,metadata=print:file=-",
    "-f", "null", "-",
  ]);
  const values = [...result.stdout.matchAll(/lavfi\.signalstats\.YAVG=([0-9.]+)/g)]
    .map((match) => Number(match[1]))
    .filter(Number.isFinite);
  return {
    changedFrames: values.filter((value) => value >= MIN_MOTION_YAVG).length,
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

function compressGif(sourcePath, outputPath) {
  const filter = "fps=6,split[gifbase][palettebase];"
    + "[palettebase]palettegen=max_colors=48:stats_mode=diff[palette];"
    + "[gifbase][palette]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle";
  run("ffmpeg", [
    "-y", "-v", "error", "-i", sourcePath,
    "-filter_complex", filter, "-loop", "0", outputPath,
  ]);
}

function mirror(entryDir, source) {
  const relative = path.relative(path.join(ROOT, "docs"), entryDir);
  const rootAssets = path.join(ROOT, relative, "assets");
  fs.mkdirSync(rootAssets, { recursive: true });
  fs.copyFileSync(source, path.join(rootAssets, "visual-preview.gif"));
}

async function captureEntry(browser, entryDir, serverBaseUrl) {
  const assets = path.join(entryDir, "assets");
  const output = path.join(assets, "visual-preview.gif");
  const partial = path.join(assets, "visual-preview.partial.gif");
  const compressed = path.join(assets, "visual-preview.compressed.gif");
  const still = path.join(assets, "visual-preview.webp");
  if (!fs.existsSync(still)) fail(`${path.basename(entryDir)} is missing audited visual-preview.webp`);
  fs.mkdirSync(assets, { recursive: true });
  const page = await browser.newPage({ viewport: { width: 960, height: 540 }, deviceScaleFactor: 1 });
  await suppressText(page);
  let mode = "animated-still";
  try {
    const relativeLive = path.relative(ROOT, path.join(entryDir, "live")).split(path.sep).join("/");
    await page.goto(`${serverBaseUrl}/${relativeLive}/`, {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });
    await page.waitForTimeout(900);
    const canvas = await markAndIsolateLargestCanvas(page);
    if (canvas) {
      await page.mouse.move(500, 270, { steps: 12 });
      await page.mouse.click(500, 270);
      await page.waitForTimeout(350);
      await streamCanvasGif(page, partial);
      mode = "canvas-motion";
    } else {
      animateStill(still, partial);
    }
  } catch (error) {
    console.warn(`${path.basename(entryDir)} canvas capture fallback: ${error.message}`);
    animateStill(still, partial);
    mode = "animated-still-fallback";
  } finally {
    await page.close();
  }

  let motion = inspectMotion(partial);
  if (motion.changedFrames < 2 || motion.averageYavg < MIN_MOTION_YAVG) {
    animateStill(still, partial);
    motion = inspectMotion(partial);
    mode = "animated-still-no-motion-fallback";
  }
  if (motion.changedFrames < 2 || motion.averageYavg < MIN_MOTION_YAVG) {
    fail(`${path.basename(entryDir)} GIF has no visible motion: ${JSON.stringify(motion)}`);
  }

  let probe = probeGif(partial);
  if (probe.bytes > MAX_BYTES) {
    compressGif(partial, compressed);
    fs.renameSync(compressed, partial);
    probe = probeGif(partial);
    mode += "-compressed";
  }
  const expectedWidth = mode.startsWith("canvas-motion") ? WIDTH : FALLBACK_WIDTH;
  const expectedHeight = mode.startsWith("canvas-motion") ? HEIGHT : FALLBACK_HEIGHT;
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
  const result = { date: path.basename(entryDir), mode, ...probe, ...motion };
  console.log(JSON.stringify(result));
  return result;
}

async function main() {
  if (!all && !dateFilter) fail("Pass --all or --date YYYY-MM-DD");
  if (!Number.isInteger(jobCount) || jobCount < 1 || jobCount > 4) fail("--jobs must be an integer from 1 to 4");
  run("ffmpeg", ["-version"]);
  run("ffprobe", ["-version"]);
  const entries = listEntries();
  if (!entries.length) fail("No matching live entries found");
  const server = await startStaticServer();
  const chromePath = process.env.CHROME_PATH || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const browser = await chromium.launch(fs.existsSync(chromePath)
    ? { headless: true, executablePath: chromePath }
    : { headless: true });
  const results = new Array(entries.length);
  try {
    let nextIndex = 0;
    const worker = async () => {
      while (nextIndex < entries.length) {
        const index = nextIndex;
        nextIndex += 1;
        results[index] = await captureEntry(browser, entries[index], server.baseUrl);
      }
    };
    await Promise.all(Array.from({ length: Math.min(jobCount, entries.length) }, worker));
  } finally {
    await browser.close();
    await server.close();
  }
  console.log(JSON.stringify({
    complete: true,
    count: results.length,
    canvasMotion: results.filter((result) => result.mode.startsWith("canvas-motion")).length,
    fallbackMotion: results.filter((result) => !result.mode.startsWith("canvas-motion")).length,
    totalBytesPerTree: results.reduce((sum, result) => sum + result.bytes, 0),
    largestBytes: Math.max(...results.map((result) => result.bytes)),
  }));
}

await main();
