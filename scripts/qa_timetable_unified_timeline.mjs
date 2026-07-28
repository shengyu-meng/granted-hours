#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const days = [...timetableData.days].sort((a, b) => a.date.localeCompare(b.date));

let daysWithAssignedWork = 0;
for (const day of days) {
  assert.ok(day.background_pulses.length > 0, `${day.date} has no real background pulses`);
  assert.equal(day.timeline_events.filter((event) => event.origin === "self").length, 1);
  if (day.timeline_events.some((event) => event.origin === "assigned")) daysWithAssignedWork += 1;
  assert.ok(day.timeline_events.some((event) => event.origin === "background"));
  assert.match(day.autonomous_work.visual_preview_url, /visual-preview\.gif$/);
}
assert.ok(daysWithAssignedWork >= 40, `only ${daysWithAssignedWork} days expose assigned work`);

const browser = await chromium.launch({ headless: true });
try {
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await desktop.newPage();
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  await page.click('.calendar-day-button[data-date="2026-07-26"]');
  await page.waitForSelector("#dayDialog.is-open");
  assert.equal(await page.locator(".self-detail").count(), 0, "separate autonomous panel must be removed");
  assert.equal(await page.locator(".timeline-list").count(), 1);
  assert.equal(await page.locator(".autonomous-event").count(), 1);
  assert.ok(await page.locator(".pulse-event").count() > 0);
  assert.ok(await page.locator(".assigned-item").count() > 0);
  assert.equal(
    await page.locator(".routine-reading-card").count(),
    days.at(-1).reading_items.filter(
      (item) => item.source === "pulses",
    ).length,
    "background reading cards must match the public projection",
  );
  assert.ok(
    await page.locator(".routine-reading-card").count()
      < await page.locator(".pulse-event").count(),
    "climate projection must be smaller than the exact footprint audit",
  );
  const timelineTimes = await page.locator(".timeline-event").evaluateAll((events) =>
    events.map((event) => event.dataset.start),
  );
  assert.deepEqual(timelineTimes, [...timelineTimes].sort());
  const preview = await page.locator("#selfPreview").evaluate(async (image) => {
    await image.decode();
    return { src: image.currentSrc || image.src, width: image.naturalWidth, height: image.naturalHeight };
  });
  assert.match(preview.src, /visual-preview\.gif$/);
  assert.ok(preview.width > 0 && preview.height > 0, JSON.stringify(preview));

  const firstPulse = page.locator(".routine-reading-card").first();
  const readingId = await firstPulse.getAttribute("data-reading-id");
  const pulseEvidence = days.at(-1).reading_items.find(
    (item) => item.reading_id === readingId,
  );
  assert.ok(pulseEvidence, readingId);
  const sourcePulse = days.at(-1).background_pulses.find(
    (pulse) => pulse.footprint_id === pulseEvidence.source_refs[0],
  );
  const renderedSummaries = await firstPulse.locator(".pulse-summary > span").allTextContents();
  const expectedSummaryZh = renderedSummaries[0]?.trim() || sourcePulse?.summary_zh;
  const expectedSummaryEn = renderedSummaries[1]?.trim() || sourcePulse?.summary_en;
  await firstPulse.click({ force: true });
  await page.waitForSelector("#taskDialog.is-open");
  assert.equal((await page.locator("#taskDetailZh").textContent())?.trim(), expectedSummaryZh);
  assert.equal((await page.locator("#taskDetailEn").textContent())?.trim(), expectedSummaryEn);
  assert.match((await page.locator("#taskDetailTime").textContent()) || "", /(?:exact windows|window \d+ min)/);
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("#dayDialog").getAttribute("hidden"), null);

  const rows = page.locator(".assigned-item");
  let clampedIndex = -1;
  for (let index = 0; index < await rows.count(); index += 1) {
    const state = await rows.nth(index).locator(".assigned-copy").evaluate((copy) => {
      const style = getComputedStyle(copy);
      return {
        clamp: style.webkitLineClamp,
        overflow: style.overflow,
        clamped: copy.classList.contains("is-clamped"),
        ellipsis: getComputedStyle(copy, "::after").content,
      };
    });
    assert.equal(state.clamp, "4", JSON.stringify(state));
    assert.equal(state.overflow, "hidden");
    if (state.clamped) {
      assert.ok(state.ellipsis.includes("…"), `clamped summary lacks visible continuation ${JSON.stringify(state)}`);
      clampedIndex = index;
    }
  }

  const triggerIndex = clampedIndex >= 0 ? clampedIndex : 0;
  const trigger = rows.nth(triggerIndex);
  const selectedTask = days.at(-1).task_residues[triggerIndex];
  await trigger.scrollIntoViewIfNeeded();
  const dayScrollBefore = await page.locator("#dayDialogPanel").evaluate((panel) => {
    return panel.scrollTop;
  });
  await trigger.click();
  await page.waitForSelector("#taskDialog.is-open");
  assert.equal(await page.evaluate(() => document.activeElement?.id), "closeTaskDetail");
  assert.equal((await page.locator("#taskDetailZh").textContent())?.trim(), selectedTask.zh);
  assert.equal((await page.locator("#taskDetailEn").textContent())?.trim(), selectedTask.en);
  assert.ok((await page.locator("#taskDetailProvenance").textContent())?.includes(selectedTask.source_kind));
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("#taskDialog").getAttribute("hidden"), "");
  assert.equal(await page.locator("#dayDialog").getAttribute("hidden"), null);
  assert.equal(await page.evaluate(() => document.activeElement?.classList.contains("assigned-item")), true);
  assert.equal(await page.locator("#dayDialogPanel").evaluate((panel) => panel.scrollTop), dayScrollBefore);

  assert.equal(await page.locator("#nextDay").isDisabled(), true);
  assert.equal(await page.locator("#prevDay").isDisabled(), false);
  await page.locator("#dayDialogPanel").evaluate((panel) => { panel.scrollTop = panel.scrollHeight; });
  await page.click("#prevDay");
  assert.equal(await page.locator("#dayDialog").getAttribute("data-selected-date"), "2026-07-25");
  assert.ok(await page.locator("#dayDialogPanel").evaluate((panel) => panel.scrollTop <= 1));
  assert.equal(await page.evaluate(() => document.activeElement?.id), "prevDay");

  await page.keyboard.press("Escape");
  await page.click("#prevMonth");
  await page.click("#prevMonth");
  await page.click('.calendar-day-button[data-date="2026-05-31"]');
  await page.click("#nextDay");
  assert.equal(await page.locator("#dayDialog").getAttribute("data-selected-date"), "2026-06-01");
  assert.match((await page.locator("#todayButton").textContent()) || "", /June|6月/);
  await page.keyboard.press("Escape");

  await page.click("#prevMonth");
  await page.click('.calendar-day-button[data-date="2026-05-07"]');
  assert.equal(await page.locator("#prevDay").isDisabled(), true);
  assert.equal(await page.locator("#nextDay").isDisabled(), false);
  await page.keyboard.press("Escape");
  await desktop.close();

  for (const viewport of [
    { width: 390, height: 844, label: "mobile" },
    { width: 421, height: 386, label: "short-touch" },
  ]) {
    const context = await browser.newContext({
      viewport,
      isMobile: true,
      hasTouch: true,
      deviceScaleFactor: 2,
    });
    const mobile = await context.newPage();
    await mobile.goto(baseUrl, { waitUntil: "networkidle" });
    await mobile.tap('.calendar-day-button[data-date="2026-07-24"]');
    await mobile.waitForSelector("#dayDialog.is-open");
    assert.ok(
      await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth <= 1),
      `${viewport.label} horizontal overflow`,
    );
    await mobile.locator(".assigned-item").first().tap();
    assert.equal(await mobile.locator(".assigned-item").first().getAttribute("aria-pressed"), "true");
    assert.equal(await mobile.locator(".assigned-item").first().getAttribute("aria-expanded"), null);
    assert.equal(await mobile.locator("#taskDialog").getAttribute("hidden"), "");
    await mobile.locator(".assigned-item").first().tap();
    await mobile.waitForSelector("#taskDialog.is-open");
    const bounds = await mobile.locator("#taskDialogPanel").boundingBox();
    assert.ok(bounds && bounds.x >= 0 && bounds.y >= 0);
    assert.ok(bounds.x + bounds.width <= viewport.width + 1);
    assert.ok(bounds.y + bounds.height <= viewport.height + 1);
    await mobile.keyboard.press("Escape");
    assert.equal(await mobile.locator("#dayDialog").getAttribute("hidden"), null);
    assert.equal(await mobile.evaluate(() => document.activeElement?.classList.contains("assigned-item")), true);
    await mobile.keyboard.press("Escape");
    assert.equal(await mobile.locator("#dayDialog").getAttribute("hidden"), "");
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, days: days.length }, null, 2));
