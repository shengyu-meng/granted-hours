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
const sampleDate = timetableData.days.find((day) => {
  const durations = new Set(day.task_residues.map((task) => task.duration_minutes));
  return day.date.startsWith("2026-07") && day.task_residues.length >= 2 && durations.size >= 2;
})?.date || timetableData.days.find((day) => day.task_residues.length > 0)?.date || timetableData.days.at(-1).date;
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
    if (day.autonomous_work?.origin === "absence") {
      assert.equal(day.autonomous_work.live_url, "", `${day.date} absence day must not expose a live URL`);
      assert.equal(day.autonomous_work.bgm_url, "", `${day.date} absence day must not expose BGM`);
      continue;
    }
    const livePath = fileURLToPath(
      new URL(`../docs/archive/${year}/${month}/${day.date}/live/index.html`, import.meta.url),
    );
    const html = readFileSync(livePath, "utf8");
    assert.equal((html.match(/id="granted-hours-fold-script"/g) || []).length, 1, `${day.date} embed script count`);
    assert.ok(html.indexOf("id=\"granted-hours-fold-script\"") < html.indexOf("</head>"), `${day.date} embed guard must load in head`);
    assert.match(html, /body\.gh-chamber-embed h1/);
    assert.match(html, /body\.gh-chamber-embed button/);
    assert.match(html, /params\.get\('embed'\) === 'calendar'/);
    assert.doesNotMatch(html, /IS_TIMETABLE_FULL_VIEW/);
    assert.match(html, /function alignWorkNote\(\)/);
    assert.doesNotMatch(html, /gh-fold-toggle/);
    assert.match(html, /className = 'gh-work-note-trigger'/);
    assert.match(html, /makeElement\('section', 'gh-work-note-overlay'\)/);
    assert.ok(html.includes("archive.href = '../';"), `${day.date} archive link`);
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
  await context.addInitScript(() => {});
  const page = await context.newPage();
  const initialUrl = new URL(baseUrl);
  initialUrl.searchParams.set("date", sampleDate);
  initialUrl.searchParams.set("regression", "calendar-enrichment");
  await page.goto(initialUrl.href, { waitUntil: "domcontentloaded" });
  await page.waitForSelector(`#dayDialog.is-open[data-selected-date="${sampleDate}"]`);
  await page.keyboard.press("Escape");

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

  await check("calendar cells contain no decorative theme icons", async () => {
    const result = await page.evaluate(() => {
      const buttons = [...document.querySelectorAll(".calendar-day-button")];
      return {
        buttonCount: buttons.length,
        iconCount: document.querySelectorAll(".calendar-day-button .theme-icon").length,
        customDoodleCount: document.querySelectorAll(".theme-doodle").length,
      };
    });
    assert.ok(result.buttonCount > 0, JSON.stringify(result));
    assert.equal(result.iconCount, 0, JSON.stringify(result));
    assert.equal(result.customDoodleCount, 0, JSON.stringify(result));
  });

  await page.tap(`.calendar-day-button[data-date="${sampleDate}"]`);
  await page.waitForFunction(() => document.activeElement?.id === "closeDetail");

  await check("mobile day header keeps one Chinese lead and folds the longer bilingual context", async () => {
    const collapsed = await page.evaluate(() => {
      const details = document.querySelector("#dialogContextDetails");
      const header = document.querySelector(".dialog-header");
      const englishTitle = document.querySelector(".dialog-title-en");
      const boundary = document.querySelector("#dialogBoundary");
      return {
        detailsOpen: details.open,
        headerHeight: header.getBoundingClientRect().height,
        lead: document.querySelector(".dialog-mobile-lead")?.innerText.trim() || "",
        englishTitleVisible: englishTitle.getClientRects().length > 0,
        boundaryVisible: boundary.getClientRects().length > 0,
        pcbControls: document.querySelectorAll(
          "#dayViewToggle,.day-view-toggle,.pcb-chip-hardware,[data-view-mode='pcb']",
        ).length,
        pageCopy: document.body.innerText,
      };
    });
    assert.equal(collapsed.detailsOpen, false, JSON.stringify(collapsed));
    assert.ok(collapsed.headerHeight <= 190, JSON.stringify(collapsed));
    assert.match(collapsed.lead, /时间足迹保持真实位置/);
    assert.equal(collapsed.englishTitleVisible, false, JSON.stringify(collapsed));
    assert.equal(collapsed.boundaryVisible, false, JSON.stringify(collapsed));
    assert.equal(collapsed.pcbControls, 0, JSON.stringify(collapsed));
    assert.doesNotMatch(collapsed.pageCopy, /PCB DAY MAP|电路板日程表/);

    await page.locator("#dialogContextDetails > summary").click();
    const expanded = await page.evaluate(() => ({
      detailsOpen: document.querySelector("#dialogContextDetails").open,
      boundaryVisible: document.querySelector("#dialogBoundary").getClientRects().length > 0,
      fullCopy: document.querySelector("#dialogContextDetails").innerText,
    }));
    assert.equal(expanded.detailsOpen, true, JSON.stringify(expanded));
    assert.equal(expanded.boundaryVisible, true, JSON.stringify(expanded));
    assert.match(expanded.fullCopy, /Footprints preserve exact position/);
    assert.match(expanded.fullCopy, /compress continuous idle intervals while keeping every hourly mark/);
    await page.locator("#dialogContextDetails > summary").click();
  });

  await check("day detail presents active human–AI provenance and concrete work content without duplication", async () => {
    const task = page.locator(".assigned-item").first();
    const provenance = (await task.locator(".record-provenance").textContent())?.trim() || "";
    const detail = (await task.locator(".assigned-copy").textContent())?.trim() || "";
    assert.match(provenance, /ACTIVE HUMAN–AI COLLABORATION/);
    assert.ok(detail.length >= 12, `work summary too short: ${JSON.stringify(detail)}`);
    assert.equal(await task.locator(".assigned-task-name").count(), 0);
  });

  await check("day schedule blocks expose readable work types, colors, and duration-proportional heights", async () => {
    const result = await page.locator(".assigned-event").evaluateAll((events) => events.map((event) => {
      const item = [...document.querySelectorAll(".assigned-item")].find((card) =>
        (card.dataset.memberFootprintIds || "").split(" ").includes(event.dataset.footprintId)
      );
      const style = getComputedStyle(item);
      return {
        duration: Number(event.dataset.durationMinutes || 0),
        provenance: item.dataset.timeProvenance,
        type: item.querySelector(".assigned-work-type")?.textContent?.trim() || "",
        icon: item.querySelector(".assigned-type-icon svg[data-lucide]")?.getAttribute("data-lucide") || "",
        footprintHeight: event.getBoundingClientRect().height,
        cardHeight: item.getBoundingClientRect().height,
        accent: style.getPropertyValue("--task-accent").trim(),
      };
    }));
    assert.ok(result.length >= 2, JSON.stringify(result));
    assert.ok(
      result.every((item) =>
        item.duration > 0
        && ["estimated_semantic_window", "observed_message_envelope", "observed_session_window"].includes(item.provenance)
      ),
      JSON.stringify(result),
    );
    assert.ok(result.every((item) => item.type.length >= 4 && item.icon && item.accent), JSON.stringify(result));
    assert.ok(result.every((item) => item.cardHeight >= 48), JSON.stringify(result));
    const shortest = result.reduce((a, b) => a.duration < b.duration ? a : b);
    const longest = result.reduce((a, b) => a.duration > b.duration ? a : b);
    assert.ok(
      longest.footprintHeight > shortest.footprintHeight * 1.2,
      JSON.stringify({ shortest, longest, result }),
    );
    for (const longer of result) {
      for (const shorter of result) {
        if (longer.duration >= shorter.duration + 20) {
          assert.ok(
            longer.footprintHeight >= shorter.footprintHeight,
            `footprint height must follow duration rather than reading-card copy: ${JSON.stringify({ longer, shorter, result })}`,
          );
        }
      }
    }
  });

  await check("proposal-day block geometry follows duration even when copy lengths differ", async () => {
    const durationPage = await context.newPage();
    try {
      const durationUrl = new URL(baseUrl);
      durationUrl.searchParams.set("date", "2026-07-18");
      await durationPage.goto(durationUrl.href, { waitUntil: "networkidle" });
      await durationPage.waitForSelector('#dayDialog.is-open[data-selected-date="2026-07-18"]');
      const result = await durationPage.locator(".assigned-event").evaluateAll((events) => events.map((event) => ({
        duration: Number(event.dataset.durationMinutes || 0),
        height: event.getBoundingClientRect().height,
      })));
      for (const longer of result) {
        for (const shorter of result) {
          if (longer.duration >= shorter.duration + 20) {
            assert.ok(longer.height >= shorter.height, JSON.stringify({ longer, shorter, result }));
          }
        }
      }
    } finally {
      await durationPage.close();
    }
  });

  await check("calendar opens autonomous work in one interactive in-page chamber", async () => {
    const linkedDateUrl = new URL(baseUrl);
    linkedDateUrl.searchParams.set("date", "2026-07-17");
    linkedDateUrl.searchParams.set("regression", "calendar-enrichment");
    await page.goto(linkedDateUrl.href, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('#dayDialog.is-open[data-selected-date="2026-07-17"]');
    const result = await page.locator("#enterAutonomous").evaluate((card) => {
      const previewLink = card.querySelector(".autonomous-preview-frame");
      const liveLink = card.querySelector(".autonomous-open-copy");
      const sourceDayLink = card.querySelector(".autonomous-source-day-link");
      return {
        tag: card.tagName,
        role: card.getAttribute("role"),
        tabindex: card.getAttribute("tabindex"),
        cardHref: card.getAttribute("href"),
        cardTarget: card.getAttribute("target"),
        previewTag: previewLink?.tagName || "",
        previewPopup: previewLink?.getAttribute("aria-haspopup") || "",
        previewName: previewLink?.getAttribute("aria-label") || "",
        liveTag: liveLink?.tagName || "",
        livePopup: liveLink?.getAttribute("aria-haspopup") || "",
        sourceTag: sourceDayLink?.tagName || "",
        sourceHref: sourceDayLink?.href || "",
        chamberCount: document.querySelectorAll("#artworkDialog,#artworkLiveFrame").length,
      };
    });
    assert.equal(result.tag, "ARTICLE", JSON.stringify(result));
    assert.equal(result.role, null, JSON.stringify(result));
    assert.equal(result.tabindex, null, JSON.stringify(result));
    assert.equal(result.cardHref, null, JSON.stringify(result));
    assert.equal(result.cardTarget, null, JSON.stringify(result));
    assert.equal(result.previewTag, "BUTTON", JSON.stringify(result));
    assert.equal(result.liveTag, "BUTTON", JSON.stringify(result));
    assert.equal(result.sourceTag, "A", JSON.stringify(result));
    assert.match(result.sourceHref, /[?&]date=\d{4}-\d{2}-\d{2}(?:&|$)/);
    assert.equal(result.previewPopup, "dialog", JSON.stringify(result));
    assert.equal(result.livePopup, "dialog", JSON.stringify(result));
    assert.match(result.previewName, /Open interactive artwork in the calendar/);
    assert.equal(result.chamberCount, 2, JSON.stringify(result));

    const pageCountBefore = context.pages().length;
    await page.locator(".autonomous-preview-frame").click();
    await page.waitForSelector("#artworkDialog.is-open");
    await page.waitForFunction(() => document.querySelector("#artworkLiveFrame").src.includes("embed=calendar"));
    const chamber = await page.evaluate(() => ({
      dialogOpen: !document.querySelector("#artworkDialog").hidden,
      iframeSrc: document.querySelector("#artworkLiveFrame").src,
      calendarPaused: document.querySelector("#calendarBgm").paused,
      suspended: document.querySelector("#calendarBgmToggle").dataset.suspended,
    }));
    assert.equal(context.pages().length, pageCountBefore, JSON.stringify(chamber));
    assert.equal(chamber.dialogOpen, true, JSON.stringify(chamber));
    assert.equal(chamber.calendarPaused, true, JSON.stringify(chamber));
    assert.equal(chamber.suspended, "true", JSON.stringify(chamber));
    assert.match(chamber.iframeSrc, /\/live\//);
    assert.match(chamber.iframeSrc, /[?&]embed=calendar(?:&|$)/);
    assert.match(chamber.iframeSrc, /[?&]gh_channel=[a-f0-9]{32}(?:&|$)/);
    await page.locator("#closeArtworkDetail").click();
    await page.waitForSelector("#artworkDialog", { state: "hidden" });
  });

  await check("representative embed variants hide chrome and begin with media safely paused", async () => {
    let audioElementCount = 0;
    for (const date of ["2026-05-07", "2026-07-06", "2026-07-26", "2026-08-12"]) {
      const [year, month] = date.split("-");
      const embedPage = await context.newPage();
      await embedPage.goto(new URL(`archive/${year}/${month}/${date}/live/?embed=calendar`, archiveBaseUrl).href, { waitUntil: "commit" });
      await embedPage.locator("body.gh-chamber-embed").waitFor();
      await embedPage.waitForTimeout(300);
      const result = await embedPage.evaluate(() => {
        const selectors = ["h1", "h2", "h3", ".title", ".brief", "#brief", ".hint", "#hint", ".ledger", ".hud", ".status", ".label", ".controls", ".toolbar", ".ui", ".overlay", "button", "[role=button]"];
        const visible = selectors.flatMap((selector) =>
          [...document.querySelectorAll(selector)]
            .filter((element) => {
              const style = getComputedStyle(element);
              const rect = element.getBoundingClientRect();
              return style.display !== "none" && style.visibility !== "hidden" && Number(style.opacity) > 0.01 && rect.width > 1 && rect.height > 1;
            })
            .filter((element) => !element.closest("#ghTouchKeyDock"))
            .map(() => selector),
        );
        return {
          visible,
          touchKeys: document.querySelectorAll("#ghTouchKeyDock .gh-touch-key").length,
          audio: [...document.querySelectorAll("audio")].map((audio) => ({ paused: audio.paused, muted: audio.muted })),
          video: [...document.querySelectorAll("video")].map((video) => ({ muted: video.muted })),
        };
      });
      assert.deepEqual(result.visible, [], `${date}: ${JSON.stringify(result)}`);
      assert.equal(result.touchKeys, date === "2026-05-07" ? 3 : 0, `${date}: ${JSON.stringify(result)}`);
      assert.ok(result.audio.every((audio) => audio.paused && audio.muted), `${date}: ${JSON.stringify(result.audio)}`);
      assert.ok(result.video.every((video) => video.muted), `${date}: ${JSON.stringify(result.video)}`);
      audioElementCount += result.audio.length;
      await embedPage.close();
    }
    assert.ok(audioElementCount > 0, "representative embed media assertions must not be vacuous");
  });


  await check("direct live page keeps its text, controls, and unforced media state", async () => {
    const directPage = await context.newPage();
    await directPage.goto(new URL("archive/2026/07/2026-07-26/live/", archiveBaseUrl).href, { waitUntil: "commit" });
    await directPage.waitForSelector("h1, .title", { state: "attached" });
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
        liveBriefVisible: isVisible(document.querySelector("#ghLiveBrief")),
        liveBriefTitle: document.querySelector("#ghLiveBrief .gh-live-brief-title")?.textContent || "",
        workNoteVisible: isVisible(document.querySelector("#ghWorkNoteTrigger")),
        foldControlAbsent: !document.querySelector(".gh-fold-toggle"),
        artworkControlVisible: isVisible(document.querySelector("button:not(.gh-work-note-trigger)")),
        media: [...document.querySelectorAll("audio, video")].map((media) => ({ muted: media.muted })),
      };
    });
    assert.ok(!result.classes.includes("gh-chamber-embed"), JSON.stringify(result));
    assert.ok(result.titleVisible || result.liveBriefVisible, JSON.stringify(result));
    assert.match(result.liveBriefTitle, /\S+\s*\/\s*\S+/, JSON.stringify(result));
    assert.ok(result.workNoteVisible, JSON.stringify(result));
    assert.equal(result.foldControlAbsent, true, JSON.stringify(result));
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
