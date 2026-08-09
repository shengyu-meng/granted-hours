#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8874/timetable/";
const sampleDate = "2026-07-08";
const browser = await chromium.launch({ headless: true });

async function scrollTopology(page) {
  return page.evaluate(() => {
    const candidates = [
      document.querySelector("#dayDialog"),
      document.querySelector("#dayDialogPanel"),
      document.querySelector(".timeline-detail"),
      document.querySelector(".timeline-list"),
    ].filter(Boolean);
    return candidates.map((element) => {
      const style = getComputedStyle(element);
      return {
        selector: element.id ? `#${element.id}` : `.${element.classList[0]}`,
        overflowY: style.overflowY,
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
        canScroll: element.scrollHeight > element.clientHeight + 2
          && ["auto", "scroll"].includes(style.overflowY),
      };
    });
  });
}

try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
  const page = await context.newPage();
  const sampleUrl = new URL(baseUrl);
  sampleUrl.searchParams.set("date", sampleDate);
  await page.goto(sampleUrl.href, { waitUntil: "domcontentloaded" });

  const latest = [...timetableData.days].sort((a, b) => b.date.localeCompare(a.date))[0];
  assert.equal(
    timetableData.bgm_playlist.length,
    timetableData.days.filter((day) => day.autonomous_work?.origin !== "absence").length,
  );
  assert.equal(timetableData.bgm_playlist[0].date, latest.date);
  assert.equal(await page.locator("#calendarBgm").getAttribute("data-date"), latest.date);

  await page.waitForSelector(`#dayDialog.is-open[data-selected-date="${sampleDate}"]`);
  await page.waitForFunction(() => {
    const panel = document.querySelector("#dayDialogPanel");
    if (!panel) return false;
    const transform = getComputedStyle(panel).transform;
    if (transform === "none") return true;
    return Math.abs(new DOMMatrixReadOnly(transform).m42) < 0.5;
  });
  const geometry = await page.locator("#dayDialogPanel").evaluate((panel) => {
    const rect = panel.getBoundingClientRect();
    return { top: rect.top, bottom: rect.bottom, viewport: innerHeight };
  });
  assert.ok(geometry.top >= 0 && geometry.top <= 16, JSON.stringify(geometry));
  assert.ok(geometry.bottom <= geometry.viewport && geometry.bottom >= geometry.viewport - 16, JSON.stringify(geometry));

  const roots = await scrollTopology(page);
  assert.deepEqual(
    roots.filter((root) => root.canScroll).map((root) => root.selector),
    ["#dayDialogPanel"],
    JSON.stringify(roots),
  );
  assert.equal(await page.locator(".self-detail").count(), 0);
  assert.equal(await page.locator(".autonomous-event").count(), 1);
  assert.ok(await page.locator(".pulse-event").count() > 0);
  assert.equal(await page.locator(".sediment-track").count(), 0);

  const preview = await page.locator("#selfPreview").evaluate(async (image) => {
    await image.decode();
    const card = image.closest(".autonomous-reading-card");
    const previewLink = image.closest(".autonomous-preview-frame");
    const launch = card?.querySelector(".autonomous-open-copy");
    return {
      src: image.currentSrc || image.src,
      alt: image.alt,
      cardTag: card?.tagName,
      cardRole: card?.getAttribute("role"),
      cardTabindex: card?.getAttribute("tabindex"),
      cardHref: card?.getAttribute("href"),
      previewTag: previewLink?.tagName,
      previewPopup: previewLink?.getAttribute("aria-haspopup"),
      previewName: previewLink?.getAttribute("aria-label"),
      launchTag: launch?.tagName,
      launchPopup: launch?.getAttribute("aria-haspopup"),
      launchName: launch?.textContent?.trim(),
    };
  });
  assert.match(preview.src, /visual-preview\.gif$/);
  assert.match(preview.alt, /Text-free visual preview/);
  assert.equal(preview.cardTag, "ARTICLE");
  assert.equal(preview.cardRole, null);
  assert.equal(preview.cardTabindex, null);
  assert.equal(preview.cardHref, null);
  assert.equal(preview.previewTag, "BUTTON");
  assert.equal(preview.previewPopup, "dialog");
  assert.match(preview.previewName, /Open interactive artwork in the calendar/);
  assert.equal(preview.launchTag, "BUTTON");
  assert.equal(preview.launchPopup, "dialog");
  assert.match(preview.launchName, /Open interactive artwork/);
  const outerActivationCount = await page.locator("#enterAutonomous").evaluate((card) => {
    const originalOpen = window.open;
    let opens = 0;
    window.open = () => {
      opens += 1;
      return null;
    };
    try {
      card.click();
      card.dispatchEvent(new KeyboardEvent("keydown", {
        key: "Enter",
        bubbles: true,
        cancelable: true,
      }));
      card.dispatchEvent(new KeyboardEvent("keydown", {
        key: " ",
        bubbles: true,
        cancelable: true,
      }));
    } finally {
      window.open = originalOpen;
    }
    return opens;
  });
  assert.equal(outerActivationCount, 0);

  const artworkPage = await context.newPage();
  await artworkPage.route("https://shengyu-meng.github.io/granted-hours/archive/**/live/**", async (route) => {
    await route.fulfill({
      contentType: "text/html",
      body: `<!doctype html><body class="gh-chamber-embed"><script>
        const channel = new URL(location.href).searchParams.get("gh_channel");
        addEventListener("message", (event) => {
          const data = event.data;
          if (data?.type !== "granted-hours:media" || data?.version !== 1 || data?.channel !== channel) return;
          document.body.dataset.ghAudioEnabled = data.action === "play" ? "1" : "0";
        });
      <\/script></body>`,
    });
  });
  const artworkUrl = new URL(baseUrl);
  artworkUrl.searchParams.set("date", latest.date);
  await artworkPage.goto(artworkUrl.href, { waitUntil: "domcontentloaded" });
  await artworkPage.waitForSelector(`#dayDialog.is-open[data-selected-date="${latest.date}"]`);
  assert.equal(await artworkPage.locator("#calendarBgmToggle").getAttribute("aria-pressed"), "true");
  assert.equal(await artworkPage.locator("#calendarPianoToggle").getAttribute("aria-pressed"), "true");
  const pageCountBeforeArtwork = context.pages().length;
  await artworkPage.locator(".autonomous-preview-frame").click();
  await artworkPage.waitForSelector("#artworkDialog.is-open");
  assert.equal(context.pages().length, pageCountBeforeArtwork);
  assert.equal(await artworkPage.locator("#calendarBgm").evaluate((audio) => audio.paused), true);
  assert.equal(await artworkPage.locator("#calendarBgmToggle").getAttribute("data-suspended"), "true");
  const artworkFrameSrc = await artworkPage.locator("#artworkLiveFrame").getAttribute("src");
  assert.match(artworkFrameSrc, /[?&]embed=calendar(?:&|$)/);
  assert.match(artworkFrameSrc, /[?&]gh_channel=[a-f0-9]{32}(?:&|$)/);
  const artworkFrame = artworkPage.frames().find((frame) => frame.url().includes("embed=calendar"));
  assert.ok(artworkFrame);
  await artworkFrame.locator("body.gh-chamber-embed").waitFor({ state: "attached" });
  await artworkFrame.waitForFunction(() => document.body.dataset.ghAudioEnabled === "1");
  await artworkPage.locator("#artworkFullscreen").click();
  await artworkPage.waitForFunction(() => document.fullscreenElement?.id === "artworkDialogPanel");
  assert.equal(await artworkPage.locator("#artworkReturnCalendar").isVisible(), true);
  await artworkPage.evaluate(() => document.querySelector("#artworkReturnCalendar").click());
  await artworkPage.waitForFunction(() => document.fullscreenElement === null);
  await artworkPage.waitForSelector("#artworkDialog", { state: "hidden" });
  assert.equal(await artworkPage.locator("#artworkLiveFrame").getAttribute("src"), "about:blank");
  assert.equal(await artworkPage.locator("#calendarBgmToggle").getAttribute("aria-pressed"), "true");
  assert.equal(await artworkPage.locator("#calendarBgmToggle").getAttribute("data-suspended"), "false");
  await artworkPage.waitForFunction(() => document.activeElement?.classList.contains("autonomous-preview-frame"));
  await artworkPage.close();

  const rows = await page.locator(".assigned-item").evaluateAll((items) => items.map((item) => ({
    status: item.dataset.redactionStatus || "",
    copy: item.querySelector(".assigned-copy")?.textContent || "",
    badge: item.querySelector(".redaction-badge")?.textContent || "",
  })));
  assert.ok(rows.every((row) => ["none", "partial", "withheld"].includes(row.status)), JSON.stringify(rows));
  assert.ok(rows.filter((row) => row.status !== "none").every((row) => row.copy.includes("████") && row.badge), JSON.stringify(rows));

  await page.locator("#dayDialogPanel").evaluate((panel) => { panel.scrollTop = panel.scrollHeight; });
  assert.ok(await page.locator(".timeline-event").last().evaluate((event) => {
    const rect = event.getBoundingClientRect();
    const panel = document.querySelector("#dayDialogPanel").getBoundingClientRect();
    return rect.top >= panel.top - 1 && rect.bottom <= panel.bottom + 1;
  }));
  await page.locator("#enterAutonomous").scrollIntoViewIfNeeded();
  assert.ok(await page.locator("#enterAutonomous").isVisible());
  await page.keyboard.press("Escape");
  await page.click(`.calendar-day-button[data-date="${sampleDate}"]`);
  assert.ok(await page.locator("#dayDialogPanel").evaluate((panel) => panel.scrollTop <= 1));
  await page.keyboard.press("Escape");
  await context.close();

  const mobile = await browser.newContext({
    viewport: { width: 421, height: 386 },
    isMobile: true,
    hasTouch: true,
    deviceScaleFactor: 2.75,
  });
  const mobilePage = await mobile.newPage();
  await mobilePage.goto(sampleUrl.href, { waitUntil: "domcontentloaded" });
  await mobilePage.waitForSelector(`#dayDialog.is-open[data-selected-date="${sampleDate}"]`);
  const mobileRoots = await scrollTopology(mobilePage);
  assert.deepEqual(
    mobileRoots.filter((root) => root.canScroll).map((root) => root.selector),
    ["#dayDialogPanel"],
    JSON.stringify(mobileRoots),
  );
  const panelBox = await mobilePage.locator("#dayDialogPanel").boundingBox();
  const cdp = await mobile.newCDPSession(mobilePage);
  const x = panelBox.x + panelBox.width * 0.55;
  const startY = panelBox.y + panelBox.height * 0.8;
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: [{ x, y: startY }] });
  for (const delta of [55, 110, 165, 220]) {
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: [{ x, y: startY - delta }] });
  }
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await mobilePage.waitForTimeout(100);
  assert.ok(await mobilePage.locator("#dayDialogPanel").evaluate((panel) => panel.scrollTop > 0));
  await mobilePage.locator("#dayDialogPanel").evaluate((panel) => { panel.scrollTop = panel.scrollHeight; });
  assert.ok(await mobilePage.locator(".timeline-event").last().evaluate((event) => {
    const rect = event.getBoundingClientRect();
    return rect.top >= -1 && rect.bottom <= innerHeight + 1;
  }));
  await mobilePage.locator("#enterAutonomous").scrollIntoViewIfNeeded();
  assert.ok(await mobilePage.locator("#enterAutonomous").isVisible());
  await mobile.close();
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, sampleDate }, null, 2));
