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
  if (day.type === "calendar") {
    continue;
  }
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
    const calendarReturn = page.locator("#ghCalendarReturn");
    await calendarReturn.waitFor({ state: "visible" });
    assert.equal(await calendarReturn.textContent(), "Calendar / 非人时间表");
    assert.equal(
      await calendarReturn.getAttribute("aria-label"),
      "Return to the non-human timetable / 返回非人时间表",
    );
    assert.equal(await calendarReturn.evaluate((node) => node.href), new URL(`timetable/?date=${day.date}`, siteUrl).href);
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
    await calendarReturn.click();
    await page.waitForURL(
      (currentUrl) => currentUrl.pathname.endsWith("/timetable/")
        && currentUrl.searchParams.get("date") === day.date,
      { timeout: 30000 },
    );
    const returnedDayDialog = page.locator(
      `#dayDialog.is-open[data-selected-date="${day.date}"]`,
    );
    await returnedDayDialog.waitFor({ state: "visible", timeout: 30000 });
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
  assert.equal(
    await embedPage.locator("#ghCalendarReturn").isVisible(),
    false,
    "Embed mode exposed the timetable-return control",
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
    {
      label: "tablet-touch-820x1180",
      context: {
        viewport: { width: 820, height: 1180 },
        deviceScaleFactor: 2,
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
        for (let current = element; current instanceof HTMLElement; current = current.parentElement) {
          const style = getComputedStyle(current);
          if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) <= 0.01) return false;
          if (current === document.body) break;
        }
        const rect = element.getBoundingClientRect();
        return rect.width > 1 && rect.height > 1;
      };
      const trigger = document.querySelector("#ghWorkNoteTrigger");
      const calendarReturn = document.querySelector("#ghCalendarReturn");
      const brief = document.querySelector("#ghLiveBrief[data-gh-live-brief='bilingual']");
      const sound = [...document.querySelectorAll(
        '#sound, .sound, #soundToggle, #musicToggle, button[id*="sound" i], button[id*="music" i], button[id*="bgm" i]',
      )].find(isVisible);
      const triggerRect = trigger.getBoundingClientRect();
      const calendarReturnRect = calendarReturn.getBoundingClientRect();
      const briefRect = brief?.getBoundingClientRect();
      const soundRect = sound?.getBoundingClientRect();
      const overlapWidth = soundRect
        ? Math.max(0, Math.min(triggerRect.right, soundRect.right) - Math.max(triggerRect.left, soundRect.left))
        : 0;
      const overlapHeight = soundRect
        ? Math.max(0, Math.min(triggerRect.bottom, soundRect.bottom) - Math.max(triggerRect.top, soundRect.top))
        : 0;
      const viewportArea = innerWidth * innerHeight;
      const textBlocks = [...document.querySelectorAll(
        'h1,h2,h3,h4,h5,h6,p,span,div,label,legend,figcaption,li,a,button,aside,section',
      )].filter((el) => isVisible(el)
        && (el.innerText || "").trim().length > 0
        && !el.closest("#ghWorkNoteOverlay")
        && !el.closest("#ghLiveBrief")
        && el !== trigger
        && el !== calendarReturn
        && !el.contains(trigger)
        && !el.contains(calendarReturn)
        && !(sound && (el === sound || sound.contains(el) || el.contains(sound)))
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
      const briefOverlapWidth = briefRect
        ? Math.max(0, Math.min(triggerRect.right, briefRect.right) - Math.max(triggerRect.left, briefRect.left))
        : 0;
      const briefOverlapHeight = briefRect
        ? Math.max(0, Math.min(triggerRect.bottom, briefRect.bottom) - Math.max(triggerRect.top, briefRect.top))
        : 0;
      const briefSoundOverlapWidth = briefRect && soundRect
        ? Math.max(0, Math.min(soundRect.right, briefRect.right) - Math.max(soundRect.left, briefRect.left))
        : 0;
      const briefSoundOverlapHeight = briefRect && soundRect
        ? Math.max(0, Math.min(soundRect.bottom, briefRect.bottom) - Math.max(soundRect.top, briefRect.top))
        : 0;
      return {
        viewport: { width: innerWidth, height: innerHeight },
        horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        trigger: triggerRect.toJSON(),
        calendarReturn: calendarReturnRect.toJSON(),
        calendarReturnHref: calendarReturn.href,
        calendarReturnLayout: calendarReturn.dataset.ghControlLayout || "",
        calendarReturnOverlapArea: Math.max(
          0,
          Math.min(triggerRect.right, calendarReturnRect.right) - Math.max(triggerRect.left, calendarReturnRect.left),
        ) * Math.max(
          0,
          Math.min(triggerRect.bottom, calendarReturnRect.bottom) - Math.max(triggerRect.top, calendarReturnRect.top),
        ),
        calendarReturnNearTrigger: (
          Math.abs(calendarReturnRect.right - triggerRect.left) <= 12
          || Math.abs(calendarReturnRect.bottom - triggerRect.top) <= 12
        ),
        brief: briefRect ? briefRect.toJSON() : null,
        briefExpanded: brief?.querySelector(".gh-live-brief-toggle")?.getAttribute("aria-expanded"),
        briefSummaryZh: (brief?.querySelector("[data-gh-brief-section='summary'] [lang='zh-CN']")?.textContent || "").trim(),
        briefSummaryEn: (brief?.querySelector("[data-gh-brief-section='summary'] [lang='en']")?.textContent || "").trim(),
        briefInstructionsZh: (brief?.querySelector("[data-gh-brief-section='instructions'] [lang='zh-CN']")?.textContent || "").trim(),
        briefInstructionsEn: (brief?.querySelector("[data-gh-brief-section='instructions'] [lang='en']")?.textContent || "").trim(),
        briefTriggerOverlapArea: briefOverlapWidth * briefOverlapHeight,
        briefSoundOverlapArea: briefSoundOverlapWidth * briefSoundOverlapHeight,
        sound: soundRect ? soundRect.toJSON() : null,
        triggerLeftOfSound: Boolean(soundRect && triggerRect.right <= soundRect.left + 1),
        bottomAlignedWithSound: Boolean(soundRect && Math.abs(triggerRect.bottom - soundRect.bottom) <= 2),
        overlapArea: overlapWidth * overlapHeight,
        liftedAboveSound: Boolean(soundRect && triggerRect.bottom < soundRect.top),
        soundBottomRight,
        soundDocked: sound?.dataset.ghSoundMobileDocked === "true",
        noteLayout: trigger.dataset.ghControlLayout || "",
        noteContrastSafe: trigger.classList.contains("gh-work-note-trigger--contrast-safe"),
        compactConcealedCount: document.querySelectorAll('[data-gh-brief-covered="true"]').length,
        textOverlapCount,
        worstTextOverlap,
      };
    });
    assert.ok(geometry.horizontalOverflow <= 1, `${spec.label} horizontal overflow`);
    assert.ok(geometry.trigger.height >= 37.5, `${spec.label} trigger touch target`);
    assert.ok(geometry.brief, `${spec.label} bilingual brief missing`);
    assert.equal(geometry.briefExpanded, "true", `${spec.label} bilingual brief not expanded by default`);
    assert.ok(geometry.briefSummaryZh && geometry.briefSummaryEn, `${spec.label} bilingual summary missing`);
    assert.ok(geometry.briefInstructionsZh && geometry.briefInstructionsEn, `${spec.label} bilingual instructions missing`);
    assert.ok(geometry.brief.left >= 0 && geometry.brief.top >= 0, `${spec.label} bilingual brief offscreen`);
    assert.ok(geometry.brief.right <= geometry.viewport.width && geometry.brief.bottom <= geometry.viewport.height, `${spec.label} bilingual brief offscreen`);
    assert.equal(geometry.briefTriggerOverlapArea, 0, `${spec.label} bilingual brief overlaps work-note trigger`);
    assert.equal(geometry.briefSoundOverlapArea, 0, `${spec.label} bilingual brief overlaps sound control`);
    assert.ok(geometry.trigger.left >= 0 && geometry.trigger.top >= 0, `${spec.label} trigger offscreen`);
    assert.ok(geometry.trigger.right <= geometry.viewport.width && geometry.trigger.bottom <= geometry.viewport.height, `${spec.label} trigger offscreen`);
    assert.ok(geometry.calendarReturn.left >= 0 && geometry.calendarReturn.top >= 0, `${spec.label} timetable return offscreen`);
    assert.ok(geometry.calendarReturn.right <= geometry.viewport.width && geometry.calendarReturn.bottom <= geometry.viewport.height, `${spec.label} timetable return offscreen`);
    assert.equal(geometry.calendarReturnHref, new URL(`timetable/?date=${latest.date}`, siteUrl).href, `${spec.label} timetable return URL`);
    assert.equal(geometry.calendarReturnOverlapArea, 0, `${spec.label} timetable return overlaps work note`);
    assert.equal(geometry.calendarReturnNearTrigger, true, `${spec.label} timetable return is detached from work note`);
    assert.ok(geometry.sound, `${spec.label} sound control not visible`);
    assert.ok(geometry.sound.left >= 0 && geometry.sound.top >= 0, `${spec.label} sound control offscreen`);
    assert.ok(geometry.sound.right <= geometry.viewport.width && geometry.sound.bottom <= geometry.viewport.height, `${spec.label} sound control offscreen`);
    if (spec.touch) {
      assert.ok(geometry.trigger.width >= 43.5 && geometry.trigger.height >= 43.5, `${spec.label} work-note touch target`);
      assert.ok(geometry.calendarReturn.width >= 43.5 && geometry.calendarReturn.height >= 43.5, `${spec.label} timetable-return touch target`);
      assert.ok(geometry.sound.width >= 43.5 && geometry.sound.height >= 43.5, `${spec.label} sound touch target`);
    }
    if (geometry.soundBottomRight) {
      assert.ok(geometry.triggerLeftOfSound, `${spec.label} trigger is not left of the bottom-right sound control`);
    }
    assert.equal(geometry.overlapArea, 0, `${spec.label} controls overlap`);
    assert.equal(geometry.textOverlapCount, 0, `${spec.label} trigger overlaps ${geometry.textOverlapCount} visible text blocks (worst ${geometry.worstTextOverlap}px²)`);
    const briefToggle = page.locator("#ghLiveBrief .gh-live-brief-toggle");
    if (spec.label === "short-touch-421x386") {
      assert.ok(geometry.compactConcealedCount > 0, `${spec.label} did not simplify redundant native chrome`);
    }
    if (spec.touch) await briefToggle.tap();
    else await briefToggle.click();
    assert.equal(await briefToggle.getAttribute("aria-expanded"), "false", `${spec.label} bilingual brief did not collapse`);
    assert.equal(
      await page.locator('[data-gh-brief-covered="true"]').count(),
      0,
      `${spec.label} native chrome was not restored after collapsing the bilingual brief`,
    );
    if (spec.touch) await briefToggle.tap();
    else await briefToggle.click();
    assert.equal(await briefToggle.getAttribute("aria-expanded"), "true", `${spec.label} bilingual brief did not expand`);
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

  const touchDockDay = days.find((day) => day.date === "2026-07-11");
  assert.ok(touchDockDay, "Expected the dense shortcut artwork to remain declared");
  const touchDockPaths = archivePaths(touchDockDay);
  const touchDockResults = [];
  for (const spec of viewportSpecs.filter(({ label }) => label.includes("short-touch") || label.includes("tablet-touch"))) {
    const context = await browser.newContext(spec.context);
    const page = await context.newPage();
    const url = new URL(touchDockPaths.liveUrl);
    url.searchParams.set("embed", "calendar");
    url.searchParams.set("gh_channel", "touch_dock_audit_2026_x");
    await page.goto(url.href, { waitUntil: "domcontentloaded" });
    const dock = page.locator("#ghTouchKeyDock");
    await dock.waitFor({ state: "visible" });
    const geometry = await dock.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      const keys = [...element.querySelectorAll(".gh-touch-key")].map((button) => {
        const keyRect = button.getBoundingClientRect();
        return { label: button.dataset.ghKeyLabel, width: keyRect.width, height: keyRect.height };
      });
      const row = element.querySelector(".gh-touch-keys");
      return {
        viewport: { width: innerWidth, height: innerHeight },
        rect: rect.toJSON(),
        keys,
        flexWrap: getComputedStyle(row).flexWrap,
        scrollWidth: row.scrollWidth,
        clientWidth: row.clientWidth,
        horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    assert.equal(geometry.keys.length, 9, `${spec.label} dense touch dock key count`);
    geometry.keys.forEach((key) => {
      assert.ok(key.width >= 43.5 && key.height >= 43.5, `${spec.label} dock key ${key.label} is undersized`);
    });
    assert.ok(geometry.rect.left >= 0 && geometry.rect.top >= 0, `${spec.label} touch dock offscreen`);
    assert.ok(geometry.rect.right <= geometry.viewport.width && geometry.rect.bottom <= geometry.viewport.height, `${spec.label} touch dock offscreen`);
    assert.ok(geometry.horizontalOverflow <= 1, `${spec.label} embed horizontal overflow`);
    if (spec.label.includes("short-touch")) {
      assert.equal(geometry.flexWrap, "nowrap", `${spec.label} touch dock did not become one row`);
      assert.ok(geometry.scrollWidth > geometry.clientWidth, `${spec.label} dense touch dock is not horizontally scrollable`);
    }
    await page.evaluate(() => {
      window.__ghDockAudit = [];
      addEventListener("keydown", (event) => window.__ghDockAudit.push([event.type, event.key, event.code]), true);
      addEventListener("keyup", (event) => window.__ghDockAudit.push([event.type, event.key, event.code]), true);
    });
    await dock.locator(".gh-touch-key").first().tap();
    assert.deepEqual(
      await page.evaluate(() => window.__ghDockAudit),
      [["keydown", "1", "Digit1"], ["keyup", "1", "Digit1"]],
      `${spec.label} dock touch did not dispatch the original shortcut pair`,
    );
    touchDockResults.push({ label: spec.label, ...geometry });
    await context.close();
  }

  console.log(JSON.stringify({
    passed: true,
    declaredExplanationPages: days.length,
    browserCheckedDates: directResults,
    latestOverlayDate: latest.date,
    embedHidden: true,
    viewportResults,
    touchDockResults,
    pageErrors: 0,
    sameOriginHttpFailures: 0,
  }, null, 2));
} finally {
  await browser.close();
}
