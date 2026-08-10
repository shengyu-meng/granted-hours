#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const siteOrigin = new URL(baseUrl).origin;
const artworkBaseUrl = new URL(process.env.ARTWORK_SITE_URL || `${siteOrigin}/`);
const sampleDate = "2026-07-11";
const sampleLiveUrl = new URL(
  `archive/2026/07/${sampleDate}/live/?embed=calendar&gh_channel=large_modal_touch_hint_qa`,
  artworkBaseUrl,
).href;
let browser = await chromium.launch({ headless: true });
const modalResults = [];
const touchResults = [];

function rgbaAlpha(value) {
  const match = String(value).match(/rgba?\([^)]*?(?:,\s*([\d.]+))?\)$/);
  if (!match) return 1;
  return match[1] === undefined ? 1 : Number(match[1]);
}

try {
  for (const spec of [
    { label: "desktop-1280", viewport: { width: 1280, height: 720 } },
    { label: "desktop-1920", viewport: { width: 1920, height: 1080 } },
    { label: "desktop-4k", viewport: { width: 3840, height: 2160 } },
    { label: "mobile", viewport: { width: 390, height: 844 }, touch: true },
    { label: "short-touch", viewport: { width: 421, height: 386 }, touch: true },
  ]) {
    const context = await browser.newContext({
      viewport: spec.viewport,
      isMobile: Boolean(spec.touch),
      hasTouch: Boolean(spec.touch),
      deviceScaleFactor: spec.touch ? 2 : 1,
    });
    await context.route("**/*.mp3", (route) => route.abort());
    await context.route("**/archive/**/live/**", (route) => route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<!doctype html><title>Artwork stage geometry QA</title>",
    }));
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const url = new URL(baseUrl);
    url.searchParams.set("date", sampleDate);
    await page.goto(url.href, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(`#dayDialog.is-open[data-selected-date="${sampleDate}"]`);
    await page.locator(".autonomous-preview-frame").click({ force: true });
    await page.waitForSelector("#artworkDialog.is-open");
    await page.waitForTimeout(900);
    const geometry = await page.evaluate(() => {
      const panel = document.querySelector("#artworkDialogPanel");
      const stage = document.querySelector(".artwork-live-stage");
      const panelRect = panel.getBoundingClientRect();
      const stageRect = stage.getBoundingClientRect();
      return {
        viewport: { width: innerWidth, height: innerHeight },
        panel: panelRect.toJSON(),
        stage: stageRect.toJSON(),
        panelAreaRatio: (panelRect.width * panelRect.height) / (innerWidth * innerHeight),
        stageAreaRatio: (stageRect.width * stageRect.height) / (innerWidth * innerHeight),
        horizontalOverflow: document.documentElement.scrollWidth - innerWidth,
        closeVisible: document.querySelector("#closeArtworkDetail").getBoundingClientRect().width > 0,
        fullscreenVisible: document.querySelector("#artworkFullscreen").getBoundingClientRect().width > 0,
      };
    });
    assert.ok(geometry.panel.left >= 0 && geometry.panel.right <= geometry.viewport.width + 1, JSON.stringify(geometry));
    assert.ok(geometry.panel.top >= 0 && geometry.panel.bottom <= geometry.viewport.height + 1, JSON.stringify(geometry));
    assert.ok(geometry.horizontalOverflow <= 1, `${spec.label} horizontal overflow`);
    assert.equal(geometry.closeVisible, true, `${spec.label} close control hidden`);
    assert.equal(geometry.fullscreenVisible, true, `${spec.label} fullscreen control hidden`);
    if (!spec.touch) {
      assert.ok(geometry.panel.width / geometry.viewport.width >= 0.94, `${spec.label} panel remained fixed-width`);
      assert.ok(geometry.panelAreaRatio >= 0.72, `${spec.label} panel area too small: ${geometry.panelAreaRatio}`);
      assert.ok(geometry.stageAreaRatio >= 0.40, `${spec.label} live stage area too small: ${geometry.stageAreaRatio}`);
      if (geometry.viewport.width >= 3000) {
        assert.ok(geometry.stageAreaRatio >= 0.68, `${spec.label} 4K live stage did not scale up`);
      }
    } else {
      assert.ok(geometry.panel.width / geometry.viewport.width >= 0.92, `${spec.label} mobile panel too narrow`);
    }
    assert.deepEqual(pageErrors, [], `${spec.label} page errors`);
    modalResults.push({ label: spec.label, ...geometry });
    await context.close();
  }

  await browser.close();
  browser = await chromium.launch({ headless: true });

  for (const spec of [
    { label: "desktop-1920", viewport: { width: 1920, height: 1080 } },
    { label: "mobile", viewport: { width: 390, height: 844 }, touch: true },
    { label: "short-touch", viewport: { width: 421, height: 386 }, touch: true },
  ]) {
    const context = await browser.newContext({
      viewport: spec.viewport,
      isMobile: Boolean(spec.touch),
      hasTouch: Boolean(spec.touch),
      deviceScaleFactor: spec.touch ? 2 : 1,
    });
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.goto(sampleLiveUrl, { waitUntil: "domcontentloaded" });
    const dock = page.locator("#ghTouchKeyDock");
    await dock.waitFor({ state: "attached" });
    const state = await dock.evaluate((element) => {
      const style = getComputedStyle(element);
      const label = element.querySelector(".gh-touch-key-dock-label");
      const copy = element.querySelector(".gh-touch-key-dock-copy");
      const keys = [...element.querySelectorAll(".gh-touch-key")].map((button) => {
        const rect = button.getBoundingClientRect();
        const keyStyle = getComputedStyle(button);
        return {
          label: button.dataset.ghKeyLabel,
          width: rect.width,
          height: rect.height,
          backgroundColor: keyStyle.backgroundColor,
          backgroundImage: keyStyle.backgroundImage,
          borderWidth: keyStyle.borderWidth,
          boxShadow: keyStyle.boxShadow,
          pointerEvents: keyStyle.pointerEvents,
        };
      });
      const copyRect = copy.getBoundingClientRect();
      return {
        rect: element.getBoundingClientRect().toJSON(),
        backgroundColor: style.backgroundColor,
        backgroundImage: style.backgroundImage,
        borderWidth: style.borderWidth,
        boxShadow: style.boxShadow,
        backdropFilter: style.backdropFilter || style.webkitBackdropFilter,
        pointerEvents: style.pointerEvents,
        labelDisplay: getComputedStyle(label).display,
        copyText: copy.innerText.trim(),
        copyRect: copyRect.toJSON(),
        keys,
        elementAtCopy: document.elementFromPoint(copyRect.left + 4, copyRect.top + 4)?.className || "",
        horizontalOverflow: document.documentElement.scrollWidth - innerWidth,
      };
    });
    assert.equal(rgbaAlpha(state.backgroundColor), 0, `${spec.label} dock still has an opaque plate`);
    assert.equal(state.backgroundImage, "none", `${spec.label} dock still has a gradient plate`);
    assert.equal(state.borderWidth, "0px", `${spec.label} dock still has a border`);
    assert.equal(state.boxShadow, "none", `${spec.label} dock still has a thick shadow`);
    assert.equal(state.backdropFilter, "none", `${spec.label} dock still blurs the artwork`);
    assert.equal(state.pointerEvents, "none", `${spec.label} copy layer blocks artwork input`);
    assert.equal(state.labelDisplay, "none", `${spec.label} legacy TOUCH KEYS label remains visible`);
    assert.match(state.copyText, /Space/);
    assert.match(state.copyText, /R/);
    assert.ok(state.copyText.includes("暂停") || state.copyText.includes("重播种"), `${spec.label} Chinese action mapping missing`);
    assert.ok(state.horizontalOverflow <= 1, `${spec.label} embed horizontal overflow`);
    assert.equal(state.keys.length, 9, `${spec.label} dense shortcut set changed`);
    for (const key of state.keys) {
      assert.ok(key.width >= 43.5 && key.height >= 43.5, `${spec.label} key ${key.label} hit target too small`);
      assert.equal(rgbaAlpha(key.backgroundColor), 0, `${spec.label} key ${key.label} still has a filled keycap`);
      assert.equal(key.backgroundImage, "none", `${spec.label} key ${key.label} still has a gradient keycap`);
      assert.equal(key.borderWidth, "0px", `${spec.label} key ${key.label} still has a border`);
      assert.equal(key.boxShadow, "none", `${spec.label} key ${key.label} still has a thick shadow`);
      assert.equal(key.pointerEvents, "auto", `${spec.label} key ${key.label} is not touchable`);
    }
    await page.evaluate(() => {
      window.__ghLargeModalTouchAudit = [];
      addEventListener("keydown", (event) => window.__ghLargeModalTouchAudit.push([event.type, event.key, event.code]), true);
      addEventListener("keyup", (event) => window.__ghLargeModalTouchAudit.push([event.type, event.key, event.code]), true);
    });
    if (spec.touch) await dock.locator('.gh-touch-key[data-gh-key-label="R"]').tap();
    else await dock.locator('.gh-touch-key[data-gh-key-label="R"]').click();
    assert.deepEqual(
      await page.evaluate(() => window.__ghLargeModalTouchAudit),
      [["keydown", "r", "KeyR"], ["keyup", "r", "KeyR"]],
      `${spec.label} touch text did not dispatch the original R shortcut`,
    );
    assert.deepEqual(pageErrors, [], `${spec.label} embed page errors`);
    touchResults.push({ label: spec.label, ...state });
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, modalResults, touchResults }, null, 2));
