#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const sampleDate = "2026-07-24";
const sampleDay = timetableData.days.find((day) => day.date === sampleDate);
const viewports = [
  { width: 1440, height: 900, label: "desktop-wide", touch: false },
  { width: 1024, height: 768, label: "desktop-compact", touch: false },
  { width: 768, height: 700, label: "tablet", touch: false },
  { width: 390, height: 844, label: "mobile", touch: true },
  { width: 421, height: 386, label: "short-touch", touch: true },
];
let routineCorpusCount = 0;

for (const day of timetableData.days) {
  for (const event of day.timeline_events.filter((item) => item.origin === "background")) {
    assert.ok(event.label_zh?.trim() && event.label_en?.trim(), `${day.date}: missing bilingual routine title`);
    assert.ok(event.summary_zh?.trim() && event.summary_en?.trim(), `${day.date}: missing date-specific routine summary`);
    routineCorpusCount += 1;
  }
}
assert.ok(routineCorpusCount > 0);

function minutes(value) {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function rangesOverlap(leftStart, leftEnd, rightStart, rightEnd, tolerance = 1) {
  return leftStart < rightEnd - tolerance && rightStart < leftEnd - tolerance;
}

async function installOfflineAutonomousTarget(context) {
  await context.route(
    "https://shengyu-meng.github.io/granted-hours/archive/**",
    (route) => route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<!doctype html><title>Offline autonomous target</title>",
    }),
  );
}

async function inspectComposition(page) {
  return page.evaluate(() => {
    const timeline = document.querySelector(".timeline-list");
    const eventLayer = timeline.querySelector(".timeline-events-layer");
    const timelineRect = timeline.getBoundingClientRect();
    const eventLayerRect = eventLayer.getBoundingClientRect();
    const minuteHeight = Number.parseFloat(getComputedStyle(timeline).getPropertyValue("--minute-height"));
    const events = [...document.querySelectorAll(".timeline-event")].map((event) => {
      const rect = event.getBoundingClientRect();
      return {
        key: event.dataset.eventKey,
        start: event.dataset.start,
        end: event.dataset.end,
        duration: Number(event.dataset.durationMinutes),
        lane: Number(event.dataset.lane),
        laneCount: Number(event.dataset.laneCount),
        top: rect.top - eventLayerRect.top,
        height: rect.height,
        left: rect.left,
        right: rect.right,
        origin: event.classList.contains("assigned-event")
          ? "assigned"
          : event.classList.contains("autonomous-event")
            ? "self"
            : "background",
      };
    });
    const cards = [...document.querySelectorAll(".event-reading-card")].map((card) => {
      const rect = card.getBoundingClientRect();
      const style = getComputedStyle(card);
      const title = card.querySelector(".reading-title");
      const summary = card.querySelector(".reading-summary");
      return {
        key: card.dataset.eventKey,
        origin: card.dataset.origin,
        left: rect.left,
        right: rect.right,
        top: rect.top - timelineRect.top,
        bottom: rect.bottom - timelineRect.top,
        width: rect.width,
        height: rect.height,
        title: title?.textContent?.trim() || "",
        titleVisible: Boolean(title) && getComputedStyle(title).display !== "none"
          && getComputedStyle(title).visibility !== "hidden",
        summary: summary?.textContent?.trim() || "",
        summaryVisible: Boolean(summary) && getComputedStyle(summary).display !== "none"
          && getComputedStyle(summary).visibility !== "hidden",
        zIndex: style.zIndex,
      };
    });
    const connectors = [...document.querySelectorAll(".event-connector")].map((connector) => {
      const rect = connector.getBoundingClientRect();
      const style = getComputedStyle(connector);
      return {
        key: connector.dataset.eventKey,
        width: rect.width,
        height: rect.height,
        visible: style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0,
      };
    });
    return {
      minuteHeight,
      timelineHeight: timelineRect.height,
      eventLayerHeight: eventLayerRect.height,
      events,
      cards,
      connectors,
      footprintCount: document.querySelectorAll(".event-footprint").length,
      horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      panelScrollable: document.querySelector("#dayDialogPanel").scrollHeight
        > document.querySelector("#dayDialogPanel").clientHeight,
    };
  });
}

async function inspectAutonomousRegions(page) {
  return page.locator(".autonomous-reading-card").evaluate((card) => {
    const cardRect = card.getBoundingClientRect();
    const selectors = {
      time: ".autonomous-time",
      title: ".reading-title",
      summary: ".reading-summary",
      action: ".autonomous-open-copy",
      preview: ".autonomous-preview-frame",
    };
    const regions = Object.entries(selectors).map(([name, selector]) => {
      const element = card.querySelector(selector);
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return {
        name,
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height,
        visible: style.display !== "none"
          && style.visibility !== "hidden"
          && rect.width > 0
          && rect.height > 0,
      };
    });
    return {
      card: {
        left: cardRect.left,
        right: cardRect.right,
        top: cardRect.top,
        bottom: cardRect.bottom,
      },
      regions,
    };
  });
}

async function inspectLinkedState(page) {
  return page.evaluate(() => ({
    cards: [...document.querySelectorAll(".event-reading-card.is-linked-active")]
      .map((element) => element.dataset.readingId),
    events: [...document.querySelectorAll(".timeline-event.is-linked-active")]
      .map((element) => element.dataset.footprintId),
    footprints: [...document.querySelectorAll(".event-footprint.is-linked-active")]
      .map((element) => element.closest(".timeline-event")?.dataset.footprintId),
    connectors: [...document.querySelectorAll(".event-connector.is-linked-active")]
      .map((element) => element.dataset.eventKey),
  }));
}

async function expectedLinkedState(card) {
  const readingId = await card.getAttribute("data-reading-id");
  const memberIds = ((await card.getAttribute("data-member-footprint-ids")) || "")
    .split(" ")
    .filter(Boolean);
  return {
    cards: [readingId],
    events: memberIds,
    footprints: memberIds,
    connectors: [readingId],
  };
}

const browser = await chromium.launch({ headless: true });
const results = [];

try {
  for (const viewport of viewports) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.touch,
      hasTouch: viewport.touch,
      deviceScaleFactor: viewport.touch ? 2 : 1,
    });
    await installOfflineAutonomousTarget(context);
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.locator(`.calendar-day-button[data-date="${sampleDate}"]`).click();
    await page.waitForSelector("#dayDialog.is-open");
    await page.waitForFunction(
      () => document.querySelector(".timeline-reading-layer.is-placed")
        && document.querySelectorAll(".event-reading-card").length > 0,
    );

    const composition = await inspectComposition(page);
    assert.equal(composition.events.length, 106, `${viewport.label}: representative event count changed`);
    assert.equal(composition.footprintCount, composition.events.length, `${viewport.label}: footprint split`);
    assert.equal(composition.cards.length, sampleDay.reading_items.length, `${viewport.label}: reading projection`);
    assert.ok(composition.cards.length < composition.events.length, `${viewport.label}: reading layer must aggregate`);
    assert.equal(composition.connectors.length, composition.cards.length, `${viewport.label}: connector split`);
    assert.equal(await page.locator(".timeline-events-layer").getAttribute("aria-hidden"), "true");
    assert.equal(await page.locator(".timeline-events-layer").getAttribute("role"), null);
    assert.equal(await page.locator(".timeline-event[role='listitem']").count(), 0);
    assert.equal(await page.locator(".timeline-reading-layer").getAttribute("role"), "group");
    assert.ok(
      Math.abs(composition.timelineHeight - composition.minuteHeight * 1440) <= 2,
      `${viewport.label}: timeline scale ${JSON.stringify(composition)}`,
    );
    assert.ok(Math.abs(composition.eventLayerHeight - composition.timelineHeight) <= 2.1);
    assert.ok(composition.horizontalOverflow <= 1, `${viewport.label}: horizontal overflow`);
    assert.equal(composition.panelScrollable, true);
    assert.deepEqual(pageErrors, [], `${viewport.label}: page errors`);

    for (const event of composition.events) {
      const expectedTop = minutes(event.start) * composition.minuteHeight;
      const expectedHeight = event.duration * composition.minuteHeight;
      assert.ok(Math.abs(event.top - expectedTop) <= 0.25, `${viewport.label}: exact top ${JSON.stringify(event)}`);
      assert.ok(Math.abs(event.height - expectedHeight) <= 0.25, `${viewport.label}: exact height ${JSON.stringify(event)}`);
    }

    for (let leftIndex = 0; leftIndex < composition.events.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < composition.events.length; rightIndex += 1) {
        const left = composition.events[leftIndex];
        const right = composition.events[rightIndex];
        if (!rangesOverlap(minutes(left.start), minutes(left.end), minutes(right.start), minutes(right.end), 0)) continue;
        assert.ok(
          !rangesOverlap(left.left, left.right, right.left, right.right),
          `${viewport.label}: exact overlap lanes collide ${JSON.stringify({ left, right })}`,
        );
      }
    }

    const routines = composition.cards.filter((card) => card.origin === "background");
    assert.ok(routines.length > 0);
    for (const routine of routines) {
      assert.ok(routine.height >= 48, `${viewport.label}: routine under 48px ${JSON.stringify(routine)}`);
      assert.ok(routine.titleVisible && routine.title.includes("/"), `${viewport.label}: routine title ${JSON.stringify(routine)}`);
      assert.ok(routine.summaryVisible && routine.summary.length > 0, `${viewport.label}: routine summary ${JSON.stringify(routine)}`);
    }
    const assignedCards = composition.cards.filter((card) => card.origin === "assigned");
    assert.ok(assignedCards.length > 0);
    assert.ok(
      assignedCards.every((card) => card.height >= 48
        && card.titleVisible
        && card.title.includes("/")
        && card.summaryVisible
        && card.summary.length > 0),
      `${viewport.label}: assigned reading content ${JSON.stringify(assignedCards)}`,
    );

    for (let leftIndex = 0; leftIndex < composition.cards.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < composition.cards.length; rightIndex += 1) {
        const left = composition.cards[leftIndex];
        const right = composition.cards[rightIndex];
        if (!rangesOverlap(left.left, left.right, right.left, right.right)) continue;
        assert.ok(
          !rangesOverlap(left.top, left.bottom, right.top, right.bottom),
          `${viewport.label}: reading cards collide ${JSON.stringify({ left, right })}`,
        );
      }
    }
    assert.ok(
      composition.cards.every((card) => card.top >= -0.5 && card.bottom <= composition.timelineHeight + 0.5),
      `${viewport.label}: card outside 24-hour canvas`,
    );
    assert.ok(
      composition.connectors.every((connector) => connector.visible && (connector.width > 0 || connector.height > 0)),
      `${viewport.label}: missing visible connector`,
    );

    const autonomous = page.locator(".autonomous-reading-card");
    const autonomousBox = await autonomous.boundingBox();
    assert.ok(autonomousBox?.height >= 112, `${viewport.label}: autonomous reading card`);
    const autonomousFootprint = composition.events.find((event) => event.origin === "self");
    assert.ok(
      autonomousFootprint && autonomousBox.height > autonomousFootprint.height,
      `${viewport.label}: autonomous card must exceed its exact footprint`,
    );
    const preview = await autonomous.locator("#selfPreview").evaluate(async (image) => {
      await image.decode();
      const rect = image.getBoundingClientRect();
      const frameRect = image.closest(".autonomous-preview-frame").getBoundingClientRect();
      return {
        width: image.naturalWidth,
        height: image.naturalHeight,
        renderedWidth: rect.width,
        renderedHeight: rect.height,
        frameWidth: frameRect.width,
        frameHeight: frameRect.height,
        visible: getComputedStyle(image).display !== "none"
          && getComputedStyle(image).visibility !== "hidden",
        src: image.currentSrc || image.src,
      };
    });
    assert.ok(
      preview.width > 0
        && preview.height > 0
        && preview.renderedWidth > 0
        && preview.renderedHeight > 0
        && preview.frameWidth > 0
        && preview.frameHeight >= 52
        && preview.visible,
      `${viewport.label}: ${JSON.stringify(preview)}`,
    );
    const naturalRatio = preview.width / preview.height;
    assert.ok(
      Math.abs((preview.frameWidth / preview.frameHeight) - naturalRatio) <= 0.08,
      `${viewport.label}: autonomous preview frame must preserve the artwork thumbnail aspect ratio ${JSON.stringify(preview)}`,
    );
    assert.ok(
      Math.abs((preview.renderedWidth / preview.renderedHeight) - naturalRatio) <= 0.08,
      `${viewport.label}: autonomous preview image must not be compressed inside its frame ${JSON.stringify(preview)}`,
    );
    assert.match(preview.src, /visual-preview\.gif$/);

    if (viewport.label === "short-touch") {
      const autonomousRegions = await inspectAutonomousRegions(page);
      const visibleRegions = autonomousRegions.regions.filter((region) => region.visible);
      assert.ok(
        visibleRegions.some((region) => region.name === "time")
          && visibleRegions.some((region) => region.name === "title")
          && visibleRegions.some((region) => region.name === "summary")
          && visibleRegions.some((region) => region.name === "preview"),
        `short-touch: missing primary autonomous region ${JSON.stringify(autonomousRegions)}`,
      );
      for (const region of visibleRegions) {
        assert.ok(
          region.left >= autonomousRegions.card.left - 0.5
            && region.right <= autonomousRegions.card.right + 0.5
            && region.top >= autonomousRegions.card.top - 0.5
            && region.bottom <= autonomousRegions.card.bottom + 0.5,
          `short-touch: autonomous region outside card ${JSON.stringify({ region, card: autonomousRegions.card })}`,
        );
      }
      for (let leftIndex = 0; leftIndex < visibleRegions.length; leftIndex += 1) {
        for (let rightIndex = leftIndex + 1; rightIndex < visibleRegions.length; rightIndex += 1) {
          const left = visibleRegions[leftIndex];
          const right = visibleRegions[rightIndex];
          assert.ok(
            !rangesOverlap(left.left, left.right, right.left, right.right, 0.5)
              || !rangesOverlap(left.top, left.bottom, right.top, right.bottom, 0.5),
            `short-touch: autonomous regions intersect ${JSON.stringify({ left, right })}`,
          );
        }
      }
    }

    if (viewport.touch) {
      const routine = page.locator(".routine-reading-card").first();
      await routine.scrollIntoViewIfNeeded();
      await routine.tap();
      assert.equal(await routine.getAttribute("aria-pressed"), "true", `${viewport.label}: first tap selects`);
      assert.equal(await routine.getAttribute("aria-expanded"), null, `${viewport.label}: selection is not expansion`);
      assert.equal(await page.locator("#taskDialog").getAttribute("hidden"), "", `${viewport.label}: first tap must not activate`);
      assert.match(await routine.getAttribute("aria-label"), /tap again to open/);
      const routineLinkedState = await expectedLinkedState(routine);
      assert.deepEqual(
        await inspectLinkedState(page),
        routineLinkedState,
        `${viewport.label}: first tap must link every matching footprint and one connector`,
      );
      await page.locator("#timelineTitle").tap();
      assert.equal(await routine.getAttribute("aria-pressed"), "false", `${viewport.label}: outside tap clears`);
      assert.deepEqual(
        await inspectLinkedState(page),
        { cards: [], events: [], footprints: [], connectors: [] },
        `${viewport.label}: outside tap must clear linked composition`,
      );
      await routine.tap();
      await routine.tap();
      await page.waitForSelector("#taskDialog.is-open");
      assert.ok(((await page.locator("#taskDetailEn").textContent()) || "").trim().length > 0);
      await page.keyboard.press("Escape");
      assert.equal(await page.evaluate(() => document.activeElement?.classList.contains("routine-reading-card")), true);

      const autonomousTouch = page.locator(".autonomous-reading-card");
      await autonomousTouch.scrollIntoViewIfNeeded();
      await autonomousTouch.tap();
      assert.equal(await autonomousTouch.getAttribute("aria-expanded"), null);
      assert.match(
        (await page.locator("#readingSelectionStatus").textContent()) || "",
        /Autonomous work selected/,
      );
      const popupPromise = page.waitForEvent("popup");
      await autonomousTouch.tap();
      const popup = await popupPromise;
      assert.match(popup.url(), /[?&]from=timetable(?:&|$)/);
      await popup.close();
    } else {
      const routine = page.locator(".routine-reading-card").first();
      await routine.scrollIntoViewIfNeeded();
      const routineLinkedState = await expectedLinkedState(routine);
      await routine.hover();
      assert.deepEqual(
        await inspectLinkedState(page),
        routineLinkedState,
        `${viewport.label}: hover must link matching footprint group and connector`,
      );
      const secondRoutine = page.locator(".routine-reading-card").nth(1);
      const secondRoutineLinkedState = await expectedLinkedState(secondRoutine);
      await secondRoutine.focus();
      assert.deepEqual(
        await inspectLinkedState(page),
        secondRoutineLinkedState,
        `${viewport.label}: keyboard focus must override a mouse left hovering another card`,
      );
      await page.locator("#timelineTitle").hover();
      await routine.hover();
      assert.deepEqual(
        await inspectLinkedState(page),
        secondRoutineLinkedState,
        `${viewport.label}: a new mouse hover must not override an already focused card`,
      );
      await page.locator("#closeDetail").focus();
      await page.locator("#timelineTitle").hover();
      assert.deepEqual(
        await inspectLinkedState(page),
        { cards: [], events: [], footprints: [], connectors: [] },
        `${viewport.label}: hover exit must clear linked composition`,
      );
      await routine.focus();
      assert.equal(await page.evaluate(() => document.activeElement?.classList.contains("routine-reading-card")), true);
      assert.deepEqual(
        await inspectLinkedState(page),
        routineLinkedState,
        `${viewport.label}: focus must link matching footprint group and connector`,
      );
      assert.notEqual(await routine.evaluate((card) => getComputedStyle(card).transform), "none");
      await page.keyboard.press("Enter");
      await page.waitForSelector("#taskDialog.is-open");
      await page.keyboard.press("Escape");
    }

    results.push({
      label: viewport.label,
      events: composition.events.length,
      routines: routines.length,
      minuteHeight: composition.minuteHeight,
      timelineHeight: Math.round(composition.timelineHeight),
    });
    await context.close();
  }

  const hybridContext = await browser.newContext({
    viewport: { width: 1024, height: 768 },
    isMobile: false,
    hasTouch: true,
  });
  const hybridPage = await hybridContext.newPage();
  await hybridPage.goto(baseUrl, { waitUntil: "networkidle" });
  assert.equal(
    await hybridPage.evaluate(() => matchMedia("(any-pointer: coarse)").matches),
    true,
    "hybrid QA must expose a coarse pointer alongside mouse input",
  );
  await hybridPage.locator(`.calendar-day-button[data-date="${sampleDate}"]`).click();
  await hybridPage.waitForSelector("#dayDialog.is-open");
  const hybridRoutine = hybridPage.locator(".routine-reading-card").first();
  await hybridRoutine.scrollIntoViewIfNeeded();
  await hybridRoutine.click();
  await hybridPage.waitForSelector("#taskDialog.is-open");
  assert.equal(
    await hybridRoutine.getAttribute("aria-pressed"),
    "false",
    "one real mouse click on a hybrid device must open rather than stage touch selection",
  );
  await hybridPage.keyboard.press("Escape");
  await hybridContext.close();

  const reducedContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    reducedMotion: "reduce",
  });
  const reducedPage = await reducedContext.newPage();
  await reducedPage.goto(baseUrl, { waitUntil: "networkidle" });
  await reducedPage.locator(`.calendar-day-button[data-date="${sampleDate}"]`).click();
  await reducedPage.waitForSelector("#dayDialog.is-open");
  const reducedCard = reducedPage.locator(".autonomous-reading-card");
  await reducedCard.tap();
  const reducedState = await reducedCard.evaluate((card) => ({
    transform: getComputedStyle(card).transform,
    transitionDuration: getComputedStyle(card).transitionDuration,
    image: card.querySelector("#selfPreview")?.getAttribute("src") || "",
  }));
  assert.equal(reducedState.transform, "none");
  assert.ok(reducedState.transitionDuration.split(",").every((duration) => duration.trim() === "0s"));
  assert.match(reducedState.image, /visual-preview\.webp$/);
  await reducedPage.locator("#selfPreview").evaluate((image) => image.decode());
  await reducedContext.close();
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, sampleDate, routineCorpusCount, results }, null, 2));
