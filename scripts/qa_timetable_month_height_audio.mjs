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
    if (request.failure()?.errorText === "net::ERR_ABORTED" && request.resourceType() === "media") return;
    if (
      new URL(request.url()).pathname === "/cdn-cgi/rum"
      && request.failure()?.errorText === "net::ERR_ABORTED"
    ) return;
    errors.push(`request: ${request.url()} (${request.failure()?.errorText || "failed"})`);
  });
}

async function monthGeometry(page, date) {
  await page.waitForFunction((targetDate) => {
    const grid = document.querySelector("#monthGrid");
    const target = document.querySelector(`.date-cell[data-date="${targetDate}"]:not(.is-muted)`);
    if (!grid || !target || grid.dataset.previewItemFloor !== "3") return false;
    return [...grid.querySelectorAll(".date-cell:not(.is-muted) .calendar-day-button")]
      .filter((button) => button.querySelectorAll(".cell-mark").length >= 3)
      .every((button) => {
        const materialBox = button.querySelector(".cell-material").getBoundingClientRect();
        const thirdMarkBox = button.querySelectorAll(".cell-mark")[2].getBoundingClientRect();
        return thirdMarkBox.top >= materialBox.top - 1
          && thirdMarkBox.bottom <= materialBox.bottom + 1;
      });
  }, date);
  const geometry = await page.evaluate((targetDate) => {
    const grid = document.querySelector("#monthGrid");
    const cell = document.querySelector(`.date-cell[data-date="${targetDate}"]`);
    const gridBox = grid.getBoundingClientRect();
    const cells = [...grid.querySelectorAll(".date-cell")];
    const cellHeights = cells.map((entry) => entry.getBoundingClientRect().height);
    const eligiblePreviews = [...grid.querySelectorAll(".date-cell:not(.is-muted) .calendar-day-button")]
      .map((button) => {
        const marks = [...button.querySelectorAll(".cell-mark")];
        if (marks.length < 3) return null;
        const materialBox = button.querySelector(".cell-material").getBoundingClientRect();
        const thirdMarkBox = marks[2].getBoundingClientRect();
        return {
          date: button.dataset.date,
          markCount: marks.length,
          thirdVisible: thirdMarkBox.top >= materialBox.top - 1
            && thirdMarkBox.bottom <= materialBox.bottom + 1,
        };
      })
      .filter(Boolean);
    const renderedPreviews = [...grid.querySelectorAll(".date-cell:not(.is-muted) .calendar-day-button")]
      .map((button) => {
        const material = button.querySelector(".cell-material");
        const marks = [...button.querySelectorAll(".cell-mark")];
        const firstMark = marks[0];
        const materialStyle = getComputedStyle(material);
        const paddingTop = Number.parseFloat(materialStyle.paddingTop) || 0;
        const firstMarkOffset = firstMark
          ? firstMark.getBoundingClientRect().top - material.getBoundingClientRect().top - paddingTop
          : 0;
        const primaryCount = Number(button.dataset.previewPrimaryCount);
        const fillerCount = Number(button.dataset.routineFillerCount);
        const previewTarget = Number(button.dataset.previewTarget);
        return {
          date: button.dataset.date,
          alignContent: materialStyle.alignContent,
          firstMarkOffset,
          expanded: button.classList.contains("has-expanded-preview"),
          primaryCount,
          fillerCount,
          previewTarget,
          markCount: marks.length,
          routineMarkCount: button.querySelectorAll(".routine-mark").length,
          detailCount: button.querySelectorAll(".cell-mark-detail").length,
          hasRoutineSource: Boolean(button.querySelector(".cell-source-bar.routine")),
        };
      });
    const routineFilledPreviews = renderedPreviews.filter((entry) => entry.fillerCount > 0);
    const densePreviews = renderedPreviews.filter((entry) => entry.primaryCount >= entry.previewTarget);
    const sourceEmptyExpandedPreviews = renderedPreviews.filter((entry) => (
      entry.expanded && !entry.hasRoutineSource
    ));
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
    const headerControls = ["#themeToggle", "#calendarPianoToggle", "#calendarBgmSkip", "#calendarBgmToggle"]
      .map((selector) => {
        const box = document.querySelector(selector).getBoundingClientRect();
        return { selector, width: box.width, height: box.height };
      });
    const authorCredit = document.querySelector(".brand-byline");
    const authorLinks = [...authorCredit.querySelectorAll("a")];
    const authorCreditBox = authorCredit.getBoundingClientRect();
    const brandBox = document.querySelector(".brand-lockup").getBoundingClientRect();
    const footerAuthor = document.querySelector(".calendar-foot .author-credit");
    const stampSample = document.querySelector(".cell-artwork-stamp");
    return {
      weekCount: Number(grid.dataset.weekCount),
      gridHeight: gridBox.height,
      cellHeight: cell.getBoundingClientRect().height,
      cellHeightSpread: Math.max(...cellHeights) - Math.min(...cellHeights),
      lastCellBottom: Math.max(...cells.map((entry) => entry.getBoundingClientRect().bottom)),
      gridBottom: gridBox.bottom,
      previewItemFloor: Number(grid.dataset.previewItemFloor),
      eligiblePreviewCount: eligiblePreviews.length,
      failedPreviewDates: eligiblePreviews.filter((entry) => !entry.thirdVisible).map((entry) => entry.date),
      topAlignedPreviewCount: renderedPreviews.length,
      failedTopAlignmentDates: renderedPreviews
        .filter((entry) => entry.alignContent !== "start" || Math.abs(entry.firstMarkOffset) > 3)
        .map((entry) => entry.date),
      routineFilledPreviewCount: routineFilledPreviews.length,
      failedRoutineFillDates: routineFilledPreviews
        .filter((entry) => (
          !entry.expanded
          || !entry.hasRoutineSource
          || entry.primaryCount + entry.fillerCount < entry.previewTarget
          || entry.markCount < entry.previewTarget
          || entry.routineMarkCount !== entry.fillerCount
          || entry.detailCount < entry.primaryCount + entry.fillerCount
        ))
        .map((entry) => entry.date),
      missingRoutineFillDates: renderedPreviews
        .filter((entry) => entry.expanded && entry.hasRoutineSource && entry.fillerCount === 0)
        .map((entry) => entry.date),
      failedDenseMutationDates: densePreviews
        .filter((entry) => entry.expanded || entry.fillerCount > 0 || entry.detailCount > 0)
        .map((entry) => entry.date),
      failedNoFabricationDates: sourceEmptyExpandedPreviews
        .filter((entry) => entry.fillerCount > 0 || entry.routineMarkCount > 0)
        .map((entry) => entry.date),
      horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      requiredBounds,
      headerControls,
      interiorEntryPresent: Boolean(document.querySelector('a[href*="/maze"], .maze-thread')),
      authorNames: authorLinks.map((link) => link.textContent.trim()),
      authorHrefs: authorLinks.map((link) => link.href),
      authorLinkHeights: authorLinks.map((link) => link.getBoundingClientRect().height),
      authorCreditBox: {
        left: authorCreditBox.left,
        right: authorCreditBox.right,
        top: authorCreditBox.top,
        bottom: authorCreditBox.bottom,
      },
      brandBox: {
        left: brandBox.left,
        top: brandBox.top,
      },
      footerAuthorPresent: Boolean(footerAuthor),
      stampPresent: Boolean(stampSample),
      contained: requiredBounds.every((box) => box.left >= -1 && box.right <= innerWidth + 1),
    };
  }, date);
  return geometry;
}

async function geometryAudit(browser, viewport) {
  const context = await browser.newContext({
    viewport,
    hasTouch: viewport.width <= 720,
    isMobile: viewport.width <= 430,
  });
  const page = await context.newPage();
  captureErrors(page);
  const url = new URL(baseUrl);
  url.searchParams.set("date", "2026-05-15");
  await page.goto(url.href, { waitUntil: "networkidle" });
  await page.keyboard.press("Escape");
  const months = [];
  for (const date of ["2026-05-15", "2026-06-15", "2026-07-15", "2026-08-10"]) {
    months.push(await monthGeometry(page, date));
    if (date !== "2026-08-10") {
      await page.locator("#nextMonth").evaluate((button) => button.click());
    }
  }
  const [may, june, july, august] = months;
  assert.equal(july.weekCount, 5);
  assert.equal(august.weekCount, 6);
  for (const geometry of months) {
    assert.ok(geometry.cellHeightSpread <= 0.2, JSON.stringify(geometry));
    assert.ok(geometry.lastCellBottom <= geometry.gridBottom + 1);
    assert.ok(geometry.horizontalOverflow <= 1);
    assert.equal(geometry.contained, true, JSON.stringify(geometry.requiredBounds));
    assert.equal(geometry.previewItemFloor, 3);
    assert.ok(geometry.eligiblePreviewCount > 0, JSON.stringify(geometry));
    assert.deepEqual(geometry.failedPreviewDates, [], JSON.stringify(geometry));
    assert.ok(geometry.topAlignedPreviewCount > 0, JSON.stringify(geometry));
    assert.deepEqual(geometry.failedTopAlignmentDates, [], JSON.stringify(geometry));
    assert.ok(geometry.routineFilledPreviewCount > 0, JSON.stringify(geometry));
    assert.deepEqual(geometry.failedRoutineFillDates, [], JSON.stringify(geometry));
    assert.deepEqual(geometry.missingRoutineFillDates, [], JSON.stringify(geometry));
    assert.deepEqual(geometry.failedDenseMutationDates, [], JSON.stringify(geometry));
    assert.deepEqual(geometry.failedNoFabricationDates, [], JSON.stringify(geometry));
    assert.equal(geometry.interiorEntryPresent, false, JSON.stringify(geometry));
    assert.deepEqual(geometry.authorNames, ["Simon Meng", "Hermes Agent"], JSON.stringify(geometry));
    assert.deepEqual(
      geometry.authorHrefs,
      ["https://hyperint.net/me", "https://hermes-agent.nousresearch.com/"],
      JSON.stringify(geometry),
    );
    assert.ok(geometry.authorCreditBox.left >= -1, JSON.stringify(geometry));
    assert.ok(geometry.authorCreditBox.right <= viewport.width + 1, JSON.stringify(geometry));
    assert.equal(geometry.footerAuthorPresent, false, JSON.stringify(geometry));
    assert.equal(geometry.stampPresent, true, JSON.stringify(geometry));
    assert.ok(geometry.authorCreditBox.top >= geometry.brandBox.top - 1, JSON.stringify(geometry));
    assert.ok(geometry.authorCreditBox.left >= geometry.brandBox.left - 1, JSON.stringify(geometry));
  }
  if (viewport.width <= 720) {
    for (const geometry of months) {
      const [theme, piano, skip, bgm] = geometry.headerControls;
      assert.ok(Math.abs(theme.width - piano.width) <= 0.2, JSON.stringify(geometry.headerControls));
      assert.ok(Math.abs(theme.width - bgm.width) <= 0.2, JSON.stringify(geometry.headerControls));
      assert.ok(Math.abs(theme.width - skip.width) <= 0.2, JSON.stringify(geometry.headerControls));
      assert.ok(Math.abs(theme.height - piano.height) <= 0.2, JSON.stringify(geometry.headerControls));
      assert.ok(Math.abs(theme.height - bgm.height) <= 0.2, JSON.stringify(geometry.headerControls));
      assert.ok(Math.abs(theme.height - skip.height) <= 0.2, JSON.stringify(geometry.headerControls));
      assert.ok(theme.width <= 44.2 && theme.height <= 44.2, JSON.stringify(geometry.headerControls));
      assert.ok(
        geometry.authorLinkHeights.every((height) => height >= 10),
        JSON.stringify(geometry.authorLinkHeights),
      );
    }
  }
  await page.close();
  await context.close();
  return { viewport, may, june, july, august };
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
      bgmVolume: document.querySelector("#calendarBgm").volume,
      bgmOutputGain: Number(document.querySelector("#calendarBgm").dataset.outputGain),
      pianoOutputGain: Number(piano.dataset.outputGain),
      pianoOutputLimiter: piano.dataset.outputLimiter,
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
  assert.equal(migrated.bgmVolume, 0.34);
  assert.equal(migrated.bgmOutputGain, migrated.bgmVolume);
  assert.equal(migrated.pianoOutputGain, migrated.bgmOutputGain);
  assert.equal(migrated.pianoOutputLimiter, "-12dBTP");
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
  const skipAudit = await page.evaluate(() => {
    const archiveLink = [...document.querySelectorAll(".quiet-nav a")].find((link) => (
      link.textContent.trim() === "Archive"
    ));
    const skip = document.querySelector("#calendarBgmSkip");
    const skipBox = skip.getBoundingClientRect();
    const bgmBox = document.querySelector("#calendarBgmToggle").getBoundingClientRect();
    return {
      archivePresent: Boolean(archiveLink),
      skipLabel: skip.getAttribute("aria-label") || "",
      skipIcon: Boolean(skip.querySelector("svg")),
      dateBefore: document.querySelector("#calendarBgm").dataset.date || "",
      skipWidth: skipBox.width,
      skipHeight: skipBox.height,
      bgmWidth: bgmBox.width,
      bgmHeight: bgmBox.height,
    };
  });
  assert.equal(skipAudit.archivePresent, false, JSON.stringify(skipAudit));
  assert.match(skipAudit.skipLabel, /random archived BGM/i);
  assert.equal(skipAudit.skipIcon, true, JSON.stringify(skipAudit));
  assert.ok(Math.abs(skipAudit.skipWidth - skipAudit.bgmWidth) <= 0.2, JSON.stringify(skipAudit));
  assert.ok(Math.abs(skipAudit.skipHeight - skipAudit.bgmHeight) <= 0.2, JSON.stringify(skipAudit));
  await page.locator("#calendarBgmSkip").click();
  const dateAfter = await page.locator("#calendarBgm").getAttribute("data-date");
  assert.ok(dateAfter && dateAfter !== skipAudit.dateBefore, JSON.stringify({ skipAudit, dateAfter }));
  assert.equal(await page.locator("#calendarBgmToggle").getAttribute("aria-pressed"), "true");
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
    { width: 3840, height: 2160 },
  ]) {
    geometry.push(await geometryAudit(browser, viewport));
  }
  const audio = await audioAudit(browser);
  assert.deepEqual(errors, [], `browser errors: ${JSON.stringify(errors)}`);
  console.log(JSON.stringify({ passed: true, geometry, audio }, null, 2));
} finally {
  await browser.close();
}
