#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const timetableUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const siteOrigin = new URL(timetableUrl).origin;
const allowances = JSON.parse(
  readFileSync(new URL("../metadata/artwork-display-allowances.json", import.meta.url), "utf8"),
);
assert.equal(allowances.schema, "granted-hours-artwork-display-allowances-v1");
const allowedDays = allowances.days;
const results = [];
const failures = [];

function visible(element) {
  if (!element) return false;
  const style = getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return style.display !== "none"
    && style.visibility !== "hidden"
    && Number(style.opacity) > 0.01
    && rect.width > 1
    && rect.height > 1;
}

const browser = await chromium.launch({ headless: true });
const artworkDays = timetableData.days.filter((day) => day.autonomous_work?.origin !== "absence");
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });

  async function inspect(day) {
    const [year, month] = day.date.split("-");
    const page = await context.newPage();
    const pageErrors = [];
    const responseErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    page.on("response", (response) => {
      if (response.url().startsWith(siteOrigin) && response.status() >= 400) {
        responseErrors.push(`${response.status()} ${response.url()}`);
      }
    });
    const url = `${siteOrigin}/archive/${year}/${month}/${day.date}/live/?from=timetable`;
    try {
      const response = await page.goto(url, { waitUntil: "load", timeout: 45000 });
      assert.equal(response?.status(), 200, `${day.date} HTTP ${response?.status()}`);
      await page.waitForTimeout(350);
      const allowance = allowedDays[day.date];
      if (allowance?.live_mode === "interactive_form") {
        await page.locator("#appeal-form").waitFor({ state: "visible", timeout: 10000 });
      } else {
        await page.waitForFunction(() => {
          const canvases = [...document.querySelectorAll("canvas")];
          return canvases.some((canvas) => {
            const rect = canvas.getBoundingClientRect();
            return canvas.width > 0 && canvas.height > 0 && rect.width > 1 && rect.height > 1;
          });
        }, null, { timeout: 45000 });
      }
      const state = await page.evaluate(visibleFn => {
        const isVisible = new Function("element", `return (${visibleFn})(element);`);
        const visibleCanvas = [...document.querySelectorAll("canvas")].find(isVisible);
        const visualRect = visibleCanvas?.getBoundingClientRect();
        const visibleTextRoots = [
          ...document.querySelectorAll("h1,h2,.title,.panel,.card,.label,#label,.hud,.statement,.instructions,header"),
        ].filter(isVisible);
        const foldControl = document.querySelector(".gh-fold-toggle");
        const workNote = document.querySelector("#ghWorkNoteTrigger");
        return {
          embed: document.body.classList.contains("gh-chamber-embed"),
          folded: document.body.classList.contains("gh-text-folded"),
          bodyTextLength: document.body.innerText.trim().length,
          foldControlAbsent: !foldControl,
          workNoteVisible: isVisible(workNote),
          visibleTextRootCount: visibleTextRoots.length,
          visual: visualRect
            ? {
                width: visualRect.width,
                height: visualRect.height,
                intrinsicWidth: visibleCanvas.width,
                intrinsicHeight: visibleCanvas.height,
              }
            : null,
          bodyWidth: document.body.getBoundingClientRect().width,
          bodyHeight: document.body.getBoundingClientRect().height,
          horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        };
      }, visible.toString());
      assert.equal(state.embed, false, `${day.date} timetable full view became embed mode`);
      assert.equal(state.folded, false, `${day.date} timetable full view hid required copy`);
      assert.ok(state.bodyTextLength > 8, `${day.date} body is blank`);
      assert.equal(state.foldControlAbsent, true, `${day.date} fold control still exists`);
      assert.ok(state.workNoteVisible, `${day.date} work-note control is not visible`);
      if (allowance?.copy_mode !== "canvas_native") {
        assert.ok(state.visibleTextRootCount > 0, `${day.date} title/explanation is not visible`);
      }
      assert.ok(
        state.visual || (state.bodyWidth > 1 && state.bodyHeight > 1),
        `${day.date} body and visual both have zero geometry`,
      );
      assert.ok(state.horizontalOverflow <= 2, `${day.date} horizontal overflow ${state.horizontalOverflow}`);
      if (allowedDays[day.date]?.live_mode !== "interactive_form") {
        assert.ok(state.visual, `${day.date} has no visible canvas`);
        assert.ok(
          state.visual.width > 1
          && state.visual.height > 1
          && state.visual.intrinsicWidth > 0
          && state.visual.intrinsicHeight > 0,
          `${day.date} canvas has zero geometry: ${JSON.stringify(state.visual)}`,
        );
      }
      assert.deepEqual(pageErrors, [], `${day.date} page errors: ${pageErrors.join("; ")}`);
      assert.deepEqual(responseErrors, [], `${day.date} local response errors: ${responseErrors.join("; ")}`);

      const bgmPath = fileURLToPath(
        new URL(`../docs/archive/${year}/${month}/${day.date}/live/${decodeURIComponent(new URL(day.bgm).pathname.split("/").at(-1))}`, import.meta.url),
      );
      assert.ok(statSync(bgmPath).size > 0, `${day.date} BGM is missing or empty`);
      return {
        date: day.date,
        mode: allowance?.live_mode || "canvas",
        copyMode: allowance?.copy_mode || "dom",
        allowance: Boolean(allowance),
        canvas: Boolean(state.visual),
        textRoots: state.visibleTextRootCount,
      };
    } finally {
      await page.close();
    }
  }

  const concurrency = 5;
  for (let index = 0; index < artworkDays.length; index += concurrency) {
    const batch = artworkDays.slice(index, index + concurrency);
    const settled = await Promise.allSettled(batch.map(inspect));
    settled.forEach((result, batchIndex) => {
      if (result.status === "fulfilled") results.push(result.value);
      else failures.push(`${batch[batchIndex].date}: ${result.reason.message}`);
    });
  }
  await context.close();
} finally {
  await browser.close();
}

if (failures.length) {
  throw new Error(`Artwork corpus smoke failures (${failures.length}):\n- ${failures.join("\n- ")}`);
}
assert.equal(results.length, artworkDays.length);
assert.deepEqual(
  Object.keys(allowedDays).sort(),
  results.filter((result) => result.allowance).map((result) => result.date).sort(),
);
console.log(JSON.stringify({
  passed: true,
  pages: results.length,
  canvasPages: results.filter((result) => result.canvas).length,
  explicitAllowances: results.filter((result) => result.allowance),
  pageErrors: 0,
  localHttpFailures: 0,
}, null, 2));
