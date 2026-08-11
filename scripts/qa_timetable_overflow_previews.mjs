#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8896/timetable/";
const sampleDate = "2026-07-28";
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

async function openMonth(page) {
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  await page.locator(`.calendar-day-button[data-date="${sampleDate}"]`).waitFor();
}

async function desktopAudit(browser) {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  captureErrors(page);
  await openMonth(page);

  const monthOrdering = await page.locator(".cell-material").evaluateAll((elements) => ({
    everyDayStartsWithAutonomous: elements.every(
      (element) => element.firstElementChild?.classList.contains("self-mark"),
    ),
    fitted: elements.map((element) => ({
      overflowPreview: element.dataset.overflowPreview,
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    })).find((state) => state.overflowPreview === "false") || null,
  }));
  assert.equal(monthOrdering.everyDayStartsWithAutonomous, true);
  assert.ok(monthOrdering.fitted, "month sample needs a non-overflowing control cell");
  assert.ok(monthOrdering.fitted.scrollHeight <= monthOrdering.fitted.clientHeight + 1);

  const day = page.locator(`.calendar-day-button[data-date="${sampleDate}"]`);
  const material = day.locator(".cell-material");
  const monthBefore = await material.evaluate((element) => ({
    assignedMarks: element.querySelectorAll(".assigned-mark").length,
    firstPreviewClass: element.firstElementChild?.className || "",
    firstPreviewText: element.firstElementChild?.textContent?.trim() || "",
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
    scrollTop: element.scrollTop,
    overflowY: getComputedStyle(element).overflowY,
    overflowPreview: element.dataset.overflowPreview,
  }));
  assert.ok(monthBefore.assignedMarks > 2, "month cell still discards events after the first two");
  assert.match(monthBefore.firstPreviewClass, /self-mark/);
  assert.match(monthBefore.firstPreviewText, /自主\s*\/\s*SELF/);
  assert.equal(monthBefore.overflowY, "auto");
  assert.equal(monthBefore.overflowPreview, "true");
  assert.ok(monthBefore.scrollHeight > monthBefore.clientHeight + 1);

  await day.hover();
  await page.mouse.wheel(0, 150);
  await page.waitForTimeout(100);
  const monthAfter = await material.evaluate((element) => ({
    scrollTop: element.scrollTop,
    maximumScrollTop: element.scrollHeight - element.clientHeight,
    transform: getComputedStyle(element.closest(".calendar-day-button")).transform,
    thumbBackground: getComputedStyle(element, "::-webkit-scrollbar-thumb").backgroundColor,
  }));
  assert.ok(monthAfter.scrollTop > monthBefore.scrollTop, "wheel did not scroll the hovered month cell");
  assert.ok(monthAfter.scrollTop <= monthAfter.maximumScrollTop + 1);
  assert.equal(monthAfter.transform, "matrix(1, 0, 0, 1, 0, -2)");
  assert.notEqual(monthAfter.thumbBackground, "rgba(0, 0, 0, 0)");

  await day.click();
  await page.locator("#dayDialog.is-open").waitFor();
  await page.waitForTimeout(500);
  const cards = page.locator(".event-reading-card");
  const cardStates = await cards.evaluateAll((elements) => elements.map((element, index) => ({
    index,
    autonomousArtwork: Boolean(element.querySelector(".autonomous-preview-frame")),
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
    overflowY: getComputedStyle(element).overflowY,
    overflowPreview: element.dataset.overflowPreview,
    isButton: element instanceof HTMLButtonElement,
  })));
  const autonomousArtwork = cardStates.find((state) => state.autonomousArtwork);
  assert.ok(autonomousArtwork, "representative date has no autonomous artwork card");
  assert.equal(autonomousArtwork.overflowY, "hidden");
  assert.equal(autonomousArtwork.overflowPreview, undefined);
  assert.ok(autonomousArtwork.scrollHeight <= autonomousArtwork.clientHeight + 1);

  const overflowing = cardStates.find(
    (state) => !state.autonomousArtwork && state.scrollHeight > state.clientHeight + 1,
  );
  assert.ok(overflowing, "representative date has no overflowing event card");
  assert.equal(overflowing.overflowY, "auto");
  assert.equal(overflowing.overflowPreview, "true");

  const card = cards.nth(overflowing.index);
  await card.hover();
  await page.mouse.wheel(0, 140);
  await page.waitForTimeout(100);
  const cardAfter = await card.evaluate((element) => ({
    scrollTop: element.scrollTop,
    maximumScrollTop: element.scrollHeight - element.clientHeight,
    transform: getComputedStyle(element).transform,
    borderRadius: getComputedStyle(element).borderRadius,
    thumbBackground: getComputedStyle(element, "::-webkit-scrollbar-thumb").backgroundColor,
  }));
  assert.ok(cardAfter.scrollTop > 0, "wheel did not scroll the hovered event card");
  assert.ok(cardAfter.scrollTop <= cardAfter.maximumScrollTop + 1);
  assert.equal(cardAfter.transform, "matrix(1, 0, 0, 1, 0, -4)");
  assert.equal(cardAfter.borderRadius, "18px");
  assert.notEqual(cardAfter.thumbBackground, "rgba(0, 0, 0, 0)");

  const fitting = cardStates.find((state) => state.scrollHeight <= state.clientHeight + 1);
  if (fitting) assert.equal(fitting.overflowPreview, "false");

  assert.ok(
    await page.locator("html").evaluate((element) => element.scrollWidth <= element.clientWidth + 1),
    "desktop page has horizontal overflow",
  );
  await page.close();
  return { monthBefore, monthAfter, overflowing, cardAfter };
}

async function mobileAudit(browser) {
  const page = await browser.newPage({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
  });
  captureErrors(page);
  await openMonth(page);
  await page.locator(`.calendar-day-button[data-date="${sampleDate}"]`).click();
  await page.locator("#dayDialog.is-open").waitFor();
  await page.waitForTimeout(500);
  const state = await page.evaluate(() => {
    const cards = [...document.querySelectorAll(".event-reading-card")];
    const autonomousArtwork = cards.find((card) => card.querySelector(".autonomous-preview-frame"));
    const overflowing = cards.find(
      (card) => card !== autonomousArtwork && card.scrollHeight > card.clientHeight + 1,
    );
    const toolbarButtons = [...document.querySelectorAll(
      ".dialog-day-nav, .dialog-sound-toggle, .dialog-close",
    )];
    return {
      cardFound: Boolean(overflowing),
      overflowY: overflowing ? getComputedStyle(overflowing).overflowY : "",
      touchAction: overflowing ? getComputedStyle(overflowing).touchAction : "",
      overflowPreview: overflowing?.dataset.overflowPreview || "",
      autonomousArtwork: autonomousArtwork ? {
        overflowY: getComputedStyle(autonomousArtwork).overflowY,
        overflowPreview: autonomousArtwork.dataset.overflowPreview || "",
        fits: autonomousArtwork.scrollHeight <= autonomousArtwork.clientHeight + 1,
      } : null,
      horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      smallestToolbarTarget: Math.min(...toolbarButtons.map((button) => button.getBoundingClientRect().height)),
    };
  });
  assert.equal(state.cardFound, true);
  assert.equal(state.overflowY, "auto");
  assert.equal(state.touchAction, "pan-y");
  assert.equal(state.overflowPreview, "true");
  assert.deepEqual(state.autonomousArtwork, {
    overflowY: "hidden",
    overflowPreview: "",
    fits: true,
  });
  assert.ok(state.horizontalOverflow <= 1);
  assert.ok(state.smallestToolbarTarget >= 44);
  await page.close();
  return state;
}

const browser = await chromium.launch({ headless: true });
try {
  const desktop = await desktopAudit(browser);
  const mobile = await mobileAudit(browser);
  assert.deepEqual(errors, [], `browser errors: ${JSON.stringify(errors)}`);
  console.log(JSON.stringify({ passed: true, desktop, mobile }, null, 2));
} finally {
  await browser.close();
}
