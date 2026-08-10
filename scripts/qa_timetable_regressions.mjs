#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8771/timetable/";
const latestDate = [...timetableData.days].map((day) => day.date).sort().at(-1);
const phraseCounts = new Map();
const scheduleSignatures = new Set();
const categoryPatternCounts = new Map();
const artworkTitleLeaks = [];

for (const day of timetableData.days) {
  scheduleSignatures.add(day.task_residues.map((task) => `${task.start}-${task.end}:${task.zh}|${task.en}`).join("||"));
  const categoryPattern = day.task_residues.map((task) => task.category).join("|");
  categoryPatternCounts.set(categoryPattern, (categoryPatternCounts.get(categoryPattern) || 0) + 1);
  assert.equal(day.timeline_events.filter((event) => event.origin === "self" || event.origin === "absence").length, 1, day.date);
  if (day.type === "calendar" && day.background_pulses.length === 0) {
    assert.equal(day.timeline_events.some((event) => event.origin === "background"), false, day.date);
  } else {
    assert.ok(day.timeline_events.some((event) => event.origin === "background"), day.date);
  }
  assert.deepEqual(
    day.timeline_events.map((event) => event.start),
    [...day.timeline_events.map((event) => event.start)].sort(),
    day.date,
  );
  for (const task of day.task_residues) {
    const phrase = `${task.request_zh || task.zh}|${task.outcome_zh || task.en}`;
    phraseCounts.set(phrase, (phraseCounts.get(phrase) || 0) + 1);
    if (task.en.toLowerCase().includes(day.title_en.toLowerCase()) || task.zh.includes(day.title_zh)) {
      artworkTitleLeaks.push({ date: day.date, phrase });
    }
  }
}

assert.ok(phraseCounts.size >= 100, `only ${phraseCounts.size} unique phrases`);
assert.ok(scheduleSignatures.size >= 40, `only ${scheduleSignatures.size} unique schedules`);
assert.ok(Math.max(...phraseCounts.values()) <= 10);
assert.ok(Math.max(...categoryPatternCounts.values()) <= 35);
assert.equal(artworkTitleLeaks.length, 0, JSON.stringify(artworkTitleLeaks.slice(0, 5)));

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({
    viewport: { width: 421, height: 386 },
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 2.75,
  });
  const page = await context.newPage();
  await page.goto(baseUrl, { waitUntil: "networkidle" });
  if (await page.locator("#dayDialog.is-open").count()) {
    await page.locator("#closeDetail").click();
  }
  await page.tap(`.calendar-day-button[data-date="${latestDate}"]`);
  await page.waitForSelector("#dayDialog.is-open");
  const result = await page.evaluate(() => {
    const panel = document.querySelector("#dayDialogPanel");
    const candidates = [
      document.querySelector("#dayDialog"),
      panel,
      document.querySelector(".timeline-detail"),
      document.querySelector(".timeline-list"),
    ].filter(Boolean);
    const roots = candidates.map((element) => {
      const style = getComputedStyle(element);
      return {
        selector: element.id ? `#${element.id}` : `.${element.classList[0]}`,
        overflowY: style.overflowY,
        canScroll: element.scrollHeight > element.clientHeight + 4
          && ["auto", "scroll"].includes(style.overflowY),
      };
    });
    panel.scrollTop = panel.scrollHeight;
    const endScrollTop = panel.scrollTop;
    const timelineBottomAtEnd = document.querySelector(".timeline-list").getBoundingClientRect().bottom;
    const lastEvent = document.querySelector(".timeline-event:last-child");
    lastEvent.scrollIntoView({ block: "end" });
    const last = lastEvent.getBoundingClientRect();
    return {
      roots,
      splitPanelCount: document.querySelectorAll(".self-detail,.detail-layout").length,
      autonomousCount: document.querySelectorAll(".autonomous-event").length,
      pulseCount: document.querySelectorAll(".pulse-event").length,
      sedimentCount: document.querySelectorAll(".sediment-track").length,
      endScrollTop,
      maxScroll: panel.scrollHeight - panel.clientHeight,
      timelineBottomAtEnd,
      lastTop: last.top,
      lastBottom: last.bottom,
      viewport: innerHeight,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
  assert.deepEqual(result.roots.filter((root) => root.canScroll).map((root) => root.selector), ["#dayDialogPanel"]);
  assert.equal(result.splitPanelCount, 0);
  assert.equal(result.autonomousCount, 1);
  assert.ok(result.pulseCount > 0);
  assert.equal(result.sedimentCount, 0);
  assert.ok(result.endScrollTop >= result.maxScroll - 2);
  assert.ok(result.timelineBottomAtEnd >= -1 && result.timelineBottomAtEnd <= result.viewport + 1);
  assert.ok(result.lastTop >= -1 && result.lastBottom <= result.viewport + 1);
  assert.ok(result.overflow <= 1);
  await context.close();
} finally {
  await browser.close();
}

console.log(JSON.stringify({
  passed: true,
  uniqueTaskPhrases: phraseCounts.size,
  uniqueSchedules: scheduleSignatures.size,
}, null, 2));
