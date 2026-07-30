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
import { timetableData } from "../src/timetable/timetable-data.js";

const execFileAsync = promisify(execFile);
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const fixtureRoot = await mkdtemp(path.join(root, ".shared-summary-fixture-"));
const fixtureSource = path.join(fixtureRoot, "src", "timetable");
const fixtureSite = path.join(fixtureRoot, "site");
const fixtureDate = "2026-05-07";
const fixtureData = structuredClone(timetableData);
const fixtureDay = fixtureData.days.find((day) => day.date === fixtureDate);
assert.ok(fixtureDay, `missing fixture day ${fixtureDate}`);

const climateProjection = fixtureDay.reading_items.find(
  (item) => item.classification === "climate_aggregate",
);
assert.ok(climateProjection, "fixture needs a climate projection");
fixtureDay.reading_items.push({
  ...climateProjection,
  reading_id: "qa-background-report",
  classification: "background_report",
});
fixtureData.days = [fixtureDay];
fixtureData.bgm_playlist = fixtureData.bgm_playlist.filter(
  (entry) => entry.date === fixtureDate,
);

const branchTargets = [
  {
    branch: "climate",
    selector: '.event-reading-card[data-classification="climate_aggregate"]',
    heading: "Summary / 摘要",
    reminder: false,
  },
  {
    branch: "promoted routine",
    selector: '.event-reading-card[data-classification="promoted_routine_exception"]',
    heading: "Summary / 摘要",
    reminder: false,
  },
  {
    branch: "original reminder",
    selector: '.event-reading-card[data-classification="readable_reminder"]',
    heading: "Original reminder / 提醒原文",
    reminder: true,
  },
  {
    branch: "background",
    selector: '.event-reading-card[data-reading-id="qa-background-report"]',
    heading: "Summary / 摘要",
    reminder: false,
  },
  {
    branch: "assigned task",
    selector: '.event-reading-card[data-classification="foreground_event"]',
    heading: "Summary / 摘要",
    reminder: false,
  },
];

const viewports = [
  { width: 1440, height: 900, label: "desktop-wide", touch: false },
  { width: 1024, height: 768, label: "desktop-compact", touch: false },
  { width: 768, height: 1024, label: "tablet-touch", touch: true },
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

async function activateCard(page, target, viewport) {
  const card = page.locator(target.selector).first();
  assert.ok(await card.count(), `${viewport.label}/${target.branch}: target card missing`);
  await card.scrollIntoViewIfNeeded();
  if (viewport.touch) {
    await card.tap();
    if (await page.locator("#taskDialog").getAttribute("hidden") !== null) {
      await card.tap();
    }
  } else {
    await card.focus();
    await page.keyboard.press("Enter");
  }
  await page.waitForSelector("#taskDialog.is-open");
  await page.waitForFunction(() => {
    const dialog = document.querySelector("#taskDialog");
    const panel = document.querySelector("#taskDialogPanel");
    return (
      dialog
      && panel
      && !dialog.hidden
      && dialog.classList.contains("is-open")
      && getComputedStyle(dialog).opacity === "1"
      && getComputedStyle(panel).transform === "none"
      && document.activeElement?.id === "closeTaskDetail"
    );
  });
  return card;
}

async function inspectBranch(page, target, viewport) {
  const card = await activateCard(page, target, viewport);
  assert.equal(
    await page.evaluate(() => document.activeElement?.id),
    "closeTaskDetail",
    `${viewport.label}/${target.branch}: detail did not receive focus`,
  );

  const topology = await page.locator(".task-detail-copy").evaluate((copy) => {
    const headings = [...copy.querySelectorAll("h3")];
    const section = copy.querySelector("#taskDetailSummary");
    const zh = copy.querySelector("#taskDetailZh");
    const en = copy.querySelector("#taskDetailEn");
    return {
      sectionCount: copy.querySelectorAll(":scope > section").length,
      headingCount: headings.length,
      headings: headings.map((heading) => heading.textContent.trim()),
      sharedSectionCount: copy.querySelectorAll(
        ":scope > #taskDetailSummary.task-detail-summary",
      ).length,
      sharedHeadingCount: copy.querySelectorAll(
        "#taskDetailSummaryHeading.summary-card-heading",
      ).length,
      ariaLabelledby: section?.getAttribute("aria-labelledby") || "",
      sharedSectionHidden: section?.hidden ?? null,
      legacyLabelIds: copy.querySelectorAll(
        "#taskDetailZhLabel, #taskDetailEnLabel",
      ).length,
      zhHidden: zh?.hidden ?? null,
      enHidden: en?.hidden ?? null,
      zhText: zh?.textContent.trim() || "",
      enText: en?.textContent.trim() || "",
      zhBeforeEn: Boolean(
        zh
        && en
        && (zh.compareDocumentPosition(en) & Node.DOCUMENT_POSITION_FOLLOWING)
      ),
    };
  });
  assert.deepEqual(
    {
      sectionCount: topology.sectionCount,
      headingCount: topology.headingCount,
      headings: topology.headings,
      sharedSectionCount: topology.sharedSectionCount,
      sharedHeadingCount: topology.sharedHeadingCount,
      ariaLabelledby: topology.ariaLabelledby,
      sharedSectionHidden: topology.sharedSectionHidden,
      legacyLabelIds: topology.legacyLabelIds,
      zhBeforeEn: topology.zhBeforeEn,
    },
    {
      sectionCount: 1,
      headingCount: 1,
      headings: [target.heading],
      sharedSectionCount: 1,
      sharedHeadingCount: 1,
      ariaLabelledby: "taskDetailSummaryHeading",
      sharedSectionHidden: false,
      legacyLabelIds: 0,
      zhBeforeEn: true,
    },
    (
      `${viewport.label}/${target.branch}: expected one shared summary card and heading; `
      + `observed topology ${JSON.stringify(topology)}`
    ),
  );
  assert.ok(topology.zhText.length > 0, `${viewport.label}/${target.branch}: empty first body`);
  if (target.reminder) {
    assert.equal(topology.zhHidden, false, `${viewport.label}: reminder first body hidden`);
    assert.equal(topology.enHidden, true, `${viewport.label}: reminder second body not hidden`);
    assert.equal(topology.enText, "", `${viewport.label}: reminder second body not empty`);
    const markdown = page.locator("#taskDetailZh.markdown-content");
    assert.equal(await markdown.count(), 1, `${viewport.label}: reminder Markdown container`);
    assert.ok(
      await markdown.locator(":is(h1, h2, h3, ul, ol, strong, code)").count() > 0,
      `${viewport.label}: reminder Markdown semantics missing`,
    );
  } else {
    assert.equal(topology.zhHidden, false, `${viewport.label}/${target.branch}: Chinese hidden`);
    assert.equal(topology.enHidden, false, `${viewport.label}/${target.branch}: English hidden`);
    assert.ok(topology.enText.length > 0, `${viewport.label}/${target.branch}: empty English body`);
  }

  const layout = await page.evaluate(() => {
    const documentElement = document.documentElement;
    const panel = document.querySelector("#taskDialogPanel");
    const section = document.querySelector("#taskDetailSummary");
    const provenance = document.querySelector("#taskDetailProvenance");
    const panelRect = panel.getBoundingClientRect();
    const sectionRect = section.getBoundingClientRect();
    const zh = document.querySelector("#taskDetailZh");
    const en = document.querySelector("#taskDetailEn");
    const zhRect = zh.getBoundingClientRect();
    const enRect = en.getBoundingClientRect();
    const enStyle = getComputedStyle(en);
    const dividerAlphaMatch = enStyle.borderTopColor.match(
      /^rgba\([^,]+,[^,]+,[^,]+,\s*([^)]+)\)$/,
    );
    const bodyOverflowX = ["taskDetailZh", "taskDetailEn"].map((id) => {
      const body = document.getElementById(id);
      return body.hidden ? 0 : body.scrollWidth - body.clientWidth;
    });
    panel.scrollTop = panel.scrollHeight;
    const provenanceRect = provenance.getBoundingClientRect();
    const scrolledPanelRect = panel.getBoundingClientRect();
    const result = {
      pageOverflowX: documentElement.scrollWidth - documentElement.clientWidth,
      panelOverflowX: panel.scrollWidth - panel.clientWidth,
      sectionOverflowX: section.scrollWidth - section.clientWidth,
      bodyOverflowX,
      panelRect: {
        left: panelRect.left,
        top: panelRect.top,
        right: panelRect.right,
        bottom: panelRect.bottom,
      },
      sectionInsidePanel: (
        sectionRect.left >= panelRect.left - 1
        && sectionRect.right <= panelRect.right + 1
      ),
      englishDisplay: enStyle.display,
      englishDivider: {
        width: enStyle.borderTopWidth,
        style: enStyle.borderTopStyle,
        color: enStyle.borderTopColor,
        gap: enRect.top - zhRect.bottom,
        paddingTop: Number.parseFloat(enStyle.paddingTop),
        alpha: dividerAlphaMatch ? Number.parseFloat(dividerAlphaMatch[1]) : 1,
      },
      maxScrollTop: panel.scrollHeight - panel.clientHeight,
      reachedScrollTop: panel.scrollTop,
      provenanceReachable: (
        provenanceRect.top >= scrolledPanelRect.top - 1
        && provenanceRect.bottom <= scrolledPanelRect.bottom + 1
      ),
    };
    panel.scrollTop = 0;
    return result;
  });
  assert.ok(layout.pageOverflowX <= 1, `${viewport.label}: page overflow ${JSON.stringify(layout)}`);
  assert.ok(layout.panelOverflowX <= 1, `${viewport.label}: panel overflow ${JSON.stringify(layout)}`);
  assert.ok(layout.sectionOverflowX <= 1, `${viewport.label}: section overflow ${JSON.stringify(layout)}`);
  assert.ok(
    layout.bodyOverflowX.every((overflow) => overflow <= 1),
    `${viewport.label}: body overflow ${JSON.stringify(layout)}`,
  );
  assert.ok(layout.panelRect.left >= -1 && layout.panelRect.top >= -1, `${viewport.label}: panel origin`);
  assert.ok(
    layout.panelRect.right <= viewport.width + 1
      && layout.panelRect.bottom <= viewport.height + 1,
    `${viewport.label}: panel viewport fit ${JSON.stringify(layout)}`,
  );
  assert.equal(layout.sectionInsidePanel, true, `${viewport.label}: summary escaped panel`);
  if (target.reminder) {
    assert.equal(layout.englishDisplay, "none", `${viewport.label}: hidden reminder English rendered`);
  } else {
    assert.deepEqual(
      {
        width: layout.englishDivider.width,
        style: layout.englishDivider.style,
      },
      {
        width: "1px",
        style: "solid",
      },
      `${viewport.label}/${target.branch}: language divider missing`,
    );
    assert.notEqual(
      layout.englishDivider.color,
      "rgba(0, 0, 0, 0)",
      `${viewport.label}/${target.branch}: language divider transparent`,
    );
    assert.ok(
      layout.englishDivider.gap >= 11
        && layout.englishDivider.paddingTop >= 11,
      `${viewport.label}/${target.branch}: language divider spacing ${JSON.stringify(layout)}`,
    );
    assert.ok(
      layout.englishDivider.alpha > 0
        && layout.englishDivider.alpha <= 0.25,
      `${viewport.label}/${target.branch}: language divider is not subtle ${JSON.stringify(layout)}`,
    );
  }
  assert.ok(
    layout.reachedScrollTop >= layout.maxScrollTop - 1,
    `${viewport.label}: panel end unreachable ${JSON.stringify(layout)}`,
  );
  assert.equal(layout.provenanceReachable, true, `${viewport.label}: provenance unreachable`);

  await page.keyboard.press("Tab");
  assert.equal(
    await page.evaluate(() => document.activeElement?.id),
    "closeTaskDetail",
    `${viewport.label}/${target.branch}: focus trap changed`,
  );
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => document.querySelector("#taskDialog")?.hidden);
  assert.equal(
    await card.evaluate((element) => document.activeElement === element),
    true,
    `${viewport.label}/${target.branch}: Escape did not restore card focus`,
  );
}

let browser;
let server;
try {
  await cp(path.join(root, "src", "timetable"), fixtureSource, { recursive: true });
  await writeFile(
    path.join(fixtureSource, "timetable-data.js"),
    `export const timetableData = ${JSON.stringify(fixtureData)};\n`,
    "utf8",
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
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.touch,
      hasTouch: viewport.touch,
      deviceScaleFactor: viewport.touch ? 2 : 1,
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(
      `${staticServer.url}?date=${encodeURIComponent(fixtureDate)}`,
      { waitUntil: "domcontentloaded" },
    );
    await page.waitForSelector("#dayDialog.is-open");
    await page.waitForFunction(() => (
      document.querySelector(".timeline-reading-layer.is-placed")
      && document.querySelectorAll(".event-reading-card").length > 0
    ));
    for (const target of branchTargets) {
      await inspectBranch(page, target, viewport);
    }
    assert.deepEqual(errors, [], `${viewport.label}: page errors`);
    results.push({
      viewport: `${viewport.width}x${viewport.height}`,
      touch: viewport.touch,
      branches: branchTargets.map((target) => target.branch),
    });
    await context.close();
  }
  console.log(JSON.stringify({
    passed: true,
    fixtureDate,
    topologyRedContract: "legacy two-section/two-heading dialog must fail",
    sharedSection: "taskDetailSummary.task-detail-summary",
    sharedHeading: "taskDetailSummaryHeading.summary-card-heading",
    viewports: results,
  }, null, 2));
} finally {
  if (browser) await browser.close().catch(() => {});
  if (server) await new Promise((resolve) => server.close(resolve));
  await rm(fixtureRoot, { recursive: true, force: true });
}
