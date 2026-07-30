#!/usr/bin/env node
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import {
  mkdir,
  readFile,
  rm,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8892/timetable/";
const targetDates = ["2026-07-21", "2026-07-22"];
const syntheticPrivateFixtures = ["Mara Evergarden", "Orchid Lantern", "CNY 938,271.44"];
const viewports = [
  { width: 1440, height: 900, label: "desktop-wide", touch: false, screenshot: true },
  { width: 1024, height: 768, label: "desktop-compact", touch: false, screenshot: false },
  { width: 768, height: 700, label: "tablet", touch: false, screenshot: false },
  { width: 390, height: 844, label: "mobile", touch: true, screenshot: true },
  { width: 421, height: 386, label: "short-touch", touch: true, screenshot: true },
];
const screenshotRoot = new URL("../audits/public-readable-hierarchy/", import.meta.url);
const segmentManifestPath = new URL("screenshot-segments.json", screenshotRoot);
const pulseSnapshot = JSON.parse(
  await readFile(new URL("../metadata/timetable-pulses.json", import.meta.url), "utf8"),
);
const publicPulseCountByDate = new Map(pulseSnapshot.days.map((day) => [
  day.date,
  day.pulses.filter((pulse) => (
    pulse.category !== "daily_reminder"
    || (
      pulse.disclosure_policy === "authentic_entity_masked_reminder_v2"
      && pulse.disclosure_authorization === "explicit_user_authorization_2026-07-29"
      && ["self", "self_scheduler_residue"].includes(pulse.owner_scope)
      && ["explicit_user_authorization", "explicit_import_authorization"].includes(
        pulse.ownership_provenance,
      )
    )
  )).length,
]));
const redactedReminderCountByDate = new Map(pulseSnapshot.days.map((day) => [
  day.date,
  day.pulses.filter((pulse) => (
    pulse.category === "daily_reminder"
    && pulse.disclosure_policy === "authentic_entity_masked_reminder_v2"
    && pulse.redaction_count > 0
  )).length,
]));
await mkdir(screenshotRoot, { recursive: true });
const screenshotSegments = [
  ["morning", 8 * 60],
  ["midday", 12 * 60],
  ["close", 15 * 60],
  ["evening", 21 * 60],
];
const screenshotViewports = viewports.filter((viewport) => viewport.screenshot);

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function minutes(value) {
  const [hour, minute] = String(value).split(":").map(Number);
  return hour * 60 + minute;
}

function minuteLabel(value) {
  const bounded = Math.max(0, Math.min(24 * 60, Math.round(value)));
  const hour = Math.floor(bounded / 60);
  const minute = bounded % 60;
  return `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`;
}

function rangesOverlap(leftStart, leftEnd, rightStart, rightEnd, tolerance = 0.5) {
  return leftStart < rightEnd - tolerance && rightStart < leftEnd - tolerance;
}

async function removeMisleadingLegacyCaptures() {
  for (const date of targetDates) {
    for (const viewport of screenshotViewports) {
      for (const suffix of ["full-day", null]) {
        const fileName = suffix
          ? `${date}-${viewport.label}-${suffix}.png`
          : `${date}-${viewport.label}.png`;
        await rm(new URL(fileName, screenshotRoot), { force: true });
      }
    }
  }
}

async function scrollDialogToMinute(page, targetMinute) {
  const requested = await page.locator("#dayDialogPanel").evaluate(
    (panel, minuteTarget) => {
      const timeline = panel.querySelector(".timeline-list");
      const toolbar = panel.querySelector(".dialog-toolbar");
      if (!timeline || !toolbar) throw new Error("day dialog timeline scroll structure missing");
      const panelRect = panel.getBoundingClientRect();
      const timelineRect = timeline.getBoundingClientRect();
      const toolbarRect = toolbar.getBoundingClientRect();
      const minuteHeight = Number.parseFloat(
        getComputedStyle(timeline).getPropertyValue("--minute-height"),
      );
      const overflowY = getComputedStyle(panel).overflowY;
      const timelineContentTop = timelineRect.top - panelRect.top + panel.scrollTop;
      const visibleContentHeight = panel.clientHeight - toolbarRect.height;
      const desiredScrollTop = timelineContentTop
        + minuteTarget * minuteHeight
        - toolbarRect.height
        - visibleContentHeight / 2;
      const maximumScrollTop = panel.scrollHeight - panel.clientHeight;
      const clampedScrollTop = Math.max(0, Math.min(maximumScrollTop, desiredScrollTop));
      panel.scrollTop = clampedScrollTop;
      return {
        scrollRoot: "#dayDialogPanel",
        overflowY,
        requestedScrollTop: clampedScrollTop,
        maximumScrollTop,
        minuteHeight,
      };
    },
    targetMinute,
  );
  await page.waitForFunction(
    ({ requestedScrollTop }) => {
      const panel = document.querySelector("#dayDialogPanel");
      return panel && Math.abs(panel.scrollTop - requestedScrollTop) <= 1;
    },
    requested,
  );
  await page.evaluate(() => new Promise((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(resolve));
  }));
  const actual = await page.locator("#dayDialogPanel").evaluate(
    (panel, minuteTarget) => {
      const timeline = panel.querySelector(".timeline-list");
      const toolbar = panel.querySelector(".dialog-toolbar");
      const panelRect = panel.getBoundingClientRect();
      const timelineRect = timeline.getBoundingClientRect();
      const toolbarRect = toolbar.getBoundingClientRect();
      const minuteHeight = Number.parseFloat(
        getComputedStyle(timeline).getPropertyValue("--minute-height"),
      );
      const visiblePixelTop = Math.max(
        timelineRect.top,
        panelRect.top,
        toolbarRect.bottom,
      );
      const visiblePixelBottom = Math.min(timelineRect.bottom, panelRect.bottom);
      const visibleStartMinute = Math.max(
        0,
        (visiblePixelTop - timelineRect.top) / minuteHeight,
      );
      const visibleEndMinute = Math.min(
        24 * 60,
        (visiblePixelBottom - timelineRect.top) / minuteHeight,
      );
      return {
        scrollRoot: "#dayDialogPanel",
        overflowY: getComputedStyle(panel).overflowY,
        scrollTop: panel.scrollTop,
        maximumScrollTop: panel.scrollHeight - panel.clientHeight,
        clientHeight: panel.clientHeight,
        scrollHeight: panel.scrollHeight,
        minuteHeight,
        visibleStartMinute,
        visibleEndMinute,
        targetMinute: minuteTarget,
        targetVisible:
          minuteTarget >= visibleStartMinute - 0.5
          && minuteTarget <= visibleEndMinute + 0.5,
      };
    },
    targetMinute,
  );
  assert.ok(
    ["auto", "scroll"].includes(actual.overflowY),
    `day dialog is not the vertical scroll root: ${JSON.stringify(actual)}`,
  );
  assert.ok(
    actual.scrollHeight > actual.clientHeight,
    `day dialog does not expose internal scrolling: ${JSON.stringify(actual)}`,
  );
  assert.ok(
    Math.abs(actual.scrollTop - requested.requestedScrollTop) <= 1,
    `day dialog did not reach requested scrollTop: ${JSON.stringify({ requested, actual })}`,
  );
  assert.ok(
    actual.visibleStartMinute < actual.visibleEndMinute,
    `visible minute bounds are empty: ${JSON.stringify(actual)}`,
  );
  assert.ok(
    actual.targetVisible,
    `target minute is outside visible bounds: ${JSON.stringify(actual)}`,
  );
  return actual;
}

async function prepareCleanNonHoverCapture(page, label) {
  const neutral = page.locator(".dialog-toolbar:visible").first();
  const box = await neutral.boundingBox();
  assert.ok(box, `${label}: neutral dialog chrome is unavailable`);
  await page.mouse.move(box.x + Math.min(8, box.width / 2), box.y + 4);
  await page.evaluate(() => {
    document.querySelectorAll(".event-reading-card:focus").forEach((card) => card.blur());
  });
  await page.waitForFunction(() => {
    const lens = document.querySelector("#inspectionLens");
    return lens
      && lens.hidden
      && lens.getAttribute("aria-hidden") === "true"
      && !lens.classList.contains("is-visible")
      && !lens.dataset.readingId
      && !lens.dataset.mediaKind;
  });
  const lens = await page.locator("#inspectionLens").evaluate((element) => ({
    hidden: element.hidden,
    visible: element.classList.contains("is-visible")
      && Number(getComputedStyle(element).opacity) > 0,
    readingId: element.dataset.readingId || "",
    mediaKind: element.dataset.mediaKind || "",
  }));
  assert.deepEqual(
    lens,
    { hidden: true, visible: false, readingId: "", mediaKind: "" },
    `${label}: unintended inspection lens contaminated hierarchy evidence`,
  );
  return lens;
}

async function inspect(page) {
  return page.evaluate((privateFixtures) => {
    const timeline = document.querySelector(".timeline-list");
    const timelineRect = timeline.getBoundingClientRect();
    const eventsLayer = timeline.querySelector(".timeline-events-layer");
    const eventsRect = eventsLayer.getBoundingClientRect();
    const minuteHeight = Number.parseFloat(getComputedStyle(timeline).getPropertyValue("--minute-height"));
    const events = [...timeline.querySelectorAll(".timeline-event")].map((event) => {
      const rect = event.getBoundingClientRect();
      return {
        footprintId: event.dataset.footprintId,
        start: event.dataset.start,
        duration: Number(event.dataset.durationMinutes),
        top: rect.top - eventsRect.top,
        height: rect.height,
      };
    });
    const cards = [...timeline.querySelectorAll(".event-reading-card")].map((card) => {
      const rect = card.getBoundingClientRect();
      const style = getComputedStyle(card);
      return {
        readingId: card.dataset.readingId,
        layer: card.dataset.layer,
        left: rect.left,
        right: rect.right,
        top: rect.top - timelineRect.top,
        bottom: rect.bottom - timelineRect.top,
        opacity: Number(style.opacity),
        zIndex: Number(style.zIndex),
        borderColor: style.borderColor,
        boxShadow: style.boxShadow,
        label: card.querySelector(".reading-title")?.textContent?.trim() || "",
        summary: card.querySelector(".reading-summary")?.textContent?.trim() || "",
        titleMetrics: (() => {
          const title = card.querySelector(".reading-title");
          if (!title) return null;
          const titleRect = title.getBoundingClientRect();
          return {
            clientHeight: title.clientHeight,
            scrollHeight: title.scrollHeight,
            clientWidth: title.clientWidth,
            scrollWidth: title.scrollWidth,
            top: titleRect.top,
            bottom: titleRect.bottom,
            clamp: getComputedStyle(title).webkitLineClamp,
          };
        })(),
        summaryMetrics: (() => {
          const summary = card.querySelector(".reading-summary");
          if (!summary) return null;
          const summaryRect = summary.getBoundingClientRect();
          const summaryStyle = getComputedStyle(summary);
          return {
            clientHeight: summary.clientHeight,
            scrollHeight: summary.scrollHeight,
            top: summaryRect.top,
            bottom: summaryRect.bottom,
            lineHeight: Number.parseFloat(summaryStyle.lineHeight),
            clamp: summaryStyle.webkitLineClamp,
            overflow: summaryStyle.overflow,
          };
        })(),
        cardTop: rect.top,
        cardBottom: rect.bottom,
        cardClientHeight: card.clientHeight,
        cardScrollHeight: card.scrollHeight,
      };
    });
    const documentMarkup = document.documentElement.outerHTML;
    const visibleText = document.body.innerText;
    const accessibleSurface = [...document.querySelectorAll("*")]
      .flatMap((element) => [
        element.getAttribute("aria-label"),
        element.getAttribute("aria-description"),
        element.getAttribute("title"),
        element.getAttribute("alt"),
      ])
      .filter(Boolean)
      .join("\n");
    return {
      minuteHeight,
      timelineHeight: timelineRect.height,
      events,
      cards,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      vagueTitles: cards
        .map((card) => card.label)
        .filter((label) => /^(后台例行任务|系统例行任务|静默检查|Background routine|System routine|Silent check)$/i.test(label)),
      redactionBlocks: [...timeline.querySelectorAll(".redaction-block")].map((block) => block.textContent),
      privateFixtureMatches: privateFixtures.filter(
        (fixture) => documentMarkup.includes(fixture)
          || visibleText.includes(fixture)
          || accessibleSurface.includes(fixture),
      ),
    };
  }, syntheticPrivateFixtures);
}

const results = [];
const screenshots = [];
const segmentManifest = {
  schema: "timetable-screenshot-segments-v1",
  passed: false,
  baseUrl,
  scrollRoot: "#dayDialogPanel",
  misleadingFullDayCapturesRemoved: true,
  segmentTargets: screenshotSegments.map(([label, targetMinute]) => ({
    label,
    targetMinute,
    targetTime: minuteLabel(targetMinute),
  })),
  screenshots,
  errors: [],
};
let browser = null;
let failure = null;
try {
  await removeMisleadingLegacyCaptures();
  browser = await chromium.launch({ headless: true });
  for (const date of targetDates) {
    const day = new Map(timetableData.days.map((entry) => [entry.date, entry])).get(date);
    assert.ok(day, `${date}: missing day`);
    assert.equal(
      day.background_pulses.length,
      publicPulseCountByDate.get(date),
      `${date}: projected source windows changed`,
    );
    assert.equal(
      new Set(day.timeline_events.map((event) => event.footprint_id)).size,
      day.timeline_events.length,
      `${date}: footprint IDs are not one-to-one`,
    );
    const climate = day.reading_items.filter((item) => item.classification === "climate_aggregate");
    assert.ok(climate.length > 0, `${date}: missing climate groups`);
    assert.ok(
      climate.length < climate.reduce((count, item) => count + item.source_refs.length, 0),
      `${date}: climate layer was not aggregated`,
    );
    assert.ok(day.reading_items.length < day.timeline_events.length, `${date}: reading layer was not reduced`);

    for (const viewport of viewports) {
      const context = await browser.newContext({
        viewport: { width: viewport.width, height: viewport.height },
        isMobile: viewport.touch,
        hasTouch: viewport.touch,
        deviceScaleFactor: viewport.touch ? 2 : 1,
      });
      const page = await context.newPage();
      const pageErrors = [];
      page.on("pageerror", (error) => pageErrors.push(error.message));
      await page.goto(baseUrl, { waitUntil: "networkidle" });
      await page.locator(`.calendar-day-button[data-date="${date}"]`).click();
      await page.waitForSelector("#dayDialog.is-open");
      await page.waitForFunction(
        () => document.querySelector(".timeline-reading-layer.is-placed")
          && document.querySelectorAll(".event-reading-card").length > 0,
      );

      const state = await inspect(page);
      assert.deepEqual(pageErrors, [], `${date}/${viewport.label}: page errors`);
      assert.equal(state.events.length, day.timeline_events.length, `${date}/${viewport.label}: footprints`);
      assert.equal(state.cards.length, day.reading_items.length, `${date}/${viewport.label}: reading projection`);
      assert.ok(state.overflow <= 1, `${date}/${viewport.label}: horizontal overflow ${state.overflow}`);
      assert.deepEqual(state.vagueTitles, [], `${date}/${viewport.label}: vague titles`);
      if (redactedReminderCountByDate.get(date) > 0) {
        assert.ok(
          state.redactionBlocks.length > 0,
          `${date}/${viewport.label}: missing fixed redaction blocks`,
        );
      }
      assert.ok(
        state.redactionBlocks.every((block) => block === "████"),
        `${date}/${viewport.label}: bars encode source length`,
      );
      assert.deepEqual(
        state.privateFixtureMatches,
        [],
        `${date}/${viewport.label}: synthetic private fixture reached DOM or accessible attributes`,
      );

      for (const event of state.events) {
        assert.ok(
          Math.abs(event.top - minutes(event.start) * state.minuteHeight) <= 0.3,
          `${date}/${viewport.label}: exact top ${JSON.stringify(event)}`,
        );
        assert.ok(
          Math.abs(event.height - event.duration * state.minuteHeight) <= 0.3,
          `${date}/${viewport.label}: exact height ${JSON.stringify(event)}`,
        );
      }
      for (const card of state.cards) {
        assert.ok(card.label.includes("/"), `${date}/${viewport.label}: bilingual label ${JSON.stringify(card)}`);
        assert.ok(card.summary.length > 0, `${date}/${viewport.label}: empty summary`);
        assert.ok(
          card.top >= -0.5 && card.bottom <= state.timelineHeight + 0.5,
          `${date}/${viewport.label}: reading item outside canvas ${JSON.stringify(card)}`,
        );
        if (["event", "absence", "climate"].includes(card.layer)) {
          assert.ok(card.titleMetrics, `${date}/${viewport.label}: missing title metrics`);
          assert.ok(
            card.titleMetrics.scrollHeight <= card.titleMetrics.clientHeight + 1
              && card.titleMetrics.scrollWidth <= card.titleMetrics.clientWidth + 1,
            `${date}/${viewport.label}: materially truncated title ${JSON.stringify(card)}`,
          );
          assert.ok(card.summaryMetrics, `${date}/${viewport.label}: missing summary metrics`);
          const summaryIsClamped = card.summaryMetrics.scrollHeight
            > card.summaryMetrics.clientHeight + 1;
          if (summaryIsClamped) {
            assert.ok(
              card.summaryMetrics.clientHeight
                >= card.summaryMetrics.lineHeight * 3.5,
              `${date}/${viewport.label}: clamped brief exposes fewer than four lines ${JSON.stringify(card)}`,
            );
            assert.equal(
              card.summaryMetrics.overflow,
              "hidden",
              `${date}/${viewport.label}: clamped brief overflow contract`,
            );
          }
          assert.ok(
            card.titleMetrics.top >= card.cardTop - 1
              && card.titleMetrics.bottom <= card.cardBottom + 1
              && card.summaryMetrics.top >= card.cardTop - 1
              && card.summaryMetrics.bottom <= card.cardBottom + 1,
            `${date}/${viewport.label}: title or brief escapes card ${JSON.stringify(card)}`,
          );
        }
      }
      for (let leftIndex = 0; leftIndex < state.cards.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < state.cards.length; rightIndex += 1) {
          const left = state.cards[leftIndex];
          const right = state.cards[rightIndex];
          assert.ok(
            !rangesOverlap(left.left, left.right, right.left, right.right)
              || !rangesOverlap(left.top, left.bottom, right.top, right.bottom),
            `${date}/${viewport.label}: reading collision ${JSON.stringify({ left, right })}`,
          );
        }
      }

      const climateCards = state.cards.filter((card) => card.layer === "climate");
      const foregroundCards = state.cards.filter((card) => ["event", "absence", "beacon"].includes(card.layer));
      assert.ok(climateCards.length > 0 && foregroundCards.length > 0);
      assert.ok(
        climateCards.every((card) => card.opacity >= 0.999),
        `${date}/${viewport.label}: climate text is weakened by parent opacity`,
      );
      assert.ok(
        Math.max(...climateCards.map((card) => card.zIndex))
          < Math.min(...foregroundCards.map((card) => card.zIndex)),
        `${date}/${viewport.label}: climate stacking outranks foreground`,
      );

      if (viewport.screenshot) {
        const viewportSegments = [];
        for (const [segment, targetMinute] of screenshotSegments) {
          const scrollState = await scrollDialogToMinute(page, targetMinute);
          const lensCleanState = await prepareCleanNonHoverCapture(
            page,
            `${date}/${viewport.label}/${segment}`,
          );
          const segmentPath = new URL(
            `${date}-${viewport.label}-${segment}.png`,
            screenshotRoot,
          );
          const imageBytes = await page.screenshot({
            path: segmentPath.pathname,
            fullPage: false,
            animations: "disabled",
          });
          const imageSha256 = sha256(imageBytes);
          const comparisons = viewportSegments.map((previous) => {
            const scrollDeltaPx = Math.abs(scrollState.scrollTop - previous.actualScrollTop);
            const requiredScrollDeltaPx = Math.min(
              80,
              Math.max(
                24,
                Math.abs(targetMinute - previous.targetMinute)
                  * scrollState.minuteHeight
                  * 0.2,
              ),
            );
            const differentImageHash = imageSha256 !== previous.imageSha256;
            assert.ok(
              scrollDeltaPx >= requiredScrollDeltaPx,
              `${date}/${viewport.label}/${segment}: near-duplicate scroll position ${JSON.stringify({
                previous: previous.segment,
                scrollDeltaPx,
                requiredScrollDeltaPx,
              })}`,
            );
            assert.ok(
              differentImageHash,
              `${date}/${viewport.label}/${segment}: duplicate screenshot hash`,
            );
            return {
              comparedWith: previous.segment,
              scrollDeltaPx,
              requiredScrollDeltaPx,
              differentImageHash,
              rejectedAsDuplicate: false,
            };
          });
          const segmentEvidence = {
            date,
            viewport: {
              label: viewport.label,
              width: viewport.width,
              height: viewport.height,
              deviceScaleFactor: viewport.touch ? 2 : 1,
            },
            segment,
            targetMinute,
            targetTime: minuteLabel(targetMinute),
            scrollRoot: scrollState.scrollRoot,
            actualScrollTop: scrollState.scrollTop,
            maximumScrollTop: scrollState.maximumScrollTop,
            visibleMinuteRange: {
              start: scrollState.visibleStartMinute,
              end: scrollState.visibleEndMinute,
              startTime: minuteLabel(scrollState.visibleStartMinute),
              endTime: minuteLabel(scrollState.visibleEndMinute),
            },
            targetVisible: scrollState.targetVisible,
            image: path.basename(segmentPath.pathname),
            imageBytes: imageBytes.length,
            imageSha256,
            inspectionLens: {
              intended: false,
              cleanState: lensCleanState,
            },
            duplicateRejection: {
              passed: true,
              method: "minimum scroll-position delta plus exact image SHA-256 uniqueness",
              comparisons,
            },
          };
          viewportSegments.push(segmentEvidence);
          screenshots.push(segmentEvidence);
        }
        assert.equal(
          new Set(viewportSegments.map((entry) => entry.imageSha256)).size,
          screenshotSegments.length,
          `${date}/${viewport.label}: segment image hashes are not unique`,
        );
        assert.ok(
          viewportSegments.find((entry) => entry.segment === "evening")
            .visibleMinuteRange.end >= 21 * 60,
          `${date}/${viewport.label}: later-day evidence does not reach 21:00`,
        );
      }

      const climateCard = page.locator(".climate-reading-card").first();
      await climateCard.scrollIntoViewIfNeeded();
      const expectedMembers = Number(await climateCard.getAttribute("data-member-count"));
      assert.ok(expectedMembers >= 1);
      if (viewport.touch) {
        await climateCard.tap();
        assert.equal(await climateCard.getAttribute("aria-pressed"), "true");
        assert.equal(await climateCard.getAttribute("aria-expanded"), null);
        assert.equal(
          await page.locator(".timeline-event.is-linked-active").count(),
          expectedMembers,
          `${date}/${viewport.label}: group touch highlight`,
        );
        await climateCard.tap();
      } else {
        await climateCard.hover();
        assert.equal(
          await page.locator(".timeline-event.is-linked-active").count(),
          expectedMembers,
          `${date}/${viewport.label}: group hover highlight`,
        );
        await climateCard.focus();
        await page.keyboard.press("Enter");
      }
      await page.waitForSelector("#taskDialog.is-open");
      assert.equal(
        await page.locator("#taskDetailOccurrences .task-occurrence").count(),
        expectedMembers,
        `${date}/${viewport.label}: constituent drill-down`,
      );
      await page.keyboard.press("Escape");
      assert.equal(
        await climateCard.evaluate((card) => document.activeElement === card),
        true,
        `${date}/${viewport.label}: drill-down focus restoration`,
      );

      results.push({
        date,
        viewport: viewport.label,
        footprints: state.events.length,
        readingItems: state.cards.length,
        climateItems: climateCards.length,
      });
      await context.close();
    }
  }
  segmentManifest.passed = true;
  segmentManifest.results = results;
} catch (error) {
  failure = error;
  segmentManifest.errors.push(error instanceof Error ? error.message : String(error));
} finally {
  if (browser) await browser.close();
  await writeFile(
    segmentManifestPath,
    `${JSON.stringify(segmentManifest, null, 2)}\n`,
    "utf8",
  );
}

console.log(JSON.stringify({
  passed: segmentManifest.passed,
  screenshotRoot: screenshotRoot.pathname,
  segmentManifest: segmentManifestPath.pathname,
  screenshots: screenshots.map((entry) => path.join(screenshotRoot.pathname, entry.image)),
  results,
}, null, 2));
if (failure) throw failure;
