#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const days = [...timetableData.days].sort((a, b) => a.date.localeCompare(b.date));
const latestDay = days.at(-1);
const previousDay = days.at(-2);

let daysWithAssignedWork = 0;
for (const day of days) {
  assert.ok(day.background_pulses.length > 0, `${day.date} has no real background pulses`);
  assert.equal(day.timeline_events.filter((event) => event.origin === "self" || event.origin === "absence").length, 1);
  if (day.timeline_events.some((event) => event.origin === "assigned")) daysWithAssignedWork += 1;
  assert.ok(day.timeline_events.some((event) => event.origin === "background"));
  if (day.autonomous_work.origin === "absence") {
    assert.equal(day.autonomous_work.visual_preview_url, "");
  } else {
    assert.match(day.autonomous_work.visual_preview_url, /visual-preview\.gif$/);
  }
}
assert.ok(daysWithAssignedWork >= 40, `only ${daysWithAssignedWork} days expose assigned work`);

const browser = await chromium.launch({ headless: true });
try {
  const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await desktop.newPage();
  await page.goto(baseUrl, { waitUntil: "networkidle" });

  await page.click(`.calendar-day-button[data-date="${latestDay.date}"]`);
  await page.waitForSelector("#dayDialog.is-open");
  assert.equal(await page.locator(".self-detail").count(), 0, "separate autonomous panel must be removed");
  assert.equal(await page.locator(".timeline-list").count(), 1);
  assert.equal(await page.locator(".autonomous-event").count(), 1);
  assert.ok(await page.locator(".pulse-event").count() > 0);
  assert.ok(await page.locator(".assigned-item").count() > 0);
  assert.equal(
    await page.locator(".routine-reading-card").count(),
    latestDay.reading_items.filter(
      (item) => item.source === "pulses",
    ).length,
    "background reading cards must match the public projection",
  );
  assert.ok(
    await page.locator(".routine-reading-card").count()
      < await page.locator(".pulse-event").count(),
    "climate projection must be smaller than the exact footprint audit",
  );
  const timelineTimes = await page.locator(".timeline-event").evaluateAll((events) =>
    events.map((event) => event.dataset.start),
  );
  assert.deepEqual(timelineTimes, [...timelineTimes].sort());
  const preview = await page.locator("#selfPreview").evaluate(async (image) => {
    await image.decode();
    return { src: image.currentSrc || image.src, width: image.naturalWidth, height: image.naturalHeight };
  });
  assert.match(preview.src, /visual-preview\.gif$/);
  assert.ok(preview.width > 0 && preview.height > 0, JSON.stringify(preview));

  const firstPulse = page.locator(".routine-reading-card").first();
  const readingId = await firstPulse.getAttribute("data-reading-id");
  const pulseEvidence = latestDay.reading_items.find(
    (item) => item.reading_id === readingId,
  );
  assert.ok(pulseEvidence, readingId);
  const sourcePulse = latestDay.background_pulses.find(
    (pulse) => pulse.footprint_id === pulseEvidence.source_refs[0],
  );
  const renderedSummaries = await firstPulse.locator(".pulse-summary > span").allTextContents();
  const expectedSummaryZh = renderedSummaries[0]?.trim() || sourcePulse?.summary_zh;
  const expectedSummaryEn = renderedSummaries[1]?.trim() || sourcePulse?.summary_en;
  await firstPulse.click({ force: true });
  await page.waitForSelector("#taskDialog.is-open");
  assert.equal((await page.locator("#taskDetailZh").textContent())?.trim(), expectedSummaryZh);
  assert.equal((await page.locator("#taskDetailEn").textContent())?.trim(), expectedSummaryEn);
  assert.match((await page.locator("#taskDetailTime").textContent()) || "", /(?:exact windows|window \d+ min)/);
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("#dayDialog").getAttribute("hidden"), null);

  const rows = page.locator(".assigned-item");
  for (let index = 0; index < await rows.count(); index += 1) {
    const state = await rows.nth(index).evaluate((card) => {
      const copy = card.querySelector(".assigned-copy");
      const style = getComputedStyle(copy);
      return {
        clamp: style.webkitLineClamp,
        overflow: style.overflow,
        clamped: copy.classList.contains("is-clamped"),
        ellipsis: getComputedStyle(copy, "::after").content,
        cardOverflow: getComputedStyle(card).overflowY,
        cardScrollable: card.scrollHeight > card.clientHeight + 1,
      };
    });
    assert.equal(state.clamp, "none", JSON.stringify(state));
    assert.equal(state.overflow, "visible");
    assert.equal(state.clamped, false);
    assert.equal(state.ellipsis, "none");
    assert.equal(state.cardOverflow, "auto");
  }

  const triggerIndex = 0;
  const trigger = rows.nth(triggerIndex);
  const selectedTask = latestDay.task_residues[triggerIndex];
  await trigger.scrollIntoViewIfNeeded();
  const dayScrollBefore = await page.locator("#dayDialogPanel").evaluate((panel) => {
    return panel.scrollTop;
  });
  await trigger.click();
  await page.waitForSelector("#taskDialog.is-open");
  assert.equal(await page.evaluate(() => document.activeElement?.id), "closeTaskDetail");
  if (selectedTask.source_kind === "collaboration_session") {
    const completionLabelZh = selectedTask.completion_status === "completed"
      ? "完成"
      : "完成情况";
    const completionLabelEn = selectedTask.completion_status === "completed"
      ? "Completed"
      : "Completion status";
    const expectedZh = `要求：${selectedTask.request_zh}\n\n${completionLabelZh}：${selectedTask.outcome_zh}`;
    const expectedEn = `Request: ${selectedTask.request_en}\n\n${completionLabelEn}: ${selectedTask.outcome_en}`;
    assert.equal((await page.locator("#taskDetailZh").textContent())?.trim(), expectedZh);
    assert.equal((await page.locator("#taskDetailEn").textContent())?.trim(), expectedEn);
    assert.equal(await page.locator("#taskDetailEn").isHidden(), false);
  } else {
    assert.equal((await page.locator("#taskDetailZh").textContent())?.trim(), selectedTask.zh);
    assert.equal((await page.locator("#taskDetailEn").textContent())?.trim(), selectedTask.en);
  }
  assert.equal((await page.locator("#taskDetailProvenance").textContent())?.trim(), "");
  assert.equal(await page.locator("#taskDetailProvenance").isHidden(), true);
  await page.keyboard.press("Escape");
  assert.equal(await page.locator("#taskDialog").getAttribute("hidden"), "");
  assert.equal(await page.locator("#dayDialog").getAttribute("hidden"), null);
  assert.equal(await page.evaluate(() => document.activeElement?.classList.contains("assigned-item")), true);
  assert.equal(await page.locator("#dayDialogPanel").evaluate((panel) => panel.scrollTop), dayScrollBefore);

  assert.equal(await page.locator("#nextDay").isDisabled(), true);
  assert.equal(await page.locator("#prevDay").isDisabled(), false);
  await page.locator("#dayDialogPanel").evaluate((panel) => { panel.scrollTop = panel.scrollHeight; });
  await page.click("#prevDay");
  assert.equal(await page.locator("#dayDialog").getAttribute("data-selected-date"), previousDay.date);
  assert.ok(await page.locator("#dayDialogPanel").evaluate((panel) => panel.scrollTop <= 1));
  assert.equal(await page.evaluate(() => document.activeElement?.id), "prevDay");

  await page.keyboard.press("Escape");
  const mayEndUrl = new URL(baseUrl);
  mayEndUrl.searchParams.set("date", "2026-05-31");
  await page.goto(mayEndUrl.href, { waitUntil: "networkidle" });
  await page.waitForSelector('#dayDialog.is-open[data-selected-date="2026-05-31"]');
  assert.equal(
    (await page.locator("#dialogDate").textContent())?.trim(),
    "2026-05-31 · Sunday / 2026年5月31日 · 星期日",
  );
  await page.click("#nextDay");
  assert.equal(await page.locator("#dayDialog").getAttribute("data-selected-date"), "2026-06-01");
  assert.equal(
    (await page.locator("#dialogDate").textContent())?.trim(),
    "2026-06-01 · Monday / 2026年6月1日 · 星期一",
  );
  assert.match((await page.locator("#todayButton").textContent()) || "", /June|6月/);
  await page.keyboard.press("Escape");
  const mayEleven = days.find((day) => day.date === "2026-05-11");
  assert.ok(mayEleven, "2026-05-11 missing from timetable data");
  const mayElevenSupportGroups = mayEleven.reading_items.filter(
    (item) => item.classification === "climate_aggregate" && item.family === "support_checks",
  );
  assert.equal(mayElevenSupportGroups.length, 1, "2026-05-11 support routines must be one daily card");
  assert.equal(mayElevenSupportGroups[0].source_refs.length, 52);
  assert.equal(
    mayEleven.reading_items.filter((item) => (
      item.classification === "promoted_routine_exception"
      && item.source_refs.some((sourceRef) => {
        const pulse = mayEleven.background_pulses.find((entry) => entry.footprint_id === sourceRef);
        return pulse && ["system_routine", "background_routine"].includes(pulse.category);
      })
    )).length,
    0,
    "generic support alerts must not become separate cards",
  );
  const mayElevenUrl = new URL(baseUrl);
  mayElevenUrl.searchParams.set("date", "2026-05-11");
  await page.goto(mayElevenUrl.href, { waitUntil: "networkidle" });
  await page.waitForSelector('#dayDialog.is-open[data-selected-date="2026-05-11"]');
  const supportCard = page.locator(
    `.routine-reading-card[data-reading-id="${mayElevenSupportGroups[0].reading_id}"]`,
  );
  assert.equal(await supportCard.count(), 1);
  const supportCopy = (await supportCard.textContent()) || "";
  assert.match(supportCopy, /后台例行运行/);
  assert.match(supportCopy, /Background routine activity/);
  assert.doesNotMatch(supportCopy, /其他后台运行记录提示|Other background run record alert/);
  await page.keyboard.press("Escape");
  const firstDayUrl = new URL(baseUrl);
  firstDayUrl.searchParams.set("date", "2026-05-07");
  await page.goto(firstDayUrl.href, { waitUntil: "networkidle" });
  await page.waitForSelector('#dayDialog.is-open[data-selected-date="2026-05-07"]');
  assert.equal(await page.locator("#prevDay").isDisabled(), true);
  assert.equal(await page.locator("#nextDay").isDisabled(), false);
  await page.keyboard.press("Escape");
  await desktop.close();

  for (const viewport of [
    { width: 390, height: 844, label: "mobile" },
    { width: 421, height: 386, label: "short-touch" },
  ]) {
    const context = await browser.newContext({
      viewport,
      isMobile: true,
      hasTouch: true,
      deviceScaleFactor: 2,
    });
    const mobile = await context.newPage();
    const mobileUrl = new URL(baseUrl);
    mobileUrl.searchParams.set("date", "2026-07-24");
    await mobile.goto(mobileUrl.href, { waitUntil: "networkidle" });
    await mobile.waitForSelector('#dayDialog.is-open[data-selected-date="2026-07-24"]');
    assert.ok(
      await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth <= 1),
      `${viewport.label} horizontal overflow`,
    );
    await mobile.locator(".assigned-item").first().tap();
    assert.equal(await mobile.locator(".assigned-item").first().getAttribute("aria-pressed"), "true");
    assert.equal(await mobile.locator(".assigned-item").first().getAttribute("aria-expanded"), null);
    assert.equal(await mobile.locator("#taskDialog").getAttribute("hidden"), "");
    await mobile.locator(".assigned-item").first().tap();
    await mobile.waitForSelector("#taskDialog.is-open");
    const bounds = await mobile.locator("#taskDialogPanel").boundingBox();
    assert.ok(bounds && bounds.x >= 0 && bounds.y >= 0);
    assert.ok(bounds.x + bounds.width <= viewport.width + 1);
    assert.ok(bounds.y + bounds.height <= viewport.height + 1);
    await mobile.keyboard.press("Escape");
    assert.equal(await mobile.locator("#dayDialog").getAttribute("hidden"), null);
    assert.equal(await mobile.evaluate(() => document.activeElement?.classList.contains("assigned-item")), true);
    await mobile.keyboard.press("Escape");
    assert.equal(await mobile.locator("#dayDialog").getAttribute("hidden"), "");
    const mobileMayElevenUrl = new URL(baseUrl);
    mobileMayElevenUrl.searchParams.set("date", "2026-05-11");
    await mobile.goto(mobileMayElevenUrl.href, { waitUntil: "networkidle" });
    await mobile.waitForSelector('#dayDialog.is-open[data-selected-date="2026-05-11"]');
    const mobileSupportCard = mobile.locator(
      `.routine-reading-card[data-reading-id="${mayElevenSupportGroups[0].reading_id}"]`,
    );
    assert.equal(await mobileSupportCard.count(), 1, `${viewport.label}: support rollup count`);
    const mobileSupportCopy = (await mobileSupportCard.textContent()) || "";
    assert.match(mobileSupportCopy, /后台例行运行/);
    assert.doesNotMatch(
      mobileSupportCopy,
      /其他后台运行记录提示|Other background run record alert/,
    );
    assert.ok(
      await mobile.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth <= 1),
      `${viewport.label}: 2026-05-11 horizontal overflow`,
    );
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, days: days.length }, null, 2));
