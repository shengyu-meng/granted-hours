#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const timetableUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const day = [...timetableData.days]
  .reverse()
  .find((candidate) => candidate.autonomous_work?.origin !== "absence");
assert.ok(day, "No autonomous artwork is available for the preview recovery audit");

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  await context.route("**/visual-preview.gif*", (route) => route.abort("failed"));
  const page = await context.newPage();
  const url = new URL(timetableUrl);
  url.searchParams.set("date", day.date);
  await page.goto(url.href, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForSelector(`#dayDialog.is-open[data-selected-date="${day.date}"]`);
  const preview = page.locator("#selfPreview");
  await page.waitForFunction(() => (
    document.querySelector("#selfPreview")?.dataset.previewState === "static-fallback"
  ));
  assert.match(await preview.getAttribute("src"), /visual-preview\.webp(?:\?.*)?$/);

  await context.unroute("**/visual-preview.gif*");
  await page.locator(".autonomous-preview-frame").hover();
  await page.waitForFunction(() => (
    document.querySelector("#selfPreview")?.dataset.previewState === "animated"
  ), null, { timeout: 45000 });
  const recovered = await preview.evaluate((image) => ({
    src: image.currentSrc || image.src,
    state: image.dataset.previewState,
    attempt: image.dataset.previewRetryAttempt,
    radius: getComputedStyle(image).borderRadius,
    width: image.naturalWidth,
    height: image.naturalHeight,
  }));
  assert.match(recovered.src, /visual-preview\.gif\?gh_preview_retry=[12]$/);
  assert.equal(recovered.state, "animated");
  assert.ok(["1", "2"].includes(recovered.attempt));
  assert.notEqual(recovered.radius, "0px");
  assert.ok(recovered.width > 0 && recovered.height > 0);
  console.log(JSON.stringify({ passed: true, date: day.date, recovered }, null, 2));
} finally {
  await browser.close();
}
