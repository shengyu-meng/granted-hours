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

async function stubArtworkEmbed(page) {
  await page.route("https://shengyu-meng.github.io/granted-hours/archive/**/live/**", async (route) => {
    await route.fulfill({
      contentType: "text/html",
      body: `<!doctype html><body class="gh-chamber-embed"><script>
        const channel = new URL(location.href).searchParams.get("gh_channel");
        const parentOrigin = new URL(document.referrer).origin;
        const send = (event, status) => parent.postMessage({
          type: "granted-hours:media", version: 2, channel, event, status,
        }, parentOrigin);
        addEventListener("message", (event) => {
          const data = event.data;
          if (data?.type !== "granted-hours:media" || data?.version !== 2 || data?.channel !== channel) return;
          document.body.dataset.ghAudioEnabled = data.action === "play" ? "1" : "0";
          send("state", data.action === "play" ? "armed" : "paused");
        });
        queueMicrotask(() => send("ready", "ready"));
      <\/script></body>`,
    });
  });
}

async function artworkBriefLayout(page) {
  return page.evaluate(() => {
    const kicker = document.querySelector(".artwork-dialog-header .artwork-detail-kicker");
    const fullscreen = document.querySelector("#artworkFullscreen");
    const brief = document.querySelector(".artwork-brief-card");
    const rect = (element) => {
      const box = element.getBoundingClientRect();
      return { top: box.top, right: box.right, left: box.left, bottom: box.bottom };
    };
    return {
      summaryCardCount: document.querySelectorAll(".artwork-summary-card").length,
      briefCardCount: document.querySelectorAll(".artwork-brief-card").length,
      heading: document.querySelector("#artworkBriefLabel")?.textContent?.trim(),
      paragraphIds: [...brief.querySelectorAll("p")].map((paragraph) => paragraph.id),
      paragraphText: [...brief.querySelectorAll("p")].map((paragraph) => paragraph.textContent),
      languages: [...brief.querySelectorAll(".artwork-brief-language-group")]
        .map((group) => group.lang),
      dividerCount: brief.querySelectorAll(".bilingual-summary-divider").length,
      actionOrder: [...document.querySelector(".artwork-dialog-actions").children]
        .map((control) => control.id),
      kicker: rect(kicker),
      fullscreen: rect(fullscreen),
      brief: rect(brief),
      pageOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    };
  });
}

function assertArtworkBriefLayout(state, self, label) {
  assert.equal(state.summaryCardCount, 0, `${label}: legacy Summary card remains`);
  assert.equal(state.briefCardCount, 1, `${label}: Brief must be one merged card`);
  assert.equal(state.heading, "Brief / 作品摘要", `${label}: merged heading`);
  assert.deepEqual(
    state.paragraphIds,
    ["artworkDetailZh", "artworkBriefZh", "artworkDetailEn", "artworkBriefEn"],
    `${label}: language-first paragraph order`,
  );
  assert.deepEqual(
    state.paragraphText,
    [self.note_zh, self.brief_zh, self.note_en, self.brief_en],
    `${label}: Summary and Brief copy must remain complete`,
  );
  assert.deepEqual(state.languages, ["zh", "en"], `${label}: language group order`);
  assert.equal(state.dividerCount, 1, `${label}: only the language boundary needs a divider`);
  assert.deepEqual(
    state.actionOrder,
    ["closeArtworkDetail", "artworkFullscreen"],
    `${label}: fullscreen must own the aligned right edge`,
  );
  assert.ok(
    Math.abs(state.fullscreen.top - state.kicker.top) <= 1,
    `${label}: fullscreen top is not aligned to the autonomous-artwork heading ${JSON.stringify(state)}`,
  );
  assert.ok(
    Math.abs(state.fullscreen.right - state.brief.right) <= 1,
    `${label}: fullscreen right edge is not aligned to the Brief card ${JSON.stringify(state)}`,
  );
  assert.ok(state.pageOverflow <= 1, `${label}: horizontal overflow ${state.pageOverflow}`);
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
  await stubArtworkEmbed(artworkPage);
  const artworkUrl = new URL(baseUrl);
  artworkUrl.searchParams.set("date", latest.date);
  await artworkPage.goto(artworkUrl.href, { waitUntil: "domcontentloaded" });
  await artworkPage.waitForSelector(`#dayDialog.is-open[data-selected-date="${latest.date}"]`);
  assert.equal(await artworkPage.locator("#calendarBgmToggle").getAttribute("aria-pressed"), "true");
  assert.equal(await artworkPage.locator("#calendarPianoToggle").getAttribute("aria-pressed"), "true");
  const pageCountBeforeArtwork = context.pages().length;
  await artworkPage.locator(".autonomous-preview-frame").click({ noWaitAfter: true });
  await artworkPage.waitForSelector("#artworkDialog.is-open");
  assert.equal(context.pages().length, pageCountBeforeArtwork);
  assert.equal(await artworkPage.locator("#calendarBgm").evaluate((audio) => audio.paused), true);
  assert.equal(await artworkPage.locator("#calendarBgmToggle").getAttribute("data-suspended"), "true");
  const artworkFrameSrc = await artworkPage.locator("#artworkLiveFrame").getAttribute("src");
  assert.match(artworkFrameSrc, /[?&]embed=calendar(?:&|$)/);
  assert.match(artworkFrameSrc, /[?&]gh_channel=[a-f0-9]{32}(?:&|$)/);
  assert.equal(await artworkPage.locator("#artworkBriefZh").textContent(), latest.autonomous_work.brief_zh);
  assert.equal(await artworkPage.locator("#artworkBriefEn").textContent(), latest.autonomous_work.brief_en);
  assertArtworkBriefLayout(
    await artworkBriefLayout(artworkPage),
    latest.autonomous_work,
    "desktop-1280x720",
  );
  assert.match(await artworkPage.locator("#artworkLiveLink").getAttribute("href"), /\/live\//);
  assert.ok(await artworkPage.locator(".artwork-brief-card").evaluate((brief) => (
    brief.compareDocumentPosition(document.querySelector("#artworkLiveLink"))
    & Node.DOCUMENT_POSITION_FOLLOWING
  ) !== 0));
  assert.ok(await artworkPage.locator("#artworkLiveLink").evaluate((link) => (
    link.compareDocumentPosition(document.querySelector("#artworkArchiveLink"))
    & Node.DOCUMENT_POSITION_FOLLOWING
  ) !== 0));
  const artworkFrame = artworkPage.frames().find((frame) => frame.url().includes("embed=calendar"));
  assert.ok(artworkFrame);
  await artworkFrame.locator("body.gh-chamber-embed").waitFor({ state: "attached" });
  await artworkFrame.waitForFunction(() => document.body.dataset.ghAudioEnabled === "1");
  await artworkPage.waitForFunction(() => document.querySelector("#artworkRuntimeStatus").hidden);
  await artworkPage.locator("#artworkFullscreen").click();
  await artworkPage.waitForFunction(() => document.fullscreenElement?.id === "artworkDialogPanel");
  assert.equal(await artworkPage.locator("#artworkReturnCalendar").isVisible(), true);
  assert.equal(
    await artworkPage.locator("#closeArtworkDetail").getAttribute("aria-label"),
    "Exit fullscreen / 退出全屏",
  );
  const fullscreenFrameSrc = await artworkPage.locator("#artworkLiveFrame").getAttribute("src");
  await artworkPage.locator("#closeArtworkDetail").click();
  await artworkPage.waitForFunction(() => document.fullscreenElement === null);
  assert.equal(await artworkPage.locator("#artworkDialog").isVisible(), true);
  assert.equal(await artworkPage.locator("#artworkDialog").getAttribute("class"), "artwork-dialog is-open");
  assert.equal(await artworkPage.locator("#artworkLiveFrame").getAttribute("src"), fullscreenFrameSrc);
  assert.equal(await artworkPage.locator("#artworkBriefZh").isVisible(), true);
  assert.equal(await artworkPage.locator("#artworkBriefEn").isVisible(), true);
  assert.equal(await artworkPage.locator("#calendarBgmToggle").getAttribute("data-suspended"), "true");
  await artworkPage.waitForFunction(() => document.activeElement?.id === "closeArtworkDetail");
  assert.equal(
    await artworkPage.locator("#closeArtworkDetail").getAttribute("aria-label"),
    "Close artwork detail / 关闭作品详情",
  );
  await artworkPage.locator("#closeArtworkDetail").click();
  await artworkPage.waitForSelector("#artworkDialog", { state: "hidden" });
  assert.equal(await artworkPage.locator("#artworkLiveFrame").getAttribute("src"), "about:blank");
  await artworkPage.waitForFunction(() => document.activeElement?.classList.contains("autonomous-preview-frame"));
  await artworkPage.locator(".autonomous-preview-frame").click({ noWaitAfter: true });
  await artworkPage.waitForSelector("#artworkDialog.is-open");
  const escapeFrameSrc = await artworkPage.locator("#artworkLiveFrame").getAttribute("src");
  await artworkPage.locator("#artworkFullscreen").click();
  await artworkPage.waitForFunction(() => document.fullscreenElement?.id === "artworkDialogPanel");
  await artworkPage.keyboard.press("Escape");
  await artworkPage.waitForFunction(() => document.fullscreenElement === null);
  assert.equal(await artworkPage.locator("#artworkDialog").isVisible(), true);
  assert.equal(await artworkPage.locator("#artworkLiveFrame").getAttribute("src"), escapeFrameSrc);
  await artworkPage.waitForFunction(() => document.activeElement?.id === "closeArtworkDetail");
  await artworkPage.locator("#artworkFullscreen").click();
  await artworkPage.waitForFunction(() => document.fullscreenElement?.id === "artworkDialogPanel");
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
  const sampleDay = timetableData.days.find((day) => day.date === sampleDate);
  await mobilePage.locator(".autonomous-preview-frame").click({ noWaitAfter: true });
  await mobilePage.waitForSelector("#artworkDialog.is-open");
  assert.equal(await mobilePage.locator("#artworkBriefZh").textContent(), sampleDay.autonomous_work.brief_zh);
  assert.equal(await mobilePage.locator("#artworkBriefEn").textContent(), sampleDay.autonomous_work.brief_en);
  assertArtworkBriefLayout(
    await artworkBriefLayout(mobilePage),
    sampleDay.autonomous_work,
    "short-touch-421x386",
  );
  const mobileArtworkGeometry = await mobilePage.locator("#artworkDialogPanel").evaluate((panel) => {
    const rect = panel.getBoundingClientRect();
    const style = getComputedStyle(panel);
    return {
      left: rect.left,
      right: rect.right,
      viewportWidth: innerWidth,
      overflowX: style.overflowX,
      overflowY: style.overflowY,
      canScroll: panel.scrollHeight > panel.clientHeight + 2,
    };
  });
  assert.ok(mobileArtworkGeometry.left >= 0, JSON.stringify(mobileArtworkGeometry));
  assert.ok(mobileArtworkGeometry.right <= mobileArtworkGeometry.viewportWidth, JSON.stringify(mobileArtworkGeometry));
  assert.equal(mobileArtworkGeometry.overflowX, "hidden");
  assert.equal(mobileArtworkGeometry.overflowY, "auto");
  assert.equal(mobileArtworkGeometry.canScroll, true);
  await mobilePage.locator("#artworkBriefZh").scrollIntoViewIfNeeded();
  assert.equal(await mobilePage.locator("#artworkBriefZh").isVisible(), true);
  await mobilePage.locator("#artworkLiveLink").scrollIntoViewIfNeeded();
  assert.equal(await mobilePage.locator("#artworkLiveLink").isVisible(), true);
  await mobile.close();

  for (const viewportCase of [
    { label: "mobile-390x844", viewport: { width: 390, height: 844 }, mobile: true },
    { label: "desktop-4k", viewport: { width: 3840, height: 2160 }, mobile: false },
  ]) {
    const responsiveContext = await browser.newContext({
      viewport: viewportCase.viewport,
      isMobile: viewportCase.mobile,
      hasTouch: viewportCase.mobile,
    });
    const responsivePage = await responsiveContext.newPage();
    await stubArtworkEmbed(responsivePage);
    const responsiveUrl = new URL(baseUrl);
    responsiveUrl.searchParams.set("date", latest.date);
    await responsivePage.goto(responsiveUrl.href, { waitUntil: "domcontentloaded" });
    await responsivePage.waitForSelector(`#dayDialog.is-open[data-selected-date="${latest.date}"]`);
    await responsivePage.locator(".autonomous-preview-frame").click({ noWaitAfter: true });
    await responsivePage.waitForSelector("#artworkDialog.is-open");
    assertArtworkBriefLayout(
      await artworkBriefLayout(responsivePage),
      latest.autonomous_work,
      viewportCase.label,
    );
    await responsiveContext.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, sampleDate }, null, 2));
