#!/usr/bin/env node
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:4179/timetable/";
const screenshotRoot = process.env.QA_SCREENSHOT_DIR || "";
const prototypeDates = [
  "2026-08-06",
  "2026-08-07",
  "2026-08-08",
  "2026-08-09",
  "2026-08-10",
  "2026-08-11",
  "2026-08-12",
];
const dayByDate = new Map(timetableData.days.map((day) => [day.date, day]));
const responsiveCases = [
  { label: "desktop", width: 1440, height: 900, touch: false },
  { label: "mobile-390", width: 390, height: 844, touch: true },
  { label: "short-touch", width: 421, height: 386, touch: true },
  { label: "desktop-4k", width: 3840, height: 2160, touch: false },
];

const browser = await chromium.launch({ headless: true });
const results = [];

async function createContext(viewport, theme = "dark") {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height },
    colorScheme: theme,
    isMobile: viewport.touch,
    hasTouch: viewport.touch,
    deviceScaleFactor: viewport.touch ? 2 : 1,
  });
  await context.addInitScript((selectedTheme) => {
    localStorage.setItem("granted-hours-theme", selectedTheme);
  }, theme);
  await context.route("**/archive/**", (route) => {
    const type = route.request().resourceType();
    if (type === "image") {
      route.fulfill({
        status: 200,
        contentType: "image/png",
        body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=", "base64"),
      });
      return;
    }
    route.fulfill({ status: 204, body: "" });
  });
  return context;
}

async function openDay(page, date) {
  const url = new URL(baseUrl);
  url.searchParams.set("date", date);
  url.searchParams.set("regression", "pcb-prototype");
  await page.goto(url.href, { waitUntil: "domcontentloaded" });
  await page.waitForFunction(() => (
    document.querySelector("#dayDialog:not([hidden])")
    && document.querySelector(".timeline-reading-layer.is-placed")
  ));
  await page.waitForTimeout(350);
  await waitForPlacedCards(page);
}

async function waitForPlacedCards(page) {
  await page.waitForFunction(() => {
    const cards = [...document.querySelectorAll(".timeline-reading-layer .event-reading-card")];
    return cards.length > 0
      && document.querySelector(".timeline-reading-layer.is-placed")
      && cards.every((card) => card.dataset.edgeAnchored === "true");
  });
}

async function inspect(page) {
  return page.evaluate(() => {
    const dialog = document.querySelector("#dayDialog");
    const timeline = document.querySelector("#timelineList");
    const readingLayer = timeline.querySelector(".timeline-reading-layer");
    const readingRect = readingLayer.getBoundingClientRect();
    const timelineRect = timeline.getBoundingClientRect();
    const toolbar = document.querySelector(".dialog-toolbar");
    const toggle = document.querySelector("#dayViewToggle");
    const close = document.querySelector("#closeDetail");
    const toggleRect = toggle.getBoundingClientRect();
    const closeRect = close.getBoundingClientRect();
    const cards = [...timeline.querySelectorAll(".event-reading-card")].map((card) => {
      const rect = card.getBoundingClientRect();
      const style = getComputedStyle(card);
      const hardware = card.querySelector(".pcb-chip-hardware");
      return {
        readingId: card.dataset.readingId,
        layer: card.dataset.layer,
        size: card.dataset.pcbSize,
        family: card.dataset.pcbFamily,
        reference: card.dataset.pcbReference,
        edgeSide: card.dataset.edgeSide,
        edgeAnchored: card.dataset.edgeAnchored,
        memberIds: (card.dataset.memberFootprintIds || "").split(/\s+/).filter(Boolean),
        left: rect.left,
        right: rect.right,
        top: rect.top - timelineRect.top,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height,
        area: rect.width * rect.height,
        borderRadius: style.borderRadius,
        backgroundColor: style.backgroundColor,
        hardwareDisplay: hardware ? getComputedStyle(hardware).display : "missing",
      };
    });
    const footprints = [...timeline.querySelectorAll(".timeline-event[data-footprint-id]")].map((event) => {
      const rect = event.getBoundingClientRect();
      return {
        id: event.dataset.footprintId,
        start: event.dataset.start,
        end: event.dataset.end,
        top: rect.top,
        height: rect.height,
      };
    });
    const connectors = [...timeline.querySelectorAll(".event-connector")].map((connector) => ({
      key: connector.dataset.eventKey,
      opacity: Number(getComputedStyle(connector).opacity),
      width: connector.getBoundingClientRect().width,
    }));
    return {
      date: dialog.dataset.selectedDate,
      mode: dialog.dataset.viewMode,
      eligible: dialog.dataset.pcbPrototype,
      toggleHidden: toggle.hidden,
      togglePressed: toggle.getAttribute("aria-pressed"),
      title: document.querySelector("#timelineTitle").textContent,
      prototypeNoteHidden: document.querySelector("#dayViewPrototypeNote").hidden,
      timelineBackground: getComputedStyle(timeline).backgroundImage,
      horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      toolbarOverflow: toolbar.scrollWidth - toolbar.clientWidth,
      toggleBeforeClose: toggleRect.right <= closeRect.left + 0.5,
      toggleAligned: Math.abs(toggleRect.top - closeRect.top) <= 0.5,
      readingRect: { left: readingRect.left, right: readingRect.right },
      cards,
      footprints,
      connectors,
    };
  });
}

function assertPcbState(state, expectedDay, label) {
  assert.equal(state.mode, "pcb", `${label}: PCB mode did not activate`);
  assert.equal(state.eligible, "eligible", `${label}: prototype eligibility missing`);
  assert.equal(state.togglePressed, "true", `${label}: toggle pressed state`);
  assert.equal(state.prototypeNoteHidden, false, `${label}: prototype scope note missing`);
  assert.match(state.title, /PCB DAY MAP/, `${label}: PCB title missing`);
  assert.ok(state.timelineBackground !== "none", `${label}: board material missing`);
  assert.equal(state.cards.length, expectedDay.reading_items.length, `${label}: reading count changed`);
  assert.equal(state.footprints.length, expectedDay.timeline_events.length, `${label}: footprint count changed`);
  assert.equal(state.connectors.length, state.cards.length, `${label}: connector count changed`);
  assert.ok(state.cards.every((card) => card.hardwareDisplay === "block"), `${label}: chip hardware missing`);
  assert.ok(state.cards.every((card) => card.reference && card.family && card.size), `${label}: chip package metadata missing`);
  assert.ok(state.cards.every((card) => card.edgeAnchored === "true"), `${label}: centered chip returned`);
  assert.ok(state.cards.every((card) => (
    card.edgeSide === "left"
      ? Math.abs(card.left - state.readingRect.left) <= 0.75
      : Math.abs(card.right - state.readingRect.right) <= 0.75
  )), `${label}: chip no longer interrupts a board edge`);
  assert.ok(state.connectors.every((connector) => connector.opacity >= 0.6 && connector.width > 0), `${label}: a trace is not visible`);
  assert.ok(state.horizontalOverflow <= 1, `${label}: page horizontal overflow`);
  assert.ok(state.toolbarOverflow <= 1, `${label}: toolbar overflow`);
  assert.ok(state.toggleBeforeClose && state.toggleAligned, `${label}: PCB toggle is not aligned beside Close`);
  const main = state.cards.filter((card) => card.size === "main");
  assert.equal(main.length, 1, `${label}: autonomous main chip count`);
  assert.equal(main[0].reference, "AI–CORE", `${label}: autonomous main chip identity`);
  assert.ok(
    main[0].area >= Math.max(0, ...state.cards.filter((card) => card.size !== "main").map((card) => card.area)) - 1,
    `${label}: autonomous artwork is not the largest chip`,
  );
}

try {
  const context = await createContext(responsiveCases[0]);
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const packageSizes = new Set();

  await openDay(page, prototypeDates[0]);
  for (const [dateIndex, date] of prototypeDates.entries()) {
    console.log(`PCB prototype date QA: ${date}`);
    if (dateIndex > 0) {
      await page.locator("#nextDay").click();
      await page.waitForFunction(
        (expectedDate) => document.querySelector("#dayDialog").dataset.selectedDate === expectedDate,
        date,
      );
      await waitForPlacedCards(page);
    }
    const expectedDay = dayByDate.get(date);
    assert.ok(expectedDay, `${date}: missing source day`);
    const standardBefore = await inspect(page);
    assert.equal(standardBefore.mode, "standard", `${date}: fresh entry must default to normal`);
    assert.equal(standardBefore.toggleHidden, false, `${date}: PCB switch hidden`);
    assert.equal(standardBefore.cards.length, expectedDay.reading_items.length, `${date}: normal reading count`);
    assert.equal(standardBefore.footprints.length, expectedDay.timeline_events.length, `${date}: normal footprint count`);
    assert.ok(standardBefore.cards.every((card) => card.hardwareDisplay === "none"), `${date}: PCB hardware leaked into normal view`);

    const footprintGeometry = new Map(standardBefore.footprints.map((footprint) => [footprint.id, footprint]));
    await page.locator("#dayViewToggle").click({ force: true });
    await page.waitForFunction(() => document.querySelector("#dayDialog").dataset.viewMode === "pcb");
    await page.waitForTimeout(80);
    await waitForPlacedCards(page);
    const pcb = await inspect(page);
    assertPcbState(pcb, expectedDay, date);
    pcb.cards.forEach((card) => packageSizes.add(card.size));
    for (const footprint of pcb.footprints) {
      const original = footprintGeometry.get(footprint.id);
      assert.ok(original, `${date}: unknown footprint after switching`);
      assert.equal(footprint.start, original.start, `${date}: start changed`);
      assert.equal(footprint.end, original.end, `${date}: end changed`);
      assert.ok(Number.isFinite(footprint.top) && footprint.height > 0, `${date}: invalid projected footprint geometry`);
    }

    await page.locator("#dayViewToggle").click({ force: true });
    await page.waitForFunction(() => document.querySelector("#dayDialog").dataset.viewMode === "standard");
    const standardAfter = await inspect(page);
    assert.ok(standardAfter.cards.every((card) => card.hardwareDisplay === "none"), `${date}: normal rollback failed`);
    results.push({ date, cards: pcb.cards.length, footprints: pcb.footprints.length });
  }

  assert.ok(packageSizes.has("main") && packageSizes.has("large") && packageSizes.size >= 3, "prototype lacks visibly different package classes");
  assert.deepEqual(errors, [], "desktop prototype page errors");

  await openDay(page, "2026-08-05");
  const outside = await inspect(page);
  assert.equal(outside.mode, "standard", "outside range must remain normal");
  assert.equal(outside.eligible, "outside-range", "outside range eligibility");
  assert.equal(outside.toggleHidden, true, "outside range switch must be hidden");

  await openDay(page, "2026-08-11");
  await page.locator("#dayViewToggle").click({ force: true });
  await page.locator("#prevDay").click();
  await page.waitForFunction(() => document.querySelector("#dayDialog").dataset.selectedDate === "2026-08-10");
  assert.equal((await inspect(page)).mode, "pcb", "PCB comparison mode should persist inside the seven-day range");
  for (let step = 0; step < 5; step += 1) {
    await page.locator("#prevDay").click();
  }
  await page.waitForFunction(() => document.querySelector("#dayDialog").dataset.selectedDate === "2026-08-05");
  const navigatedOutside = await inspect(page);
  assert.equal(navigatedOutside.mode, "standard", "leaving prototype range must restore normal mode");
  assert.equal(navigatedOutside.toggleHidden, true, "leaving prototype range must hide switch");
  await context.close();

  for (const viewport of responsiveCases) {
    console.log(`PCB responsive QA: ${viewport.label}`);
    const responsiveContext = await createContext(viewport, viewport.label === "short-touch" ? "light" : "dark");
    const responsivePage = await responsiveContext.newPage();
    const pageErrors = [];
    responsivePage.on("pageerror", (error) => pageErrors.push(error.message));
    await openDay(responsivePage, "2026-08-11");
    await responsivePage.locator("#dayViewToggle").click({ force: true });
    await responsivePage.waitForFunction(() => document.querySelector("#dayDialog").dataset.viewMode === "pcb");
    await responsivePage.waitForTimeout(80);
    await waitForPlacedCards(responsivePage);
    const state = await inspect(responsivePage);
    assertPcbState(state, dayByDate.get("2026-08-11"), viewport.label);
    assert.deepEqual(pageErrors, [], `${viewport.label}: page errors`);
    if (screenshotRoot) {
      await mkdir(screenshotRoot, { recursive: true });
      await responsivePage.locator('.event-reading-card[data-pcb-size="main"]').scrollIntoViewIfNeeded();
      await responsivePage.screenshot({
        path: path.join(screenshotRoot, `pcb-${viewport.label}.png`),
        fullPage: false,
        animations: "disabled",
      });
    }
    results.push({ viewport: viewport.label, cards: state.cards.length, footprints: state.footprints.length });
    await responsiveContext.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ ok: true, prototypeDates, results }, null, 2));
