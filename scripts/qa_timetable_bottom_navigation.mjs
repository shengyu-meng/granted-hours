#!/usr/bin/env node
import assert from "node:assert/strict";
import fs from "node:fs";
fs.mkdirSync("tmp/calendar-motion-qa", {recursive:true});
import { chromium } from "@playwright/test";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:4177/timetable/";
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

async function bottomNavAudit(browser, viewport) {
  const context = await browser.newContext({ viewport, hasTouch: viewport.width <= 430, reducedMotion: "reduce" });
  const page = await context.newPage();
  captureErrors(page);
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  const initialState = await page.evaluate(() => {
    const topTitle = document.querySelector("#monthTitle")?.textContent || "";
    const topToday = document.querySelector("#todayButton")?.textContent || "";
    const bottomToday = document.querySelector("#todayButtonBottom")?.textContent || "";
    const bottomControls = document.querySelector("#bottomMonthControls");
    const prevBottom = document.querySelector("#prevMonthBottom");
    const nextBottom = document.querySelector("#nextMonthBottom");
    const prevTop = document.querySelector("#prevMonth");
    const nextTop = document.querySelector("#nextMonth");
    return {
      topTitle,
      topToday,
      bottomToday,
      bottomControlsPresent: Boolean(bottomControls),
      prevBottomPresent: Boolean(prevBottom),
      nextBottomPresent: Boolean(nextBottom),
      prevTopPresent: Boolean(prevTop),
      nextTopPresent: Boolean(nextTop),
      prevBottomAriaLabel: prevBottom?.getAttribute("aria-label") || "",
      nextBottomAriaLabel: nextBottom?.getAttribute("aria-label") || "",
      prevBottomWidth: prevBottom?.getBoundingClientRect().width || 0,
      prevBottomHeight: prevBottom?.getBoundingClientRect().height || 0,
      nextBottomWidth: nextBottom?.getBoundingClientRect().width || 0,
      nextBottomHeight: nextBottom?.getBoundingClientRect().height || 0,
      bottomControlsBottom: bottomControls?.getBoundingClientRect().bottom || 0,
      viewportHeight: innerHeight,
    };
  });

  assert.equal(initialState.bottomControlsPresent, true, "bottomControls should be present");
  assert.equal(initialState.prevBottomPresent, true, "prevMonthBottom should be present");
  assert.equal(initialState.nextBottomPresent, true, "nextMonthBottom should be present");
  assert.equal(initialState.prevTopPresent, true, "prevMonth (top) should be present");
  assert.equal(initialState.nextTopPresent, true, "nextMonth (top) should be present");
  assert.equal(initialState.topTitle, initialState.bottomToday, "bottom todayButton should match top title initially");
  assert.equal(initialState.topTitle, initialState.topToday, "top todayButton should match top title");
  assert.ok(initialState.prevBottomAriaLabel.includes("Previous month"), "prevBottom should have bilingual aria-label");
  assert.ok(initialState.nextBottomAriaLabel.includes("Next month"), "nextBottom should have bilingual aria-label");

  // Touch target check (min 44px)
  if (viewport.width <= 430) {
    assert.ok(initialState.prevBottomHeight >= 44, `prevBottom height ${initialState.prevBottomHeight} should be >= 44px`);
    assert.ok(initialState.nextBottomHeight >= 44, `nextBottom height ${initialState.nextBottomHeight} should be >= 44px`);
  }

  // Test navigation - click next month on bottom
  if (viewport.width <= 430) await page.locator("#nextMonthBottom").tap();
  else await page.locator("#nextMonthBottom").click();
  await page.waitForTimeout(300); // Wait for transition

  const afterNextState = await page.evaluate(() => {
    const topTitle = document.querySelector("#monthTitle")?.textContent || "";
    const topToday = document.querySelector("#todayButton")?.textContent || "";
    const bottomToday = document.querySelector("#todayButtonBottom")?.textContent || "";
    return { topTitle, topToday, bottomToday };
  });

  assert.notEqual(afterNextState.topTitle, initialState.topTitle, "next must change the month");
  assert.equal(afterNextState.topTitle, afterNextState.bottomToday, "bottom todayButton should sync after next month");
  assert.equal(afterNextState.topTitle, afterNextState.topToday, "top todayButton should match top title after next month");

  // Test navigation - click prev month on bottom
  await page.locator("#prevMonthBottom").click();
  await page.waitForTimeout(300);

  const afterPrevState = await page.evaluate(() => {
    const topTitle = document.querySelector("#monthTitle")?.textContent || "";
    const bottomToday = document.querySelector("#todayButtonBottom")?.textContent || "";
    return { topTitle, bottomToday };
  });

  assert.equal(afterPrevState.topTitle, initialState.topTitle, "prev must return to original month");
  assert.equal(afterPrevState.topTitle, afterPrevState.bottomToday, "bottom todayButton should sync after prev month");

  // Test top navigation still works independently
  await page.locator("#nextMonth").click();
  await page.waitForTimeout(300);

  const afterTopNextState = await page.evaluate(() => {
    const topTitle = document.querySelector("#monthTitle")?.textContent || "";
    const bottomToday = document.querySelector("#todayButtonBottom")?.textContent || "";
    return { topTitle, bottomToday };
  });

  assert.equal(afterTopNextState.topTitle, afterTopNextState.bottomToday, "bottom should sync when top next is clicked");

  await page.locator('#prevMonthBottom').focus();
  await page.keyboard.press('Enter');
  await page.waitForTimeout(350);
  assert.equal(await page.locator('#monthTitle').textContent(), initialState.topTitle);
  assert.equal(await page.evaluate(() => document.activeElement.id), 'prevMonthBottom');
  await page.locator('#bottomMonthControls').scrollIntoViewIfNeeded();
  await page.screenshot({path:`tmp/calendar-motion-qa/bottom-${viewport.width}.png`});
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'no horizontal overflow');
  await page.close();
  await context.close();
  return initialState;
}

const browser = await chromium.launch({ headless: true });
try {
  const results = [];
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 390, height: 844 },
    { width: 421, height: 386 },
    { width: 3840, height: 2160 },
  ]) {
    results.push(await bottomNavAudit(browser, viewport));
  }
  assert.deepEqual(errors, [], `browser errors: ${JSON.stringify(errors)}`);
  console.log(JSON.stringify({ passed: true, results }, null, 2));
} finally {
  await browser.close();
}