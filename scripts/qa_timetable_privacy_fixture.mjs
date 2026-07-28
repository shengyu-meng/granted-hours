#!/usr/bin/env node
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import {
  cp,
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { promisify } from "node:util";
import { chromium } from "@playwright/test";

const execFileAsync = promisify(execFile);
const root = path.resolve(new URL("..", import.meta.url).pathname);
const fixtureRoot = await mkdtemp(path.join(root, ".privacy-fixture-"));
const fixtureSource = path.join(fixtureRoot, "src", "timetable");
const fixtureSite = path.join(fixtureRoot, "site");
const fixturePulses = path.join(fixtureRoot, "pulses.json");
const auditRoot = path.join(root, "audits", "public-readable-hierarchy");
const screenshotPath = path.join(auditRoot, "privacy-fixture-rendered-surface.png");
const fixedBlock = "████";
const syntheticSecrets = [
  { kind: "person", value: "Mara Evergarden" },
  { kind: "project", value: "Orchid Lantern" },
  { kind: "amount", value: "CNY 938,271.44" },
];
const transparentPng = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);

function assertSecretsAbsent(surface, label) {
  for (const fixture of syntheticSecrets) {
    assert.ok(
      !String(surface).includes(fixture.value),
      `${label}: synthetic ${fixture.kind} escaped redaction`,
    );
  }
}

async function filesUnder(directory) {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const candidate = path.join(directory, entry.name);
    if (entry.isDirectory()) result.push(...await filesUnder(candidate));
    else result.push(candidate);
  }
  return result;
}

function mimeType(filePath) {
  return {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".png": "image/png",
  }[path.extname(filePath)] || "application/octet-stream";
}

async function startStaticServer(directory) {
  const server = http.createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
      let candidate = path.resolve(directory, `.${pathname}`);
      if (!candidate.startsWith(`${path.resolve(directory)}${path.sep}`)) {
        response.writeHead(403).end();
        return;
      }
      if ((await stat(candidate)).isDirectory()) candidate = path.join(candidate, "index.html");
      response.writeHead(200, { "content-type": mimeType(candidate) });
      response.end(await readFile(candidate));
    } catch {
      response.writeHead(404).end();
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  return {
    server,
    url: `http://127.0.0.1:${server.address().port}/timetable/`,
  };
}

let browser;
let server;
try {
  await mkdir(fixtureSource, { recursive: true });
  await mkdir(auditRoot, { recursive: true });
  await cp(path.join(root, "src", "timetable"), fixtureSource, { recursive: true });

  const pulseSnapshot = JSON.parse(
    await readFile(path.join(root, "metadata", "timetable-pulses.json"), "utf8"),
  );
  const fixtureDay = pulseSnapshot.days.find((day) => day.date === "2026-07-21");
  const reminder = fixtureDay.pulses.find((pulse) => pulse.category === "daily_reminder");
  assert.ok(reminder, "fixture needs an authorized reminder source");
  reminder.summary_en = `Contact ${syntheticSecrets[0].value} about ${syntheticSecrets[1].value} and ${syntheticSecrets[2].value}.`;
  reminder.summary_zh = `联系 ${syntheticSecrets[0].value}，确认 ${syntheticSecrets[1].value} 与 ${syntheticSecrets[2].value}。`;
  await writeFile(
    fixturePulses,
    `${JSON.stringify(pulseSnapshot, null, 2)}\n`,
    "utf8",
  );

  const builderOutput = path.join(fixtureSource, "timetable-data.js");
  const builderRun = await execFileAsync(
    "python3",
    [
      path.join(root, "scripts", "build_timetable_data.py"),
      "--pulses",
      fixturePulses,
      "--output",
      builderOutput,
    ],
    { cwd: root },
  );
  const generatedProjection = await readFile(builderOutput, "utf8");
  assertSecretsAbsent(generatedProjection, "isolated generated projection");
  assert.ok(generatedProjection.includes(fixedBlock), "generated projection lost fixed bars");
  assertSecretsAbsent(`${builderRun.stdout}\n${builderRun.stderr}`, "builder logs");

  const viteRun = await execFileAsync(
    path.join(root, "node_modules", ".bin", "vite"),
    [
      "build",
      fixtureSource,
      "--base",
      "./",
      "--outDir",
      path.join(fixtureSite, "timetable"),
      "--emptyOutDir",
    ],
    { cwd: root },
  );
  assertSecretsAbsent(`${viteRun.stdout}\n${viteRun.stderr}`, "bundle logs");

  const builtFiles = await filesUnder(fixtureSite);
  let builtText = "";
  for (const filePath of builtFiles) {
    try {
      builtText += await readFile(filePath, "utf8");
    } catch {}
  }
  assertSecretsAbsent(builtText, "isolated built site");
  assert.ok(builtText.includes(fixedBlock), "built site lost fixed bars");

  const staticServer = await startStaticServer(fixtureSite);
  server = staticServer.server;
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();
  const pageLogs = [];
  page.on("console", (message) => pageLogs.push(`console:${message.type()}:${message.text()}`));
  page.on("pageerror", (error) => pageLogs.push(`pageerror:${error.message}`));
  page.on("requestfailed", (request) => pageLogs.push(`requestfailed:${request.url()}`));
  await page.route(/\.(?:gif|png|webp)(?:\?.*)?$/i, async (route) => {
    await route.fulfill({ status: 200, contentType: "image/png", body: transparentPng });
  });
  await page.goto(staticServer.url, { waitUntil: "domcontentloaded" });
  await page.locator('.calendar-day-button[data-date="2026-07-21"]').click();
  await page.waitForSelector("#dayDialog.is-open");
  await page.waitForFunction(
    () => document.querySelector(".timeline-reading-layer.is-placed")
      && document.querySelectorAll(".absence-reading-card").length > 0,
  );

  const morningReminder = page.locator(".absence-reading-card").filter({
    hasText: "Morning reminder",
  }).first();
  await morningReminder.scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);
  const renderedSurface = await page.evaluate(() => {
    const attributes = [...document.querySelectorAll("*")]
      .flatMap((element) => [...element.attributes].map(
        (attribute) => `${attribute.name}=${attribute.value}`,
      ))
      .join("\n");
    const accessibleAttributes = [...document.querySelectorAll("*")]
      .flatMap((element) => [
        element.getAttribute("aria-label"),
        element.getAttribute("aria-description"),
        element.getAttribute("aria-describedby"),
        element.getAttribute("title"),
        element.getAttribute("alt"),
      ])
      .filter(Boolean)
      .join("\n");
    return {
      markup: document.documentElement.outerHTML,
      visibleText: document.body.innerText,
      attributes,
      accessibleAttributes,
      bars: [...document.querySelectorAll(".redaction-block")].map(
        (block) => block.textContent,
      ),
    };
  });
  const ariaSnapshot = await page.locator("body").ariaSnapshot();
  for (const [label, surface] of Object.entries({
    dom: renderedSurface.markup,
    visible_text: renderedSurface.visibleText,
    attributes: renderedSurface.attributes,
    accessible_attributes: renderedSurface.accessibleAttributes,
    accessible_names: ariaSnapshot,
  })) {
    assertSecretsAbsent(surface, label);
  }
  assert.ok(renderedSurface.bars.length > 0, "rendered page has no redaction bars");
  assert.ok(
    renderedSurface.bars.every((bar) => bar === fixedBlock),
    "rendered bars are not fixed length",
  );

  await page.screenshot({ path: screenshotPath, fullPage: false });
  const ocrRun = await execFileAsync(
    "tesseract",
    [screenshotPath, "stdout", "-l", "eng"],
    { cwd: root },
  );
  assertSecretsAbsent(ocrRun.stdout, "screenshot OCR surface");
  assert.ok(ocrRun.stdout.trim().length > 20, "screenshot OCR surface was empty");
  assertSecretsAbsent(pageLogs.join("\n"), "console and page logs");
  assert.deepEqual(
    pageLogs.filter((entry) => entry.startsWith("pageerror:")),
    [],
    "fixture page raised errors",
  );

  await context.close();
  console.log(JSON.stringify({
    passed: true,
    canonicalOutputUntouched: true,
    scans: [
      "isolated generated projection",
      "isolated built JS/CSS/HTML",
      "DOM and visible text",
      "all DOM attributes",
      "accessible names and attributes",
      "console/page/request logs",
      "screenshot OCR surface",
    ],
    fixedBars: renderedSurface.bars.length,
    logEntriesScanned: pageLogs.length,
    ocrCharactersScanned: ocrRun.stdout.length,
    screenshot: screenshotPath,
  }, null, 2));
} finally {
  if (browser) await browser.close().catch(() => {});
  if (server) await new Promise((resolve) => server.close(resolve));
  await rm(fixtureRoot, { recursive: true, force: true });
}
