#!/usr/bin/env node
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { chromium } from "@playwright/test";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const screenshotRoot = process.env.QA_SCREENSHOT_DIR || "/tmp/granted-hours-visual-qa";
const sampleDate = "2026-07-26";
const screenshotPaths = [];

mkdirSync(screenshotRoot, { recursive: true });

async function createContext(browser, {
  theme,
  viewport,
  isMobile = false,
  hasTouch = false,
  reducedMotion = "no-preference",
}) {
  const context = await browser.newContext({
    viewport,
    colorScheme: theme,
    reducedMotion,
    isMobile,
    hasTouch,
    deviceScaleFactor: isMobile ? 2 : 1,
  });
  await context.addInitScript((explicitTheme) => {
    if (explicitTheme) localStorage.setItem("granted-hours-theme", explicitTheme);
  }, theme);
  return context;
}

async function prepareCleanNonHoverCapture(page, label, neutralSelector) {
  const neutral = page.locator(`${neutralSelector}:visible`).first();
  const box = await neutral.boundingBox();
  assert.ok(box, `${label}: neutral chrome is unavailable`);
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
    `${label}: unintended inspection lens contaminated theme evidence`,
  );
}

async function captureTheme(browser, theme, viewport, label, mobile) {
  const context = await createContext(browser, {
    theme,
    viewport,
    isMobile: mobile,
    hasTouch: mobile,
  });
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  const state = await page.evaluate(() => {
    const toggle = document.querySelector("#themeToggle");
    const toggleBox = toggle.getBoundingClientRect();
    const shellStyle = getComputedStyle(document.querySelector(".calendar-shell"));
    const bodyStyle = getComputedStyle(document.body);
    return {
      theme: document.documentElement.dataset.theme,
      colorScheme: document.documentElement.style.colorScheme,
      toggleLabel: toggle.getAttribute("aria-label"),
      toggleHeight: toggleBox.height,
      toggleWidth: toggleBox.width,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      bodyBackground: bodyStyle.backgroundImage,
      bodyColor: bodyStyle.color,
      shellBackground: shellStyle.backgroundColor,
      shellBackdrop: shellStyle.backdropFilter || shellStyle.webkitBackdropFilter,
    };
  });
  assert.equal(state.theme, theme);
  assert.equal(state.colorScheme, theme);
  assert.match(state.toggleLabel || "", /Switch to/);
  assert.ok(state.toggleHeight >= 44 && state.toggleWidth >= 44, JSON.stringify(state));
  assert.ok(state.overflow <= 1, `${label} ${theme} horizontal overflow: ${state.overflow}`);
  assert.notEqual(state.bodyBackground, "none");
  assert.notEqual(state.bodyColor, "rgba(0, 0, 0, 0)");
  if (!mobile) assert.notEqual(state.shellBackdrop, "none");

  await page.keyboard.press("Tab");
  const focusState = await page.evaluate(() => {
    const focused = document.activeElement;
    const style = getComputedStyle(focused);
    return {
      tag: focused?.tagName,
      outlineStyle: style.outlineStyle,
      outlineWidth: style.outlineWidth,
    };
  });
  assert.notEqual(focusState.outlineStyle, "none", JSON.stringify(focusState));
  assert.notEqual(focusState.outlineWidth, "0px", JSON.stringify(focusState));
  await page.evaluate(() => document.activeElement?.blur());

  const calendarPath = path.join(screenshotRoot, `${theme}-${label}-calendar.png`);
  await prepareCleanNonHoverCapture(
    page,
    `${theme}-${label}-calendar`,
    "#themeToggle",
  );
  await page.screenshot({ path: calendarPath, fullPage: false });
  screenshotPaths.push(calendarPath);

  if (mobile) {
    await page.tap(`.calendar-day-button[data-date="${sampleDate}"]`);
  } else {
    await page.click(`.calendar-day-button[data-date="${sampleDate}"]`);
  }
  await page.waitForSelector("#dayDialog.is-open");
  assert.match(await page.locator("#selfPreview").getAttribute("src"), /visual-preview\.gif$/);
  const dialogState = await page.evaluate(() => {
    const panel = document.querySelector("#dayDialogPanel");
    const touchToggle = document.querySelector("#timelineTouchToggle");
    return {
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      panelOverflowY: getComputedStyle(panel).overflowY,
      scrollable: panel.scrollHeight > panel.clientHeight,
      touchToggleDisplay: getComputedStyle(touchToggle).display,
      touchToggleHeight: touchToggle.getBoundingClientRect().height,
    };
  });
  assert.ok(dialogState.overflow <= 1, `${label} ${theme} dialog overflow`);
  assert.equal(dialogState.panelOverflowY, "auto");
  assert.equal(dialogState.scrollable, true);
  if (mobile) {
    assert.notEqual(dialogState.touchToggleDisplay, "none");
    assert.ok(dialogState.touchToggleHeight >= 44, JSON.stringify(dialogState));
  }

  const timelinePath = path.join(screenshotRoot, `${theme}-${label}-timeline.png`);
  await prepareCleanNonHoverCapture(
    page,
    `${theme}-${label}-timeline`,
    ".dialog-toolbar",
  );
  await page.screenshot({ path: timelinePath, fullPage: false });
  screenshotPaths.push(timelinePath);
  assert.deepEqual(pageErrors, []);
  await context.close();
  return state;
}

const browser = await chromium.launch({ headless: true });
try {
  for (const systemTheme of ["dark", "light"]) {
    const context = await browser.newContext({
      viewport: { width: 960, height: 720 },
      colorScheme: systemTheme,
    });
    const page = await context.newPage();
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    assert.equal(await page.locator("html").getAttribute("data-theme"), systemTheme);
    assert.equal(await page.evaluate(() => localStorage.getItem("granted-hours-theme")), null);
    await context.close();
  }

  const persistenceContext = await browser.newContext({
    viewport: { width: 960, height: 720 },
    colorScheme: "dark",
  });
  const persistencePage = await persistenceContext.newPage();
  await persistencePage.goto(baseUrl, { waitUntil: "networkidle" });
  assert.equal(await persistencePage.locator("html").getAttribute("data-theme"), "dark");
  await persistencePage.click("#themeToggle");
  assert.equal(await persistencePage.locator("html").getAttribute("data-theme"), "light");
  assert.equal(
    await persistencePage.evaluate(() => localStorage.getItem("granted-hours-theme")),
    "light",
  );
  await persistencePage.reload({ waitUntil: "networkidle" });
  assert.equal(await persistencePage.locator("html").getAttribute("data-theme"), "light");
  await persistenceContext.close();

  const results = [];
  for (const theme of ["dark", "light"]) {
    results.push(await captureTheme(
      browser,
      theme,
      { width: 1440, height: 900 },
      "desktop",
      false,
    ));
    results.push(await captureTheme(
      browser,
      theme,
      { width: 390, height: 844 },
      "mobile",
      true,
    ));
  }

  assert.notEqual(results[0].bodyBackground, results[2].bodyBackground);
  assert.notEqual(results[0].bodyColor, results[2].bodyColor);

  const zoomContext = await createContext(browser, {
    theme: "dark",
    viewport: { width: 720, height: 450 },
  });
  const zoomPage = await zoomContext.newPage();
  await zoomPage.goto(baseUrl, { waitUntil: "networkidle" });
  assert.ok(await zoomPage.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth <= 1,
  ));
  await zoomContext.close();

  const reducedContext = await createContext(browser, {
    theme: "dark",
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    reducedMotion: "reduce",
  });
  const reducedPage = await reducedContext.newPage();
  await reducedPage.goto(baseUrl, { waitUntil: "networkidle" });
  await reducedPage.tap(`.calendar-day-button[data-date="${sampleDate}"]`);
  await reducedPage.waitForSelector("#dayDialog.is-open");
  assert.match(await reducedPage.locator("#selfPreview").getAttribute("src"), /visual-preview\.webp$/);
  await reducedPage.waitForFunction(() => {
    const image = document.querySelector("#selfPreview");
    return image?.complete && image.naturalWidth > 0;
  });
  assert.equal(
    await reducedPage.locator(".autonomous-event").evaluate(
      (element) => getComputedStyle(element).animationName,
    ),
    "none",
  );
  await reducedContext.close();

  const fallbackContext = await createContext(browser, {
    theme: "dark",
    viewport: { width: 960, height: 720 },
  });
  await fallbackContext.route("**/visual-preview.gif", (route) => route.abort());
  const fallbackPage = await fallbackContext.newPage();
  await fallbackPage.goto(baseUrl, { waitUntil: "networkidle" });
  await fallbackPage.click(`.calendar-day-button[data-date="${sampleDate}"]`);
  await fallbackPage.waitForFunction(() => {
    const image = document.querySelector("#selfPreview");
    return image?.getAttribute("src")?.endsWith("visual-preview.webp") && image.complete && image.naturalWidth > 0;
  });
  await fallbackContext.close();
} finally {
  await browser.close();
}

console.log(JSON.stringify({
  passed: true,
  themes: ["dark", "light"],
  screenshots: screenshotPaths,
}, null, 2));
