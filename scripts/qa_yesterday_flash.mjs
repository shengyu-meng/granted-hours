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
  const flashDays = timetableData.days.filter((day) => ["2026-10-30", "2026-10-31"].includes(day.date) && day.yesterday_flash);
  assert.deepEqual(flashDays.map((day) => day.date).sort(), ["2026-10-30", "2026-10-31"]);
  assert.equal(timetableData.days.find((day) => day.date === "2026-10-29")?.yesterday_flash, undefined);
  for (const viewport of [{ width: 1440, height: 900 }, { width: 390, height: 844 }, { width: 421, height: 386 }, { width: 3840, height: 2160 }]) {
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
      const flashPath = new URL(day.yesterday_flash.live_url).pathname;
      const expected = new URL(`..${flashPath.slice(flashPath.indexOf('/archive/'))}`, baseUrl).href;
      const dayCell = page.locator(`.date-cell[data-date="${day.date}"]:not(.is-muted)`);
      const line = dayCell.locator(".yesterday-flash-mark");
      assert.equal(await line.count(), 1);
      assert.equal(await line.evaluate((link) => link.href), expected);
      assert.match(await line.innerText(), /昨日闪光 \/ Yesterday's Flash/);
      assert.ok((await line.innerText()).includes(day.yesterday_flash.title_zh));
      assert.equal(await dayCell.locator("button a, button button").count(), 0);
      await page.locator("#closeDetail").click();
      const monthVisible = await line.evaluate((link) => {
        const box = link.getBoundingClientRect();
        const material = link.closest(".cell-material").getBoundingClientRect();
        return box.top >= material.top - 1 && box.bottom <= material.bottom + 1;
      });
      assert.ok(monthVisible, `${day.date}/${viewport.width}: Flash must be visible without cell scrolling`);
      if (day.date === "2026-10-31") {
        await dayCell.screenshot({ path: `tmp/yesterday-flash-qa/month-cell-${viewport.width}.png` });
        await page.screenshot({ path: `tmp/yesterday-flash-qa/month-${viewport.width}.png` });
      }
      await line.focus();
      await page.keyboard.press("Enter");
      await page.waitForURL(expected);
      assert.match(await page.title(), /昨日闪光/);
      await page.goto(`${baseUrl}?date=${day.date}`, { waitUntil: "networkidle" });
      await page.waitForFunction(() => document.querySelector(".timeline-reading-layer.is-placed"));
      const geometry = await page.evaluate(() => {
        const autonomous = document.querySelector(".autonomous-reading-card");
        const flash = document.querySelector(".yesterday-flash-reading-card");
        const primary = autonomous.getBoundingClientRect();
        const secondary = flash.getBoundingClientRect();
        const footprint = document.querySelector('.timeline-event[data-footprint-id="yesterday-flash-001"]');
        return {
          primaryCount: document.querySelectorAll(".autonomous-reading-card").length,
          flashCount: document.querySelectorAll(".yesterday-flash-reading-card").length,
          gap: secondary.top - primary.bottom,
          leftDelta: secondary.left - primary.left,
          widthDelta: secondary.width - primary.width,
          primaryContract: autonomous.dataset.heightContract,
          next: autonomous.nextElementSibling === flash,
          start: footprint.dataset.start,
          end: footprint.dataset.end,
          duration: footprint.style.getPropertyValue("--event-duration-minutes"),
          text: flash.textContent,
          overflow: document.documentElement.scrollWidth > innerWidth,
          flashClipped: flash.scrollHeight > flash.clientHeight + 1,
        };
      });
      assert.equal(geometry.primaryCount, 1);
      assert.equal(geometry.flashCount, 1);
      assert.equal(geometry.primaryContract, "autonomous-artwork-v1");
      assert.ok(geometry.next);
      assert.ok(Math.abs(geometry.gap - 4) < 1, JSON.stringify(geometry));
      assert.ok(Math.abs(geometry.leftDelta) < 1 && Math.abs(geometry.widthDelta) < 1);
      assert.equal(geometry.start, "08:10");
      assert.equal(geometry.end, "08:12");
      assert.equal(Number(geometry.duration), 2);
      assert.equal(geometry.overflow, false);
      assert.equal(geometry.flashClipped, false);
      assert.ok(geometry.text.includes(day.yesterday_flash.title_zh));
      const card = page.locator(".yesterday-flash-reading-card");
      await card.scrollIntoViewIfNeeded();
      await page.screenshot({ path: `tmp/yesterday-flash-qa/${day.date}-${viewport.width}.png` });
      if (viewport.width < 500) await card.tap();
      else await card.click();
      await page.waitForURL(expected);
      assert.match(await page.title(), /昨日闪光/);
    }
    await context.close();
  }
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ passed: true, dates: flashDays.map((day) => day.date), viewports: 4, monthAndCardNavigation: true }));
} finally {
  await browser.close();
  clearTimeout(deadline);
}
