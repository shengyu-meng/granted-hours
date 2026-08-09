#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8772/timetable/";
const sampleDate = "2026-07-27";
const failures = [];

async function unobstructedTarget(page, expected = null) {
  return page.evaluate((match) => {
    const events = [...document.querySelectorAll(".timeline-event[data-reading-id]")]
      .filter((event) => !match || event.dataset.footprintId === match.footprintId)
      .sort((first, second) => {
        const firstRect = first.getBoundingClientRect();
        const secondRect = second.getBoundingClientRect();
        return (secondRect.width * secondRect.height) - (firstRect.width * firstRect.height);
      });
    for (const event of events) {
      const rect = event.getBoundingClientRect();
      for (let yStep = 1; yStep <= 4; yStep += 1) {
        for (let xStep = 1; xStep <= 10; xStep += 1) {
          const x = rect.left + rect.width * xStep / 11;
          const y = rect.top + rect.height * yStep / 5;
          const hit = document.elementFromPoint(x, y)?.closest(".timeline-event[data-reading-id]");
          if (hit === event) {
            return { x, y, readingId: event.dataset.readingId, footprintId: event.dataset.footprintId };
          }
        }
      }
    }
    return null;
  }, expected);
}

async function check(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    failures.push(`${name}: ${error.message}`);
    console.error(`FAIL ${name}: ${error.message}`);
  }
}

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  const url = new URL(baseUrl);
  url.searchParams.set("date", sampleDate);
  url.searchParams.set("regression", "reverse-link-palette");
  await page.goto(url.href, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(`#dayDialog.is-open[data-selected-date="${sampleDate}"]`);
  await page.waitForFunction(() => document.querySelector(".timeline-reading-layer.is-placed"));
  await page.waitForFunction(() => [...document.images].every((image) => image.complete));

  await check("chromatic palette is explicit, broad, and muted", async () => {
    const result = await page.evaluate(() => {
      const cards = [...document.querySelectorAll('.event-reading-card[data-category="assigned-work"]')];
      const accents = [...new Set(cards.map((card) => getComputedStyle(card)
        .getPropertyValue("--category-accent").trim().toLowerCase()))].filter(Boolean);
      const channels = accents.map((hex) => {
        const value = hex.replace("#", "");
        return [0, 2, 4].map((offset) => Number.parseInt(value.slice(offset, offset + 2), 16));
      });
      return {
        palette: document.documentElement.dataset.palette,
        accents,
        channelSpreads: channels.map((rgb) => Math.max(...rgb) - Math.min(...rgb)),
        monthAccentCount: new Set([...document.querySelectorAll(".assigned-mark")]
          .map((mark) => getComputedStyle(mark).getPropertyValue("--month-mark-accent").trim())
          .filter(Boolean)).size,
      };
    });
    assert.equal(result.palette, "chromatic", JSON.stringify(result));
    assert.ok(result.accents.length >= 4, JSON.stringify(result));
    assert.ok(result.channelSpreads.every((spread) => spread <= 80), JSON.stringify(result));
    assert.ok(result.monthAccentCount >= 3, JSON.stringify(result));
  });

  const target = await unobstructedTarget(page);
  assert.ok(target, "expected at least one unobstructed exact footprint");

  await check("hovering an unobstructed exact footprint activates its reading card", async () => {
    const currentTarget = await unobstructedTarget(page, target);
    assert.ok(currentTarget, `footprint ${target.footprintId} became obstructed`);
    await page.mouse.move(currentTarget.x, currentTarget.y);
    await page.waitForFunction((readingId) => {
      const card = document.querySelector(`.event-reading-card[data-reading-id="${CSS.escape(readingId)}"]`);
      return card?.classList.contains("is-linked-active");
    }, target.readingId);
    const result = await page.evaluate(({ readingId, footprintId }) => {
      const card = document.querySelector(`.event-reading-card[data-reading-id="${CSS.escape(readingId)}"]`);
      const footprint = document.querySelector(`.timeline-event[data-footprint-id="${CSS.escape(footprintId)}"]`);
      return {
        cardLinked: card?.classList.contains("is-linked-active"),
        footprintLinked: footprint?.classList.contains("is-linked-active"),
        transform: card ? getComputedStyle(card).transform : "",
      };
    }, target);
    assert.equal(result.cardLinked, true, JSON.stringify(result));
    assert.equal(result.footprintLinked, true, JSON.stringify(result));
    assert.equal(result.transform, "matrix(1, 0, 0, 1, 0, -4)", JSON.stringify(result));
  });

  await check("clicking the exact footprint locks the corresponding card selection", async () => {
    const currentTarget = await unobstructedTarget(page, target);
    assert.ok(currentTarget, `footprint ${target.footprintId} became obstructed`);
    await page.mouse.click(currentTarget.x, currentTarget.y);
    const result = await page.evaluate((readingId) => {
      const card = document.querySelector(`.event-reading-card[data-reading-id="${CSS.escape(readingId)}"]`);
      return {
        selected: card?.classList.contains("is-selected"),
        pressed: card?.getAttribute("aria-pressed"),
        taskDialogOpen: document.querySelector("#taskDialog")?.classList.contains("is-open"),
      };
    }, target.readingId);
    assert.equal(result.selected, true, JSON.stringify(result));
    assert.equal(result.pressed, "true", JSON.stringify(result));
    assert.equal(result.taskDialogOpen, false, JSON.stringify(result));
    await page.mouse.move(2, 2);
    await page.waitForTimeout(40);
    assert.equal(
      await page.locator(`.event-reading-card[data-reading-id="${target.readingId}"]`).evaluate((card) => card.classList.contains("is-selected")),
      true,
    );
  });

  await check("clicking outside clears the reverse selection", async () => {
    await page.mouse.click(10, 10);
    assert.equal(await page.locator(".event-reading-card.is-selected").count(), 0);
  });
} finally {
  await browser.close();
}

if (failures.length) {
  console.error(JSON.stringify({ failures }, null, 2));
  process.exitCode = 1;
} else {
  console.log(JSON.stringify({ sampleDate, failures: [] }, null, 2));
}
