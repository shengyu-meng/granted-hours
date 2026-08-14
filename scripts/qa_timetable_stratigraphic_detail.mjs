#!/usr/bin/env node
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8892/timetable/";
const screenshotRoot = process.env.QA_SCREENSHOT_DIR || "";
const sampleDate = "2026-08-11";
const sparseDate = timetableData.days.reduce((sparsest, day) => (
  day.timeline_events.length < sparsest.timeline_events.length ? day : sparsest
)).date;
const cases = [
  { label: "desktop-dark", date: sampleDate, dense: true, width: 1440, height: 900, theme: "dark" },
  { label: "desktop-light", date: sampleDate, dense: true, width: 1440, height: 900, theme: "light" },
  { label: "desktop-4k", date: sampleDate, dense: true, width: 3840, height: 2160, theme: "dark" },
  { label: "mobile-390", date: sampleDate, dense: true, width: 390, height: 844, theme: "dark", mobile: true },
  { label: "short-touch", date: sampleDate, dense: true, width: 421, height: 386, theme: "light", mobile: true },
  { label: "sparse-desktop", date: sparseDate, width: 1440, height: 900, theme: "dark" },
  { label: "sparse-mobile", date: sparseDate, width: 390, height: 844, theme: "light", mobile: true },
];

const browser = await chromium.launch({ headless: true });
const results = [];
let corpusAudit = null;
try {
  for (const testCase of cases) {
    const context = await browser.newContext({
      viewport: { width: testCase.width, height: testCase.height },
      colorScheme: testCase.theme,
      isMobile: Boolean(testCase.mobile),
      hasTouch: Boolean(testCase.mobile),
      deviceScaleFactor: testCase.mobile ? 2 : 1,
    });
    await context.addInitScript((theme) => {
      localStorage.setItem("granted-hours-theme", theme);
    }, testCase.theme);
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const url = new URL(baseUrl);
    url.searchParams.set("date", testCase.date);
    url.searchParams.set("regression", "stratigraphic-detail");
    await page.goto(url.href, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(".timeline-reading-layer.is-placed");

    const state = await page.evaluate(() => {
      const timeline = document.querySelector(".timeline-list");
      const strataBed = timeline?.querySelector(".timeline-strata-bed");
      const eventsLayer = timeline?.querySelector(".timeline-events-layer");
      const timelineRect = timeline.getBoundingClientRect();
      const strataRect = strataBed.getBoundingClientRect();
      const eventsRect = eventsLayer.getBoundingClientRect();
      const minuteHeight = Number.parseFloat(
        getComputedStyle(timeline).getPropertyValue("--minute-height"),
      );
      const hourMarkers = [...timeline.querySelectorAll(".timeline-hour-marker")].map((marker) => ({
        minute: Number(marker.dataset.hourMinute),
        density: marker.dataset.hourDensity,
        hasEvent: marker.dataset.hasEvent === "true",
        hasCard: marker.dataset.hasCard === "true",
        bandHeight: Number(marker.dataset.bandHeight),
        activeMinutes: Number(marker.dataset.activeMinutes),
        idleMinutes: Number(marker.dataset.idleMinutes),
        top: marker.getBoundingClientRect().top - timelineRect.top,
        labelLeft: Number.parseFloat(getComputedStyle(marker.querySelector("span")).left),
        labelText: marker.querySelector("span")?.innerText || "",
      }));
      const footprints = [...eventsLayer.querySelectorAll(".timeline-event")].map((event) => {
        const footprint = event.querySelector(".event-footprint");
        const rect = footprint.getBoundingClientRect();
        const style = getComputedStyle(footprint);
        return {
          id: event.dataset.footprintId,
          start: event.dataset.start,
          end: event.dataset.end,
          duration: Number(event.dataset.durationMinutes),
          variant: event.dataset.stratumVariant,
          opacity: Number(style.opacity),
          backgroundImage: style.backgroundImage,
          backgroundColor: style.backgroundColor,
          radius: style.borderRadius,
          height: rect.height,
          expectedHeight: Number(event.dataset.durationMinutes) * minuteHeight,
        };
      });
      const footprintsById = new Map(
        [...eventsLayer.querySelectorAll(".timeline-event")]
          .map((event) => [event.dataset.footprintId, event]),
      );
      const cards = [...timeline.querySelectorAll(".event-reading-card")].map((card) => {
        const rect = card.getBoundingClientRect();
        const style = getComputedStyle(card);
        const memberIds = (card.dataset.memberFootprintIds || "").split(/\s+/).filter(Boolean);
        const memberCenters = memberIds.map((id) => {
          const event = footprintsById.get(id);
          return event
            ? (Number(event.style.getPropertyValue("--event-start-minute"))
              + Number(event.style.getPropertyValue("--event-duration-minutes")) / 2)
            : NaN;
        }).filter(Number.isFinite).sort((left, right) => left - right);
        const middle = Math.floor(memberCenters.length / 2);
        const median = memberCenters.length % 2
          ? memberCenters[middle]
          : (memberCenters[middle - 1] + memberCenters[middle]) / 2;
        return {
          key: card.dataset.readingId,
          layer: card.dataset.layer,
          memberCount: Number(card.dataset.memberCount),
          anchorMinute: Number(card.dataset.anchorMinute),
          medianMinute: median,
          anchorDisplacement: Number(card.dataset.anchorDisplacement),
          totalDurationMinutes: Number(card.dataset.totalDurationMinutes),
          copyLength: Number(card.dataset.copyLength),
          columnSpan: Number(card.dataset.readingColumnSpan),
          column: Number(card.dataset.readingColumn),
          edgeSide: card.dataset.edgeSide,
          edgeAnchored: card.dataset.edgeAnchored,
          left: rect.left,
          right: rect.right,
          top: rect.top,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
          heightContract: card.dataset.heightContract,
          contentHeight: Number(card.dataset.contentHeight),
          durationHeight: Number(card.dataset.durationHeight),
          minimumHeight: Number(card.dataset.minimumHeight),
          maximumHeight: Number(card.dataset.maximumHeight),
          targetHeight: Number(card.dataset.targetHeight),
          heightConstraint: card.dataset.heightConstraint,
          heightSource: card.dataset.heightSource,
          opacity: Number(style.opacity),
          backgroundColor: style.backgroundColor,
          borderRadius: style.borderRadius,
          backdropFilter: style.backdropFilter || style.webkitBackdropFilter,
          boxShadow: style.boxShadow,
        };
      });
      const overlaps = [];
      for (let leftIndex = 0; leftIndex < cards.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < cards.length; rightIndex += 1) {
          const left = cards[leftIndex];
          const right = cards[rightIndex];
          if (
            left.left < right.right - 0.5
            && right.left < left.right - 0.5
            && left.top < right.bottom - 0.5
            && right.top < left.bottom - 0.5
          ) overlaps.push([left.key, right.key]);
        }
      }
      const strataStyle = getComputedStyle(strataBed);
      return {
        minuteHeight,
        timelineHeight: timelineRect.height,
        linearHeight: Number(timeline.dataset.linearHeight),
        projectedHeight: Number(timeline.dataset.projectedHeight),
        activeHourCount: Number(timeline.dataset.activeHourCount),
        compressedHourCount: Number(timeline.dataset.compressedHourCount),
        fullyCompressedHourCount: Number(timeline.dataset.fullyCompressedHourCount),
        partiallyCompressedHourCount: Number(timeline.dataset.partiallyCompressedHourCount),
        activeMinuteCount: Number(timeline.dataset.activeMinuteCount),
        compressedMinuteCount: Number(timeline.dataset.compressedMinuteCount),
        projection: timeline.dataset.projection,
        readingLayer: {
          left: eventsRect.left,
          right: eventsRect.right,
          width: eventsRect.width,
        },
        hourMarkers,
        horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        strata: {
          leftDelta: Math.abs(strataRect.left - eventsRect.left),
          rightDelta: Math.abs(strataRect.right - eventsRect.right),
          heightDelta: Math.abs(strataRect.height - eventsRect.height),
          opacity: Number(strataStyle.opacity),
          backgroundImage: strataStyle.backgroundImage,
        },
        footprints,
        cards,
        overlaps,
      };
    });

    assert.deepEqual(pageErrors, [], `${testCase.label}: page errors`);
    assert.ok(state.strata.backgroundImage !== "none", `${testCase.label}: missing strata bed`);
    assert.ok(state.strata.opacity >= 0.72, `${testCase.label}: strata bed is too faint`);
    assert.ok(state.strata.leftDelta <= 0.5 && state.strata.rightDelta <= 0.5, `${testCase.label}: strata bed is misaligned`);
    assert.ok(state.strata.heightDelta <= 0.5, `${testCase.label}: strata bed height is misaligned`);
    assert.ok(
      state.footprints.length >= (testCase.dense ? 100 : 1),
      `${testCase.label}: source footprints were lost`,
    );
    assert.ok(
      state.footprints.every((footprint) => footprint.variant !== ""),
      `${testCase.label}: a stratum lacks its stable mineral variant`,
    );
    assert.ok(
      state.footprints.every((footprint) => footprint.opacity >= 0.82),
      `${testCase.label}: an exact stratum still relies on low opacity`,
    );
    assert.ok(
      state.footprints.every((footprint) => footprint.backgroundImage !== "none" || footprint.backgroundColor !== "rgba(0, 0, 0, 0)"),
      `${testCase.label}: an exact stratum has no material fill`,
    );
    assert.ok(
      state.footprints.every((footprint) => Math.abs(footprint.height - footprint.expectedHeight) <= 0.7),
      `${testCase.label}: exact duration geometry drifted`,
    );
    assert.deepEqual(state.overlaps, [], `${testCase.label}: reading fossils overlap`);
    assert.ok(state.horizontalOverflow <= 1, `${testCase.label}: horizontal overflow`);
    assert.ok(
      state.cards.every((card) => Number.parseFloat(card.borderRadius) >= 14 && card.backdropFilter.includes("blur")),
      `${testCase.label}: embedded cards lost rounded mineral material`,
    );
    assert.ok(
      state.cards.every((card) => card.opacity === 1 && card.backgroundColor !== "rgba(0, 0, 0, 0)"),
      `${testCase.label}: a reading card still depends on transparency`,
    );
    assert.ok(
      state.cards.every((card) => {
        const leftInset = Math.abs(card.left - state.readingLayer.left);
        const rightInset = Math.abs(state.readingLayer.right - card.right);
        return card.edgeAnchored === "true"
          && ((card.edgeSide === "left" && leftInset <= 0.75)
            || (card.edgeSide === "right" && rightInset <= 0.75));
      }),
      `${testCase.label}: a reading card is centered instead of interrupting an edge`,
    );
    assert.ok(
      state.cards.filter((card) => card.memberCount > 1).every((card) => (
        Math.abs(card.anchorMinute - card.medianMinute) <= 0.01
        && card.anchorDisplacement <= (testCase.mobile ? 430 : 140)
      )),
      `${testCase.label}: an aggregate card is detached from its strata`,
    );
    if (testCase.dense) {
      assert.ok(
        new Set(state.cards.filter((card) => card.layer !== "beacon").map((card) => Math.round(card.height))).size >= 2,
        `${testCase.label}: card height no longer responds to content and duration`,
      );
    }
    assert.ok(
      state.cards.filter((card) => card.layer !== "beacon").every((card) => {
        const expected = Math.min(
          card.maximumHeight,
          Math.max(card.minimumHeight, card.contentHeight, card.durationHeight),
        );
        return card.heightContract === "content-duration-max-v1"
          && Math.abs(card.targetHeight - expected) <= 0.01
          && Math.abs(card.height - card.targetHeight) <= 0.7
          && ["content", "duration"].includes(card.heightSource)
          && ["minimum", "maximum", "none"].includes(card.heightConstraint);
      }),
      `${testCase.label}: non-artwork cards no longer use max(content, duration) height`,
    );
    assert.ok(
      state.cards.filter((card) => card.layer === "beacon").every((card) => (
        card.heightContract === "autonomous-artwork-v1"
        && Math.abs(card.height - card.targetHeight) <= 0.7
      )),
      `${testCase.label}: autonomous artwork height was folded into the compact card rule`,
    );
    assert.equal(state.projection, "compressed-idle-segments-v2", `${testCase.label}: missing continuous idle-time projection`);
    assert.equal(state.hourMarkers.length, 25, `${testCase.label}: hourly orientation marks were lost`);
    assert.ok(state.compressedMinuteCount > 0, `${testCase.label}: no idle minutes were compressed`);
    assert.ok(state.projectedHeight < state.linearHeight, `${testCase.label}: timeline did not become more compact`);
    assert.equal(
      state.hourMarkers.slice(0, 24).filter((marker) => marker.density !== "active").length,
      state.compressedHourCount,
      `${testCase.label}: compressed/mixed hour marks disagree with the projection`,
    );
    const compressedMarkers = state.hourMarkers.filter((marker) => marker.density === "compressed");
    assert.ok(
      compressedMarkers.every((marker) => !marker.hasEvent && !marker.hasCard),
      `${testCase.label}: a fully compressed hour contains an event or card`,
    );
    assert.ok(
      compressedMarkers.every((marker) => marker.bandHeight <= (testCase.mobile ? 10 : 9)),
      `${testCase.label}: empty-hour bands are still too tall: ${JSON.stringify(compressedMarkers)}`,
    );
    const mixedMarkers = state.hourMarkers.filter((marker) => marker.density === "mixed");
    if (testCase.dense) {
      assert.ok(mixedMarkers.length > 0, `${testCase.label}: partial-hour idle gaps were not detected`);
    }
    assert.ok(
      mixedMarkers.every((marker) => (
        marker.activeMinutes > 0
        && marker.idleMinutes > 0
        && marker.bandHeight < 60 * state.minuteHeight
      )),
      `${testCase.label}: partially occupied hours still reserve their full linear height`,
    );
    assert.ok(
      state.hourMarkers.every((marker, index, markers) => index === 0 || marker.top > markers[index - 1].top),
      `${testCase.label}: hour labels no longer preserve chronological order`,
    );
    if (testCase.mobile) {
      const compactMarkers = state.hourMarkers.filter((marker) => marker.density !== "active");
      assert.ok(
        new Set(compactMarkers.map((marker) => Math.round(marker.labelLeft))).size >= 3,
        `${testCase.label}: compact hour labels no longer use staggered orientation tracks`,
      );
      assert.ok(
        compactMarkers.every((marker) => !marker.labelText.includes(":00")),
        `${testCase.label}: compact hour labels did not switch to the concise mobile form`,
      );
    }
    if (!testCase.dense) {
      assert.ok(
        state.projectedHeight <= state.linearHeight * 0.62,
        `${testCase.label}: sparse day was not materially compacted`,
      );
    }

    const hoverCard = page.locator(testCase.dense
      ? '.event-reading-card[data-layer="event"]'
      : '.event-reading-card[data-layer="beacon"]').first();
    await hoverCard.evaluate((card) => card.scrollIntoView({ block: "center", inline: "nearest" }));
    await page.mouse.move(testCase.width - 8, 8);
    await page.waitForTimeout(340);
    if (screenshotRoot) {
      await mkdir(screenshotRoot, { recursive: true });
      await page.screenshot({
        path: path.join(screenshotRoot, `${testCase.date}-${testCase.label}-resting.png`),
        fullPage: false,
        animations: "disabled",
        timeout: 120_000,
      });
    }
    const beforeHoverShadow = await hoverCard.evaluate((card) => getComputedStyle(card).boxShadow);
    if (!testCase.mobile) {
      await hoverCard.hover();
      const hoverState = await hoverCard.evaluate((card) => ({
        transform: getComputedStyle(card).transform,
        boxShadow: getComputedStyle(card).boxShadow,
        linkedMemberCount: (card.dataset.memberFootprintIds || "")
          .split(/\s+/)
          .filter(Boolean)
          .filter((id) => document.querySelector(`.timeline-event[data-footprint-id="${CSS.escape(id)}"]`)?.classList.contains("is-linked-active"))
          .length,
        memberCount: Number(card.dataset.memberCount),
      }));
      assert.equal(hoverState.transform, "matrix(1, 0, 0, 1, 0, -4)", `${testCase.label}: hover lift drifted`);
      assert.notEqual(hoverState.boxShadow, beforeHoverShadow, `${testCase.label}: hover lacks depth change`);
      assert.equal(hoverState.linkedMemberCount, hoverState.memberCount, `${testCase.label}: hover does not reveal every member stratum`);
    }

    results.push({
      label: testCase.label,
      date: testCase.date,
      minuteHeight: state.minuteHeight,
      timelineHeight: state.timelineHeight,
      footprints: state.footprints.length,
      cards: state.cards.length,
      activeHours: state.activeHourCount,
      compressedHours: state.compressedHourCount,
      fullyCompressedHours: state.fullyCompressedHourCount,
      partiallyCompressedHours: state.partiallyCompressedHourCount,
      activeMinutes: state.activeMinuteCount,
      compressedMinutes: state.compressedMinuteCount,
      compressionRatio: state.timelineHeight / state.linearHeight,
      maximumAggregateDisplacement: Math.max(
        0,
        ...state.cards.filter((card) => card.memberCount > 1).map((card) => card.anchorDisplacement),
      ),
    });
    await context.close();
  }

  const corpusDates = timetableData.days.map((day) => day.date).sort();
  const corpusContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    colorScheme: "dark",
  });
  await corpusContext.addInitScript(() => {
    localStorage.setItem("granted-hours-theme", "dark");
  });
  const corpusPage = await corpusContext.newPage();
  const firstUrl = new URL(baseUrl);
  firstUrl.searchParams.set("date", corpusDates[0]);
  firstUrl.searchParams.set("regression", "reading-card-height-corpus");
  await corpusPage.goto(firstUrl.href, { waitUntil: "domcontentloaded" });
  const heightSources = new Set();
  let auditedCardCount = 0;
  let clampedMaximumCount = 0;
  for (let index = 0; index < corpusDates.length; index += 1) {
    const date = corpusDates[index];
    await corpusPage.waitForFunction((expectedDate) => (
      document.querySelector("#dayDialog")?.dataset.selectedDate === expectedDate
      && document.querySelector(".timeline-reading-layer")?.classList.contains("is-placed")
    ), date);
    const cards = await corpusPage.locator(".event-reading-card").evaluateAll((elements) => (
      elements.map((card) => ({
        id: card.dataset.readingId,
        layer: card.dataset.layer,
        height: card.getBoundingClientRect().height,
        contract: card.dataset.heightContract,
        content: Number(card.dataset.contentHeight),
        duration: Number(card.dataset.durationHeight),
        minimum: Number(card.dataset.minimumHeight),
        maximum: Number(card.dataset.maximumHeight),
        target: Number(card.dataset.targetHeight),
        constraint: card.dataset.heightConstraint,
        source: card.dataset.heightSource,
      }))
    ));
    assert.ok(cards.length > 0, `${date}: selected day has no reading cards`);
    for (const card of cards) {
      if (card.layer === "beacon") {
        assert.equal(card.contract, "autonomous-artwork-v1", `${date} ${card.id}: artwork height contract drifted`);
        assert.ok(Math.abs(card.height - card.target) <= 0.7, `${date} ${card.id}: artwork height drifted`);
        continue;
      }
      const expected = Math.min(card.maximum, Math.max(card.minimum, card.content, card.duration));
      assert.equal(card.contract, "content-duration-max-v1", `${date} ${card.id}: missing compact height contract`);
      assert.ok(Math.abs(card.target - expected) <= 0.01, `${date} ${card.id}: target is not max(content, duration)`);
      assert.ok(Math.abs(card.height - card.target) <= 0.7, `${date} ${card.id}: rendered height differs from target`);
      heightSources.add(card.source);
      auditedCardCount += 1;
      if (card.constraint === "maximum") clampedMaximumCount += 1;
    }
    if (index < corpusDates.length - 1) {
      await corpusPage.click("#nextDay");
    }
  }
  assert.deepEqual(
    [...heightSources].sort(),
    ["content", "duration"],
    "full corpus did not exercise both content-led and duration-led card heights",
  );
  corpusAudit = {
    days: corpusDates.length,
    nonArtworkCards: auditedCardCount,
    heightSources: [...heightSources].sort(),
    clampedMaximumCards: clampedMaximumCount,
  };
  await corpusContext.close();
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, sampleDate, results, corpusAudit }, null, 2));
