#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "https://shengyu-meng.github.io/granted-hours/timetable/";
const metadataDays = JSON.parse(readFileSync(new URL("../metadata/days.json", import.meta.url), "utf8"));
const expectedDates = metadataDays.map((day) => day.date).sort();
const actualDates = timetableData.days.map((day) => day.date).sort();
const latestDate = actualDates.at(-1);
const errors = [];
const results = [];

assert.deepEqual(actualDates, expectedDates, "the public timetable must contain every metadata day exactly once");
for (const day of timetableData.days) {
  const liveUrl = day.autonomous_work.live_url;
  assert.match(
    liveUrl,
    /^https:\/\/shengyu-meng\.github\.io\/granted-hours\/archive\/\d{4}\/\d{2}\/\d{4}-\d{2}-\d{2}\/live\/$/,
    `${day.date} must use its absolute canonical GitHub Pages live-work URL`,
  );
}

const browser = await chromium.launch({ headless: true });

function isInside(inner, outer, tolerance = 1) {
  return inner.top >= outer.top - tolerance
    && inner.left >= outer.left - tolerance
    && inner.bottom <= outer.bottom + tolerance
    && inner.right <= outer.right + tolerance;
}

async function performNativeTouchDrag(page, panelMetrics) {
  const client = await page.context().newCDPSession(page);
  const x = Math.round(panelMetrics.left + panelMetrics.width * 0.5);
  const startY = Math.round(Math.min(panelMetrics.bottom - 38, innerHeightFor(panelMetrics) - 38));
  const endY = Math.round(Math.max(panelMetrics.top + 54, 54));

  await client.send("Input.dispatchTouchEvent", {
    type: "touchStart",
    touchPoints: [{ x, y: startY }],
  });
  for (let step = 1; step <= 8; step += 1) {
    const y = Math.round(startY + ((endY - startY) * step) / 8);
    await client.send("Input.dispatchTouchEvent", {
      type: "touchMove",
      touchPoints: [{ x, y }],
    });
  }
  await client.send("Input.dispatchTouchEvent", {
    type: "touchEnd",
    touchPoints: [],
  });
  await page.waitForTimeout(80);
}

function innerHeightFor(panelMetrics) {
  return panelMetrics.viewportHeight;
}

async function waitForDetailSettled(page) {
  await page.waitForFunction(() => {
    const transform = getComputedStyle(document.querySelector("#dayDialogPanel")).transform;
    return transform === "none" || Math.abs(new DOMMatrixReadOnly(transform).m42) <= 0.5;
  });
}

async function inspectViewport(spec) {
  const context = await browser.newContext(spec.context);
  const page = await context.newPage();
  const pageErrors = [];
  const recordError = (message) => {
    pageErrors.push(message);
    errors.push(`${spec.label}:${message}`);
  };

  page.on("pageerror", (error) => recordError(`page:${error.message}`));
  page.on("console", (message) => {
    if (message.type() === "error" && !/ERR_ABORTED|bgm/i.test(message.text())) {
      recordError(`console:${message.text()}`);
    }
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      recordError(`http:${response.status()}:${response.url()}`);
    }
  });

  await page.goto(`${baseUrl}?qa=${spec.label}`, { waitUntil: "networkidle" });
  await page.waitForSelector(`.calendar-day-button[data-date="${latestDate}"]`);

  const month = await page.evaluate(() => ({
    dateSamples: Array.from(document.querySelectorAll(".cell-date-number, .empty-date-number"))
      .map((element) => element.textContent.trim()),
    horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));
  assert.ok(
    month.dateSamples.length > 0 && month.dateSamples.every((value) => /^\d{1,2}\/\d{1,2}$/.test(value)),
    `${spec.label}: every visible calendar date must use month/day text`,
  );
  assert.ok(month.horizontalOverflow <= 1, `${spec.label}: calendar has ${month.horizontalOverflow}px horizontal overflow`);

  const origin = page.locator(`.calendar-day-button[data-date="${latestDate}"]`);
  if (spec.mobile) {
    await origin.tap();
  } else {
    await origin.click();
  }
  await page.waitForFunction(() => document.activeElement?.id === "closeDetail");
  await waitForDetailSettled(page);

  const before = await page.evaluate(() => {
    const dialog = document.querySelector("#dayDialog");
    const panel = document.querySelector("#dayDialogPanel");
    const layout = document.querySelector(".detail-layout");
    const assigned = document.querySelector(".assigned-detail");
    const lastTask = document.querySelector(".assigned-item:last-child");
    const self = document.querySelector(".self-detail");
    const selfTitle = document.querySelector("#selfTitle");
    const selfNote = document.querySelector("#selfNote");
    const enter = document.querySelector("#enterAutonomous");
    const track = document.querySelector(".sediment-track");
    const viewport = { top: 0, left: 0, right: innerWidth, bottom: innerHeight };
    const selectorFor = (element) => {
      if (element.id) return `#${element.id}`;
      if (element.classList.length) return `.${element.classList[0]}`;
      return element.tagName.toLowerCase();
    };
    const candidates = [dialog, panel, ...panel.querySelectorAll("*")];
    const roots = candidates.map((element) => {
      const style = getComputedStyle(element);
      return {
        selector: selectorFor(element),
        clientHeight: element.clientHeight,
        scrollHeight: element.scrollHeight,
        overflowY: style.overflowY,
        touchAction: style.touchAction,
        containsLastTask: element.contains(lastTask),
        canScroll: element.scrollHeight > element.clientHeight + 2
          && ["auto", "scroll"].includes(style.overflowY),
      };
    });
    return {
      activeId: document.activeElement?.id,
      backgroundInert: document.querySelector("#timetableRoot").hasAttribute("inert"),
      horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      layoutDisplay: getComputedStyle(layout).display,
      layoutColumns: getComputedStyle(layout).gridTemplateColumns.split(/\s+/).filter(Boolean),
      layoutRect: layout.getBoundingClientRect().toJSON(),
      lastRect: lastTask.getBoundingClientRect().toJSON(),
      assignedRect: assigned.getBoundingClientRect().toJSON(),
      selfRect: self.getBoundingClientRect().toJSON(),
      selfTitleRect: selfTitle.getBoundingClientRect().toJSON(),
      selfNoteRect: selfNote.getBoundingClientRect().toJSON(),
      enterRect: enter.getBoundingClientRect().toJSON(),
      trackDisplay: track ? getComputedStyle(track).display : "absent",
      panelMetrics: {
        ...panel.getBoundingClientRect().toJSON(),
        scrollTop: panel.scrollTop,
        maxScroll: panel.scrollHeight - panel.clientHeight,
        overflowY: getComputedStyle(panel).overflowY,
        touchAction: getComputedStyle(panel).touchAction,
        overscrollBehaviorY: getComputedStyle(panel).overscrollBehaviorY,
        viewportHeight: innerHeight,
      },
      roots,
      viewport,
    };
  });

  assert.equal(before.activeId, "closeDetail", `${spec.label}: focus must enter the close button`);
  assert.equal(before.backgroundInert, true, `${spec.label}: background must be inert while detail is open`);
  assert.ok(before.horizontalOverflow <= 1, `${spec.label}: detail has ${before.horizontalOverflow}px horizontal overflow`);

  let accessibility;
  let scrolledRootSelector = null;
  if (spec.mobile) {
    assert.ok(["none", "absent"].includes(before.trackDisplay), `${spec.label}: decorative sediment track must be absent or hidden`);
    assert.equal(before.layoutDisplay, "block", `${spec.label}: detail content must use single-column block flow`);
    assert.ok(
      Math.abs(before.panelMetrics.height - before.panelMetrics.viewportHeight) <= 1,
      `${spec.label}: panel height ${before.panelMetrics.height}px must match ${before.panelMetrics.viewportHeight}px viewport`,
    );
    assert.ok(
      before.lastRect.bottom <= before.selfRect.top + 1,
      `${spec.label}: last assigned row overlaps AI self section by ${before.lastRect.bottom - before.selfRect.top}px`,
    );
    assert.equal(before.panelMetrics.overflowY, "auto", `${spec.label}: panel must be the mobile scroll root`);
    assert.equal(before.panelMetrics.touchAction, "pan-y", `${spec.label}: panel must permit native vertical touch panning`);
    assert.equal(
      before.panelMetrics.overscrollBehaviorY,
      "contain",
      `${spec.label}: panel must contain vertical overscroll`,
    );
    assert.deepEqual(
      before.roots.filter((root) => root.canScroll).map((root) => root.selector),
      ["#dayDialogPanel"],
      `${spec.label}: #dayDialogPanel must be the only real vertical scroll root`,
    );

    const startScrollTop = before.panelMetrics.scrollTop;
    let touchScrollTop = startScrollTop;
    for (let attempt = 0; attempt < 12; attempt += 1) {
      await performNativeTouchDrag(page, before.panelMetrics);
      const progress = await page.locator("#dayDialogPanel").evaluate((panel) => ({
        scrollTop: panel.scrollTop,
        maxScroll: panel.scrollHeight - panel.clientHeight,
      }));
      touchScrollTop = progress.scrollTop;
      if (progress.scrollTop >= progress.maxScroll - 2) break;
    }

    const afterTouch = await page.evaluate(() => {
      const panel = document.querySelector("#dayDialogPanel");
      const enter = document.querySelector("#enterAutonomous").getBoundingClientRect();
      return {
        scrollTop: panel.scrollTop,
        maxScroll: panel.scrollHeight - panel.clientHeight,
        enterVisible: enter.top >= -1 && enter.bottom <= innerHeight + 1,
      };
    });
    assert.ok(touchScrollTop > startScrollTop + 2, `${spec.label}: native CDP touch drag did not move the panel`);
    assert.ok(
      afterTouch.scrollTop >= afterTouch.maxScroll - 2,
      `${spec.label}: native touch scrolling stopped at ${afterTouch.scrollTop}/${afterTouch.maxScroll}`,
    );
    assert.equal(afterTouch.enterVisible, true, `${spec.label}: live-work button is not visible at panel bottom`);
    accessibility = { startScrollTop, touchScrollTop, ...afterTouch };
    scrolledRootSelector = "#dayDialogPanel";
  } else {
    assert.ok(before.layoutColumns.length >= 2, `${spec.label}: desktop detail must retain assigned/self columns`);
    const allScrollRoots = before.roots.filter((candidate) => candidate.canScroll);
    assert.ok(allScrollRoots.length <= 1, `${spec.label}: desktop detail must not create nested scroll roots`);
    if (allScrollRoots.length) {
      assert.equal(allScrollRoots[0].selector, "#dayDialogPanel", `${spec.label}: the panel must own desktop scrolling`);
      scrolledRootSelector = "#dayDialogPanel";
    }

    const reach = async (selector) => {
      await page.locator(selector).scrollIntoViewIfNeeded();
      return page.locator(selector).evaluate((element) => {
        const rect = element.getBoundingClientRect();
        const rootRect = document.querySelector("#dayDialogPanel").getBoundingClientRect();
        return {
          top: rect.top,
          bottom: rect.bottom,
          visible: rect.top >= rootRect.top - 1
            && rect.bottom <= rootRect.bottom + 1
            && rect.top >= -1
            && rect.bottom <= innerHeight + 1,
        };
      });
    };
    const lastAssigned = await reach(".assigned-item:last-child");
    assert.equal(lastAssigned.visible, true, `${spec.label}: last assigned row is unreachable`);
    const liveEntry = await reach("#enterAutonomous");
    assert.equal(liveEntry.visible, true, `${spec.label}: live-work entry is unreachable`);
    const panelProgress = await page.locator("#dayDialogPanel").evaluate((panel) => ({
      scrollTop: panel.scrollTop,
      maxScroll: panel.scrollHeight - panel.clientHeight,
    }));
    accessibility = { lastAssigned, liveEntry, panelProgress };
  }

  await page.keyboard.press("Escape");
  await page.waitForFunction(() => document.querySelector("#dayDialog").hidden);
  if (spec.mobile) {
    await origin.tap();
  } else {
    await origin.click();
  }
  await page.waitForFunction(() => document.activeElement?.id === "closeDetail");
  await waitForDetailSettled(page);
  if (scrolledRootSelector) {
    const reopenedScrollTop = await page.locator(scrolledRootSelector).evaluate((element) => element.scrollTop);
    assert.ok(reopenedScrollTop <= 1, `${spec.label}: reopened detail retained ${reopenedScrollTop}px scroll`);
  }

  await page.keyboard.press("Escape");
  await page.waitForFunction(() => document.querySelector("#dayDialog").hidden);
  const afterEscape = await page.evaluate((date) => ({
    hidden: document.querySelector("#dayDialog").hidden,
    backgroundInert: document.querySelector("#timetableRoot").hasAttribute("inert"),
    focusReturned: document.activeElement?.matches(`.calendar-day-button[data-date="${date}"]`) || false,
  }), latestDate);
  assert.deepEqual(
    afterEscape,
    { hidden: true, backgroundInert: false, focusReturned: true },
    `${spec.label}: Escape must close, restore background, and return focus`,
  );

  const result = {
    label: spec.label,
    month,
    detail: {
      activeId: before.activeId,
      backgroundInert: before.backgroundInert,
      horizontalOverflow: before.horizontalOverflow,
      layoutDisplay: before.layoutDisplay,
      layoutColumns: before.layoutColumns,
      trackDisplay: before.trackDisplay,
      panelMetrics: before.panelMetrics,
      scrollRoots: before.roots.filter((root) => root.canScroll),
    },
    accessibility,
    afterEscape,
    pageErrors,
  };
  results.push(result);
  await context.close();
}

try {
  const viewports = [
    { label: "desktop-1440x900", context: { viewport: { width: 1440, height: 900 } }, mobile: false },
    { label: "desktop-1024x768", context: { viewport: { width: 1024, height: 768 } }, mobile: false },
    { label: "desktop-768x700", context: { viewport: { width: 768, height: 700 } }, mobile: false },
    {
      label: "mobile-390x844",
      context: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2.75, isMobile: true, hasTouch: true },
      mobile: true,
    },
    {
      label: "mobile-421x386-touch",
      context: { viewport: { width: 421, height: 386 }, deviceScaleFactor: 2.75, isMobile: true, hasTouch: true },
      mobile: true,
    },
  ];

  for (const spec of viewports) {
    await inspectViewport(spec);
  }
  assert.deepEqual(errors, [], `page, console, or HTTP errors occurred:\n${errors.join("\n")}`);
  console.log(JSON.stringify({ passed: true, baseUrl, latestDate, results }, null, 2));
} finally {
  await browser.close();
}
