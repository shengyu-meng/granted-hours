#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "https://shengyu-meng.github.io/granted-hours/timetable/";
const baseOrigin = new URL(baseUrl).origin;
const metadataDays = JSON.parse(readFileSync(new URL("../metadata/days.json", import.meta.url), "utf8"));
const expectedDates = metadataDays.map((day) => day.date).sort();
const actualDates = timetableData.days.map((day) => day.date).sort();
const latestDate = actualDates.at(-1);
const results = [];
const errors = [];

assert.deepEqual(actualDates, expectedDates);
for (const day of timetableData.days) {
  assert.match(day.autonomous_work.live_url, /^https:\/\/shengyu-meng\.github\.io\/granted-hours\/archive\/.+\/live\/$/);
  assert.match(day.autonomous_work.visual_preview_url, /^https:\/\/shengyu-meng\.github\.io\/granted-hours\/archive\/.+\/assets\/visual-preview\.gif$/);
}

const browser = await chromium.launch({ headless: true });

async function touchDrag(page, panelRect) {
  const client = await page.context().newCDPSession(page);
  const x = panelRect.left + panelRect.width * 0.5;
  const startY = Math.min(panelRect.bottom - 30, panelRect.viewportHeight - 30);
  const endY = Math.max(panelRect.top + 50, 50);
  await client.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: startY }] });
  for (let step = 1; step <= 8; step += 1) {
    await client.send("Input.dispatchTouchEvent", {
      type: "touchMove",
      touchPoints: [{ x, y: startY + ((endY - startY) * step) / 8 }],
    });
  }
  await client.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await page.waitForTimeout(80);
}

async function inspectViewport(spec) {
  const context = await browser.newContext(spec.context);
  const page = await context.newPage();
  const pageErrors = [];
  const recordError = (message) => {
    pageErrors.push(message);
    errors.push(`${spec.label}:${message}`);
  };
  page.on("pageerror", (error) => recordError(`page:${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && !/ERR_ABORTED|bgm/i.test(message.text())) {
      recordError(`console:${message.text()}`);
    }
  });
  page.on("response", (response) => {
    if (response.url().startsWith(baseOrigin) && response.status() >= 400) {
      recordError(`http:${response.status()}:${response.url()}`);
    }
  });

  await page.goto(`${baseUrl}?qa=${spec.label}`, { waitUntil: "networkidle" });
  const month = await page.evaluate(() => ({
    dates: [...document.querySelectorAll(".cell-date-number,.empty-date-number")].map((element) => element.textContent.trim()),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));
  assert.ok(month.dates.length > 0 && month.dates.every((date) => /^\d{1,2}\/\d{1,2}$/.test(date)));
  assert.ok(month.overflow <= 1, `${spec.label} calendar overflow ${month.overflow}`);

  const origin = page.locator(`.calendar-day-button[data-date="${latestDate}"]`);
  if (spec.mobile) await origin.tap();
  else await origin.click();
  await page.waitForFunction(() => document.activeElement?.id === "closeDetail");
  await page.waitForTimeout(180);

  const before = await page.evaluate(() => {
    const dialog = document.querySelector("#dayDialog");
    const panel = document.querySelector("#dayDialogPanel");
    const timeline = document.querySelector(".timeline-detail");
    const list = document.querySelector(".timeline-list");
    const candidates = [dialog, panel, timeline, list];
    const roots = candidates.map((element) => {
      const style = getComputedStyle(element);
      return {
        selector: element.id ? `#${element.id}` : `.${element.classList[0]}`,
        canScroll: element.scrollHeight > element.clientHeight + 2
          && ["auto", "scroll"].includes(style.overflowY),
        overflowY: style.overflowY,
      };
    });
    const rect = panel.getBoundingClientRect();
    return {
      activeId: document.activeElement?.id,
      backgroundInert: document.querySelector("#timetableRoot").hasAttribute("inert"),
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      panel: {
        ...rect.toJSON(),
        viewportHeight: innerHeight,
        scrollTop: panel.scrollTop,
        maxScroll: panel.scrollHeight - panel.clientHeight,
        overflowY: getComputedStyle(panel).overflowY,
        touchAction: getComputedStyle(panel).touchAction,
        overscrollBehaviorY: getComputedStyle(panel).overscrollBehaviorY,
      },
      roots,
      autonomousCount: document.querySelectorAll(".autonomous-event").length,
      pulseCount: document.querySelectorAll(".pulse-event").length,
      splitPanelCount: document.querySelectorAll(".self-detail,.detail-layout").length,
      taskCount: document.querySelectorAll(".assigned-item").length,
      timelineTimes: [...document.querySelectorAll(".timeline-event")].map((event) => event.dataset.start),
    };
  });
  assert.equal(before.activeId, "closeDetail");
  assert.equal(before.backgroundInert, true);
  assert.ok(before.overflow <= 1, `${spec.label} detail overflow ${before.overflow}`);
  assert.deepEqual(before.roots.filter((root) => root.canScroll).map((root) => root.selector), ["#dayDialogPanel"]);
  assert.equal(before.panel.overflowY, "auto");
  assert.equal(before.panel.touchAction, "pan-y");
  assert.equal(before.panel.overscrollBehaviorY, "contain");
  assert.equal(before.autonomousCount, 1);
  assert.ok(before.pulseCount > 0 && before.taskCount > 0);
  assert.equal(before.splitPanelCount, 0);
  assert.deepEqual(before.timelineTimes, [...before.timelineTimes].sort());
  if (spec.mobile) {
    assert.ok(Math.abs(before.panel.height - before.panel.viewportHeight) <= 1, JSON.stringify(before.panel));
    // the dialog sits inside a 12px safe-area gutter so the panel may be a few px shorter than the viewport
    assert.ok(before.panel.bottom <= before.panel.viewportHeight + 2, JSON.stringify(before.panel));
  } else {
    // the dialog is allowed to extend slightly beyond the viewport by the bottom safe-area margin
    assert.ok(before.panel.top >= 0, JSON.stringify(before.panel));
    assert.ok(before.panel.bottom <= before.panel.viewportHeight + 16, JSON.stringify(before.panel));
  }

  let accessibility;
  if (spec.mobile) {
    let progress = before.panel.scrollTop;
    for (let attempt = 0; attempt < 18; attempt += 1) {
      await touchDrag(page, before.panel);
      const current = await page.locator("#dayDialogPanel").evaluate((panel) => ({
        scrollTop: panel.scrollTop,
        maxScroll: panel.scrollHeight - panel.clientHeight,
      }));
      progress = current.scrollTop;
      if (current.scrollTop >= current.maxScroll - 2) break;
    }
    const bottom = await page.evaluate(() => {
      const panel = document.querySelector("#dayDialogPanel");
      const last = document.querySelector(".timeline-event:last-child").getBoundingClientRect();
      return {
        scrollTop: panel.scrollTop,
        maxScroll: panel.scrollHeight - panel.clientHeight,
        lastVisible: last.top >= -1 && last.bottom <= innerHeight + 1,
      };
    });
    assert.ok(progress > before.panel.scrollTop + 2, `${spec.label} native touch did not move`);
    assert.ok(bottom.scrollTop >= bottom.maxScroll - 2, `${spec.label} stopped at ${bottom.scrollTop}/${bottom.maxScroll}`);
    assert.equal(bottom.lastVisible, true);
    accessibility = bottom;
  } else {
    await page.locator(".assigned-item").last().scrollIntoViewIfNeeded();
    assert.ok(await page.locator(".assigned-item").last().isVisible());
    await page.locator("#enterAutonomous").scrollIntoViewIfNeeded();
    assert.ok(await page.locator("#enterAutonomous").isVisible());
    accessibility = await page.locator("#dayDialogPanel").evaluate((panel) => ({
      scrollTop: panel.scrollTop,
      maxScroll: panel.scrollHeight - panel.clientHeight,
    }));
  }

  await page.keyboard.press("Escape");
  await page.waitForFunction(() => document.querySelector("#dayDialog").hidden);
  if (spec.mobile) await origin.tap();
  else await origin.click();
  await page.waitForFunction(() => document.activeElement?.id === "closeDetail");
  assert.ok(await page.locator("#dayDialogPanel").evaluate((panel) => panel.scrollTop <= 1));
  await page.keyboard.press("Escape");
  await page.waitForFunction(() => document.querySelector("#dayDialog").hidden);
  const afterEscape = await page.evaluate((date) => ({
    hidden: document.querySelector("#dayDialog").hidden,
    backgroundInert: document.querySelector("#timetableRoot").hasAttribute("inert"),
    focusReturned: document.activeElement?.matches(`.calendar-day-button[data-date="${date}"]`) || false,
  }), latestDate);
  assert.deepEqual(afterEscape, { hidden: true, backgroundInert: false, focusReturned: true });

  results.push({ label: spec.label, month, detail: before, accessibility, afterEscape, pageErrors });
  await context.close();
}

try {
  const viewports = [
    { label: "desktop-1440x900", context: { viewport: { width: 1440, height: 900 } }, mobile: false },
    { label: "desktop-1024x768", context: { viewport: { width: 1024, height: 768 } }, mobile: false },
    { label: "desktop-768x700", context: { viewport: { width: 768, height: 700 } }, mobile: false },
    {
      label: "mobile-390x844",
      context: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2.75, isMobile: true, hasTouch: true },
      mobile: true,
    },
    {
      label: "mobile-421x386-touch",
      context: { viewport: { width: 421, height: 386 }, deviceScaleFactor: 2.75, isMobile: true, hasTouch: true },
      mobile: true,
    },
  ];
  for (const spec of viewports) await inspectViewport(spec);
  assert.deepEqual(errors, [], `page, console, or local HTTP errors:\n${errors.join("\n")}`);
  console.log(JSON.stringify({
    passed: true,
    baseUrl,
    latestDate,
    viewports: results.map((result) => ({
      label: result.label,
      calendarOverflow: result.month.overflow,
      detailOverflow: result.detail.overflow,
      scrollRoots: result.detail.roots.filter((root) => root.canScroll).map((root) => root.selector),
      maxScroll: result.detail.panel.maxScroll,
      pageErrors: result.pageErrors.length,
      focusReturned: result.afterEscape.focusReturned,
    })),
  }, null, 2));
} finally {
  await browser.close();
}
