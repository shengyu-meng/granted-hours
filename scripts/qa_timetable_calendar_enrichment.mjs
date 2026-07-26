#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8772/timetable/";
const parsedBaseUrl = new URL(baseUrl);
const archiveBaseUrl = /^(?:127\.0\.0\.1|localhost)$/.test(parsedBaseUrl.hostname)
  ? `${parsedBaseUrl.origin}/`
  : timetableData.canonical_base_url;
const sampleDate = timetableData.days.some((day) => day.date === "2026-07-17")
  ? "2026-07-17"
  : timetableData.days.at(-1).date;
const failures = [];

async function check(name, fn) {
  try {
    await fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    failures.push(`${name}: ${error.message}`);
    console.error(`FAIL ${name}: ${error.message}`);
  }
}

await check("every assigned residue has a concrete public task name", () => {
  const taskNames = new Set();
  const fallbackNames = new Set([
    "公开内容编排",
    "文稿整理与修订",
    "功能开发与验证",
    "专题研究与综合",
    "Agent 系统运维",
    "系统维护工作",
    "视觉内容制作",
  ]);
  let taskCount = 0;
  let fallbackCount = 0;
  for (const day of timetableData.days) {
    for (const task of day.task_residues) {
      assert.ok(task.task_name_zh?.trim(), `${day.date} missing task_name_zh`);
      assert.ok(task.task_name_en?.trim(), `${day.date} missing task_name_en`);
      assert.notEqual(task.task_name_zh, task.label_zh, `${day.date} task name repeats generic taxonomy label`);
      assert.notEqual(task.task_name_en, task.label_en, `${day.date} task name repeats generic taxonomy label`);
      taskNames.add(task.task_name_zh);
      taskCount += 1;
      if (fallbackNames.has(task.task_name_zh)) fallbackCount += 1;
    }
  }
  assert.ok(taskNames.size >= 50, `expected at least 50 recognizable task types; got ${taskNames.size}`);
  assert.ok(fallbackCount / taskCount <= 0.1, `generic fallback share is ${(fallbackCount / taskCount * 100).toFixed(1)}%`);
});

await check("every day has a semantic motif and every live page has controllable embed media", () => {
  const allowedMotifs = new Set(["window", "seam", "bridge", "echo", "weather", "time", "room", "light", "void"]);
  for (const day of timetableData.days) {
    assert.ok(allowedMotifs.has(day.theme_motif), `${day.date} has invalid theme_motif: ${day.theme_motif}`);
    const [year, month] = day.date.split("-");
    const livePath = fileURLToPath(
      new URL(`../docs/archive/${year}/${month}/${day.date}/live/index.html`, import.meta.url),
    );
    const html = readFileSync(livePath, "utf8");
    assert.equal((html.match(/id="granted-hours-fold-script"/g) || []).length, 1, `${day.date} embed script count`);
    assert.ok(html.indexOf("id=\"granted-hours-fold-script\"") < html.indexOf("</head>"), `${day.date} embed guard must load in head`);
    assert.match(html, /body\.gh-chamber-embed h1/);
    assert.match(html, /body\.gh-chamber-embed button/);
    assert.match(html, /new URLSearchParams\(window\.location\.search\)\.get\('embed'\) === 'calendar'/);
    assert.match(html, /IS_TIMETABLE_FULL_VIEW/);
    assert.match(html, /params\.get\('from'\) === 'timetable'/);
    assert.match(html, /HTMLMediaElement\.prototype\.play/);
    assert.match(html, /silenceEmbeddedMedia/);
    assert.match(html, /granted-hours:media/);
    assert.match(html, /event\.source !== window\.parent/);
  }
});

const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext({
    viewport: { width: 421, height: 386 },
    deviceScaleFactor: 2.75,
    isMobile: true,
    hasTouch: true,
  });
  const [sampleYear, sampleMonth] = sampleDate.split("-");
  const sampleLivePath = fileURLToPath(
    new URL(`../docs/archive/${sampleYear}/${sampleMonth}/${sampleDate}/live/index.html`, import.meta.url),
  );
  await context.route(
    new RegExp(`^https://shengyu-meng\\.github\\.io/granted-hours/archive/${sampleYear}/${sampleMonth}/${sampleDate}/live/(?:\\?.*)?$`),
    (route) => route.fulfill({ path: sampleLivePath, contentType: "text/html" }),
  );
  await context.addInitScript(() => {
    localStorage.setItem("grantedHoursTextFolded", "0");
  });
  const page = await context.newPage();
  await page.goto(`${baseUrl}?regression=calendar-enrichment`, { waitUntil: "networkidle" });

  await check("month control shows the concrete visible month and changes with navigation", async () => {
    const before = (await page.locator("#todayButton").textContent())?.trim() || "";
    assert.doesNotMatch(before, /this month|这个月|本月/i);
    assert.match(before, /2026/);
    assert.match(before, /(?:5|6|7)月|may|june|july/i);
    await page.tap("#prevMonth");
    const previous = (await page.locator("#todayButton").textContent())?.trim() || "";
    assert.notEqual(previous, before);
    assert.match(previous, /6月|june/i);
    assert.doesNotMatch(previous, /this month|这个月|本月/i);
    await page.tap("#prevMonth");
    const earliest = (await page.locator("#todayButton").textContent())?.trim() || "";
    assert.match(earliest, /5月|may/i);
    assert.doesNotMatch(earliest, /this month|这个月|本月/i);
    await page.tap("#nextMonth");
    assert.equal((await page.locator("#todayButton").textContent())?.trim() || "", previous);
    await page.tap("#nextMonth");
    assert.equal((await page.locator("#todayButton").textContent())?.trim() || "", before);
  });

  await check("public days use varied library-backed vector icons", async () => {
    const result = await page.evaluate(() => {
      const buttons = [...document.querySelectorAll(".calendar-day-button")];
      const icons = buttons.map((button) => button.querySelector(".theme-icon svg[data-lucide]")?.getAttribute("data-lucide") || "");
      return {
        buttonCount: buttons.length,
        iconCount: icons.filter(Boolean).length,
        iconTypeCount: new Set(icons.filter(Boolean)).size,
        customDoodleCount: document.querySelectorAll(".theme-doodle").length,
      };
    });
    assert.equal(result.iconCount, result.buttonCount, JSON.stringify(result));
    assert.ok(result.iconTypeCount >= 3, `current month needs thematic vector variation: ${JSON.stringify(result)}`);
    assert.equal(result.customDoodleCount, 0, JSON.stringify(result));
  });

  await page.tap(`.calendar-day-button[data-date="${sampleDate}"]`);
  await page.waitForFunction(() => document.activeElement?.id === "closeDetail");

  await check("day detail presents faithful record provenance and concrete work summary without duplication", async () => {
    const task = page.locator(".assigned-item").first();
    const provenance = (await task.locator(".record-provenance").textContent())?.trim() || "";
    const detail = (await task.locator(".assigned-copy").textContent())?.trim() || "";
    assert.match(provenance, /FAITHFUL RECORD SUMMARY/);
    assert.ok(detail.length >= 12, `work summary too short: ${JSON.stringify(detail)}`);
    assert.equal(await task.locator(".assigned-task-name").count(), 0);
  });

  await check("day schedule blocks expose readable work types, colors, and duration-proportional heights", async () => {
    const result = await page.locator(".assigned-item").evaluateAll((items) => items.map((item) => {
      const style = getComputedStyle(item);
      return {
        duration: Number(item.dataset.durationMinutes || 0),
        provenance: item.dataset.timeProvenance,
        type: item.querySelector(".assigned-work-type")?.textContent?.trim() || "",
        icon: item.querySelector(".assigned-type-icon svg[data-lucide]")?.getAttribute("data-lucide") || "",
        height: item.getBoundingClientRect().height,
        accent: style.getPropertyValue("--task-accent").trim(),
      };
    }));
    assert.ok(result.length >= 2, JSON.stringify(result));
    assert.ok(result.every((item) => item.duration > 0 && item.provenance === "estimated"), JSON.stringify(result));
    assert.ok(result.every((item) => item.type.length >= 4 && item.icon && item.accent), JSON.stringify(result));
    const shortest = result.reduce((a, b) => a.duration < b.duration ? a : b);
    const longest = result.reduce((a, b) => a.duration > b.duration ? a : b);
    assert.ok(longest.height > shortest.height * 1.2, JSON.stringify({ shortest, longest, result }));
    for (const longer of result) {
      for (const shorter of result) {
        if (longer.duration >= shorter.duration + 20) {
          assert.ok(
            longer.height > shorter.height,
            `block height must follow duration rather than copy length: ${JSON.stringify({ longer, shorter, result })}`,
          );
        }
      }
    }
  });

  await check("proposal-day block geometry follows duration even when copy lengths differ", async () => {
    const durationPage = await context.newPage();
    try {
      await durationPage.goto(baseUrl, { waitUntil: "networkidle" });
      await durationPage.tap('.calendar-day-button[data-date="2026-07-18"]');
      await durationPage.waitForSelector("#dayDialog.is-open");
      const result = await durationPage.locator(".assigned-item").evaluateAll((items) => items.map((item) => ({
        duration: Number(item.dataset.durationMinutes || 0),
        height: item.getBoundingClientRect().height,
      })));
      for (const longer of result) {
        for (const shorter of result) {
          if (longer.duration >= shorter.duration + 20) {
            assert.ok(longer.height > shorter.height, JSON.stringify({ longer, shorter, result }));
          }
        }
      }
    } finally {
      await durationPage.close();
    }
  });

  await check("calendar opens the complete canonical work instead of an iframe chamber", async () => {
    const result = await page.locator("#enterAutonomous").evaluate((link) => ({
      tag: link.tagName,
      href: link.href,
      target: link.target,
      rel: link.rel,
      chamberCount: document.querySelectorAll("#crystalChamber,#liveFrame").length,
    }));
    assert.equal(result.tag, "A", JSON.stringify(result));
    assert.equal(result.target, "_blank", JSON.stringify(result));
    assert.match(result.rel, /noopener/);
    assert.doesNotMatch(result.href, /[?&]embed=calendar/);
    assert.match(result.href, /[?&]from=timetable(?:&|$)/);
    assert.equal(result.chamberCount, 0, JSON.stringify(result));
  });

  await check("representative embed variants hide chrome and begin with media safely paused", async () => {
    let audioElementCount = 0;
    for (const date of ["2026-05-07", "2026-07-06", "2026-07-26"]) {
      const [year, month] = date.split("-");
      const embedPage = await context.newPage();
      await embedPage.goto(new URL(`archive/${year}/${month}/${date}/live/?embed=calendar`, archiveBaseUrl).href, { waitUntil: "load" });
      await embedPage.locator("body.gh-chamber-embed").waitFor();
      await embedPage.waitForTimeout(300);
      const result = await embedPage.evaluate(() => {
        const selectors = ["h1", "h2", "h3", ".title", ".hud", ".status", ".label", ".controls", ".toolbar", ".ui", ".overlay", "button", "[role=button]"];
        const visible = selectors.flatMap((selector) =>
          [...document.querySelectorAll(selector)]
            .filter((element) => {
              const style = getComputedStyle(element);
              const rect = element.getBoundingClientRect();
              return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0.01 && rect.width > 1 && rect.height > 1;
            })
            .map(() => selector),
        );
        return {
          visible,
          audio: [...document.querySelectorAll("audio")].map((audio) => ({ paused: audio.paused, muted: audio.muted })),
          video: [...document.querySelectorAll("video")].map((video) => ({ muted: video.muted })),
        };
      });
      assert.deepEqual(result.visible, [], `${date}: ${JSON.stringify(result)}`);
      assert.ok(result.audio.every((audio) => audio.paused && audio.muted), `${date}: ${JSON.stringify(result.audio)}`);
      assert.ok(result.video.every((video) => video.muted), `${date}: ${JSON.stringify(result.video)}`);
      audioElementCount += result.audio.length;
      await embedPage.close();
    }
    assert.ok(audioElementCount > 0, "representative embed media assertions must not be vacuous");
  });


  await check("direct live page keeps its text, controls, and unforced media state", async () => {
    const directPage = await context.newPage();
    await directPage.goto(new URL("archive/2026/07/2026-07-26/live/", archiveBaseUrl).href, { waitUntil: "load" });
    await directPage.waitForTimeout(300);
    const result = await directPage.evaluate(() => {
      const isVisible = (element) => {
        if (!element) return false;
        const style = getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0.01 && rect.width > 1 && rect.height > 1;
      };
      return {
        classes: [...document.body.classList],
        titleVisible: isVisible(document.querySelector("h1, .title")),
        toggleVisible: isVisible(document.querySelector(".gh-fold-toggle")),
        artworkControlVisible: isVisible(document.querySelector("button:not(.gh-fold-toggle)")),
        media: [...document.querySelectorAll("audio, video")].map((media) => ({ muted: media.muted })),
      };
    });
    assert.ok(!result.classes.includes("gh-chamber-embed"), JSON.stringify(result));
    assert.ok(result.titleVisible, JSON.stringify(result));
    assert.ok(result.toggleVisible, JSON.stringify(result));
    assert.ok(result.artworkControlVisible, JSON.stringify(result));
    assert.ok(result.media.length > 0, JSON.stringify(result));
    assert.ok(result.media.every((media) => media.muted === false), JSON.stringify(result));
    await directPage.close();
  });

  await check("320px viewport keeps a seven-column calendar without horizontal overflow", async () => {
    const narrowContext = await browser.newContext({
      viewport: { width: 320, height: 568 },
      deviceScaleFactor: 2,
      isMobile: true,
      hasTouch: true,
    });
    try {
      const narrowPage = await narrowContext.newPage();
      await narrowPage.goto(baseUrl, { waitUntil: "networkidle" });
      const result = await narrowPage.evaluate(() => ({
        columns: getComputedStyle(document.querySelector("#monthGrid")).gridTemplateColumns.split(" ").length,
        overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
        buttons: document.querySelectorAll(".calendar-day-button").length,
      }));
      assert.equal(result.columns, 7, JSON.stringify(result));
      assert.ok(result.buttons > 0, JSON.stringify(result));
      assert.ok(result.overflow <= 1, JSON.stringify(result));
    } finally {
      await narrowContext.close();
    }
  });
} finally {
  await browser.close();
}

if (failures.length) {
  throw new Error(`Calendar enrichment regressions (${failures.length}):\n- ${failures.join("\n- ")}`);
}

console.log(JSON.stringify({ passed: true, sampleDate }, null, 2));
