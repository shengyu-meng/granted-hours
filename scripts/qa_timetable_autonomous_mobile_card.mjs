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
  { date: regressionDate, width: 3840, height: 2160, label: "2026-07-17-desktop-4k", compact: false, touch: false },
];

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
    const panel = document.querySelector("#dayDialogPanel");
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
      panel,
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
    const panelRect = rect(panel);
    const timelineRect = rect(timeline);
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
      previewPopup: previewLink.getAttribute("aria-haspopup"),
      previewName: previewLink.getAttribute("aria-label") || "",
      actionTag: hint.tagName,
      actionPopup: hint.getAttribute("aria-haspopup"),
      actionName: hint.textContent.trim(),
      className: card.className,
      compactClass: card.classList.contains("is-compact-reading-card"),
      narrowClass: card.classList.contains("is-narrow-reading-card"),
      veryNarrowClass: card.classList.contains("is-very-narrow-reading-card"),
      readingColumn: Number(card.dataset.readingColumn),
      readingColumnSpan: Number(card.dataset.readingColumnSpan),
      edgeSide: card.dataset.edgeSide,
      edgeAnchored: card.dataset.edgeAnchored,
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
      panel: {
        ...panelRect,
        clientHeight: panel.clientHeight,
        scrollHeight: panel.scrollHeight,
      },
      timeline: timelineRect,
      panelScrollable: panel.scrollHeight > panel.clientHeight + 4,
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
    await page.goto(caseUrl.href, { waitUntil: "domcontentloaded" });
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
    check(result.previewTag === "BUTTON", `${testCase.label}: preview is not an in-page dialog button`, failures);
    check(result.actionTag === "BUTTON", `${testCase.label}: visible action is not an in-page dialog button`, failures);
    check(result.previewPopup === "dialog" && result.actionPopup === "dialog", `${testCase.label}: artwork dialog semantics missing`, failures);
    check(/Open interactive artwork in the calendar/.test(result.previewName), `${testCase.label}: preview button name is unclear`, failures);
    check(/Open interactive artwork/.test(result.actionName), `${testCase.label}: action button name is unclear`, failures);
    check(
      result.previewAnimatedSource === expectedVisualSource(testCase.date)
        && archivePath(result.previewCurrentSrc) === archivePath(result.previewAnimatedSource),
      `${testCase.label}: generated-art GIF source changed`,
      failures,
    );
    check(
      Math.abs(result.previewRenderedRatio - 1) <= 0.03
        && result.previewObjectFit === "cover"
        && Math.abs(result.preview.width - result.previewImage.width) <= 2.5
        && Math.abs(result.preview.height - result.previewImage.height) <= 2.5
        && Math.abs(result.preview.width - result.preview.height) <= 1
        && Math.abs(result.preview.height - (result.card.height - 4)) <= 1.5
        && result.previewFrameRadius >= 10,
      `${testCase.label}: preview must be a card-height square crop`,
      failures,
    );
    check(
      result.preview.top >= result.card.top - 0.5
        && result.preview.bottom <= result.card.bottom + 0.5,
      `${testCase.label}: preview escapes the visible card ${JSON.stringify({ card: result.card, preview: result.preview })}`,
      failures,
    );
    check(
      !result.cardScroll.canScroll,
      `${testCase.label}: autonomous artwork card must not require internal scrolling ${JSON.stringify(result.cardScroll)}`,
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
    check(
      result.edgeAnchored === "true"
        && ((result.edgeSide === "left" && Math.abs(result.leftInset) <= 0.75)
          || (result.edgeSide === "right" && Math.abs(result.rightInset) <= 0.75)),
      `${testCase.label}: artwork card is centered instead of edge-anchored`,
      failures,
    );

    if (testCase.compact) {
      check(result.compactClass, `${testCase.label}: missing compact class contract`, failures);
      check([4, 5].includes(result.readingColumnSpan), `${testCase.label}: compact edge span changed`, failures);
      check(result.card.height >= 132 && result.card.height <= 188, `${testCase.label}: compact height ${result.card.height}`, failures);
      check(
        result.preview.width >= 128 && result.preview.height >= 128,
        `${testCase.label}: preview too small ${result.preview.width}x${result.preview.height}`,
        failures,
      );
      check(
        result.dateRelation.visible
          && result.dateRelation.fontSize >= 7
          && result.dateRelation.lineHeight >= result.dateRelation.fontSize * 1.1
          && result.dateRelation.clientHeight >= result.dateRelation.lineHeight,
        `${testCase.label}: dual-date metadata unreadable ${JSON.stringify(result.dateRelation)}`,
        failures,
      );
      check(
        result.summary.visible
          && result.summary.display !== "none"
          && result.summary.visibleLines >= 1
          && result.summary.bottom <= result.copy.bottom + 1,
        `${testCase.label}: summary unreadable ${JSON.stringify(result.summary)}`,
        failures,
      );
      check(result.hint.visible, `${testCase.label}: launch hint hidden`, failures);
      if (result.legacyNarrowCombination) {
        check(
          result.legacyNarrowCombination.display !== "none"
            && result.legacyNarrowCombination.visibility !== "hidden"
            && result.legacyNarrowCombination.visibleLines >= 1,
          `${testCase.label}: narrow/very-narrow classes hid compact summary `
            + JSON.stringify(result.legacyNarrowCombination),
          failures,
        );
      }
      check(
        (result.preview.right <= result.copy.left + 1 || result.copy.right <= result.preview.left + 1)
          && result.time.bottom <= result.copy.bottom + 1
          && result.copy.bottom <= result.hint.top + 1,
        `${testCase.label}: compact square crop and copy are not side-by-side`,
        failures,
      );
      check(
        result.panelScrollable
          || (
            result.panel.scrollHeight <= result.panel.clientHeight + 4
            && result.timeline.bottom <= result.panel.bottom + 1
          ),
        `${testCase.label}: non-scrollable dialog clips timetable content `
          + JSON.stringify({ panel: result.panel, timeline: result.timeline }),
        failures,
      );
      if (testCase.width === 421 && testCase.height === 386) {
        check(
          JSON.stringify(result.scrollRoots) === JSON.stringify(["#dayDialogPanel"]),
          `${testCase.label}: expected one scroll root, got ${JSON.stringify(result.scrollRoots)}`,
          failures,
        );
      }
    } else {
      check(!result.compactClass, `${testCase.label}: desktop incorrectly compact`, failures);
      check(result.readingColumnSpan === 2, `${testCase.label}: desktop span changed`, failures);
      check(result.card.height >= 260 && result.card.height <= 275, `${testCase.label}: desktop height changed`, failures);
      check(result.fullWidthDelta >= result.readingLayer.width * 0.35, `${testCase.label}: desktop card became full-width`, failures);
      check(
        result.preview.right <= result.copy.left + 1 || result.copy.right <= result.preview.left + 1,
        `${testCase.label}: desktop is no longer side-by-side`,
        failures,
      );
      check(
        result.kicker.bottom <= result.title.top + 1
          && result.title.bottom <= result.dateRelation.top + 1
          && result.dateRelation.bottom <= result.summary.top + 1
          && result.summary.bottom <= result.copy.bottom + 1
          && result.copy.bottom <= result.hint.top + 1
          && result.hint.bottom <= result.card.bottom + 1,
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
        || (testCase.width === 421 && testCase.height === 386)
        || (testCase.width === 1440 && testCase.height === 900)
        || (testCase.width === 3840 && testCase.height === 2160))
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
