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
const requestedDate = process.env.ARTWORK_QA_DATE || "";
const pageTimeoutMs = Number(process.env.ARTWORK_QA_TIMEOUT_MS || 120000);
assert.ok(Number.isInteger(pageTimeoutMs) && pageTimeoutMs >= 45000 && pageTimeoutMs <= 300000);

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
const artworkDays = timetableData.days.filter((day) => (
  day.autonomous_work?.origin !== "absence"
  && (!requestedDate || day.date === requestedDate)
));
if (requestedDate) {
  assert.equal(artworkDays.length, 1, `No live artwork found for ${requestedDate}`);
}
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  // This audit checks DOM copy, controls, canvas geometry, and resource health;
  // it is not an animation-quality test. A handful of legacy works can otherwise
  // saturate the page main thread and starve the assertions themselves. Allow a
  // few startup frames, then hold subsequent animation frames during the audit.
  if (process.env.ARTWORK_QA_LIVE_ANIMATION !== "1") {
    await context.addInitScript(() => {
      const nativeRequestAnimationFrame = window.requestAnimationFrame.bind(window);
      let startupFrames = 0;
      window.requestAnimationFrame = (callback) => (
        startupFrames++ < 6 ? nativeRequestAnimationFrame(callback) : 0
      );
    });
  }
  // Audio integrity is checked from disk below. Aborting media here keeps the
  // full-corpus visual/DOM audit from waiting on every BGM file to finish loading.
  await context.route("**/*", async (route) => {
    if (route.request().resourceType() === "media") await route.abort();
    else await route.continue();
  });

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
      const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: pageTimeoutMs });
      assert.equal(response?.status(), 200, `${day.date} HTTP ${response?.status()}`);
      await page.waitForTimeout(350);
      const allowance = allowedDays[day.date];
      if (allowance?.live_mode === "interactive_form") {
        await page.locator("#appeal-form").waitFor({ state: "visible", timeout: pageTimeoutMs });
      } else {
        await page.waitForFunction(() => {
          const canvases = [...document.querySelectorAll("canvas")];
          return canvases.some((canvas) => {
            const rect = canvas.getBoundingClientRect();
            return canvas.width > 0 && canvas.height > 0 && rect.width > 1 && rect.height > 1;
          });
        }, null, { timeout: pageTimeoutMs });
      }
      const briefToggle = page.locator("#ghLiveBrief .gh-live-brief-toggle");
      const briefBody = page.locator("#ghLiveBriefBody");
      await briefToggle.waitFor({ state: "visible", timeout: pageTimeoutMs });
      assert.equal(
        await briefToggle.getAttribute("aria-expanded"),
        "false",
        `${day.date} bilingual brief is not collapsed by default`,
      );
      assert.equal(await briefBody.isVisible(), false, `${day.date} collapsed brief body remains visible`);
      await briefToggle.click();
      assert.equal(await briefToggle.getAttribute("aria-expanded"), "true", `${day.date} bilingual brief did not expand`);
      assert.equal(await briefBody.isVisible(), true, `${day.date} expanded brief body is hidden`);
      const state = await page.evaluate(visibleFn => {
        const isVisible = new Function("element", `return (${visibleFn})(element);`);
        const visibleCanvas = [...document.querySelectorAll("canvas")].find(isVisible);
        const visualRect = visibleCanvas?.getBoundingClientRect();
        const visibleTextRoots = [
          ...document.querySelectorAll("h1,h2,.title,.panel,.card,.label,#label,.hud,.statement,.instructions,header"),
        ].filter((element) => isVisible(element) && !element.closest("#ghLiveBrief"));
        const foldControl = document.querySelector(".gh-fold-toggle");
        const workNote = document.querySelector("#ghWorkNoteTrigger");
        const calendarReturn = document.querySelector("#ghCalendarReturn");
        const liveBrief = document.querySelector("#ghLiveBrief[data-gh-live-brief='bilingual']");
        const touchKeys = [...document.querySelectorAll(".gh-touch-keys-inline .gh-touch-key")];
        const briefRect = liveBrief?.getBoundingClientRect();
        const workNoteRect = workNote?.getBoundingClientRect();
        const calendarReturnRect = calendarReturn?.getBoundingClientRect();
        const reserved = briefRect ? {
          left: briefRect.left,
          top: briefRect.top,
          right: briefRect.left + Math.max(briefRect.width, Math.min(352, innerWidth - 24)),
          bottom: briefRect.top + Math.min(innerHeight * 0.46, 390),
        } : null;
        const intersects = (a, b) => Boolean(a && b
          && Math.min(a.right, b.right) > Math.max(a.left, b.left)
          && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top));
        const visibleNativeTitleChrome = [...document.querySelectorAll(
          'h1,h2,p,.title,.subtitle,.kicker,.brief,#brief,.intro,.description,.statement,.instructions',
        )].filter((element) => {
          if (!isVisible(element) || element.closest("#ghLiveBrief, #ghWorkNoteOverlay")) return false;
          const rect = element.getBoundingClientRect();
          const upperTitle = element.matches("h1,h2,.title")
            && rect.top < Math.min(innerHeight * 0.48, 430)
            && rect.left < innerWidth * 0.76;
          return upperTitle || intersects(rect, reserved);
        });
        const briefText = (selector, lang) => (
          liveBrief?.querySelector(`${selector} .gh-live-brief-copy[lang='${lang}']`)?.textContent || ""
        ).trim();
        return {
          embed: document.body.classList.contains("gh-chamber-embed"),
          folded: document.body.classList.contains("gh-text-folded"),
          bodyTextLength: document.body.innerText.trim().length,
          foldControlAbsent: !foldControl,
          workNoteVisible: isVisible(workNote),
          calendarReturn: {
            visible: isVisible(calendarReturn),
            href: calendarReturn?.href || "",
            rect: calendarReturnRect?.toJSON() || null,
            overlapsWorkNote: intersects(calendarReturnRect, workNoteRect),
            nearWorkNote: Boolean(calendarReturnRect && workNoteRect && (
              Math.abs(calendarReturnRect.right - workNoteRect.left) <= 12
              || Math.abs(calendarReturnRect.bottom - workNoteRect.top) <= 12
            )),
          },
          visibleNativeTitleChrome: visibleNativeTitleChrome.map((element) => (
            (element.innerText || element.textContent || "").trim().slice(0, 100)
          )),
          suppressedNativeTitleCount: document.querySelectorAll('[data-gh-native-title-suppressed="true"]').length,
          liveBrief: {
            visible: isVisible(liveBrief),
            draggable: liveBrief?.dataset.ghDraggable || "",
            summaryZh: briefText("[data-gh-brief-section='summary']", "zh-CN"),
            summaryEn: briefText("[data-gh-brief-section='summary']", "en"),
            instructionsZh: briefText("[data-gh-brief-section='instructions']", "zh-CN"),
            instructionsEn: briefText("[data-gh-brief-section='instructions']", "en"),
            expanded: liveBrief?.querySelector(".gh-live-brief-toggle")?.getAttribute("aria-expanded"),
            rect: briefRect?.toJSON() || null,
          },
          touchKeys: touchKeys.map((button) => {
            const rect = button.getBoundingClientRect();
            return {
              label: button.dataset.ghKeyLabel,
              key: button.dataset.ghKey,
              code: button.dataset.ghCode,
              visible: isVisible(button),
              width: rect.width,
              height: rect.height,
            };
          }),
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
      assert.ok(state.calendarReturn.visible, `${day.date} timetable return is not visible`);
      assert.equal(
        state.calendarReturn.href,
        `${siteOrigin}/timetable/?date=${day.date}`,
        `${day.date} timetable return does not preserve the artwork date`,
      );
      assert.ok(state.calendarReturn.rect, `${day.date} timetable return has no geometry`);
      assert.ok(state.calendarReturn.rect.left >= 0 && state.calendarReturn.rect.top >= 0, `${day.date} timetable return is offscreen`);
      assert.ok(state.calendarReturn.rect.right <= 1280 && state.calendarReturn.rect.bottom <= 720, `${day.date} timetable return exceeds the viewport`);
      assert.equal(state.calendarReturn.overlapsWorkNote, false, `${day.date} timetable return overlaps the work-note control`);
      assert.equal(state.calendarReturn.nearWorkNote, true, `${day.date} timetable return is detached from the work-note control`);
      assert.deepEqual(
        state.visibleNativeTitleChrome,
        [],
        `${day.date} still exposes legacy top-left title/explanation chrome`,
      );
      assert.ok(state.liveBrief.visible, `${day.date} bilingual top-left brief is not visible`);
      assert.ok(state.liveBrief.summaryZh, `${day.date} Chinese brief is empty`);
      assert.ok(state.liveBrief.summaryEn, `${day.date} English brief is empty`);
      assert.ok(state.liveBrief.instructionsZh, `${day.date} Chinese instructions are empty`);
      assert.ok(state.liveBrief.instructionsEn, `${day.date} English instructions are empty`);
      assert.equal(state.liveBrief.expanded, "true", `${day.date} bilingual brief did not remain expanded`);
      assert.equal(state.liveBrief.draggable, "header", `${day.date} bilingual brief lacks its drag contract`);
      assert.ok(state.liveBrief.rect, `${day.date} bilingual brief has no geometry`);
      assert.ok(state.liveBrief.rect.left >= 0 && state.liveBrief.rect.left <= 24, `${day.date} brief is not left-aligned`);
      assert.ok(state.liveBrief.rect.top >= 0 && state.liveBrief.rect.top <= 24, `${day.date} brief is not top-aligned`);
      assert.ok(state.liveBrief.rect.right <= 1280, `${day.date} brief exceeds viewport width`);
      assert.ok(state.liveBrief.rect.bottom <= 720, `${day.date} brief exceeds viewport height`);
      state.touchKeys.forEach((key) => {
        assert.ok(key.visible, `${day.date} touch key ${key.label} is hidden`);
        assert.ok(key.width >= 44, `${day.date} touch key ${key.label} is narrower than 44px`);
        assert.ok(key.height >= 44, `${day.date} touch key ${key.label} is shorter than 44px`);
        assert.ok(key.key, `${day.date} touch key ${key.label} lacks key mapping`);
        assert.ok(key.code, `${day.date} touch key ${key.label} lacks code mapping`);
      });
      if (state.touchKeys.length) {
        await page.evaluate(() => {
          window.__ghTouchAudit = [];
          const record = (event) => window.__ghTouchAudit.push({
            type: event.type,
            key: event.key,
            code: event.code,
            target: event.target?.tagName || "",
          });
          window.addEventListener("keydown", record, true);
          window.addEventListener("keyup", record, true);
        });
        const auditKeyState = state.touchKeys.find(({ label }) => label === "Space") || state.touchKeys[0];
        await page.evaluate((label) => {
          document.querySelector(`.gh-touch-keys-inline .gh-touch-key[data-gh-key-label='${label}']`)?.click();
        }, auditKeyState.label);
        const touchAudit = await page.evaluate(() => window.__ghTouchAudit);
        assert.deepEqual(
          touchAudit.map(({ type, key, code }) => ({ type, key, code })),
          [
            { type: "keydown", key: auditKeyState.key, code: auditKeyState.code },
            { type: "keyup", key: auditKeyState.key, code: auditKeyState.code },
          ],
          `${day.date} touch key did not dispatch one matching keydown/keyup pair`,
        );
        assert.ok(
          ["CANVAS", "SVG", "BODY"].includes(touchAudit[0]?.target),
          `${day.date} touch key dispatched from an unsafe target ${touchAudit[0]?.target}`,
        );
      }
      if (allowance?.copy_mode !== "canvas_native") {
        assert.ok(
          state.visibleTextRootCount > 0 || state.liveBrief.visible,
          `${day.date} title/explanation is not visible`,
        );
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

      await briefToggle.click();
      assert.equal(await briefToggle.getAttribute("aria-expanded"), "false", `${day.date} bilingual brief did not collapse again`);
      assert.equal(await briefBody.isVisible(), false, `${day.date} re-collapsed brief body remains visible`);

      if (state.touchKeys.length) {
        const embedUrl = `${siteOrigin}/archive/${year}/${month}/${day.date}/live/?embed=calendar&gh_channel=touch_audit_2026_x`;
        const embedResponse = await page.goto(embedUrl, { waitUntil: "domcontentloaded", timeout: pageTimeoutMs });
        assert.equal(embedResponse?.status(), 200, `${day.date} embed HTTP ${embedResponse?.status()}`);
        const embedKeys = await page.locator("#ghTouchKeyDock .gh-touch-key").evaluateAll((buttons) => buttons.map((button) => {
          const rect = button.getBoundingClientRect();
          return {
            label: button.dataset.ghKeyLabel,
            visible: getComputedStyle(button).display !== "none" && getComputedStyle(button).visibility !== "hidden",
            width: rect.width,
            height: rect.height,
          };
        }));
        assert.deepEqual(
          embedKeys.map(({ label }) => label),
          state.touchKeys.map(({ label }) => label),
          `${day.date} embed touch keys differ from the direct-page keys`,
        );
        embedKeys.forEach((key) => {
          assert.ok(key.visible, `${day.date} embed touch key ${key.label} is hidden`);
          assert.ok(key.width >= 44 && key.height >= 44, `${day.date} embed touch key ${key.label} is below 44px`);
        });
      }

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
        bilingualBrief: true,
        touchKeys: state.touchKeys.length,
        suppressedNativeTitles: state.suppressedNativeTitleCount,
      };
    } finally {
      await page.close();
    }
  }

  // Keep WebGL/canvas startup below the 45 s per-work budget on constrained CI
  // hosts; override explicitly for stronger runners.
  const concurrency = Number(process.env.ARTWORK_QA_CONCURRENCY || 3);
  assert.ok(Number.isInteger(concurrency) && concurrency > 0 && concurrency <= 8);
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
if (!requestedDate) {
  assert.deepEqual(
    Object.keys(allowedDays).sort(),
    results.filter((result) => result.allowance).map((result) => result.date).sort(),
  );
}
console.log(JSON.stringify({
  passed: true,
  pages: results.length,
  canvasPages: results.filter((result) => result.canvas).length,
  bilingualBriefPages: results.filter((result) => result.bilingualBrief).length,
  touchShortcutPages: results.filter((result) => result.touchKeys > 0).length,
  touchShortcutButtons: results.reduce((total, result) => total + result.touchKeys, 0),
  suppressedNativeTitleNodes: results.reduce((total, result) => total + result.suppressedNativeTitles, 0),
  explicitAllowances: results.filter((result) => result.allowance),
  pageErrors: 0,
  localHttpFailures: 0,
}, null, 2));
