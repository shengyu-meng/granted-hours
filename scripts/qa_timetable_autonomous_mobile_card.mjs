#!/usr/bin/env node
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8895/timetable/";
const screenshotRoot = process.env.QA_SCREENSHOT_DIR || "";
const screenshotPhase = process.env.QA_SCREENSHOT_PHASE || "qa";
const regressionDate = "2026-07-17";
const latestDate = [...timetableData.days].map((day) => day.date).sort().at(-1);
const cases = [
  { date: "2026-07-11", width: 1440, height: 900, label: "2026-07-11-desktop-overlap-regression", compact: false, touch: false },
  { date: regressionDate, width: 390, height: 844, label: "2026-07-17-mobile", compact: true, touch: true },
  { date: latestDate, width: 390, height: 844, label: "latest-mobile", compact: true, touch: true },
  { date: regressionDate, width: 421, height: 386, label: "2026-07-17-short-touch", compact: true, touch: true },
  { date: regressionDate, width: 320, height: 700, label: "2026-07-17-defensive-narrow", compact: true, touch: true },
  { date: regressionDate, width: 1440, height: 900, label: "2026-07-17-desktop-wide", compact: false, touch: false },
];

function expectedLiveHref(date) {
  const day = timetableData.days.find((candidate) => candidate.date === date);
  assert.ok(day, `missing timetable day ${date}`);
  const autonomous = day.timeline_events.find((event) => event.origin === "self");
  assert.ok(autonomous, `missing autonomous event ${date}`);
  const href = new URL(autonomous.live_url || day.live_url);
  href.searchParams.set("from", "timetable");
  href.searchParams.set("date", date);
  return href.href;
}

function expectedVisualSource(date) {
  const day = timetableData.days.find((candidate) => candidate.date === date);
  assert.ok(day, `missing timetable day ${date}`);
  const autonomous = day.timeline_events.find((event) => event.origin === "self");
  assert.ok(autonomous?.visual_preview_url, `missing autonomous visual preview ${date}`);
  return autonomous.visual_preview_url;
}

function check(condition, message, failures) {
  if (!condition) failures.push(message);
}

function archivePath(value) {
  const pathname = new URL(value).pathname;
  return pathname.slice(pathname.indexOf("/archive/"));
}

async function inspect(page) {
  return page.evaluate(() => {
    const card = document.querySelector(".autonomous-reading-card");
    const readingLayer = document.querySelector(".timeline-reading-layer");
    const timeline = document.querySelector(".timeline-list");
    const event = document.querySelector(".timeline-event.autonomous-event");
    const footprint = event?.querySelector(".event-footprint");
    const connector = document.querySelector(
      `.event-connector[data-event-key="${CSS.escape(card?.dataset.eventKey || "")}"]`,
    );
    const previewFrame = card?.querySelector(".autonomous-preview-frame");
    const preview = card?.querySelector(".self-preview");
    const time = card?.querySelector(".autonomous-time");
    const copy = card?.querySelector(".autonomous-copy");
    const kicker = card?.querySelector(".autonomous-kicker");
    const title = card?.querySelector(".reading-title");
    const summary = card?.querySelector(".reading-summary");
    const dateRelation = card?.querySelector(".autonomous-date-relation");
    const previewLink = card?.querySelector(".autonomous-preview-frame");
    const hint = card?.querySelector(".autonomous-open-copy");
    const required = {
      card,
      readingLayer,
      timeline,
      event,
      footprint,
      connector,
      previewFrame,
      preview,
      time,
      copy,
      kicker,
      title,
      summary,
      dateRelation,
      previewLink,
      hint,
    };
    for (const [name, element] of Object.entries(required)) {
      if (!element) throw new Error(`missing autonomous card region: ${name}`);
    }

    const rect = (element) => {
      const bounds = element.getBoundingClientRect();
      return {
        left: bounds.left,
        right: bounds.right,
        top: bounds.top,
        bottom: bounds.bottom,
        width: bounds.width,
        height: bounds.height,
      };
    };
    const visibility = (element) => {
      const style = getComputedStyle(element);
      const bounds = element.getBoundingClientRect();
      return {
        display: style.display,
        visibility: style.visibility,
        overflow: style.overflow,
        lineClamp: style.webkitLineClamp,
        lineHeight: Number.parseFloat(style.lineHeight),
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
        visible: style.display !== "none"
          && style.visibility !== "hidden"
          && bounds.width > 0
          && bounds.height > 0,
      };
    };
    const cardRect = rect(card);
    const layerRect = rect(readingLayer);
    const eventRect = rect(event);
    const footprintRect = rect(footprint);
    const connectorRect = rect(connector);
    const previewRect = rect(previewFrame);
    const previewImageRect = rect(preview);
    const timeRect = rect(time);
    const copyRect = rect(copy);
    const kickerRect = rect(kicker);
    const titleRect = rect(title);
    const summaryRect = rect(summary);
    const dateRelationRect = rect(dateRelation);
    const hintRect = rect(hint);
    const titleVisibility = visibility(title);
    const summaryVisibility = visibility(summary);
    const dateRelationVisibility = visibility(dateRelation);
    const hintVisibility = visibility(hint);
    const minuteHeight = Number.parseFloat(getComputedStyle(timeline).getPropertyValue("--minute-height"));
    const cards = [...document.querySelectorAll(".event-reading-card")].map((element) => ({
      key: element.dataset.eventKey,
      ...rect(element),
    }));
    const overlaps = [];
    for (let leftIndex = 0; leftIndex < cards.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < cards.length; rightIndex += 1) {
        const left = cards[leftIndex];
        const right = cards[rightIndex];
        const overlapsX = left.left < right.right - 1 && right.left < left.right - 1;
        const overlapsY = left.top < right.bottom - 1 && right.top < left.bottom - 1;
        if (overlapsX && overlapsY) overlaps.push({ left: left.key, right: right.key });
      }
    }
    const scrollCandidates = [
      document.querySelector("#dayDialog"),
      document.querySelector("#dayDialogPanel"),
      document.querySelector(".timeline-detail"),
      timeline,
    ].filter(Boolean).map((element) => {
      const style = getComputedStyle(element);
      return {
        selector: element.id ? `#${element.id}` : `.${element.classList[0]}`,
        overflowY: style.overflowY,
        canScroll: element.scrollHeight > element.clientHeight + 4
          && ["auto", "scroll"].includes(style.overflowY),
      };
    });
    return {
      cardTag: card.tagName,
      cardRole: card.getAttribute("role"),
      cardTabindex: card.getAttribute("tabindex"),
      cardHref: card.getAttribute("href"),
      cardTarget: card.getAttribute("target"),
      previewTag: previewLink.tagName,
      previewHref: previewLink.href,
      previewTarget: previewLink.target,
      previewRel: previewLink.rel,
      previewName: previewLink.getAttribute("aria-label") || "",
      actionTag: hint.tagName,
      actionHref: hint.href,
      actionTarget: hint.target,
      actionRel: hint.rel,
      actionName: hint.textContent.trim(),
      className: card.className,
      compactClass: card.classList.contains("is-compact-reading-card"),
      narrowClass: card.classList.contains("is-narrow-reading-card"),
      veryNarrowClass: card.classList.contains("is-very-narrow-reading-card"),
      readingColumn: Number(card.dataset.readingColumn),
      readingColumnSpan: Number(card.dataset.readingColumnSpan),
      card: cardRect,
      cardScroll: {
        clientHeight: card.clientHeight,
        scrollHeight: card.scrollHeight,
        overflowY: getComputedStyle(card).overflowY,
        canScroll: card.scrollHeight > card.clientHeight + 1
          && ["auto", "scroll"].includes(getComputedStyle(card).overflowY),
        contentBottom: cardRect.top + card.scrollHeight,
      },
      readingLayer: layerRect,
      fullWidthDelta: layerRect.width - cardRect.width,
      leftInset: cardRect.left - layerRect.left,
      rightInset: layerRect.right - cardRect.right,
      event: eventRect,
      footprint: footprintRect,
      footprintExpectedHeight: 60 * minuteHeight,
      connector: {
        ...connectorRect,
        visible: visibility(connector).visible && Number(getComputedStyle(connector).opacity) > 0,
      },
      preview: previewRect,
      previewImage: previewImageRect,
      previewRenderedRatio: previewRect.width / previewRect.height,
      previewNaturalWidth: preview.naturalWidth,
      previewNaturalHeight: preview.naturalHeight,
      previewNaturalRatio: preview.naturalWidth / preview.naturalHeight,
      previewObjectFit: getComputedStyle(preview).objectFit,
      previewFrameRadius: Number.parseFloat(getComputedStyle(previewFrame).borderTopLeftRadius),
      previewCurrentSrc: preview.currentSrc,
      previewAnimatedSource: preview.dataset.animatedPreviewUrl,
      time: timeRect,
      timeText: time.textContent.trim(),
      copy: copyRect,
      kicker: kickerRect,
      title: {
        ...titleRect,
        ...titleVisibility,
        text: title.textContent.trim(),
        clipped: title.scrollHeight > title.clientHeight + 1,
      },
      summary: {
        ...summaryRect,
        ...summaryVisibility,
        text: summary.textContent.trim(),
        visibleLines: summaryVisibility.clientHeight / summaryVisibility.lineHeight,
        exposedFraction: summaryVisibility.clientHeight / summaryVisibility.scrollHeight,
      },
      dateRelation: {
        ...dateRelationRect,
        ...dateRelationVisibility,
        text: dateRelation.textContent.trim(),
        fontSize: Number.parseFloat(getComputedStyle(dateRelation).fontSize),
        clipped: dateRelation.scrollHeight > dateRelation.clientHeight + 1,
      },
      hint: {
        ...hintRect,
        ...hintVisibility,
      },
      overlaps,
      horizontalOverflow: document.documentElement.scrollWidth
        - document.documentElement.clientWidth,
      panelScrollable: document.querySelector("#dayDialogPanel").scrollHeight
        > document.querySelector("#dayDialogPanel").clientHeight + 4,
      scrollRoots: scrollCandidates.filter((candidate) => candidate.canScroll)
        .map((candidate) => candidate.selector),
    };
  });
}

if (screenshotRoot) await mkdir(screenshotRoot, { recursive: true });

const browser = await chromium.launch({ headless: true });
const results = [];
const failures = [];

try {
  for (const testCase of cases) {
    const context = await browser.newContext({
      viewport: { width: testCase.width, height: testCase.height },
      isMobile: testCase.touch,
      hasTouch: testCase.touch,
      deviceScaleFactor: testCase.touch ? 2 : 1,
    });
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const caseUrl = new URL(baseUrl);
    caseUrl.searchParams.set("date", testCase.date);
    await page.goto(caseUrl.href, { waitUntil: "networkidle" });
    await page.waitForSelector(`#dayDialog.is-open[data-selected-date="${testCase.date}"]`);
    await page.waitForFunction(
      () => document.querySelector(".timeline-reading-layer.is-placed")
        && document.querySelector(".autonomous-reading-card")?.getBoundingClientRect().width > 0,
    );
    await page.waitForFunction(
      () => {
        const image = document.querySelector(".autonomous-reading-card .self-preview");
        return image?.complete && image.naturalWidth > 0 && image.naturalHeight > 0;
      },
    );
    await page.mouse.move(1, 1);
    await page.waitForTimeout(200);
    const result = {
      label: testCase.label,
      date: testCase.date,
      viewport: { width: testCase.width, height: testCase.height },
      ...(await inspect(page)),
    };
    if (testCase.width === 320) {
      result.legacyNarrowCombination = await page.locator(".autonomous-reading-card").evaluate((card) => {
        const originalClassName = card.className;
        card.classList.add("is-narrow-reading-card", "is-very-narrow-reading-card");
        const summary = card.querySelector(".reading-summary");
        const style = getComputedStyle(summary);
        const lineHeight = Number.parseFloat(style.lineHeight);
        const combination = {
          className: card.className,
          display: style.display,
          visibility: style.visibility,
          clientHeight: summary.clientHeight,
          scrollHeight: summary.scrollHeight,
          visibleLines: summary.clientHeight / lineHeight,
        };
        card.className = originalClassName;
        return combination;
      });
    }
    results.push(result);

    check(pageErrors.length === 0, `${testCase.label}: page errors ${JSON.stringify(pageErrors)}`, failures);
    check(result.cardTag === "ARTICLE", `${testCase.label}: card must remain an article`, failures);
    check(result.cardRole === null, `${testCase.label}: article has a misleading explicit role`, failures);
    check(result.cardTabindex === null, `${testCase.label}: article remains focusable`, failures);
    check(result.cardHref === null && result.cardTarget === null, `${testCase.label}: article carries pseudo-link properties`, failures);
    check(result.previewTag === "A", `${testCase.label}: preview is not a native link`, failures);
    check(result.actionTag === "A", `${testCase.label}: visible action is not a native link`, failures);
    check(result.previewHref === expectedLiveHref(testCase.date), `${testCase.label}: preview launch href changed`, failures);
    check(result.actionHref === result.previewHref, `${testCase.label}: native launch links disagree`, failures);
    check(result.previewTarget === "_blank" && result.actionTarget === "_blank", `${testCase.label}: direct launch target changed`, failures);
    check(result.previewRel.split(/\s+/).includes("noopener"), `${testCase.label}: preview missing noopener`, failures);
    check(result.actionRel.split(/\s+/).includes("noopener"), `${testCase.label}: action missing noopener`, failures);
    check(/Open complete live work/.test(result.previewName), `${testCase.label}: preview link name is unclear`, failures);
    check(/Open complete live work/.test(result.actionName), `${testCase.label}: action link name is unclear`, failures);
    check(
      result.previewAnimatedSource === expectedVisualSource(testCase.date)
        && archivePath(result.previewCurrentSrc) === archivePath(result.previewAnimatedSource),
      `${testCase.label}: generated-art GIF source changed`,
      failures,
    );
    check(
      result.compactClass
        ? Math.abs(result.previewRenderedRatio - result.previewNaturalRatio) <= 0.03
        : result.previewObjectFit === "cover"
          && Math.abs(result.preview.width - result.previewImage.width) <= 1
          && Math.abs(result.preview.height - result.previewImage.height) <= 1
          && result.previewFrameRadius >= 12,
      `${testCase.label}: preview must either preserve mobile ratio or use the rounded desktop cover crop`,
      failures,
    );
    check(
      Math.abs(result.footprint.height - result.footprintExpectedHeight) <= 0.5,
      `${testCase.label}: true 60-minute footprint changed`,
      failures,
    );
    check(
      /03:17-04:17/.test(result.timeText)
        && /granted 60 min \/ 授时 60 分钟/.test(result.timeText),
      `${testCase.label}: granted-time duration is unclear: ${result.timeText}`,
      failures,
    );
    check(
      result.connector.visible && Math.max(result.connector.width, result.connector.height) >= 8,
      `${testCase.label}: connector missing`,
      failures,
    );
    check(result.overlaps.length === 0, `${testCase.label}: reading-card overlaps ${JSON.stringify(result.overlaps)}`, failures);
    check(result.horizontalOverflow <= 1, `${testCase.label}: horizontal overflow ${result.horizontalOverflow}`, failures);
    check(
      result.card.left >= result.readingLayer.left - 0.5
        && result.card.right <= result.readingLayer.right + 0.5,
      `${testCase.label}: card outside reading canvas horizontally`,
      failures,
    );

    if (testCase.compact) {
      const minimumPreviewWidth = testCase.width >= 390 ? 270 : 220;
      const minimumPreviewHeight = testCase.width >= 390 ? 145 : 120;
      check(result.compactClass, `${testCase.label}: missing compact class contract`, failures);
      check(result.readingColumn === 0, `${testCase.label}: compact card is not in first reading column`, failures);
      check(result.readingColumnSpan === 3, `${testCase.label}: compact card does not span all 3 columns`, failures);
      check(result.fullWidthDelta <= 1, `${testCase.label}: compact card is not full reading width`, failures);
      check(Math.abs(result.leftInset) <= 0.5, `${testCase.label}: unexpected left inset`, failures);
      check(Math.abs(result.rightInset) <= 0.5, `${testCase.label}: unexpected right inset`, failures);
      check(result.card.height >= 340 && result.card.height <= 385, `${testCase.label}: compact height ${result.card.height}`, failures);
      if (testCase.width === 390) {
        check(result.card.width >= 300, `${testCase.label}: card width ${result.card.width}`, failures);
      }
      check(
        result.preview.width >= minimumPreviewWidth && result.preview.height >= minimumPreviewHeight,
        `${testCase.label}: preview too small ${result.preview.width}x${result.preview.height}`,
        failures,
      );
      check(
        result.dateRelation.visible
          && result.dateRelation.fontSize >= 9
          && result.dateRelation.lineHeight >= result.dateRelation.fontSize * 1.2
          && !result.dateRelation.clipped,
        `${testCase.label}: dual-date metadata unreadable ${JSON.stringify(result.dateRelation)}`,
        failures,
      );
      check(!result.title.clipped, `${testCase.label}: title clipped`, failures);
      check(
        result.summary.visible
          && result.summary.display !== "none"
          && result.summary.visibleLines >= 4
          && result.summary.exposedFraction >= 0.3
          && result.summary.bottom <= result.copy.bottom + 1,
        `${testCase.label}: summary unreadable ${JSON.stringify(result.summary)}`,
        failures,
      );
      check(result.hint.visible, `${testCase.label}: launch hint hidden`, failures);
      if (result.legacyNarrowCombination) {
        check(
          result.legacyNarrowCombination.display !== "none"
            && result.legacyNarrowCombination.visibility !== "hidden"
            && result.legacyNarrowCombination.visibleLines >= 4,
          `${testCase.label}: narrow/very-narrow classes hid compact summary `
            + JSON.stringify(result.legacyNarrowCombination),
          failures,
        );
      }
      check(
        result.time.bottom <= result.preview.top + 1
          && result.preview.bottom <= result.copy.top + 1
          && result.copy.bottom <= result.hint.top + 1,
        `${testCase.label}: compact reading order is not stacked`,
        failures,
      );
      check(result.panelScrollable, `${testCase.label}: dialog is not scrollable`, failures);
      if (testCase.width === 421 && testCase.height === 386) {
        check(
          JSON.stringify(result.scrollRoots) === JSON.stringify(["#dayDialogPanel"]),
          `${testCase.label}: expected one scroll root, got ${JSON.stringify(result.scrollRoots)}`,
          failures,
        );
      }
    } else {
      const contentExtendsBelowFrame = result.hint.bottom > result.card.bottom - 4;
      check(!result.compactClass, `${testCase.label}: desktop incorrectly compact`, failures);
      check(result.readingColumnSpan === 2, `${testCase.label}: desktop span changed`, failures);
      check(result.card.height >= 180 && result.card.height <= 230, `${testCase.label}: desktop height changed`, failures);
      check(result.fullWidthDelta >= result.readingLayer.width * 0.35, `${testCase.label}: desktop card became full-width`, failures);
      check(result.preview.left >= result.copy.right - 1, `${testCase.label}: desktop is no longer side-by-side`, failures);
      check(
        result.kicker.bottom <= result.title.top + 1
          && result.title.bottom <= result.dateRelation.top + 1
          && result.dateRelation.bottom <= result.summary.top + 1
          && result.summary.bottom <= result.copy.bottom + 1
          && result.copy.bottom <= result.hint.top + 1
          && result.hint.bottom <= result.cardScroll.contentBottom + 1
          && (!contentExtendsBelowFrame || result.cardScroll.canScroll),
        `${testCase.label}: autonomous copy regions overlap or escape their column `
          + JSON.stringify({
            kicker: result.kicker,
            title: result.title,
            dateRelation: result.dateRelation,
            summary: result.summary,
            copy: result.copy,
          }),
        failures,
      );
    }

    if (
      screenshotRoot
      && testCase.date === regressionDate
      && ((testCase.width === 390 && testCase.height === 844)
        || (testCase.width === 421 && testCase.height === 386))
    ) {
      await page.locator(".autonomous-reading-card").scrollIntoViewIfNeeded();
      await page.screenshot({
        path: path.join(
          screenshotRoot,
          `${screenshotPhase}-${testCase.width}x${testCase.height}-${testCase.date}.png`,
        ),
        fullPage: false,
      });
    }
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ baseUrl, latestDate, results, failures }, null, 2));
assert.deepEqual(failures, [], `autonomous mobile-card QA failed:\n${failures.join("\n")}`);
