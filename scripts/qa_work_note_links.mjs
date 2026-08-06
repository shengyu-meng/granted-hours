#!/usr/bin/env node
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const siteUrl = new URL(
  process.env.WORK_NOTE_SITE_URL || "http://127.0.0.1:8891/",
);
if (!siteUrl.pathname.endsWith("/")) siteUrl.pathname += "/";
const siteOrigin = siteUrl.origin;
const days = JSON.parse(
  readFileSync(new URL("../metadata/days.json", import.meta.url), "utf8"),
);

const args = process.argv.slice(2);
const requestedDates = [];
for (let index = 0; index < args.length; index += 1) {
  if (args[index] !== "--date") continue;
  const value = args[index + 1];
  assert.match(value || "", /^\d{4}-\d{2}-\d{2}$/, "--date must be YYYY-MM-DD");
  requestedDates.push(value);
  index += 1;
}
const selectedDays = requestedDates.length
  ? days.filter((day) => requestedDates.includes(day.date))
  : days.slice(-3);

assert.ok(days.length > 0, "Expected at least one declared public day");
assert.equal(
  new Set(days.map((day) => day.date)).size,
  days.length,
  "Declared public days must be unique",
);
assert.equal(
  selectedDays.length,
  requestedDates.length || Math.min(3, days.length),
  "Every requested work-note date must be declared",
);

function archivePaths(day) {
  const [year, month] = day.date.split("-");
  return {
    explanationFile: new URL(
      `../docs/archive/${year}/${month}/${day.date}/index.html`,
      import.meta.url,
    ),
    liveFile: new URL(
      `../docs/archive/${year}/${month}/${day.date}/live/index.html`,
      import.meta.url,
    ),
    explanationUrl: new URL(
      `archive/${year}/${month}/${day.date}/`,
      siteUrl,
    ).href,
    liveUrl: new URL(
      `archive/${year}/${month}/${day.date}/live/`,
      siteUrl,
    ).href,
  };
}

for (const day of days) {
  const paths = archivePaths(day);
  assert.ok(existsSync(paths.explanationFile), `${day.date} explanation page is missing`);
  assert.ok(existsSync(paths.liveFile), `${day.date} live page is missing`);
  const liveHtml = readFileSync(paths.liveFile, "utf8");
  assert.match(
    liveHtml,
    /gh-work-note-(?:link|trigger)/,
    `${day.date} live page has no checked-in work-note contract`,
  );
}

function trackPageHealth(page, label) {
  const pageErrors = [];
  const responseErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("response", (response) => {
    if (new URL(response.url()).origin === siteOrigin && response.status() >= 400) {
      responseErrors.push(`${response.status()} ${response.url()}`);
    }
  });
  return {
    assertHealthy() {
      assert.deepEqual(pageErrors, [], `${label} page errors: ${pageErrors.join("; ")}`);
      assert.deepEqual(
        responseErrors,
        [],
        `${label} same-origin response errors: ${responseErrors.join("; ")}`,
      );
    },
  };
}

const browser = await chromium.launch({ headless: true });
try {
  const directResults = [];
  for (const day of selectedDays) {
    const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });
    const page = await context.newPage();
    const health = trackPageHealth(page, day.date);
    const paths = archivePaths(day);
    const url = new URL(paths.liveUrl);
    url.searchParams.set("qa", "work-note-direct");
    const response = await page.goto(url.href, {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });
    assert.equal(response?.status(), 200, `${day.date} HTTP ${response?.status()}`);
    const trigger = page.locator('.gh-work-note-trigger[aria-controls="ghWorkNoteOverlay"]');
    await trigger.waitFor({ state: "visible", timeout: 20000 });
    assert.equal(await trigger.count(), 1, `${day.date} work-note trigger count`);
    assert.equal(await trigger.textContent(), "Work note / 作品说明");
    assert.equal(
      await trigger.getAttribute("aria-label"),
      "Open the artwork note over the interactive work / 在交互作品上方打开作品说明",
    );
    await trigger.click();
    const overlay = page.locator("#ghWorkNoteOverlay");
    await overlay.waitFor({ state: "visible" });
    assert.ok(await overlay.evaluate((node) => node.classList.contains("is-open")));
    const archive = overlay.locator(".gh-work-note-archive");
    assert.equal(await archive.getAttribute("href"), "../");
    assert.equal(await archive.evaluate((node) => node.href), paths.explanationUrl);
    assert.ok(await overlay.locator(".gh-work-note-section").count() >= 3);
    await page.keyboard.press("Escape");
    await overlay.waitFor({ state: "hidden" });
    health.assertHealthy();
    directResults.push(day.date);
    await context.close();
  }

  const latest = selectedDays.at(-1);
  const latestPaths = archivePaths(latest);
  const embedContext = await browser.newContext({ viewport: { width: 960, height: 540 } });
  const embedPage = await embedContext.newPage();
  const embedHealth = trackPageHealth(embedPage, `${latest.date} embed`);
  const embedUrl = new URL(latestPaths.liveUrl);
  embedUrl.searchParams.set("embed", "calendar");
  embedUrl.searchParams.set("qa", "work-note-embed");
  await embedPage.goto(embedUrl.href, { waitUntil: "domcontentloaded" });
  await embedPage.waitForFunction(() => document.body.classList.contains("gh-chamber-embed"));
  assert.equal(
    await embedPage.locator('.gh-work-note-trigger[aria-controls="ghWorkNoteOverlay"]').isVisible(),
    false,
    "Embed mode exposed the work-note trigger",
  );
  embedHealth.assertHealthy();
  await embedContext.close();

  const viewportSpecs = [
    { label: "desktop-1440x900", context: { viewport: { width: 1440, height: 900 } }, touch: false },
    {
      label: "mobile-390x844",
      context: {
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 2.75,
        isMobile: true,
        hasTouch: true,
      },
      touch: true,
    },
    {
      label: "short-touch-421x386",
      context: {
        viewport: { width: 421, height: 386 },
        deviceScaleFactor: 2.75,
        isMobile: true,
        hasTouch: true,
      },
      touch: true,
    },
  ];
  const viewportResults = [];
  for (const spec of viewportSpecs) {
    const context = await browser.newContext(spec.context);
    const page = await context.newPage();
    const health = trackPageHealth(page, `${latest.date} ${spec.label}`);
    const url = new URL(latestPaths.liveUrl);
    url.searchParams.set("qa", spec.label);
    await page.goto(url.href, { waitUntil: "domcontentloaded" });
    const trigger = page.locator("#ghWorkNoteTrigger");
    await trigger.waitFor({ state: "visible" });
    assert.equal(await page.locator(".gh-fold-toggle").count(), 0, `${spec.label} fold control still exists`);
    const geometry = await page.evaluate(() => {
      const isVisible = (element) => {
        if (!element) return false;
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0.01 && rect.width > 1 && rect.height > 1;
      };
      const trigger = document.querySelector("#ghWorkNoteTrigger");
      const sound = [...document.querySelectorAll(
        '#sound, .sound, #soundToggle, #musicToggle, button[id*="sound" i], button[id*="music" i], button[id*="bgm" i]',
      )].find(isVisible);
      const triggerRect = trigger.getBoundingClientRect();
      const soundRect = sound?.getBoundingClientRect();
      const overlapWidth = soundRect
        ? Math.max(0, Math.min(triggerRect.right, soundRect.right) - Math.max(triggerRect.left, soundRect.left))
        : 0;
      const overlapHeight = soundRect
        ? Math.max(0, Math.min(triggerRect.bottom, soundRect.bottom) - Math.max(triggerRect.top, soundRect.top))
        : 0;
      const viewportArea = innerWidth * innerHeight;
      const textBlocks = [...document.querySelectorAll(
        'h1,h2,h3,h4,h5,h6,p,span,div,label,legend,figcaption,li,a,button',
      )].filter((el) => isVisible(el)
        && (el.innerText || "").trim().length > 0
        && !el.closest("#ghWorkNoteOverlay")
        && el !== trigger
        && !(sound && (el === sound || sound.contains(el)))
        && el.getBoundingClientRect().width * el.getBoundingClientRect().height <= viewportArea * 0.55);
      let textOverlapCount = 0;
      let worstTextOverlap = 0;
      for (const el of textBlocks) {
        const rect = el.getBoundingClientRect();
        const iw = Math.max(0, Math.min(triggerRect.right, rect.right) - Math.max(triggerRect.left, rect.left));
        const ih = Math.max(0, Math.min(triggerRect.bottom, rect.bottom) - Math.max(triggerRect.top, rect.top));
        if (iw > 0 && ih > 0) {
          textOverlapCount += 1;
          worstTextOverlap = Math.max(worstTextOverlap, iw * ih);
        }
      }
      const soundBottomRight = Boolean(
        soundRect
        && soundRect.left > innerWidth * 0.25
        && soundRect.width <= innerWidth * 0.45
        && soundRect.bottom > innerHeight * 0.45,
      );
      return {
        viewport: { width: innerWidth, height: innerHeight },
        horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        trigger: triggerRect.toJSON(),
        sound: soundRect ? soundRect.toJSON() : null,
        triggerLeftOfSound: Boolean(soundRect && triggerRect.right <= soundRect.left + 1),
        bottomAlignedWithSound: Boolean(soundRect && Math.abs(triggerRect.bottom - soundRect.bottom) <= 2),
        overlapArea: overlapWidth * overlapHeight,
        liftedAboveSound: Boolean(soundRect && triggerRect.bottom < soundRect.top),
        soundBottomRight,
        textOverlapCount,
        worstTextOverlap,
      };
    });
    assert.ok(geometry.horizontalOverflow <= 1, `${spec.label} horizontal overflow`);
    assert.ok(geometry.trigger.height >= 38, `${spec.label} trigger touch target`);
    assert.ok(geometry.trigger.left >= 0 && geometry.trigger.top >= 0, `${spec.label} trigger offscreen`);
    assert.ok(geometry.trigger.right <= geometry.viewport.width && geometry.trigger.bottom <= geometry.viewport.height, `${spec.label} trigger offscreen`);
    assert.ok(geometry.sound, `${spec.label} sound control not visible`);
    if (geometry.soundBottomRight) {
      assert.ok(geometry.triggerLeftOfSound, `${spec.label} trigger is not left of the bottom-right sound control`);
      assert.ok(
        geometry.bottomAlignedWithSound || geometry.liftedAboveSound,
        `${spec.label} trigger is neither aligned with nor lifted above the sound control`,
      );
    }
    assert.equal(geometry.overlapArea, 0, `${spec.label} controls overlap`);
    assert.equal(geometry.textOverlapCount, 0, `${spec.label} trigger overlaps ${geometry.textOverlapCount} visible text blocks (worst ${geometry.worstTextOverlap}px²)`);
    if (spec.touch) await trigger.tap();
    else await trigger.click();
    const overlay = page.locator("#ghWorkNoteOverlay");
    await overlay.waitFor({ state: "visible" });
    const close = overlay.locator(".gh-work-note-close");
    if (spec.touch) await close.tap();
    else await close.click();
    await overlay.waitFor({ state: "hidden" });
    health.assertHealthy();
    viewportResults.push({ label: spec.label, ...geometry });
    await context.close();
  }

  console.log(JSON.stringify({
    passed: true,
    declaredExplanationPages: days.length,
    browserCheckedDates: directResults,
    latestOverlayDate: latest.date,
    embedHidden: true,
    viewportResults,
    pageErrors: 0,
    sameOriginHttpFailures: 0,
  }, null, 2));
} finally {
  await browser.close();
}
