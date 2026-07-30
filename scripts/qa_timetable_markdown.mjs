#!/usr/bin/env node
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import {
  cp,
  mkdtemp,
  readFile,
  rm,
  stat,
  writeFile,
} from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { chromium } from "@playwright/test";

const execFileAsync = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixtureRoot = await mkdtemp(path.join(root, ".markdown-fixture-"));
const fixtureSource = path.join(fixtureRoot, "src", "timetable");
const fixtureSite = path.join(fixtureRoot, "site");
const fixturePulses = path.join(fixtureRoot, "pulses.json");
const fixtureDate = "2026-07-21";
const fixedBlock = "████";
const markdownBody = [
  "# Grounding",
  "",
  "P **steady** *gentle*  ",
  `L \`inline()\` ${fixedBlock}`,
  "",
  "- u",
  "",
  "1. o",
  "",
  "> q",
  "",
  "```js",
  "x()",
  "```",
  "",
  "[h](https://e.co) [m](mailto:q%40e.invalid) [j](javascript:x) [d](data:x) [v](vbscript:x)",
  "<script>x</script><style>x</style><iframe></iframe><img src=x onerror=x>",
].join("\n");
const viewports = [
  { width: 1440, height: 900, label: "desktop", touch: false },
  { width: 390, height: 844, label: "mobile", touch: true },
  { width: 421, height: 386, label: "short-touch", touch: true },
];

function mimeType(filePath) {
  return {
    ".css": "text/css; charset=utf-8",
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
  }[path.extname(filePath)] || "application/octet-stream";
}

async function startStaticServer(directory) {
  const resolvedDirectory = path.resolve(directory);
  const server = http.createServer(async (request, response) => {
    try {
      const pathname = decodeURIComponent(new URL(request.url, "http://127.0.0.1").pathname);
      let candidate = path.resolve(directory, `.${pathname}`);
      if (
        candidate !== resolvedDirectory
        && !candidate.startsWith(`${resolvedDirectory}${path.sep}`)
      ) {
        response.writeHead(403).end();
        return;
      }
      if ((await stat(candidate)).isDirectory()) {
        candidate = path.join(candidate, "index.html");
      }
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

async function assertMarkdownSemantics(container, label) {
  assert.equal(await container.locator(":scope > h1").count(), 1, `${label}: heading`);
  assert.ok(await container.locator(":scope > p").count() >= 1, `${label}: paragraph`);
  assert.equal(await container.locator("strong").count(), 1, `${label}: strong`);
  assert.equal(await container.locator("em").count(), 1, `${label}: emphasis`);
  assert.equal(await container.locator("br").count(), 1, `${label}: hard line break`);
  assert.equal(await container.locator(":scope > ul").count(), 1, `${label}: unordered list`);
  assert.equal(await container.locator(":scope > ol").count(), 1, `${label}: ordered list`);
  assert.equal(await container.locator(":scope > blockquote").count(), 1, `${label}: blockquote`);
  assert.equal(await container.locator("p > code").count(), 1, `${label}: inline code`);
  assert.equal(await container.locator(":scope > pre > code").count(), 1, `${label}: fenced code`);
}

async function assertXssBoundary(page, container, label, { interactiveLinks = true } = {}) {
  assert.equal(
    await container.locator("script, style, iframe, img").count(),
    0,
    `${label}: dangerous elements`,
  );
  assert.equal(
    await container.locator("[onabort], [onerror], [onload], [onclick], [onmouseover]").count(),
    0,
    `${label}: event-handler attributes`,
  );
  const links = await container.locator("a").evaluateAll((anchors) => anchors.map((anchor) => ({
    href: anchor.getAttribute("href"),
    target: anchor.getAttribute("target"),
    rel: anchor.getAttribute("rel"),
  })));
  if (!interactiveLinks) {
    assert.deepEqual(links, [], `${label}: compact cards must not contain focusable links`);
    assert.equal(
      await container.locator(".markdown-link-label").count(),
      2,
      `${label}: safe link labels should remain visible without nested interaction`,
    );
    assert.equal(await page.evaluate(() => window.__markdownXss), "", `${label}: XSS marker`);
    return;
  }
  assert.deepEqual(
    links.map((link) => link.href),
    ["https://e.co/", "mailto:q%40e.invalid"],
    `${label}: only allowlisted URLs should remain links`,
  );
  for (const link of links) {
    assert.equal(link.target, "_blank", `${label}: external target`);
    assert.deepEqual(
      new Set((link.rel || "").split(/\s+/).filter(Boolean)),
      new Set(["noopener", "noreferrer"]),
      `${label}: external rel`,
    );
  }
  assert.equal(await page.evaluate(() => window.__markdownXss), "", `${label}: XSS marker`);
}

async function inspectViewport(browser, url, viewport) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    isMobile: viewport.touch,
    hasTouch: viewport.touch,
    deviceScaleFactor: viewport.touch ? 2 : 1,
  });
  await context.addInitScript(() => {
    window.__markdownXss = "";
  });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto(url, { waitUntil: "networkidle" });
  await page.locator(`.calendar-day-button[data-date="${fixtureDate}"]`).click();
  await page.waitForSelector("#dayDialog.is-open");
  const card = page.locator(
    ".routine-reading-card[data-pulse-category='daily_reminder']",
  ).first();
  await card.waitFor();
  await page.waitForFunction(() => {
    const layer = document.querySelector(".timeline-reading-layer");
    return layer?.classList.contains("is-placed");
  });

  const cardMarkdown = card.locator(".markdown-content");
  await assertMarkdownSemantics(cardMarkdown, `${viewport.label} card`);
  await assertXssBoundary(page, cardMarkdown, `${viewport.label} card`, {
    interactiveLinks: false,
  });
  assert.equal(await card.evaluate((element) => element.tagName), "BUTTON");
  const accessibleName = await card.getAttribute("aria-label") || "";
  assert.match(accessibleName, /Grounding/, `${viewport.label}: plain accessible name`);
  assert.ok(accessibleName.includes(fixedBlock), `${viewport.label}: accessible redaction block`);
  assert.doesNotMatch(
    accessibleName,
    /(?:^|\s)#{1,6}\s|\*\*|```|`inline|\]\(|<script|<style|<iframe|<img/i,
    `${viewport.label}: accessible name exposed Markdown or HTML tokens`,
  );
  const cardBars = await card.locator(".redaction-block").allTextContents();
  assert.deepEqual(cardBars, [fixedBlock], `${viewport.label}: fixed card redaction`);
  const compactState = await cardMarkdown.evaluate((element) => {
    const card = element.closest(".event-reading-card");
    return {
      cardOverflow: getComputedStyle(card).overflow,
      contentOverflowX: getComputedStyle(element).overflowX,
      contentOverflowY: getComputedStyle(element).overflowY,
      clipped: element.scrollHeight > element.clientHeight + 1,
      horizontalOverflow: element.scrollWidth - element.clientWidth,
    };
  });
  assert.equal(compactState.cardOverflow, "hidden", `${viewport.label}: compact card overflow`);
  assert.ok(compactState.clipped, `${viewport.label}: long Markdown should be compactly clipped`);
  assert.ok(
    compactState.horizontalOverflow <= 1,
    `${viewport.label}: card Markdown horizontal overflow ${JSON.stringify(compactState)}`,
  );

  if (viewport.touch) {
    await card.tap();
    assert.equal(await card.getAttribute("aria-pressed"), "true");
    assert.equal(await page.locator("#taskDialog").getAttribute("hidden"), "");
    await card.tap();
  } else {
    await card.focus();
    await page.keyboard.press("Enter");
  }
  await page.waitForSelector("#taskDialog.is-open");
  const detailMarkdown = page.locator("#taskDetailZh.markdown-content");
  await assertMarkdownSemantics(detailMarkdown, `${viewport.label} detail`);
  await assertXssBoundary(page, detailMarkdown, `${viewport.label} detail`);
  await context.route("https://e.co/**", (route) => route.fulfill({
    status: 200,
    contentType: "text/html",
    body: "<!doctype html><title>Safe external Markdown link</title>",
  }));
  const externalPagePromise = context.waitForEvent("page");
  await detailMarkdown.locator("a").first().click();
  const externalPage = await externalPagePromise;
  await externalPage.waitForLoadState("domcontentloaded");
  assert.equal(
    await page.locator("#taskDialog").getAttribute("hidden"),
    null,
    `${viewport.label}: detail link unexpectedly closed the event detail`,
  );
  await externalPage.close();
  assert.ok(
    (await detailMarkdown.textContent() || "").includes("x()"),
    `${viewport.label}: full detail was truncated`,
  );
  assert.deepEqual(
    await detailMarkdown.locator(".redaction-block").allTextContents(),
    [fixedBlock],
    `${viewport.label}: fixed detail redaction`,
  );

  const geometry = await page.evaluate(() => {
    const documentElement = document.documentElement;
    const taskPanel = document.querySelector("#taskDialogPanel");
    const panelRect = taskPanel.getBoundingClientRect();
    const timeline = document.querySelector(".timeline-list");
    const eventsLayerRect = document.querySelector(".timeline-events-layer").getBoundingClientRect();
    const minuteHeight = Number.parseFloat(
      getComputedStyle(timeline).getPropertyValue("--minute-height"),
    );
    const toMinutes = (value) => {
      const [hours, minutes] = value.split(":").map(Number);
      return hours * 60 + minutes;
    };
    const cards = [...document.querySelectorAll(".event-reading-card")].map((card) => {
      const rect = card.getBoundingClientRect();
      return {
        id: card.dataset.readingId,
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
      };
    });
    const cardOverlaps = [];
    for (let leftIndex = 0; leftIndex < cards.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < cards.length; rightIndex += 1) {
        const left = cards[leftIndex];
        const right = cards[rightIndex];
        const overlapX = Math.min(left.right, right.right) - Math.max(left.left, right.left);
        const overlapY = Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top);
        if (overlapX > 1 && overlapY > 1) {
          cardOverlaps.push([left.id, right.id]);
        }
      }
    }
    const markdownContainers = [
      ...document.querySelectorAll(".event-reading-card .markdown-content, #taskDetailZh.markdown-content"),
    ];
    return {
      viewport: { width: innerWidth, height: innerHeight },
      pageOverflowX: documentElement.scrollWidth - documentElement.clientWidth,
      panel: {
        left: panelRect.left,
        top: panelRect.top,
        right: panelRect.right,
        bottom: panelRect.bottom,
      },
      markdownOverflowX: markdownContainers.map(
        (element) => element.scrollWidth - element.clientWidth,
      ),
      cardOverlaps,
      eventFootprints: [...document.querySelectorAll(".timeline-event")].map((event) => {
        const rect = event.getBoundingClientRect();
        const startMinute = toMinutes(event.dataset.start);
        const durationMinutes = toMinutes(event.dataset.end) - startMinute;
        return {
          start: event.dataset.start,
          end: event.dataset.end,
          topError: Math.abs(
            rect.top - eventsLayerRect.top - startMinute * minuteHeight
          ),
          heightError: Math.abs(rect.height - durationMinutes * minuteHeight),
        };
      }),
    };
  });
  assert.ok(geometry.pageOverflowX <= 1, `${viewport.label}: page horizontal overflow`);
  assert.ok(
    geometry.markdownOverflowX.every((overflow) => overflow <= 1),
    `${viewport.label}: Markdown horizontal overflow ${JSON.stringify(geometry.markdownOverflowX)}`,
  );
  assert.ok(geometry.panel.left >= -1 && geometry.panel.top >= -1, `${viewport.label}: panel origin`);
  assert.ok(
    geometry.panel.right <= viewport.width + 1
      && geometry.panel.bottom <= viewport.height + 1,
    `${viewport.label}: panel viewport fit ${JSON.stringify(geometry.panel)}`,
  );
  assert.deepEqual(geometry.cardOverlaps, [], `${viewport.label}: reading cards overlap`);
  for (const footprint of geometry.eventFootprints) {
    assert.ok(
      footprint.topError <= 0.25 && footprint.heightError <= 0.25,
      `${viewport.label}: untruthful footprint geometry ${JSON.stringify(footprint)}`,
    );
  }
  assert.deepEqual(errors, [], `${viewport.label}: page errors`);
  await context.close();
  return {
    label: viewport.label,
    size: `${viewport.width}x${viewport.height}`,
    pageOverflowX: geometry.pageOverflowX,
    markdownOverflowX: Math.max(...geometry.markdownOverflowX),
    cardOverlaps: geometry.cardOverlaps.length,
    maxFootprintError: Math.max(...geometry.eventFootprints.flatMap(
      (footprint) => [footprint.topError, footprint.heightError],
    )),
    eventFootprints: geometry.eventFootprints.length,
  };
}

let browser;
let server;
try {
  await cp(path.join(root, "src", "timetable"), fixtureSource, { recursive: true });
  const pulseSnapshot = JSON.parse(
    await readFile(path.join(root, "metadata", "timetable-pulses.json"), "utf8"),
  );
  pulseSnapshot.schema = "granted-hours-timetable-pulses-v5";
  const fixtureDay = pulseSnapshot.days.find((day) => day.date === fixtureDate);
  assert.ok(fixtureDay, "fixture date is missing");
  const sourceReminder = fixtureDay.pulses.find(
    (pulse) => pulse.category === "daily_reminder",
  );
  assert.ok(sourceReminder, "fixture date needs a reminder timing footprint");
  for (const day of pulseSnapshot.days) {
    day.pulses = day.pulses.filter((pulse) => pulse.category !== "daily_reminder");
  }
  fixtureDay.pulses.push({
    ...sourceReminder,
    summary_original: markdownBody,
    excerpt_original: markdownBody,
    original_language: "en",
    projection_kind: "verbatim_redacted",
    redaction_policy: "targeted_entity_mask_v2",
    redaction_count: 1,
  });
  fixtureDay.pulses.sort((left, right) => (
    left.start.localeCompare(right.start) || left.category.localeCompare(right.category)
  ));
  await writeFile(fixturePulses, `${JSON.stringify(pulseSnapshot, null, 2)}\n`, "utf8");

  await execFileAsync(
    "python3",
    [
      path.join(root, "scripts", "build_timetable_data.py"),
      "--pulses",
      fixturePulses,
      "--output",
      path.join(fixtureSource, "timetable-data.js"),
    ],
    { cwd: root },
  );
  await execFileAsync(
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

  const staticServer = await startStaticServer(fixtureSite);
  server = staticServer.server;
  browser = await chromium.launch({ headless: true });
  const results = [];
  for (const viewport of viewports) {
    results.push(await inspectViewport(browser, staticServer.url, viewport));
  }
  console.log(JSON.stringify({
    passed: true,
    fixtureDate,
    semantics: [
      "paragraphs and hard line breaks",
      "strong and emphasis",
      "heading",
      "ordered and unordered lists",
      "blockquote",
      "inline and fenced code",
      "allowlisted links",
    ],
    xssBoundary: [
      "raw script/style/iframe/img",
      "event-handler attributes",
      "javascript/data/vbscript URLs",
    ],
    viewports: results,
  }, null, 2));
} finally {
  if (browser) await browser.close().catch(() => {});
  if (server) await new Promise((resolve) => server.close(resolve));
  await rm(fixtureRoot, { recursive: true, force: true });
}
