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
const expectedCount = 78;
const failures = [];
const results = [];

assert.equal(days.length, expectedCount, `Expected ${expectedCount} declared public days`);

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
try {
  const corpusContext = await browser.newContext({
    viewport: { width: 1280, height: 720 },
  });

  async function inspectDirectPage(day) {
    const paths = archivePaths(day);
    const page = await corpusContext.newPage();
    const health = trackPageHealth(page, day.date);
    try {
      const directUrl = new URL(paths.liveUrl);
      directUrl.searchParams.set("qa", "work-note-corpus");
      const response = await page.goto(directUrl.href, {
        waitUntil: "domcontentloaded",
        timeout: 45000,
      });
      assert.equal(response?.status(), 200, `${day.date} HTTP ${response?.status()}`);
      await page.locator(".gh-work-note-link").waitFor({
        state: "visible",
        // A few WebGL-heavy works can delay the appended navigation link when
        // several pages initialize concurrently. The link is injected by the
        // shared importer and is healthy in isolation; give the corpus check a
        // realistic startup budget instead of treating CPU contention as loss.
        timeout: 20000,
      });
      const state = await page.evaluate(visibleFn => {
        const isVisible = new Function("element", `return (${visibleFn})(element);`);
        const links = [...document.querySelectorAll(".gh-work-note-link")];
        return {
          count: links.length,
          visibleCount: links.filter(isVisible).length,
          text: links[0]?.textContent,
          hrefAttribute: links[0]?.getAttribute("href"),
          resolvedHref: links[0]?.href,
          ariaLabel: links[0]?.getAttribute("aria-label"),
        };
      }, visible.toString());
      assert.deepEqual(
        {
          count: state.count,
          visibleCount: state.visibleCount,
          text: state.text,
          hrefAttribute: state.hrefAttribute,
          resolvedHref: state.resolvedHref,
          ariaLabel: state.ariaLabel,
        },
        {
          count: 1,
          visibleCount: 1,
          text: "Work note / 作品说明",
          hrefAttribute: "../",
          resolvedHref: paths.explanationUrl,
          ariaLabel: "Open the artwork intention and context note / 打开作品发心与创作语境说明",
        },
        `${day.date} work-note contract`,
      );
      health.assertHealthy();
      return day.date;
    } finally {
      await page.close();
    }
  }

  const concurrency = 3;
  for (let index = 0; index < days.length; index += concurrency) {
    const batch = days.slice(index, index + concurrency);
    const settled = await Promise.allSettled(batch.map(inspectDirectPage));
    settled.forEach((result, batchIndex) => {
      if (result.status === "fulfilled") results.push(result.value);
      else failures.push(`${batch[batchIndex].date}: ${result.reason.message}`);
    });
  }
  await corpusContext.close();

  if (failures.length) {
    throw new Error(
      `Work-note corpus failures (${failures.length}):\n- ${failures.join("\n- ")}`,
    );
  }
  assert.equal(results.length, expectedCount);

  const latest = days.at(-1);
  const latestPaths = archivePaths(latest);

  const clickContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const clickPage = await clickContext.newPage();
  const clickHealth = trackPageHealth(clickPage, `${latest.date} click`);
  const clickUrl = new URL(latestPaths.liveUrl);
  clickUrl.searchParams.set("from", "timetable");
  clickUrl.searchParams.set("qa", "work-note-click");
  await clickPage.goto(clickUrl.href, { waitUntil: "domcontentloaded" });
  await clickPage.locator(".gh-work-note-link").click();
  await clickPage.waitForURL(latestPaths.explanationUrl);
  await clickPage.getByRole("heading", { name: "Intention", exact: true }).waitFor();
  await clickPage.getByRole("heading", { name: "发心", exact: true }).waitFor();
  await clickPage.getByRole("heading", { name: "Creative Rationale", exact: true }).waitFor();
  await clickPage.getByRole("heading", { name: "创作缘由", exact: true }).waitFor();
  clickHealth.assertHealthy();
  await clickContext.close();

  const embedContext = await browser.newContext({
    viewport: { width: 960, height: 540 },
  });
  const embedPage = await embedContext.newPage();
  const embedHealth = trackPageHealth(embedPage, `${latest.date} embed`);
  const embedUrl = new URL(latestPaths.liveUrl);
  embedUrl.searchParams.set("embed", "calendar");
  embedUrl.searchParams.set("qa", "work-note-embed");
  await embedPage.goto(embedUrl.href, { waitUntil: "domcontentloaded" });
  await embedPage.waitForFunction(() => document.body.classList.contains("gh-chamber-embed"));
  assert.equal(
    await embedPage.locator(".gh-work-note-link").count(),
    0,
    "Embed mode exposed the work-note link",
  );
  embedHealth.assertHealthy();
  await embedContext.close();

  const viewportSpecs = [
    {
      label: "desktop-1440x900",
      context: { viewport: { width: 1440, height: 900 } },
      touch: false,
    },
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
    url.searchParams.set("from", "timetable");
    url.searchParams.set("qa", spec.label);
    await page.goto(url.href, { waitUntil: "domcontentloaded" });
    const note = page.locator(".gh-work-note-link");
    const fold = page.locator(".gh-fold-toggle");
    await note.waitFor({ state: "visible" });
    await fold.waitFor({ state: "visible" });
    if (spec.touch) await fold.tap();
    else await fold.click();
    await page.waitForFunction(() => document.body.classList.contains("gh-text-folded"));
    assert.ok(await note.isVisible(), `${spec.label} folded overlays hid the work-note link`);

    const geometry = await page.evaluate(() => {
      const noteRect = document.querySelector(".gh-work-note-link").getBoundingClientRect();
      const foldRect = document.querySelector(".gh-fold-toggle").getBoundingClientRect();
      const overlapWidth = Math.max(
        0,
        Math.min(noteRect.right, foldRect.right) - Math.max(noteRect.left, foldRect.left),
      );
      const overlapHeight = Math.max(
        0,
        Math.min(noteRect.bottom, foldRect.bottom) - Math.max(noteRect.top, foldRect.top),
      );
      return {
        viewport: { width: innerWidth, height: innerHeight },
        horizontalOverflow:
          document.documentElement.scrollWidth - document.documentElement.clientWidth,
        note: noteRect.toJSON(),
        fold: foldRect.toJSON(),
        overlapArea: overlapWidth * overlapHeight,
      };
    });
    assert.ok(
      geometry.horizontalOverflow <= 1,
      `${spec.label} horizontal overflow ${geometry.horizontalOverflow}`,
    );
    assert.ok(geometry.note.height >= 40, `${spec.label} touch target ${geometry.note.height}px`);
    assert.ok(
      geometry.note.left >= 0
        && geometry.note.top >= 0
        && geometry.note.right <= geometry.viewport.width
        && geometry.note.bottom <= geometry.viewport.height,
      `${spec.label} link outside viewport: ${JSON.stringify(geometry)}`,
    );
    assert.ok(
      geometry.fold.left >= 0
        && geometry.fold.top >= 0
        && geometry.fold.right <= geometry.viewport.width
        && geometry.fold.bottom <= geometry.viewport.height,
      `${spec.label} fold toggle outside viewport: ${JSON.stringify(geometry)}`,
    );
    assert.equal(
      geometry.overlapArea,
      0,
      `${spec.label} work-note link collides with fold toggle`,
    );
    health.assertHealthy();
    viewportResults.push({ label: spec.label, ...geometry });
    await context.close();
  }

  console.log(JSON.stringify({
    passed: true,
    siteUrl: siteUrl.href,
    declaredExplanationPages: expectedCount,
    directLiveWorkNoteLinks: results.length,
    latestClickDestination: latestPaths.explanationUrl,
    latestExplanationHeadings: [
      "Intention",
      "发心",
      "Creative Rationale",
      "创作缘由",
    ],
    embedHidden: true,
    viewportResults,
    pageErrors: 0,
    sameOriginHttpFailures: 0,
  }, null, 2));
} finally {
  await browser.close();
}
