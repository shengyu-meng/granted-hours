#!/usr/bin/env node
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const captureScreenshots = process.env.FIRST_PERSON_QA_CAPTURE !== "0";
const targetDate = "2026-08-10";
const targetDay = timetableData.days.find((day) => day.date === targetDate);
assert.ok(targetDay, `${targetDate} is missing from timetable data`);
const collaborations = targetDay.task_residues.filter(
  (task) => task.source_kind === "collaboration_session",
);
assert.equal(collaborations.length, 3, "approved 2026-08-10 collaboration cards are incomplete");
assert.equal(
  collaborations.filter((task) => task.assessment_zh).length,
  2,
  "approved 2026-08-10 assessment layers are incomplete",
);
assert.equal(
  collaborations.filter((task) => task.owner_response_zh).length,
  0,
  "owner-response copy appeared without explicit evidence",
);

const screenshotRoot = new URL("../audits/first-person-voice/", import.meta.url);
if (captureScreenshots) {
  await mkdir(fileURLToPath(screenshotRoot), { recursive: true });
}
const browser = await chromium.launch({ headless: true });
const results = [];

try {
  for (const viewport of [
    { width: 1440, height: 900, label: "desktop", touch: false },
    { width: 390, height: 844, label: "mobile", touch: true },
  ]) {
    const context = await browser.newContext({
      viewport,
      isMobile: viewport.touch,
      hasTouch: viewport.touch,
      deviceScaleFactor: viewport.touch ? 2 : 1,
    });
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(error.message));
    const targetUrl = new URL(baseUrl);
    targetUrl.searchParams.set("date", targetDate);
    await page.goto(targetUrl.href, { waitUntil: "domcontentloaded" });
    await page.waitForSelector(`#dayDialog.is-open[data-selected-date="${targetDate}"]`);
    await page.waitForTimeout(240);

    const boundary = (await page.locator("#dialogBoundary").textContent()) || "";
    assert.match(boundary, /第一人称档案位置/);
    assert.match(boundary, /first-person archival position/);

    const visibleDayText = await page.locator("#dayDialogPanel").innerText();
    for (const task of collaborations) {
      assert.ok(visibleDayText.includes(task.request_zh), `${viewport.label}: missing ${task.request_zh}`);
      assert.ok(visibleDayText.includes(task.request_en), `${viewport.label}: missing ${task.request_en}`);
      assert.ok(visibleDayText.includes(task.outcome_zh), `${viewport.label}: missing first-person completion`);
      assert.ok(visibleDayText.includes(task.outcome_en), `${viewport.label}: missing English completion`);
      if (task.assessment_zh) {
        assert.ok(
          visibleDayText.includes(`我的判断：${task.assessment_zh}`),
          `${viewport.label}: missing approved Chinese assessment`,
        );
        assert.ok(
          visibleDayText.includes(`My assessment: ${task.assessment_en}`),
          `${viewport.label}: missing approved English assessment`,
        );
      }
    }
    assert.ok(!visibleDayText.includes("Simon 的回应"), `${viewport.label}: inferred owner response`);
    assert.ok(!visibleDayText.includes("Simon's response"), `${viewport.label}: inferred owner response`);

    const routineSummaries = await page.locator(
      ".routine-reading-card:not(.has-markdown)",
    ).evaluateAll((cards) => cards.map((card) => ({
      zh: card.querySelector(".pulse-summary-zh")?.textContent?.trim() || "",
      en: card.querySelector(".pulse-summary-en")?.textContent?.trim() || "",
    })));
    assert.ok(routineSummaries.length > 0, `${viewport.label}: no routine summaries to audit`);
    assert.ok(
      routineSummaries.every(({ zh, en }) => zh.startsWith("我") && en.startsWith("I ")),
      `${viewport.label}: a routine summary lost the first-person voice`,
    );

    const cards = page.locator(".assigned-reading-card").filter({ hasText: "Simon 让我" });
    assert.ok(await cards.count() >= 1, `${viewport.label}: no first-person collaboration card rendered`);
    const firstCard = cards.first();
    const firstCardText = await firstCard.innerText();
    const firstTask = collaborations.find((task) => firstCardText.includes(task.request_zh));
    assert.ok(firstTask, `${viewport.label}: collaboration card cannot be matched to source data`);
    await firstCard.scrollIntoViewIfNeeded();
    if (viewport.touch) {
      await firstCard.tap();
      await firstCard.tap();
    } else {
      await firstCard.click({ force: true });
    }
    await page.waitForSelector("#taskDialog.is-open");
    const detailZh = (await page.locator("#taskDetailZh").innerText()).trim();
    const detailEn = (await page.locator("#taskDetailEn").innerText()).trim();
    assert.ok(detailZh.startsWith(firstTask.request_zh), `${viewport.label}: detail lost owner-to-AI voice`);
    assert.ok(detailZh.includes(firstTask.outcome_zh), `${viewport.label}: detail lost AI completion voice`);
    assert.ok(detailEn.startsWith(firstTask.request_en), `${viewport.label}: detail lost English owner-to-AI voice`);
    assert.ok(detailEn.includes(firstTask.outcome_en), `${viewport.label}: detail lost English AI voice`);
    if (firstTask.assessment_zh) {
      assert.ok(detailZh.includes(`我的判断：${firstTask.assessment_zh}`));
      assert.ok(detailEn.includes(`My assessment: ${firstTask.assessment_en}`));
    }
    assert.ok(
      await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1),
      `${viewport.label}: first-person detail caused horizontal overflow`,
    );
    if (captureScreenshots) {
      await page.locator("#taskDialogPanel").screenshot({
        path: fileURLToPath(new URL(`${targetDate}-${viewport.label}.png`, screenshotRoot)),
      });
    }

    assert.deepEqual(pageErrors, [], `${viewport.label}: page errors`);
    results.push({
      viewport: viewport.label,
      collaborations: collaborations.length,
      approvedAssessments: collaborations.filter((task) => task.assessment_zh).length,
      routinesChecked: routineSummaries.length,
      detailChineseCharacters: detailZh.length,
      detailEnglishCharacters: detailEn.length,
    });
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, targetDate, results }, null, 2));
