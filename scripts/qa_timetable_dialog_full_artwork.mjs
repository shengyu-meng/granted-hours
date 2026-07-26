#!/usr/bin/env node
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8874/timetable/";
const failures = [];
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
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  const directLivePath = fileURLToPath(new URL("../docs/archive/2026/07/2026-07-08/live/index.html", import.meta.url));
  const previewGifPath = fileURLToPath(new URL("../docs/archive/2026/07/2026-07-08/assets/preview.gif", import.meta.url));
  const latestBgmPath = fileURLToPath(new URL("../docs/archive/2026/07/2026-07-26/assets/2026-07-26-window-that-does-not-watch-back-bgm.mp3", import.meta.url));
  await context.route(
    /^https:\/\/shengyu-meng\.github\.io\/granted-hours\/archive\/2026\/07\/2026-07-08\/live\/(?:\?.*)?$/,
    (route) => route.fulfill({ path: directLivePath, contentType: "text/html" }),
  );
  await context.route(
    "https://shengyu-meng.github.io/granted-hours/archive/2026/07/2026-07-08/assets/preview.gif",
    (route) => route.fulfill({ path: previewGifPath, contentType: "image/gif" }),
  );
  await page.route("**/*.mp3", (route) => route.fulfill({ path: latestBgmPath, contentType: "audio/mpeg" }));
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  await check("main timetable exposes latest-first BGM playlist and control", async () => {
    const latest = [...timetableData.days].sort((a, b) => b.date.localeCompare(a.date))[0];
    assert.ok(Array.isArray(timetableData.bgm_playlist));
    assert.equal(timetableData.bgm_playlist.length, timetableData.days.length);
    assert.equal(timetableData.bgm_playlist[0].date, latest.date);
    assert.ok(timetableData.bgm_playlist.every((item, index, list) => index === 0 || list[index - 1].date > item.date));
    assert.ok(timetableData.bgm_playlist.every((item) => /^https:\/\//.test(item.bgm_url)));
    const state = await page.evaluate(() => ({
      toggle: !!document.querySelector("#calendarBgmToggle"),
      status: document.querySelector("#calendarBgmStatus")?.textContent?.trim() || "",
      audio: Boolean(document.querySelector("#calendarBgm")),
      date: document.querySelector("#calendarBgm")?.dataset.date,
      src: document.querySelector("#calendarBgm")?.getAttribute("src") || "",
      paused: document.querySelector("#calendarBgm")?.paused,
      pressed: document.querySelector("#calendarBgmToggle")?.getAttribute("aria-pressed"),
    }));
    assert.ok(state.toggle && state.audio, JSON.stringify(state));
    assert.equal(state.date, latest.date);
    assert.match(state.src, /\.mp3(?:\?|$)/i);
    assert.equal(state.paused, true, JSON.stringify(state));
    assert.equal(state.pressed, "false", JSON.stringify(state));
    await page.click("#calendarBgmToggle");
    await page.waitForFunction(() => !document.querySelector("#calendarBgm")?.paused);
    assert.equal(await page.locator("#calendarBgmToggle").getAttribute("aria-pressed"), "true");
    const second = timetableData.bgm_playlist[1];
    await page.locator("#calendarBgm").evaluate((audio) => audio.dispatchEvent(new Event("ended")));
    await page.waitForFunction((date) => document.querySelector("#calendarBgm")?.dataset.date === date && !document.querySelector("#calendarBgm")?.paused, second.date);
    const advanced = await page.locator("#calendarBgm").evaluate((audio) => ({ date: audio.dataset.date, src: audio.getAttribute("src") || "" }));
    assert.equal(advanced.date, second.date, JSON.stringify(advanced));
    assert.equal(advanced.src, second.bgm_url, JSON.stringify(advanced));
    const third = timetableData.bgm_playlist[2];
    await page.evaluate(() => {
      const audio = document.querySelector("#calendarBgm");
      document.querySelector("#calendarBgmToggle")?.click();
      audio?.dispatchEvent(new Event("ended"));
    });
    await page.waitForFunction((date) => document.querySelector("#calendarBgm")?.dataset.date === date, third.date);
    assert.equal(await page.locator("#calendarBgm").evaluate((audio) => audio.paused), true);
    assert.equal(await page.locator("#calendarBgmToggle").getAttribute("aria-pressed"), "false");
  });

  await page.click('.calendar-day-button[data-date="2026-07-08"]');
  await page.waitForSelector("#dayDialog.is-open");
  await page.waitForTimeout(220);

  await check("desktop dialog fills usable viewport instead of sitting low", async () => {
    const geometry = await page.locator("#dayDialogPanel").evaluate((panel) => {
      const rect = panel.getBoundingClientRect();
      return { top: rect.top, bottom: rect.bottom, innerHeight, left: rect.left, right: rect.right, innerWidth };
    });
    assert.ok(geometry.top >= 0 && geometry.top <= 16, JSON.stringify(geometry));
    assert.ok(geometry.bottom <= geometry.innerHeight && geometry.bottom >= geometry.innerHeight - 16, JSON.stringify(geometry));
    assert.ok(geometry.left >= 0 && geometry.right <= geometry.innerWidth, JSON.stringify(geometry));
  });

  await check("daily dialog has one real vertical scroll root and no fake sediment rail", async () => {
    const topology = await page.evaluate(() => {
      const selectors = ["#dayDialog", "#dayDialogPanel", ".detail-layout", ".assigned-detail", ".self-detail"];
      return {
        roots: selectors.map((selector) => {
          const element = document.querySelector(selector);
          const style = getComputedStyle(element);
          return { selector, overflowY: style.overflowY, clientHeight: element.clientHeight, scrollHeight: element.scrollHeight };
        }),
        sedimentCount: document.querySelectorAll(".sediment-track,.sediment-segment").length,
      };
    });
    const scrollRoots = topology.roots.filter((root) => ["auto", "scroll"].includes(root.overflowY) && root.scrollHeight > root.clientHeight + 1);
    assert.deepEqual(scrollRoots.map((root) => root.selector), ["#dayDialogPanel"], JSON.stringify(topology));
    assert.equal(topology.sedimentCount, 0, JSON.stringify(topology));
  });

  await check("desktop wheel scroll moves the dialog panel and reaches final assigned work", async () => {
    const panel = page.locator("#dayDialogPanel");
    const box = await panel.boundingBox();
    assert.ok(box);
    for (let attempt = 0; attempt < 2; attempt += 1) {
      await page.mouse.move(box.x + box.width * 0.45, box.y + box.height * 0.65);
      await page.mouse.wheel(0, 1000);
      try {
        await page.waitForFunction(() => document.querySelector("#dayDialogPanel")?.scrollTop > 0, null, { timeout: 900 });
        break;
      } catch {
        if (attempt === 1) throw new Error("wheel did not move the dialog panel after two real-input attempts");
      }
    }
    assert.ok(await panel.evaluate((node) => node.scrollTop > 0));
    const bottom = await panel.evaluate((node) => {
      node.scrollTop = node.scrollHeight;
      const finalItem = document.querySelector(".assigned-item:last-child");
      const panelRect = node.getBoundingClientRect();
      const itemRect = finalItem.getBoundingClientRect();
      return { scrollTop: node.scrollTop, max: node.scrollHeight - node.clientHeight, itemBottom: itemRect.bottom, panelBottom: panelRect.bottom };
    });
    assert.ok(bottom.scrollTop >= bottom.max - 2, JSON.stringify(bottom));
    assert.ok(bottom.itemBottom <= bottom.panelBottom + 2, JSON.stringify(bottom));
  });

  await check("closing and reopening resets the single dialog scroll root", async () => {
    await page.click("#closeDetail");
    await page.click('.calendar-day-button[data-date="2026-07-08"]');
    await page.waitForSelector("#dayDialog.is-open");
    assert.equal(await page.locator("#dayDialogPanel").evaluate((panel) => panel.scrollTop), 0);
  });

  await check("live artwork opens as a complete direct page in a new tab", async () => {
    const link = page.locator("#enterAutonomous");
    const attrs = await link.evaluate((node) => ({ tag: node.tagName, href: node.href, target: node.target, rel: node.rel }));
    assert.equal(attrs.tag, "A", JSON.stringify(attrs));
    assert.equal(attrs.target, "_blank", JSON.stringify(attrs));
    assert.match(attrs.rel, /noopener/);
    assert.doesNotMatch(attrs.href, /[?&]embed=calendar/);
    assert.match(attrs.href, /[?&]from=timetable(?:&|$)/);
    const [popup] = await Promise.all([context.waitForEvent("page"), link.click()]);
    await popup.waitForLoadState("domcontentloaded");
    assert.doesNotMatch(popup.url(), /[?&]embed=calendar/);
    const direct = await popup.evaluate(() => ({
      embedded: document.body.classList.contains("gh-chamber-embed"),
      folded: document.body.classList.contains("gh-text-folded"),
      titleVisible: [...document.querySelectorAll("h1,.title")].some((node) => getComputedStyle(node).display !== "none" && node.getBoundingClientRect().width > 0),
      audioCount: document.querySelectorAll("audio").length,
    }));
    assert.equal(direct.embedded, false);
    assert.equal(direct.folded, false, JSON.stringify(direct));
    assert.ok(direct.titleVisible && direct.audioCount > 0, JSON.stringify(direct));
    await popup.close();
  });

  await check("autonomous side includes a clickable GIF or preview", async () => {
    await page.waitForFunction(() => {
      const image = document.querySelector("#selfPreview");
      return image?.complete && image.naturalWidth > 0 && image.naturalHeight > 0;
    });
    const preview = await page.locator("#selfPreview").evaluate((node) => ({ src: node.currentSrc || node.src, alt: node.alt, parentTag: node.parentElement?.tagName, target: node.parentElement?.target, href: node.parentElement?.href }));
    assert.match(preview.src, /preview\.(?:gif|png)(?:\?|$)/i, JSON.stringify(preview));
    assert.ok(preview.alt.length >= 4, JSON.stringify(preview));
    assert.equal(preview.parentTag, "A");
    assert.equal(preview.target, "_blank");
    assert.doesNotMatch(preview.href, /[?&]embed=calendar/);
    assert.match(preview.href, /[?&]from=timetable(?:&|$)/);
  });

  await check("rendered work copy exposes builder redaction state", async () => {
    const rows = await page.locator(".assigned-item").evaluateAll((items) => items.map((item) => ({
      status: item.dataset.redactionStatus || "",
      copy: item.querySelector(".assigned-copy")?.textContent || "",
      badge: item.querySelector(".redaction-badge")?.textContent || "",
    })));
    assert.ok(rows.every((row) => ["none", "partial", "withheld"].includes(row.status)), JSON.stringify(rows));
    assert.ok(rows.filter((row) => row.status !== "none").every((row) => row.copy.includes("████") && row.badge.length > 0), JSON.stringify(rows));
  });

  const mobile = await browser.newContext({ viewport: { width: 421, height: 386 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2.75 });
  const mobilePage = await mobile.newPage();
  await mobilePage.goto(baseUrl, { waitUntil: "networkidle" });
  await mobilePage.tap('.calendar-day-button[data-date="2026-07-08"]');
  await mobilePage.waitForSelector("#dayDialog.is-open");

  await check("short mobile uses the same single panel scroll root and reaches the live-work link", async () => {
    const panelBox = await mobilePage.locator("#dayDialogPanel").boundingBox();
    assert.ok(panelBox);
    const cdp = await mobile.newCDPSession(mobilePage);
    const x = panelBox.x + panelBox.width * 0.55;
    const startY = panelBox.y + panelBox.height * 0.78;
    await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: startY }] });
    for (const delta of [55, 110, 165, 220]) {
      await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: startY - delta }] });
    }
    await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
    await mobilePage.waitForTimeout(100);
    assert.ok(await mobilePage.locator("#dayDialogPanel").evaluate((panel) => panel.scrollTop > 0));
    const topology = await mobilePage.evaluate(() => {
      const panel = document.querySelector("#dayDialogPanel");
      const layout = document.querySelector(".detail-layout");
      const panelStyle = getComputedStyle(panel);
      const layoutStyle = getComputedStyle(layout);
      panel.scrollTop = panel.scrollHeight;
      const linkRect = document.querySelector("#enterAutonomous").getBoundingClientRect();
      const panelRect = panel.getBoundingClientRect();
      return {
        panelOverflow: panelStyle.overflowY,
        layoutOverflow: layoutStyle.overflowY,
        panelTop: panelRect.top,
        panelBottom: panelRect.bottom,
        viewport: innerHeight,
        scrollTop: panel.scrollTop,
        max: panel.scrollHeight - panel.clientHeight,
        linkBottom: linkRect.bottom,
        linkTop: linkRect.top,
      };
    });
    assert.equal(topology.panelOverflow, "auto", JSON.stringify(topology));
    assert.notEqual(topology.layoutOverflow, "auto", JSON.stringify(topology));
    assert.ok(topology.panelTop >= 0 && topology.panelBottom <= topology.viewport, JSON.stringify(topology));
    assert.ok(topology.scrollTop >= topology.max - 2, JSON.stringify(topology));
  });
  await mobile.close();
} finally {
  await browser.close();
}

if (failures.length) throw new Error(`Dialog/full-artwork regressions (${failures.length}):\n- ${failures.join("\n- ")}`);
console.log(JSON.stringify({ passed: true }, null, 2));
