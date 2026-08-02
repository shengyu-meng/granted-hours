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
  { kind: "institution", value: "Northlake Institute" },
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

async function prepareCleanNonHoverCapture(page, label) {
  const neutral = page.locator(".dialog-toolbar:visible").first();
  const box = await neutral.boundingBox();
  assert.ok(box, `${label}: neutral dialog chrome is unavailable`);
  await page.mouse.move(box.x + Math.min(8, box.width / 2), box.y + 4);
  await page.evaluate(() => {
    document.querySelectorAll(".event-reading-card:focus").forEach((card) => card.blur());
  });
  await page.waitForTimeout(330);
  const lens = await page.locator("#inspectionLens").evaluate((element) => ({
    hidden: element.hidden,
    visible: element.classList.contains("is-visible")
      && Number(getComputedStyle(element).opacity) > 0,
    readingId: element.dataset.readingId || "",
    mediaKind: element.dataset.mediaKind || "",
  }));
  assert.deepEqual(
    lens,
    { hidden: true, visible: false, readingId: "", mediaKind: "" },
    `${label}: unintended inspection lens contaminated privacy evidence`,
  );
  return lens;
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

async function scanCanonicalDownstream() {
  const textExtensions = new Set([".css", ".html", ".js", ".json", ".map", ".md", ".svg", ".txt"]);
  const candidates = [
    path.join(root, "metadata", "timetable-pulses.json"),
    path.join(root, "src", "timetable", "timetable-data.js"),
    ...await filesUnder(path.join(root, "docs", "timetable")),
    ...await filesUnder(path.join(root, "docs", "archive")),
  ].filter((filePath) => textExtensions.has(path.extname(filePath)));
  for (const filePath of candidates) {
    assertSecretsAbsent(await readFile(filePath, "utf8"), "canonical downstream");
  }
  return candidates.length;
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
  const canonicalFilesScanned = await scanCanonicalDownstream();
  await mkdir(fixtureSource, { recursive: true });
  await mkdir(auditRoot, { recursive: true });
  await cp(path.join(root, "src", "timetable"), fixtureSource, { recursive: true });

  const pulseSnapshot = JSON.parse(
    await readFile(path.join(root, "metadata", "timetable-pulses.json"), "utf8"),
  );
  pulseSnapshot.schema = "granted-hours-timetable-pulses-v6";
  const fixtureDay = pulseSnapshot.days.find((day) => day.date === "2026-07-21");
  const legacyReminder = fixtureDay.pulses.find(
    (pulse) => pulse.category === "daily_reminder",
  );
  assert.ok(legacyReminder, "fixture needs a reminder timing footprint");
  for (const day of pulseSnapshot.days) {
    day.pulses = day.pulses.filter((pulse) => pulse.category !== "daily_reminder");
  }
  const originalBody = (
    "Contact ████ about the ████ project.\n\n"
    + "You do not have to prove your worth to the external scoreboard. Allow yourself to rest."
  );
  const originalBodyZh = (
    "联系 ████ 讨论 ████ 项目。\n\n"
    + "不必向外部记分板证明自己的价值，也可以允许自己休息。"
  );
  const reminder = {
    start: legacyReminder.start,
    end: legacyReminder.end,
    duration_minutes: legacyReminder.duration_minutes,
    execution_minutes: legacyReminder.execution_minutes,
    time_bucket: legacyReminder.time_bucket,
    category: "daily_reminder",
    count: legacyReminder.count,
    time_provenance: legacyReminder.time_provenance,
    summary_provenance: "semantic_public_projection",
    owner_scope: "self",
    ownership_provenance: "explicit_import_authorization",
    disclosure_policy: "semantic_abstraction_entity_masked_reminder_v3",
    disclosure_authorization: "explicit_user_authorization_2026-07-29",
    public_label_zh: "晨间提醒",
    public_label_en: "Morning reminder",
    summary_original: originalBodyZh,
    excerpt_original: originalBodyZh,
    original_language: "zh",
    projection_kind: "verbatim_redacted",
    redaction_policy: "semantic_abstraction_then_entity_mask_v3",
    redaction_count: 2,
    semantic_abstraction_count: 0,
    projection_provenance: "semantic_public_projection",
    summary_en: originalBody,
    excerpt_en: originalBody,
    translation_provenance: "public_mask_preserving_translation_v1",
  };
  fixtureDay.pulses.push(reminder);
  fixtureDay.pulses.sort((left, right) => (
    left.start.localeCompare(right.start) || left.category.localeCompare(right.category)
  ));
  const tamperedSnapshot = structuredClone(pulseSnapshot);
  const tamperedReminder = tamperedSnapshot.days
    .find((day) => day.date === fixtureDay.date)
    .pulses.find((pulse) => pulse.category === "daily_reminder");
  tamperedReminder.raw_reconstruction_trap = syntheticSecrets.map((item) => item.value).join(" / ");
  await writeFile(
    fixturePulses,
    `${JSON.stringify(tamperedSnapshot, null, 2)}\n`,
    "utf8",
  );

  const builderOutput = path.join(fixtureSource, "timetable-data.js");
  let tamperedProjectionRejected = false;
  try {
    await execFileAsync(
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
  } catch (error) {
    tamperedProjectionRejected = true;
    assertSecretsAbsent(
      `${error.stdout || ""}\n${error.stderr || ""}`,
      "fail-closed builder logs",
    );
  }
  assert.equal(
    tamperedProjectionRejected,
    true,
    "a v2 reminder carrying a raw reconstruction field must fail closed",
  );
  await writeFile(
    fixturePulses,
    `${JSON.stringify(pulseSnapshot, null, 2)}\n`,
    "utf8",
  );
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
  assert.ok(
    generatedProjection.includes("Contact ████ about the ████ project."),
    "generated projection lost the original opening",
  );
  assert.ok(
    generatedProjection.includes("You do not have to prove your worth to the external scoreboard."),
    "generated projection lost the original reminder wording",
  );
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
      && document.querySelectorAll(
        ".routine-reading-card[data-pulse-category='daily_reminder']",
      ).length > 0,
  );

  const maskedReminder = page.locator(
    ".routine-reading-card[data-pulse-category='daily_reminder']",
  ).first();
  await maskedReminder.scrollIntoViewIfNeeded();
  await page.waitForTimeout(150);
  const reminderCardText = (await maskedReminder.textContent()) || "";
  assert.equal(reminderCardText.split("external scoreboard").length - 1, 1);
  assert.doesNotMatch(
    reminderCardText,
    /Masked residue|Inner weather|absence layer|public layer|contour/i,
  );
  await maskedReminder.click();
  await page.waitForSelector("#taskDialog:not([hidden])");
  const detailBody = (await page.locator("#taskDetailZh").textContent()) || "";
  const detailEnglishSectionVisible = await page.locator("#taskDetailEn")
    .evaluate((element) => !element.closest("section").hidden);
  const detailProvenance = (await page.locator("#taskDetailProvenance").textContent()) || "";
  assert.equal(detailBody, originalBodyZh);
  assert.equal(detailEnglishSectionVisible, true);
  assert.equal(detailProvenance, "");
  assert.equal(await page.locator("#taskDetailProvenance").isHidden(), true);
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

  const lensCleanState = await prepareCleanNonHoverCapture(
    page,
    "privacy-fixture-rendered-surface",
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
    tamperedProjectionRejected,
    scans: [
      "canonical generated and built artifacts",
      "isolated generated projection",
      "isolated built JS/CSS/HTML",
      "DOM and visible text",
      "all DOM attributes",
      "accessible names and attributes",
      "console/page/request logs",
      "screenshot OCR surface",
    ],
    fixedBars: renderedSurface.bars.length,
    canonicalFilesScanned,
    logEntriesScanned: pageLogs.length,
    ocrCharactersScanned: ocrRun.stdout.length,
    inspectionLens: {
      intended: false,
      cleanState: lensCleanState,
    },
    screenshot: screenshotPath,
  }, null, 2));
} finally {
  if (browser) await browser.close().catch(() => {});
  if (server) await new Promise((resolve) => server.close(resolve));
  await rm(fixtureRoot, { recursive: true, force: true });
}
