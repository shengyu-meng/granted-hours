#!/usr/bin/env node
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const siteUrl = new URL(
  process.env.WORK_NOTE_SITE_URL || "http://127.0.0.1:8891/",
);
if (!siteUrl.pathname.endsWith("/")) siteUrl.pathname += "/";

const siteOrigin = siteUrl.origin;
const days = JSON.parse(
  readFileSync(new URL("../metadata/days.json", import.meta.url), "utf8"),
);
const expectedCount = 78;
const expectedHeadings = [
  "Intention",
  "Afterimage",
  "发心",
  "余像",
  "Creative Rationale",
  "创作缘由",
];
const failures = [];
const results = [];

assert.equal(days.length, expectedCount, `Expected ${expectedCount} declared public days`);

function archivePaths(day) {
  const [year, month] = day.date.split("-");
  return {
    explanationFile: new URL(
      `../docs/archive/${year}/${month}/${day.date}/index.html`,
      import.meta.url,
    ),
    liveFile: new URL(
      `../docs/archive/${year}/${month}/${day.date}/live/index.html`,
      import.meta.url,
    ),
    explanationUrl: new URL(
      `archive/${year}/${month}/${day.date}/`,
      siteUrl,
    ).href,
    liveUrl: new URL(
      `archive/${year}/${month}/${day.date}/live/`,
      siteUrl,
    ).href,
  };
}

for (const day of days) {
  const paths = archivePaths(day);
  assert.ok(existsSync(paths.explanationFile), `${day.date} explanation page is missing`);
  assert.ok(existsSync(paths.liveFile), `${day.date} live page is missing`);
}

function trackPageHealth(page, label) {
  const pageErrors = [];
  const responseErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("response", (response) => {
    if (new URL(response.url()).origin === siteOrigin && response.status() >= 400) {
      responseErrors.push(`${response.status()} ${response.url()}`);
    }
  });
  return {
    assertHealthy() {
      assert.deepEqual(pageErrors, [], `${label} page errors: ${pageErrors.join("; ")}`);
      assert.deepEqual(
        responseErrors,
        [],
        `${label} same-origin response errors: ${responseErrors.join("; ")}`,
      );
    },
  };
}

async function assertClosedWithFocusReturn(page, label) {
  assert.equal(
    await page.locator(".gh-work-note-modal").isHidden(),
    true,
    `${label} dialog did not close`,
  );
  assert.equal(
    await page.evaluate(() => document.body.classList.contains("gh-work-note-open")),
    false,
    `${label} body scroll lock remained after close`,
  );
  assert.equal(
    await page.evaluate(
      () => document.activeElement?.classList.contains("gh-work-note-button") || false,
    ),
    true,
    `${label} focus did not return to Work note`,
  );
}

const browser = await chromium.launch({ headless: true });
try {
  const parserPage = await browser.newPage();
  const archiveSources = days.map((day) => ({
    date: day.date,
    source: readFileSync(archivePaths(day).explanationFile, "utf8"),
  }));
  const expectedCopyEntries = await parserPage.evaluate(
    ({ sources, headings }) => sources.map(({ date, source }) => {
      const documentNode = new DOMParser().parseFromString(source, "text/html");
      const sections = [...documentNode.querySelectorAll("section.two")].slice(0, 2);
      const copy = sections.flatMap((section) => [...section.querySelectorAll("h2")].map(
        (heading) => ({
          heading: heading.textContent.replace(/\s+/g, " ").trim(),
          paragraph:
            heading.nextElementSibling?.matches("p")
              ? heading.nextElementSibling.textContent.replace(/\s+/g, " ").trim()
              : null,
        }),
      ));
      if (
        sections.length !== 2
        || copy.length !== headings.length
        || copy.some((item, index) => (
          item.heading !== headings[index] || !item.paragraph
        ))
      ) {
        throw new Error(`${date} does not have the required first-two-section copy`);
      }
      return [date, copy];
    }),
    { sources: archiveSources, headings: expectedHeadings },
  );
  await parserPage.close();
  const expectedCopyByDate = new Map(expectedCopyEntries);

  const corpusContext = await browser.newContext({
    viewport: { width: 1280, height: 720 },
  });

  async function inspectDirectAndEmbedPage(day) {
    const paths = archivePaths(day);
    const page = await corpusContext.newPage();
    const health = trackPageHealth(page, day.date);
    try {
      const directUrl = new URL(paths.liveUrl);
      directUrl.searchParams.set("from", "timetable");
      directUrl.searchParams.set("qa", "work-note-corpus");
      const response = await page.goto(directUrl.href, {
        waitUntil: "domcontentloaded",
        timeout: 45000,
      });
      assert.equal(response?.status(), 200, `${day.date} HTTP ${response?.status()}`);
      const actions = page.locator(".gh-work-note-actions");
      await actions.waitFor({ state: "visible", timeout: 20000 });

      const expectedCopy = expectedCopyByDate.get(day.date);
      const state = await page.evaluate(() => {
        const workNoteButtons = [...document.querySelectorAll("button")]
          .filter((element) => element.textContent.trim() === "Work note / 作品说明");
        const archiveLinks = [...document.querySelectorAll("a")]
          .filter((element) => element.textContent.trim() === "Artwork archive / 作品档案");
        const actionRows = [...document.querySelectorAll(".gh-work-note-actions")];
        const modal = document.querySelector(".gh-work-note-modal");
        const copy = modal
          ? [...modal.querySelectorAll(".gh-work-note-copy section")].map((section) => ({
            heading: section.querySelector("h2")?.textContent.replace(/\s+/g, " ").trim(),
            paragraph: section.querySelector("p")?.textContent.replace(/\s+/g, " ").trim(),
            headingCount: section.querySelectorAll("h2").length,
            paragraphCount: section.querySelectorAll("p").length,
          }))
          : [];
        const scriptText =
          document.getElementById("granted-hours-fold-script")?.textContent || "";
        return {
          buttonCount: workNoteButtons.length,
          buttonTag: workNoteButtons[0]?.tagName,
          buttonHref: workNoteButtons[0]?.getAttribute("href"),
          archiveCount: archiveLinks.length,
          archiveTag: archiveLinks[0]?.tagName,
          archiveHref: archiveLinks[0]?.getAttribute("href"),
          archiveResolvedHref: archiveLinks[0]?.href,
          actionRowCount: actionRows.length,
          actionRowFinal:
            actionRows[0]?.parentElement?.lastElementChild === actionRows[0],
          actionRowPosition:
            actionRows[0] ? getComputedStyle(actionRows[0]).position : "",
          hostClass: actionRows[0]?.parentElement?.className || "",
          modalCount: document.querySelectorAll(".gh-work-note-modal").length,
          modalHidden: modal?.hidden,
          role: modal?.getAttribute("role"),
          ariaModal: modal?.getAttribute("aria-modal"),
          labelledBy: modal?.getAttribute("aria-labelledby"),
          labelledHeading: modal
            ? document.getElementById(modal.getAttribute("aria-labelledby"))?.textContent
            : null,
          closeCount: modal?.querySelectorAll("button.gh-work-note-close").length || 0,
          copy,
          modalForbiddenCount:
            modal?.querySelectorAll(
              ".gh-work-note-copy a, .gh-work-note-copy audio, .gh-work-note-copy button, "
              + ".gh-work-note-copy canvas, .gh-work-note-copy form, "
              + ".gh-work-note-copy iframe, .gh-work-note-copy img, "
              + ".gh-work-note-copy input, .gh-work-note-copy link, "
              + ".gh-work-note-copy meta, .gh-work-note-copy script, "
              + ".gh-work-note-copy style, .gh-work-note-copy svg, "
              + ".gh-work-note-copy video",
            ).length || 0,
          sourceFetch: /\bfetch\s*\(/.test(scriptText),
          sourceInnerHtml: /\.innerHTML\b/.test(scriptText),
          bodyLocked: document.body.classList.contains("gh-work-note-open"),
        };
      });
      assert.deepEqual(
        {
          buttonCount: state.buttonCount,
          buttonTag: state.buttonTag,
          buttonHref: state.buttonHref,
          archiveCount: state.archiveCount,
          archiveTag: state.archiveTag,
          archiveHref: state.archiveHref,
          archiveResolvedHref: state.archiveResolvedHref,
          actionRowCount: state.actionRowCount,
          actionRowFinal: state.actionRowFinal,
          actionRowPosition: state.actionRowPosition,
          modalCount: state.modalCount,
          modalHidden: state.modalHidden,
          role: state.role,
          ariaModal: state.ariaModal,
          labelledBy: state.labelledBy,
          labelledHeading: state.labelledHeading,
          closeCount: state.closeCount,
          copy: state.copy,
          modalForbiddenCount: state.modalForbiddenCount,
          sourceFetch: state.sourceFetch,
          sourceInnerHtml: state.sourceInnerHtml,
          bodyLocked: state.bodyLocked,
        },
        {
          buttonCount: 1,
          buttonTag: "BUTTON",
          buttonHref: null,
          archiveCount: 1,
          archiveTag: "A",
          archiveHref: "../",
          archiveResolvedHref: paths.explanationUrl,
          actionRowCount: 1,
          actionRowFinal: true,
          actionRowPosition: "static",
          modalCount: 1,
          modalHidden: true,
          role: "dialog",
          ariaModal: "true",
          labelledBy: "gh-work-note-title",
          labelledHeading: "Work note / 作品说明",
          closeCount: 1,
          copy: expectedCopy.map((item) => ({
            ...item,
            headingCount: 1,
            paragraphCount: 1,
          })),
          modalForbiddenCount: 0,
          sourceFetch: false,
          sourceInnerHtml: false,
          bodyLocked: false,
        },
        `${day.date} direct dialog contract`,
      );

      const directHref = page.url();
      await page.locator(".gh-work-note-button").click();
      await page.locator(".gh-work-note-modal").waitFor({ state: "visible" });
      assert.equal(page.url(), directHref, `${day.date} Work note navigated or reloaded`);
      assert.equal(
        await page.evaluate(() => document.body.classList.contains("gh-work-note-open")),
        true,
        `${day.date} body scroll was not locked while open`,
      );
      assert.equal(
        await page.evaluate(
          () => document.activeElement?.classList.contains("gh-work-note-close") || false,
        ),
        true,
        `${day.date} focus did not move to close`,
      );
      await page.locator(".gh-work-note-close").click();
      await assertClosedWithFocusReturn(page, `${day.date} close button`);
      assert.equal(page.url(), directHref, `${day.date} close changed the live URL`);

      const embedUrl = new URL(paths.liveUrl);
      embedUrl.searchParams.set("embed", "calendar");
      embedUrl.searchParams.set("qa", "work-note-embed-corpus");
      const embedResponse = await page.goto(embedUrl.href, {
        waitUntil: "domcontentloaded",
        timeout: 45000,
      });
      assert.equal(
        embedResponse?.status(),
        200,
        `${day.date} embed HTTP ${embedResponse?.status()}`,
      );
      await page.waitForFunction(
        () => document.body.classList.contains("gh-chamber-embed"),
      );
      assert.deepEqual(
        await page.evaluate(() => ({
          actions: document.querySelectorAll(".gh-work-note-actions").length,
          buttons: document.querySelectorAll(".gh-work-note-button").length,
          archives: document.querySelectorAll(".gh-artwork-archive-link").length,
          modals: document.querySelectorAll(".gh-work-note-modal").length,
        })),
        { actions: 0, buttons: 0, archives: 0, modals: 0 },
        `${day.date} embed exposed work-note UI`,
      );
      health.assertHealthy();
      return {
        date: day.date,
        button: 1,
        archive: 1,
        finalRow: 1,
        modalCopy: 1,
        openClose: 1,
        embedHidden: 1,
      };
    } finally {
      await page.close();
    }
  }

  const concurrency = 3;
  for (let index = 0; index < days.length; index += concurrency) {
    const batch = days.slice(index, index + concurrency);
    const settled = await Promise.allSettled(
      batch.map(inspectDirectAndEmbedPage),
    );
    settled.forEach((result, batchIndex) => {
      if (result.status === "fulfilled") results.push(result.value);
      else failures.push(`${batch[batchIndex].date}: ${result.reason.message}`);
    });
  }
  await corpusContext.close();

  if (failures.length) {
    throw new Error(
      `Work-note corpus failures (${failures.length}):\n- ${failures.join("\n- ")}`,
    );
  }
  assert.equal(results.length, expectedCount);

  const latest = days.at(-1);
  const latestPaths = archivePaths(latest);
  const behaviorContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const behaviorPage = await behaviorContext.newPage();
  const behaviorHealth = trackPageHealth(behaviorPage, `${latest.date} behavior`);
  const behaviorUrl = new URL(latestPaths.liveUrl);
  behaviorUrl.searchParams.set("from", "timetable");
  behaviorUrl.searchParams.set("qa", "work-note-behavior");
  await behaviorPage.goto(behaviorUrl.href, { waitUntil: "domcontentloaded" });
  const behaviorButton = behaviorPage.locator(".gh-work-note-button");
  const behaviorModal = behaviorPage.locator(".gh-work-note-modal");
  await behaviorButton.waitFor({ state: "visible" });

  await behaviorButton.click();
  await behaviorPage.keyboard.press("Escape");
  await assertClosedWithFocusReturn(behaviorPage, "Escape");

  await behaviorButton.click();
  await behaviorModal.locator(".gh-work-note-copy p").first().click();
  assert.equal(
    await behaviorModal.isVisible(),
    true,
    "Clicking inside the dialog closed it",
  );
  await behaviorModal.click({ position: { x: 2, y: 2 } });
  await assertClosedWithFocusReturn(behaviorPage, "backdrop");

  const behaviorActions = behaviorPage.locator(".gh-work-note-actions");
  const behaviorFold = behaviorPage.locator(".gh-fold-toggle");
  await behaviorFold.click();
  await behaviorPage.waitForFunction(
    () => document.body.classList.contains("gh-text-folded"),
  );
  assert.equal(
    await behaviorActions.isVisible(),
    false,
    "Folded information panel left actions floating",
  );
  await behaviorFold.click();
  await behaviorPage.waitForFunction(
    () => !document.body.classList.contains("gh-text-folded"),
  );
  assert.equal(
    await behaviorActions.isVisible(),
    true,
    "Actions did not return with the unfolded panel",
  );
  behaviorHealth.assertHealthy();
  await behaviorContext.close();

  const navigationContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const navigationPage = await navigationContext.newPage();
  const navigationHealth = trackPageHealth(
    navigationPage,
    `${latest.date} archive navigation`,
  );
  const navigationUrl = new URL(latestPaths.liveUrl);
  navigationUrl.searchParams.set("from", "timetable");
  navigationUrl.searchParams.set("qa", "archive-navigation");
  await navigationPage.goto(navigationUrl.href, { waitUntil: "domcontentloaded" });
  await navigationPage.locator(".gh-artwork-archive-link").click();
  await navigationPage.waitForURL(latestPaths.explanationUrl);
  for (const heading of expectedHeadings) {
    await navigationPage.getByRole("heading", { name: heading, exact: true }).waitFor();
  }
  navigationHealth.assertHealthy();
  await navigationContext.close();

  const viewportSpecs = [
    {
      label: "desktop-1440x900",
      context: { viewport: { width: 1440, height: 900 } },
      touch: false,
    },
    {
      label: "mobile-390x844",
      context: {
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 2.75,
        isMobile: true,
        hasTouch: true,
      },
      touch: true,
    },
    {
      label: "short-touch-421x386",
      context: {
        viewport: { width: 421, height: 386 },
        deviceScaleFactor: 2.75,
        isMobile: true,
        hasTouch: true,
      },
      touch: true,
    },
  ];
  const viewportResults = [];
  for (const spec of viewportSpecs) {
    const context = await browser.newContext(spec.context);
    const page = await context.newPage();
    const health = trackPageHealth(page, `${latest.date} ${spec.label}`);
    const url = new URL(latestPaths.liveUrl);
    url.searchParams.set("from", "timetable");
    url.searchParams.set("qa", spec.label);
    await page.goto(url.href, { waitUntil: "domcontentloaded" });
    const actions = page.locator(".gh-work-note-actions");
    const workNote = page.locator(".gh-work-note-button");
    const archiveLink = page.locator(".gh-artwork-archive-link");
    const fold = page.locator(".gh-fold-toggle");
    await actions.waitFor({ state: "visible" });
    await fold.waitFor({ state: "visible" });
    await actions.scrollIntoViewIfNeeded();

    const geometry = await page.evaluate(() => {
      const actionElement = document.querySelector(".gh-work-note-actions");
      const workNoteElement = document.querySelector(".gh-work-note-button");
      const archiveElement = document.querySelector(".gh-artwork-archive-link");
      const hostElement = actionElement.parentElement;
      const actionRect = actionElement.getBoundingClientRect();
      const workNoteRect = workNoteElement.getBoundingClientRect();
      const archiveRect = archiveElement.getBoundingClientRect();
      const hostRect = hostElement.getBoundingClientRect();
      const foldRect = document.querySelector(".gh-fold-toggle").getBoundingClientRect();
      const overlapWidth = Math.max(
        0,
        Math.min(actionRect.right, foldRect.right)
          - Math.max(actionRect.left, foldRect.left),
      );
      const overlapHeight = Math.max(
        0,
        Math.min(actionRect.bottom, foldRect.bottom)
          - Math.max(actionRect.top, foldRect.top),
      );
      return {
        viewport: { width: innerWidth, height: innerHeight },
        horizontalOverflow:
          document.documentElement.scrollWidth - document.documentElement.clientWidth,
        actions: actionRect.toJSON(),
        workNote: workNoteRect.toJSON(),
        archive: archiveRect.toJSON(),
        host: hostRect.toJSON(),
        hostClass: hostElement.className,
        actionPosition: getComputedStyle(actionElement).position,
        isLastChild: hostElement.lastElementChild === actionElement,
        fold: foldRect.toJSON(),
        overlapArea: overlapWidth * overlapHeight,
      };
    });
    assert.ok(
      geometry.horizontalOverflow <= 1,
      `${spec.label} horizontal overflow ${geometry.horizontalOverflow}`,
    );
    assert.ok(
      geometry.workNote.height >= 40 && geometry.archive.height >= 40,
      `${spec.label} action touch targets are too short`,
    );
    assert.ok(
      /gh-work-note-host/.test(geometry.hostClass)
        && geometry.actionPosition === "static"
        && geometry.isLastChild
        && geometry.actions.left >= geometry.host.left - 1
        && geometry.actions.top >= geometry.host.top - 1
        && geometry.actions.right <= geometry.host.right + 1
        && geometry.actions.bottom <= geometry.host.bottom + 1,
      `${spec.label} action row is not final inside its panel: ${JSON.stringify(geometry)}`,
    );
    assert.ok(
      geometry.actions.left >= 0
        && geometry.actions.top >= 0
        && geometry.actions.right <= geometry.viewport.width
        && geometry.actions.bottom <= geometry.viewport.height,
      `${spec.label} actions are not reachable in the viewport: ${JSON.stringify(geometry)}`,
    );
    assert.ok(
      geometry.fold.left >= 0
        && geometry.fold.top >= 0
        && geometry.fold.right <= geometry.viewport.width
        && geometry.fold.bottom <= geometry.viewport.height,
      `${spec.label} fold toggle outside viewport: ${JSON.stringify(geometry)}`,
    );
    assert.equal(
      geometry.overlapArea,
      0,
      `${spec.label} actions collide with fold toggle`,
    );

    if (spec.touch) await fold.tap();
    else await fold.click();
    await page.waitForFunction(
      () => document.body.classList.contains("gh-text-folded"),
    );
    assert.equal(
      await actions.isVisible(),
      false,
      `${spec.label} folded information panel left actions floating`,
    );
    if (spec.touch) await fold.tap();
    else await fold.click();
    await page.waitForFunction(
      () => !document.body.classList.contains("gh-text-folded"),
    );
    assert.equal(
      await actions.isVisible(),
      true,
      `${spec.label} actions did not return with the panel`,
    );

    if (spec.touch) await workNote.tap();
    else await workNote.click();
    const modal = page.locator(".gh-work-note-modal");
    await modal.waitFor({ state: "visible" });
    const dialogGeometry = await page.evaluate(() => {
      const modalElement = document.querySelector(".gh-work-note-modal");
      const glassElement = modalElement.querySelector(".gh-work-note-glass");
      const closeElement = modalElement.querySelector(".gh-work-note-close");
      return {
        viewport: { width: innerWidth, height: innerHeight },
        modal: modalElement.getBoundingClientRect().toJSON(),
        glass: glassElement.getBoundingClientRect().toJSON(),
        close: closeElement.getBoundingClientRect().toJSON(),
        internalOverflow: glassElement.scrollHeight - glassElement.clientHeight,
        bodyLocked: document.body.classList.contains("gh-work-note-open"),
        closeFocused: document.activeElement === closeElement,
      };
    });
    assert.equal(dialogGeometry.bodyLocked, true, `${spec.label} body was not locked`);
    assert.equal(dialogGeometry.closeFocused, true, `${spec.label} close was not focused`);
    assert.ok(
      dialogGeometry.close.left >= 0
        && dialogGeometry.close.top >= 0
        && dialogGeometry.close.right <= dialogGeometry.viewport.width
        && dialogGeometry.close.bottom <= dialogGeometry.viewport.height,
      `${spec.label} close is unreachable: ${JSON.stringify(dialogGeometry)}`,
    );
    assert.ok(
      dialogGeometry.glass.top >= 0
        && dialogGeometry.glass.bottom <= dialogGeometry.viewport.height + 1,
      `${spec.label} glass exceeds viewport: ${JSON.stringify(dialogGeometry)}`,
    );
    if (spec.touch) {
      assert.ok(
        dialogGeometry.internalOverflow > 0,
        `${spec.label} dialog does not provide internal scroll`,
      );
    }
    const close = page.locator(".gh-work-note-close");
    if (spec.touch) await close.tap();
    else await close.click();
    await assertClosedWithFocusReturn(page, `${spec.label} close`);
    assert.equal(
      await archiveLink.getAttribute("href"),
      "../",
      `${spec.label} archive href changed`,
    );
    health.assertHealthy();
    viewportResults.push({
      label: spec.label,
      horizontalOverflow: geometry.horizontalOverflow,
      actionRowFinal: geometry.isLastChild,
      workNoteHeight: geometry.workNote.height,
      archiveHeight: geometry.archive.height,
      dialogInternalOverflow: dialogGeometry.internalOverflow,
      closeReachable: true,
    });
    await context.close();
  }

  const sum = (field) => results.reduce((total, result) => total + result[field], 0);
  console.log(JSON.stringify({
    passed: true,
    siteUrl: siteUrl.href,
    declaredArchivePages: expectedCount,
    directLivePages: results.length,
    workNoteButtons: sum("button"),
    archiveLinks: sum("archive"),
    actionRowsFinal: sum("finalRow"),
    modalCopyMatches: sum("modalCopy"),
    buttonOpenCloseChecks: sum("openClose"),
    embedHiddenPages: sum("embedHidden"),
    escapeCloseChecks: 1,
    insideClickChecks: 1,
    backdropCloseChecks: 1,
    focusReturnChecks: expectedCount + 2 + viewportSpecs.length,
    bodyScrollLockChecks: expectedCount + 2 + viewportSpecs.length,
    foldUnfoldChecks: 1 + viewportSpecs.length,
    archiveNavigationChecks: 1,
    viewportChecks: viewportSpecs.length,
    viewportResults,
    pageErrors: 0,
    sameOriginHttpFailures: 0,
  }, null, 2));
} finally {
  await browser.close();
}
