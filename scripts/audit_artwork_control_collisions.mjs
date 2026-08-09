#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const siteUrl = new URL(process.env.ARTWORK_SITE_URL || "http://127.0.0.1:8891/");
if (!siteUrl.pathname.endsWith("/")) siteUrl.pathname += "/";
const siteOrigin = siteUrl.origin;
const liveArtworkMode = process.env.LIVE_ARTWORK === "1";
const viewports = [
  { name: "desktop", width: 1280, height: 720 },
  { name: "mobile", width: 390, height: 844, isMobile: true, hasTouch: true },
];
const requestedDates = new Set((process.env.ARTWORK_DATES || "").split(",").filter(Boolean));
const artworkDays = timetableData.days.filter(
  (day) => day.autonomous_work?.origin !== "absence" && (!requestedDates.size || requestedDates.has(day.date)),
);
const findings = [];
const adjustments = [];

const browser = await chromium.launch({ headless: true });
try {
  for (const viewport of viewports) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.isMobile,
      hasTouch: viewport.hasTouch,
    });
    await context.route("**/*", async (route) => {
      if (route.request().resourceType() === "media") await route.abort();
      else await route.continue();
    });
    const inspect = async (day) => {
      const [year, month] = day.date.split("-");
      const page = await context.newPage();
      const url = new URL(
        `archive/${year}/${month}/${day.date}/live/?from=collision-audit`,
        siteUrl,
      ).href;
      try {
        if (liveArtworkMode) {
          const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 45000 });
          assert.equal(response?.status(), 200, `${day.date} returned ${response?.status()}`);
        } else {
          const source = readFileSync(
            new URL(`../docs/archive/${year}/${month}/${day.date}/live/index.html`, import.meta.url),
            "utf8",
          );
          const staticChrome = source
            .replace(
              /<script\b(?![^>]*\bid=["']granted-hours-fold-script["'])[^>]*>[\s\S]*?<\/script>/gi,
              "",
            )
            .replace(/<head([^>]*)>/i, `<head$1><base href="${url}">`);
          await page.setContent(staticChrome, { waitUntil: "domcontentloaded", timeout: 45000 });
        }
        await page.locator("#ghWorkNoteTrigger").waitFor({ state: "attached", timeout: 15000 });
        await page.waitForTimeout(liveArtworkMode ? 500 : 120);
        const result = await page.evaluate(() => {
        const visible = (element) => {
          if (!(element instanceof HTMLElement)) return false;
          const style = getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          return style.display !== "none"
            && style.visibility !== "hidden"
            && Number(style.opacity) > 0.01
            && rect.width > 1
            && rect.height > 1;
        };
        const intersect = (a, b) => (
          Math.min(a.right, b.right) > Math.max(a.left, b.left)
          && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top)
        );
        const note = document.querySelector("#ghWorkNoteTrigger");
        const soundSelectors = [
          "#sound", ".sound", "#soundToggle", "#musicToggle",
          "button[id*='sound' i]", "button[id*='music' i]", "button[id*='bgm' i]",
        ];
        const soundCandidates = [];
        soundSelectors.flatMap((selector) => [...document.querySelectorAll(selector)]).forEach((matched) => {
          const element = matched.matches("button,input,[role='button']")
            ? matched
            : matched.querySelector("button,input,[role='button']") || matched;
          if (visible(element) && !soundCandidates.includes(element)) soundCandidates.push(element);
        });
        soundCandidates.sort((a, b) => {
          const score = (element) => {
            const rect = element.getBoundingClientRect();
            const interactive = element.matches("button,input,[role='button']") ? 1000 : 0;
            const named = /sound|music|bgm/i.test(`${element.id} ${element.className}`) ? 120 : 0;
            const compact = rect.height <= Math.max(72, innerHeight * 0.16) ? 60 : -300;
            return interactive + named + compact - Math.min(rect.width * rect.height / 1000, 100);
          };
          return score(b) - score(a);
        });
        const sound = soundCandidates[0] || null;
        const controls = [note, sound].filter(visible);
        const controlRects = controls.map((element) => ({
          id: element.id || "",
          className: typeof element.className === "string" ? element.className : "",
          rect: element.getBoundingClientRect().toJSON(),
        }));
        const collisions = [...document.querySelectorAll("h1,h2,h3,h4,h5,h6,p,span,label,legend,figcaption,li,a,div")]
          .filter((element) => {
            if (!visible(element)) return false;
            if (element.closest("#ghLiveBrief, #ghWorkNoteOverlay, #ghWorkNoteTrigger, #ghTouchKeyDock")) return false;
            if (controls.some((control) => element === control || control.contains(element))) return false;
            const text = (element.innerText || element.textContent || "").trim();
            if (!text) return false;
            const rect = element.getBoundingClientRect();
            if (rect.width * rect.height > innerWidth * innerHeight * 0.35) return false;
            if (rect.right < innerWidth * 0.48 || rect.bottom < innerHeight * 0.48) return false;
            const directText = [...element.childNodes].some(
              (node) => node.nodeType === Node.TEXT_NODE && (node.textContent || "").trim(),
            );
            if (!directText && !/^(H[1-6]|P|LABEL|LEGEND|FIGCAPTION|LI|A|SPAN)$/.test(element.tagName)) return false;
            return controlRects.some(({ rect: controlRect }) => intersect(rect, controlRect));
          })
          .map((element) => ({
            tag: element.tagName,
            id: element.id || "",
            className: typeof element.className === "string" ? element.className : "",
            text: (element.innerText || element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 180),
            rect: element.getBoundingClientRect().toJSON(),
            adjusted: element.dataset.ghControlOffset === "true",
          }));
        const offsets = [...document.querySelectorAll('[data-gh-control-offset="true"]')].map((element) => ({
          tag: element.tagName,
          id: element.id || "",
          className: typeof element.className === "string" ? element.className : "",
          text: (element.innerText || element.textContent || "").trim().replace(/\s+/g, " ").slice(0, 180),
          offset: getComputedStyle(element).getPropertyValue("--gh-control-offset-y").trim(),
          rect: element.getBoundingClientRect().toJSON(),
        }));
        return { controlRects, collisions, offsets };
        });
        if (result.collisions.length) {
          findings.push({ date: day.date, viewport: viewport.name, ...result });
        }
        if (result.offsets.length) {
          adjustments.push({ date: day.date, viewport: viewport.name, targets: result.offsets });
        }
      } finally {
        await page.close();
      }
    };
    const concurrency = 5;
    for (let index = 0; index < artworkDays.length; index += concurrency) {
      await Promise.all(artworkDays.slice(index, index + concurrency).map(inspect));
    }
    await context.close();
  }
} finally {
  await browser.close();
}

const affectedDates = [...new Set(findings.map(({ date }) => date))].sort();
const adjustedDates = [...new Set(adjustments.map(({ date }) => date))].sort();
console.log(JSON.stringify({
  passed: findings.length === 0,
  mode: liveArtworkMode ? "live" : "static-chrome",
  pages: artworkDays.length,
  viewportAudits: artworkDays.length * viewports.length,
  affectedDates,
  affectedDateCount: affectedDates.length,
  adjustedDates,
  adjustedDateCount: adjustedDates.length,
  adjustedViewportStates: adjustments.length,
  adjustedTargetCount: adjustments.reduce((total, state) => total + state.targets.length, 0),
  findings,
}, null, 2));
if (process.env.FAIL_ON_COLLISION !== "0") {
  assert.equal(findings.length, 0, `native text overlaps injected controls on ${affectedDates.length} artwork pages`);
}
