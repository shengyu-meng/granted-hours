#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:4177/timetable/";
const audioVersionKey = "granted-hours-audio-defaults-version";
const audioVersion = "2026-08-10-default-on-v2";
const bgmKey = "granted-hours-calendar-bgm";
const pianoKey = "granted-hours-piano-sounds";
const errors = [];

function captureErrors(page) {
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => errors.push(`page: ${error.message}`));
  page.on("requestfailed", (request) => {
    errors.push(`request: ${request.url()} (${request.failure()?.errorText || "failed"})`);
  });
}

async function monthGeometry(context, date) {
  const page = await context.newPage();
  captureErrors(page);
  const url = new URL(baseUrl);
  url.searchParams.set("date", date);
  await page.goto(url.href, { waitUntil: "networkidle" });
  await page.keyboard.press("Escape");
  const geometry = await page.evaluate((targetDate) => {
    const grid = document.querySelector("#monthGrid");
    const cell = document.querySelector(`.date-cell[data-date="${targetDate}"]`);
    const gridBox = grid.getBoundingClientRect();
    const cells = [...grid.querySelectorAll(".date-cell")];
    const requiredSelectors = [
      ".protocol-bar",
      ".calendar-shell",
      ".calendar-head",
      ".month-controls",
      ".calendar-legend",
      "#monthGrid",
    ];
    const requiredBounds = requiredSelectors.map((selector) => {
      const box = document.querySelector(selector).getBoundingClientRect();
      return { selector, left: box.left, right: box.right };
    });
    return {
      weekCount: Number(grid.dataset.weekCount),
      gridHeight: gridBox.height,
      cellHeight: cell.getBoundingClientRect().height,
      lastCellBottom: Math.max(...cells.map((entry) => entry.getBoundingClientRect().bottom)),
      gridBottom: gridBox.bottom,
      horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      requiredBounds,
      contained: requiredBounds.every((box) => box.left >= -1 && box.right <= innerWidth + 1),
    };
  }, date);
  await page.close();
  return geometry;
}

async function geometryAudit(browser, viewport) {
  const context = await browser.newContext({
    viewport,
    hasTouch: viewport.width <= 720,
    isMobile: viewport.width <= 430,
  });
  const july = await monthGeometry(context, "2026-07-15");
  const august = await monthGeometry(context, "2026-08-10");
  assert.equal(july.weekCount, 5);
  assert.equal(august.weekCount, 6);
  assert.ok(Math.abs(july.cellHeight - august.cellHeight) <= 0.2, JSON.stringify({ july, august }));
  assert.ok(august.gridHeight > july.gridHeight + august.cellHeight * 0.9);
  assert.ok(july.lastCellBottom <= july.gridBottom + 1);
  assert.ok(august.lastCellBottom <= august.gridBottom + 1);
  assert.ok(july.horizontalOverflow <= 1);
  assert.ok(august.horizontalOverflow <= 1);
  assert.equal(july.contained, true, JSON.stringify(july.requiredBounds));
  assert.equal(august.contained, true, JSON.stringify(august.requiredBounds));
  await context.close();
  return { viewport, july, august };
}

async function audioAudit(browser) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await context.addInitScript(({ bgmKey, pianoKey }) => {
    localStorage.setItem(bgmKey, "off");
    localStorage.setItem(pianoKey, "off");
  }, { bgmKey, pianoKey });
  const page = await context.newPage();
  captureErrors(page);
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  const migrated = await page.evaluate(({ audioVersionKey, bgmKey, pianoKey }) => {
    const bgm = document.querySelector("#calendarBgmToggle");
    const piano = document.querySelector("#calendarPianoToggle");
    const style = getComputedStyle(bgm);
    return {
      bgmPressed: bgm.getAttribute("aria-pressed"),
      pianoPressed: piano.getAttribute("aria-pressed"),
      storedVersion: localStorage.getItem(audioVersionKey),
      storedBgm: localStorage.getItem(bgmKey),
      storedPiano: localStorage.getItem(pianoKey),
      backgroundColor: style.backgroundColor,
      color: style.color,
      borderColor: style.borderColor,
      boxShadow: style.boxShadow,
    };
  }, { audioVersionKey, bgmKey, pianoKey });
  assert.equal(migrated.bgmPressed, "true");
  assert.equal(migrated.pianoPressed, "true");
  assert.equal(migrated.storedVersion, audioVersion);
  assert.equal(migrated.storedBgm, "on");
  assert.equal(migrated.storedPiano, "on");
  assert.doesNotMatch(migrated.boxShadow, /16px/);

  await page.locator("#calendarBgmToggle").click();
  await page.locator("#calendarPianoToggle").click();
  assert.equal(await page.locator("#calendarBgmToggle").getAttribute("aria-pressed"), "false");
  assert.equal(await page.locator("#calendarPianoToggle").getAttribute("aria-pressed"), "false");
  await page.reload({ waitUntil: "networkidle" });
  assert.equal(await page.locator("#calendarBgmToggle").getAttribute("aria-pressed"), "false");
  assert.equal(await page.locator("#calendarPianoToggle").getAttribute("aria-pressed"), "false");
  await page.locator("#calendarBgmToggle").click();
  await page.locator("#calendarPianoToggle").click();
  assert.equal(await page.locator("#calendarBgmToggle").getAttribute("aria-pressed"), "true");
  assert.equal(await page.locator("#calendarPianoToggle").getAttribute("aria-pressed"), "true");
  await context.close();
  return migrated;
}

const browser = await chromium.launch({ headless: true });
try {
  const geometry = [];
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
    { width: 421, height: 386 },
  ]) {
    geometry.push(await geometryAudit(browser, viewport));
  }
  const audio = await audioAudit(browser);
  assert.deepEqual(errors, [], `browser errors: ${JSON.stringify(errors)}`);
  console.log(JSON.stringify({ passed: true, geometry, audio }, null, 2));
} finally {
  await browser.close();
}
