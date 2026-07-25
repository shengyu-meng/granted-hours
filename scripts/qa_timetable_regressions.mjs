#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8771/timetable/";
const latestDate = [...timetableData.days].map((day) => day.date).sort().at(-1);
const phraseCounts = new Map();
const scheduleSignatures = new Set();
const categoryPatternCounts = new Map();
const categoryCounts = new Map();
const artworkTitleLeaks = [];

for (const day of timetableData.days) {
  const signature = day.task_residues.map((task) => `${task.start}-${task.end}:${task.zh}|${task.en}`).join("||");
  scheduleSignatures.add(signature);
  const categoryPattern = day.task_residues.map((task) => task.category).join("|");
  categoryPatternCounts.set(categoryPattern, (categoryPatternCounts.get(categoryPattern) || 0) + 1);
  for (const task of day.task_residues) {
    const phrase = `${task.zh}|${task.en}`;
    phraseCounts.set(phrase, (phraseCounts.get(phrase) || 0) + 1);
    categoryCounts.set(task.category, (categoryCounts.get(task.category) || 0) + 1);
    if (task.en.toLowerCase().includes(day.title_en.toLowerCase()) || task.zh.includes(day.title_zh)) {
      artworkTitleLeaks.push({ date: day.date, category: task.category, en: task.en });
    }
  }
}

const uniqueTaskPhrases = phraseCounts.size;
const maxPhraseReuse = Math.max(...phraseCounts.values());
const maxCategoryPatternReuse = Math.max(...categoryPatternCounts.values());
assert.ok(uniqueTaskPhrases >= 100, `expected >=100 historical task phrases; got ${uniqueTaskPhrases}`);
assert.ok(scheduleSignatures.size >= 60, `expected >=60 distinct daily schedules; got ${scheduleSignatures.size}`);
assert.ok(maxPhraseReuse <= 8, `one task phrase is reused ${maxPhraseReuse} times; history still looks templated`);
assert.equal(artworkTitleLeaks.length, 0, `assigned residues must not recycle autonomous artwork production: ${JSON.stringify(artworkTitleLeaks.slice(0, 5))}`);
assert.ok(maxCategoryPatternReuse <= 8, `one assigned category skeleton is reused ${maxCategoryPatternReuse} days`);
assert.ok((categoryCounts.get("social_media_organization") || 0) >= 20, `historical public-content work is underrepresented: ${categoryCounts.get("social_media_organization") || 0}`);

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2.75,
    isMobile: true,
    hasTouch: true,
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}?regression=mobile-detail`, { waitUntil: "networkidle" });

  const dateText = (await page.locator(".cell-date-number").first().textContent())?.trim() || "";
  assert.match(dateText, /^\d{1,2}\/\d{1,2}$/, `calendar cell must show month/day, got ${JSON.stringify(dateText)}`);

  await page.tap(`.calendar-day-button[data-date="${latestDate}"]`);
  await page.waitForFunction(() => document.activeElement?.id === "closeDetail");

  const before = await page.evaluate(() => {
    const dialog = document.querySelector("#dayDialog");
    const panel = document.querySelector(".day-dialog-panel");
    const layout = document.querySelector(".detail-layout");
    const lastTask = document.querySelector(".assigned-item:last-child");
    const self = document.querySelector(".self-detail");
    const track = document.querySelector(".sediment-track");
    const roots = [dialog, panel, layout].map((element) => ({
      selector: element.id ? `#${element.id}` : `.${element.classList[0]}`,
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
      overflowY: getComputedStyle(element).overflowY,
      touchAction: getComputedStyle(element).touchAction,
    }));
    return {
      roots,
      overlap: Math.max(0, lastTask.getBoundingClientRect().bottom - self.getBoundingClientRect().top),
      sedimentDisplay: getComputedStyle(track).display,
    };
  });

  assert.equal(before.sedimentDisplay, "none", "mobile decorative sediment track must not masquerade as a scrollbar");
  assert.ok(before.overlap <= 0.5, `last assigned task overlaps autonomous section by ${before.overlap}px`);

  const scrollable = before.roots.find((root) =>
    root.scrollHeight > root.clientHeight + 4 &&
    ["auto", "scroll"].includes(root.overflowY) &&
    root.touchAction !== "none"
  );
  assert.ok(scrollable, `no real touch-scroll container found: ${JSON.stringify(before.roots)}`);

  const scrollResult = await page.locator(scrollable.selector).evaluate((element) => {
    element.scrollTo({ top: element.scrollHeight, behavior: "instant" });
    return { scrollTop: element.scrollTop, max: element.scrollHeight - element.clientHeight };
  });
  assert.ok(scrollResult.scrollTop > 0, `scroll root ${scrollable.selector} did not move`);
  assert.ok(scrollResult.scrollTop >= scrollResult.max - 2, `scroll root ${scrollable.selector} cannot reach bottom`);

  const enterVisible = await page.locator("#enterAutonomous").evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return rect.top < innerHeight && rect.bottom > 0;
  });
  assert.ok(enterVisible, "autonomous live-work button is not reachable after scrolling to bottom");

  console.log(JSON.stringify({
    passed: true,
    latestDate,
    uniqueTaskPhrases,
    distinctDailySchedules: scheduleSignatures.size,
    maxPhraseReuse,
    dateText,
    scrollable,
    scrollResult,
  }, null, 2));
} finally {
  await browser.close();
}
