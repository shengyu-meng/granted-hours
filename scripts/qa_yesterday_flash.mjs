#!/usr/bin/env node
import assert from "node:assert/strict";
import { mkdirSync } from "node:fs";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:4177/timetable/";
const deadline = setTimeout(() => { throw new Error("Flash QA exceeded five minutes"); }, 300000);
const browser = await chromium.launch({ headless: true });
const errors = [];
mkdirSync("tmp/yesterday-flash-qa", { recursive: true });
try {
  const flashDays = timetableData.days.filter((day) => ["2026-10-30", "2026-10-31"].includes(day.date) && day.yesterday_flash_entries);
  assert.deepEqual(flashDays.map((day) => day.date).sort(), ["2026-10-30", "2026-10-31"]);
  assert.equal(timetableData.days.find((day) => day.date === "2026-10-29")?.yesterday_flash_entries, undefined);
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }]) {
    const context = await browser.newContext({ viewport, hasTouch: viewport.width < 500, isMobile: viewport.width < 500 });
    const page = await context.newPage();
    page.setDefaultTimeout(20000);
    page.on("pageerror", (error) => errors.push(error.message));
    await page.addInitScript(() => {
      localStorage.setItem("granted-hours-audio-defaults-version", "2026-08-10-default-on-v2");
      localStorage.setItem("granted-hours-calendar-bgm", "off");
      localStorage.setItem("granted-hours-piano-sounds", "off");
    });
    for (const day of flashDays) {
      await page.goto(`${baseUrl}?date=${day.date}`, { waitUntil: "networkidle" });
      const marks = page.locator(`.date-cell[data-date="${day.date}"]:not(.is-muted) a.assigned-mark`);
      assert.equal(await marks.count(), 2);
      const titles = await marks.allInnerTexts();
      assert.match(titles[0], /三条闪光 \/ Three glints/);
      assert.match(titles[1], /抽出的一件 \/ Entered piece/);
      const work = day.yesterday_flash_entries.find((entry) => entry.kind === "work");
      await marks.nth(1).click();
      await page.waitForURL((url) => url.href.includes("/yesterday-flash/live/"));
      await page.goto(`${baseUrl}?date=${day.date}`, { waitUntil: "networkidle" });
      await page.waitForFunction(() => document.querySelector(".timeline-reading-layer.is-placed"));
      const cards = page.locator('a.assigned-reading-card[data-classification="flash_slot"]');
      assert.equal(await cards.count(), 2);
      const flashSize = await cards.first().locator(".assigned-work-type").evaluate((node) => getComputedStyle(node).fontSize);
      const eventSize = await page.locator(".assigned-reading-card .assigned-work-type").first().evaluate((node) => getComputedStyle(node).fontSize);
      assert.equal(flashSize, eventSize);
      assert.equal(await page.locator(".yesterday-flash-reading-card").count(), 0);
      assert.ok(work.href.includes("/yesterday-flash/live/"));
    }
    await context.close();
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ passed: true, dates: flashDays.map((day) => day.date) }));
} finally {
  await browser.close();
  clearTimeout(deadline);
}
