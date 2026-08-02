#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8895/timetable/";
const daysByDate = new Map(timetableData.days.map((day) => [day.date, day]));
const linkedDay = timetableData.days.find((day) => daysByDate.has(day.source_date));
assert.ok(linkedDay, "dual-date QA needs one artwork with a public Source Day");
const sourceDay = daysByDate.get(linkedDay.source_date);
assert.equal(linkedDay.crystallization_date, linkedDay.date);
assert.equal(linkedDay.autonomous_work.source_date, linkedDay.source_date);
assert.equal(sourceDay.forward_artwork_seeds.length, 1);
assert.equal(
  sourceDay.forward_artwork_seeds[0].crystallization_date,
  linkedDay.date,
);

const cases = [
  { width: 390, height: 844, touch: true, label: "390x844" },
  { width: 421, height: 386, touch: true, label: "421x386" },
  { width: 768, height: 900, touch: true, label: "768-touch" },
  { width: 1440, height: 900, touch: false, label: "desktop" },
];
const browser = await chromium.launch({ headless: true });
const results = [];

function assertPublicContract(text, label) {
  assert.match(text, /提醒尽量保留原句；可识别实体以 ████ 遮挡。/, label);
  assert.match(
    text,
    /Reminders retain original wording; identifying entities appear as ████\./,
    label,
  );
  assert.doesNotMatch(
    text,
    /audited templates|fixed templates|Masked residue|Reminder residue|Inner weather|absence layer|public layer retains|This day reveals only|经审计|固定模板|遮挡残影|提醒残影|内在天气|缺席层|公开层留下|这一天只显出一处/i,
    label,
  );
}

try {
  for (const testCase of cases) {
    const context = await browser.newContext({
      viewport: { width: testCase.width, height: testCase.height },
      isMobile: testCase.touch && testCase.width < 500,
      hasTouch: testCase.touch,
      deviceScaleFactor: testCase.touch ? 2 : 1,
    });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    const directUrl = new URL(baseUrl);
    directUrl.searchParams.set("date", sourceDay.date);
    directUrl.searchParams.set("qa", "dual-date");
    await page.goto(directUrl.href, { waitUntil: "networkidle" });
    await page.waitForSelector(
      `#dayDialog.is-open[data-selected-date="${sourceDay.date}"]`,
    );
    await page.waitForFunction(() => document.activeElement?.id === "closeDetail");

    const sourceState = await page.evaluate(() => {
      const panel = document.querySelector("#dayDialogPanel");
      const seed = document.querySelector("#dialogCrystallizationLink a");
      const roots = [
        document.querySelector("#dayDialog"),
        panel,
        document.querySelector(".timeline-detail"),
        document.querySelector(".timeline-list"),
      ].filter(Boolean).filter((element) => {
        const style = getComputedStyle(element);
        return element.scrollHeight > element.clientHeight + 4
          && ["auto", "scroll"].includes(style.overflowY);
      });
      return {
        selectedDate: document.querySelector("#dayDialog")?.dataset.selectedDate,
        seedHref: seed?.href || "",
        seedText: seed?.textContent?.trim() || "",
        fullBeaconCount: document.querySelectorAll(".autonomous-reading-card").length,
        autonomousFootprintCount: document.querySelectorAll(
          ".timeline-event.autonomous-event",
        ).length,
        publicNote: {
          text: document.querySelector("#publicNote")?.textContent?.trim() || "",
          visible: getComputedStyle(document.querySelector("#publicNote")).display !== "none",
        },
        dialogBoundary: {
          text: document.querySelector("#dialogBoundary")?.textContent?.trim() || "",
          visible: getComputedStyle(document.querySelector("#dialogBoundary")).display !== "none",
        },
        horizontalOverflow:
          document.documentElement.scrollWidth - document.documentElement.clientWidth,
        scrollRoots: roots.map((element) => (
          element.id ? `#${element.id}` : `.${element.classList[0]}`
        )),
        decorativeIconCount: document.querySelectorAll(
          ".theme-icon, .theme-toggle-icon, .seed-mark",
        ).length,
        forbiddenVisibleCopy: document.body.innerText.match(
          /Seed\s*\/\s*种子|Masked residue|Inner weather|absence layer|遮挡残影|内在天气|缺席层/gi,
        ) || [],
      };
    });
    assert.equal(sourceState.selectedDate, sourceDay.date, testCase.label);
    assert.match(sourceState.seedHref, new RegExp(`[?&]date=${linkedDay.date}(?:&|$)`));
    assert.match(sourceState.seedText, /Next crystallization|下一结晶/);
    assert.equal(sourceState.fullBeaconCount, 1);
    assert.equal(sourceState.autonomousFootprintCount, 1);
    assert.equal(sourceState.publicNote.visible, true);
    assert.equal(sourceState.dialogBoundary.visible, true);
    assertPublicContract(sourceState.publicNote.text, `${testCase.label} footer contract`);
    assertPublicContract(sourceState.dialogBoundary.text, `${testCase.label} dialog contract`);
    assert.ok(sourceState.horizontalOverflow <= 1, testCase.label);
    assert.deepEqual(sourceState.scrollRoots, ["#dayDialogPanel"]);
    assert.equal(sourceState.decorativeIconCount, 0);
    assert.deepEqual(sourceState.forbiddenVisibleCopy, []);

    await page.locator("#dialogCrystallizationLink a").click();
    await page.waitForFunction(
      (date) => document.querySelector("#dayDialog")?.dataset.selectedDate === date,
      linkedDay.date,
    );
    await page.waitForFunction(
      () => document.querySelector(".timeline-reading-layer.is-placed"),
    );
    await page.waitForFunction(() => document.activeElement?.id === "closeDetail");
    assert.equal(new URL(page.url()).searchParams.get("date"), linkedDay.date);
    const crystalState = await page.evaluate(() => {
      const card = document.querySelector(".autonomous-reading-card");
      const footprint = document.querySelector(".timeline-event.autonomous-event");
      const relation = card?.querySelector(".autonomous-date-relation");
      const sourceLink = card?.querySelector(".autonomous-source-day-link");
      const previewLink = card?.querySelector(".autonomous-preview-frame");
      const actionLink = card?.querySelector(".autonomous-open-copy");
      const panel = document.querySelector("#dayDialogPanel");
      const cards = [...document.querySelectorAll(".event-reading-card")].map(
        (element) => element.getBoundingClientRect(),
      );
      const collisions = [];
      for (let left = 0; left < cards.length; left += 1) {
        for (let right = left + 1; right < cards.length; right += 1) {
          const a = cards[left];
          const b = cards[right];
          if (
            a.left < b.right - 1
            && b.left < a.right - 1
            && a.top < b.bottom - 1
            && b.top < a.bottom - 1
          ) collisions.push([left, right]);
        }
      }
      return {
        selectedDate: document.querySelector("#dayDialog")?.dataset.selectedDate,
        cardCount: document.querySelectorAll(".autonomous-reading-card").length,
        footprintCount: document.querySelectorAll(
          ".timeline-event.autonomous-event",
        ).length,
        start: footprint?.dataset.start,
        end: footprint?.dataset.end,
        duration: footprint?.dataset.durationMinutes,
        relationText: relation?.textContent?.trim() || "",
        relationAria: card?.getAttribute("aria-label") || "",
        cardTag: card?.tagName,
        cardRole: card?.getAttribute("role"),
        cardTabindex: card?.getAttribute("tabindex"),
        cardHref: card?.getAttribute("href"),
        sourceTag: sourceLink?.tagName,
        sourceHref: sourceLink?.href,
        sourceName: sourceLink?.textContent?.trim() || "",
        previewTag: previewLink?.tagName,
        previewHref: previewLink?.href,
        previewTarget: previewLink?.target,
        previewRel: previewLink?.rel,
        previewName: previewLink?.getAttribute("aria-label") || "",
        actionTag: actionLink?.tagName,
        actionHref: actionLink?.href,
        actionTarget: actionLink?.target,
        actionRel: actionLink?.rel,
        collisions,
        panelScrollable: panel.scrollHeight > panel.clientHeight + 4,
        horizontalOverflow:
          document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    assert.equal(crystalState.selectedDate, linkedDay.date);
    assert.equal(crystalState.cardCount, 1);
    assert.equal(crystalState.footprintCount, 1);
    assert.equal(crystalState.start, timetableData.autonomous_hour.start);
    assert.equal(crystalState.end, timetableData.autonomous_hour.end);
    assert.equal(crystalState.duration, "60");
    assert.match(crystalState.relationText, /Source.*Crystallized/);
    assert.match(crystalState.relationText, /来源.*结晶/);
    assert.match(crystalState.relationAria, /Source Day.*Crystallization Day/);
    assert.equal(crystalState.cardTag, "ARTICLE");
    assert.equal(crystalState.cardRole, null);
    assert.equal(crystalState.cardTabindex, null);
    assert.equal(crystalState.cardHref, null);
    assert.equal(crystalState.sourceTag, "A");
    assert.match(crystalState.sourceHref, new RegExp(`[?&]date=${sourceDay.date}(?:&|$)`));
    assert.match(crystalState.sourceName, /Source|来源/);
    assert.equal(crystalState.previewTag, "A");
    assert.equal(crystalState.actionTag, "A");
    assert.equal(crystalState.previewHref, crystalState.actionHref);
    assert.equal(crystalState.previewTarget, "_blank");
    assert.equal(crystalState.actionTarget, "_blank");
    assert.match(crystalState.previewRel, /noopener/);
    assert.match(crystalState.actionRel, /noopener/);
    assert.match(crystalState.previewName, /Open complete live work/);
    assert.deepEqual(crystalState.collisions, []);
    assert.equal(crystalState.panelScrollable, true);
    assert.ok(crystalState.horizontalOverflow <= 1);
    assert.deepEqual(errors, []);

    const reminderCards = page.locator(
      ".routine-reading-card[data-pulse-category='daily_reminder']",
    );
    if (await reminderCards.count()) {
      const card = reminderCards.first();
      const meaning = `${await card.textContent()} ${await card.getAttribute("aria-label")}`;
      assert.match(
        meaning,
        /Morning reminder|Midday reminder|Evening reminder|晨间提醒|午间提醒|晚间提醒/,
      );
      assert.doesNotMatch(
        meaning,
        /Inner weather|Masked residue|absence layer|内在天气|遮挡残影|缺席层/i,
      );
      assert.doesNotMatch(
        await card.getAttribute("data-accessible-name") || "",
        /undefined|null/,
      );
    }

    await page.locator(".autonomous-source-day-link").click();
    await page.waitForFunction(
      (date) => document.querySelector("#dayDialog")?.dataset.selectedDate === date,
      sourceDay.date,
    );
    await page.waitForFunction(() => document.activeElement?.id === "closeDetail");
    assert.equal(new URL(page.url()).searchParams.get("date"), sourceDay.date);

    await page.keyboard.press("Escape");
    await page.waitForFunction(() => document.querySelector("#dayDialog")?.hidden);
    const closedState = await page.evaluate((date) => ({
      dateParam: new URL(location.href).searchParams.get("date"),
      focusRestored: document.activeElement?.matches(
        `.calendar-day-button[data-date="${date}"]`,
      ) || false,
      backgroundInert: document.querySelector("#timetableRoot")?.hasAttribute("inert"),
    }), sourceDay.date);
    assert.deepEqual(closedState, {
      dateParam: null,
      focusRestored: true,
      backgroundInert: false,
    });

    for (const expectedDate of [sourceDay.date, linkedDay.date, sourceDay.date]) {
      await page.goBack();
      await page.waitForSelector(
        `#dayDialog.is-open[data-selected-date="${expectedDate}"]`,
      );
      await page.waitForFunction(() => document.activeElement?.id === "closeDetail");
      assert.equal(new URL(page.url()).searchParams.get("date"), expectedDate);
    }
    await page.keyboard.press("Escape");
    await page.waitForFunction(() => document.querySelector("#dayDialog")?.hidden);

    results.push({
      label: testCase.label,
      selectedDate: linkedDay.date,
      collisions: crystalState.collisions.length,
      scrollRoots: sourceState.scrollRoots.length,
    });
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, results }, null, 2));
