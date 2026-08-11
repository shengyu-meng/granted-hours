#!/usr/bin/env node
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8892/timetable/";
const screenshotRoot = process.env.QA_SCREENSHOT_DIR || "";
const sampleDate = "2026-08-11";
const cases = [
  { label: "desktop-dark", width: 1440, height: 900, theme: "dark" },
  { label: "desktop-light", width: 1440, height: 900, theme: "light" },
  { label: "desktop-4k", width: 3840, height: 2160, theme: "dark" },
  { label: "mobile-390", width: 390, height: 844, theme: "dark", mobile: true },
  { label: "short-touch", width: 421, height: 386, theme: "light", mobile: true },
];

const browser = await chromium.launch({ headless: true });
const results = [];
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
    url.searchParams.set("date", sampleDate);
    url.searchParams.set("regression", "stratigraphic-detail");
    await page.goto(url.href, { waitUntil: "networkidle" });
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
          left: rect.left,
          right: rect.right,
          top: rect.top,
          bottom: rect.bottom,
          width: rect.width,
          height: rect.height,
          opacity: Number(style.opacity),
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
    assert.ok(state.footprints.length >= 100, `${testCase.label}: dense source footprints were lost`);
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
      state.cards.every((card) => card.borderRadius.startsWith("18px") && card.backdropFilter.includes("blur")),
      `${testCase.label}: embedded cards lost rounded frosted material`,
    );
    assert.ok(
      state.cards.filter((card) => card.layer === "climate").every((card) => card.opacity >= 0.45 && card.opacity <= 0.75),
      `${testCase.label}: climate reading cards no longer recede`,
    );
    assert.ok(
      state.cards.filter((card) => card.memberCount > 1).every((card) => (
        Math.abs(card.anchorMinute - card.medianMinute) <= 0.01
        && card.anchorDisplacement <= 96
      )),
      `${testCase.label}: an aggregate card is detached from its strata`,
    );
    assert.ok(
      new Set(state.cards.filter((card) => card.layer !== "beacon").map((card) => Math.round(card.height))).size >= 2,
      `${testCase.label}: card height no longer responds to content and duration`,
    );
    if (testCase.mobile) {
      const eventCards = state.cards.filter((card) => card.layer === "event");
      const climateCards = state.cards.filter((card) => card.layer === "climate");
      assert.ok(eventCards.every((card) => card.columnSpan === 3), `${testCase.label}: informative events are not full reading width`);
      assert.ok(climateCards.every((card) => card.columnSpan === 2), `${testCase.label}: climate cards do not leave a visible stratum lane`);
    }

    const hoverCard = page.locator('.event-reading-card[data-layer="event"]').first();
    await hoverCard.scrollIntoViewIfNeeded();
    await page.mouse.move(testCase.width - 8, 8);
    await page.waitForTimeout(340);
    if (screenshotRoot) {
      await mkdir(screenshotRoot, { recursive: true });
      await page.screenshot({
        path: path.join(screenshotRoot, `${testCase.label}-resting.png`),
        fullPage: false,
        animations: "disabled",
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
      minuteHeight: state.minuteHeight,
      timelineHeight: state.timelineHeight,
      footprints: state.footprints.length,
      cards: state.cards.length,
      maximumAggregateDisplacement: Math.max(
        0,
        ...state.cards.filter((card) => card.memberCount > 1).map((card) => card.anchorDisplacement),
      ),
    });
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, sampleDate, results }, null, 2));
