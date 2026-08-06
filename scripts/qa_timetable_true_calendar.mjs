#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const sampleDate = "2026-07-16";
const browser = await chromium.launch({ headless: true });
const results = [];

function minutes(value) {
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

try {
  for (const viewport of [
    { width: 1440, height: 900, label: "desktop" },
    { width: 390, height: 844, label: "mobile" },
  ]) {
    const context = await browser.newContext({
      viewport,
      isMobile: viewport.width < 500,
      hasTouch: viewport.width < 500,
      deviceScaleFactor: viewport.width < 500 ? 2 : 1,
    });
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const sampleUrl = new URL(baseUrl);
    sampleUrl.searchParams.set("date", sampleDate);
    await page.goto(sampleUrl.href, { waitUntil: "networkidle" });
    await page.waitForSelector(`#dayDialog.is-open[data-selected-date="${sampleDate}"]`);
    await page.waitForTimeout(240);
    assert.equal(
      (await page.locator("#dialogDate").textContent())?.trim(),
      "2026-07-16 · Thursday / 2026年7月16日 · 星期四",
      `${viewport.label} day detail must show the bilingual weekday`,
    );

    const geometry = await page.evaluate(() => {
      const timeline = document.querySelector(".timeline-list");
      const timelineRect = timeline.getBoundingClientRect();
      const eventLayerRect = timeline.querySelector(".timeline-events-layer").getBoundingClientRect();
      const minuteHeight = Number.parseFloat(getComputedStyle(timeline).getPropertyValue("--minute-height"));
      return {
        minuteHeight,
        timelineHeight: timelineRect.height,
        horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        events: [...document.querySelectorAll(".timeline-event")].map((element) => {
          const rect = element.getBoundingClientRect();
          return {
            start: element.dataset.start,
            end: element.dataset.end,
            lane: Number(element.dataset.lane),
            laneCount: Number(element.dataset.laneCount),
            duration: Number(element.dataset.durationMinutes),
            top: rect.top - eventLayerRect.top,
            height: rect.height,
            left: rect.left,
            right: rect.right,
            origin: element.classList.contains("assigned-event")
              ? "assigned"
              : element.classList.contains("autonomous-event")
                ? "self"
                : "background",
          };
        }),
      };
    });

    assert.ok(Math.abs(geometry.timelineHeight - 1440 * geometry.minuteHeight) <= 2, JSON.stringify(geometry));
    assert.ok(geometry.events.length > 20, "representative day needs parallel routine evidence");
    assert.ok(geometry.events.some((event) => event.laneCount > 1), "overlapping events must use multiple lanes");
    assert.ok(geometry.events.some((event) => event.origin === "background" && event.lane > 0));
    assert.ok(geometry.horizontalOverflow <= 1, `${viewport.label} horizontal overflow`);

    const autonomousAccessibility = await page.locator(".autonomous-event").evaluate((element) => {
      const card = document.querySelector(".autonomous-work-link");
      const previewLink = card?.querySelector(".autonomous-preview-frame");
      const actionLink = card?.querySelector(".autonomous-open-copy");
      return {
        footprintHidden: element.getAttribute("aria-hidden"),
        eventName: element.getAttribute("aria-label"),
        cardName: card?.getAttribute("aria-label"),
        cardTag: card?.tagName,
        cardRole: card?.getAttribute("role"),
        cardTabindex: card?.getAttribute("tabindex"),
        previewTag: previewLink?.tagName,
        previewName: previewLink?.getAttribute("aria-label"),
        previewHref: previewLink?.href,
        actionTag: actionLink?.tagName,
        actionHref: actionLink?.href,
      };
    });
    assert.equal(autonomousAccessibility.footprintHidden, "true");
    assert.equal(autonomousAccessibility.eventName, null);
    assert.equal(autonomousAccessibility.cardTag, "ARTICLE");
    assert.equal(autonomousAccessibility.cardRole, null);
    assert.equal(autonomousAccessibility.cardTabindex, null);
    assert.match(autonomousAccessibility.cardName || "", /03:17-04:17, 60-minute autonomous event/);
    assert.equal(autonomousAccessibility.previewTag, "A");
    assert.match(autonomousAccessibility.previewName || "", /Open complete live work/);
    assert.equal(autonomousAccessibility.actionTag, "A");
    assert.equal(autonomousAccessibility.previewHref, autonomousAccessibility.actionHref);

    for (const event of geometry.events) {
      const expectedTop = minutes(event.start) * geometry.minuteHeight;
      const expectedHeight = event.duration * geometry.minuteHeight;
      assert.ok(Math.abs(event.top - expectedTop) <= 0.25, `${viewport.label} top ${JSON.stringify(event)}`);
      assert.ok(Math.abs(event.height - expectedHeight) <= 0.25, `${viewport.label} height ${JSON.stringify(event)}`);
    }

    for (let leftIndex = 0; leftIndex < geometry.events.length; leftIndex += 1) {
      for (let rightIndex = leftIndex + 1; rightIndex < geometry.events.length; rightIndex += 1) {
        const left = geometry.events[leftIndex];
        const right = geometry.events[rightIndex];
        const overlapsInTime = minutes(left.start) < minutes(right.end) && minutes(right.start) < minutes(left.end);
        if (!overlapsInTime) continue;
        const separatedHorizontally = left.right <= right.left + 1 || right.right <= left.left + 1;
        assert.ok(separatedHorizontally, `${viewport.label} overlap columns collide: ${JSON.stringify({ left, right })}`);
      }
    }

    if (viewport.label === "desktop") {
      const hoverTarget = page.locator(".routine-reading-card").first();
      await hoverTarget.hover({ force: true });
      const expanded = await hoverTarget.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return {
          width: rect.width,
          height: rect.height,
          right: rect.right,
          viewportWidth: innerWidth,
          overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
          summaryDisplay: getComputedStyle(element.querySelector(".pulse-summary")).display,
          transform: getComputedStyle(element).transform,
        };
      });
      assert.ok(expanded.width >= 48 && expanded.height >= 48, JSON.stringify(expanded));
      assert.ok(expanded.right <= expanded.viewportWidth + 1, JSON.stringify(expanded));
      assert.ok(expanded.overflow <= 1, JSON.stringify(expanded));
      assert.notEqual(expanded.summaryDisplay, "none");
      assert.equal(expanded.transform, "none");
      await page.mouse.move(0, 0);
    } else {
      const touchToggle = page.locator("#timelineTouchToggle");
      const toggleBox = await touchToggle.boundingBox();
      assert.ok(toggleBox && toggleBox.height >= 44 && toggleBox.width >= 44, JSON.stringify(toggleBox));
      await touchToggle.tap();
      assert.equal(await touchToggle.getAttribute("aria-expanded"), "true");
      const touchControls = page.locator(".timeline-touch-control");
      assert.equal(await touchControls.count(), geometry.events.length);
      const targetGeometry = await touchControls.evaluateAll((controls) => controls.map((control) => {
        const rect = control.getBoundingClientRect();
        return { width: rect.width, height: rect.height };
      }));
      assert.ok(
        targetGeometry.every((target) => target.width >= 44 && target.height >= 44),
        JSON.stringify(targetGeometry),
      );
      const concurrencyLabels = await page.locator(".timeline-touch-group h4").allTextContents();
      assert.ok(concurrencyLabels.some((label) => /up to \d+ concurrent/.test(label)), JSON.stringify(concurrencyLabels));
      assert.ok(concurrencyLabels.every((label) => /^\d{2}:\d{2}-\d{2}:\d{2}/.test(label)), JSON.stringify(concurrencyLabels));
      const autonomousTouchName = await page.locator(".autonomous-touch-control").getAttribute("aria-label");
      assert.match(autonomousTouchName || "", /03:17-04:17, 60-minute autonomous event/);
      await touchToggle.tap();
      assert.equal(await touchToggle.getAttribute("aria-expanded"), "false");
    }

    const pulse = page.locator(".routine-reading-card").first();
    if (viewport.label === "mobile") {
      await pulse.tap();
      assert.equal(await pulse.getAttribute("aria-pressed"), "true");
      assert.equal(await pulse.getAttribute("aria-expanded"), null);
      await pulse.tap();
    } else {
      await pulse.click({ force: true });
    }
    await page.waitForSelector("#taskDialog.is-open");
    assert.ok(((await page.locator("#taskDetailZh").textContent()) || "").trim().length > 20);
    assert.ok(((await page.locator("#taskDetailEn").textContent()) || "").trim().length > 20);
    assert.equal((await page.locator("#taskDetailProvenance").textContent())?.trim(), "");
    assert.equal(await page.locator("#taskDetailProvenance").isHidden(), true);
    await page.keyboard.press("Escape");

    results.push({
      label: viewport.label,
      timelineHeight: Math.round(geometry.timelineHeight),
      eventCount: geometry.events.length,
      maxLanes: Math.max(...geometry.events.map((event) => event.laneCount)),
      pageErrors,
    });
    assert.deepEqual(pageErrors, []);
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, results }, null, 2));
