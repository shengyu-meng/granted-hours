#!/usr/bin/env node
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, readFile, stat, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const screenshotRoot = path.resolve(
  process.env.QA_SCREENSHOT_DIR
    || path.join(repositoryRoot, "audits", "rounded-hover-preview"),
);
const manifestPath = path.join(screenshotRoot, "evidence-manifest.json");
const privateFixtures = ["Mara Evergarden", "Orchid Lantern", "CNY 938,271.44"];
const animatedSampleDate = "2026-07-21";
const animatedSamplePath = "/archive/2026/07/2026-07-21/assets/visual-preview.gif";
const localQaHosts = new Set(["127.0.0.1", "localhost"]);
const auditedCanonicalPaths = new Map([
  ["granted-hours.pages.dev", animatedSamplePath],
  ["shengyu-meng.github.io", `/granted-hours${animatedSamplePath}`],
]);
const inspectionSettleMs = 340;
const screenshots = [];
const diagnostics = [];
const pageResponses = new WeakMap();
const evidence = {
  schema: "rounded-hover-preview-evidence-v1",
  passed: false,
  baseUrl,
  screenshots,
  lenses: {},
  mediaFallbacks: {},
  gifFrameProgression: null,
  reducedMotion: null,
  pointerCapabilities: {},
  contrast: {},
  diagnostics,
  errors: [],
};

await mkdir(screenshotRoot, { recursive: true });

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function repositoryRelativeArtifactPath(artifactPath) {
  const relativePath = path.relative(repositoryRoot, path.resolve(artifactPath));
  assert.ok(
    relativePath
      && relativePath !== ".."
      && !relativePath.startsWith(`..${path.sep}`)
      && !path.isAbsolute(relativePath),
    `artifact must remain inside the repository: ${artifactPath}`,
  );
  return relativePath.split(path.sep).join(path.posix.sep);
}

function assertPublicManifestPaths(manifest) {
  const localHome = homedir();
  const violations = [];
  const visit = (value, location = "$") => {
    if (typeof value === "string") {
      const reasons = [
        path.posix.isAbsolute(value) && "absolute POSIX path",
        path.win32.isAbsolute(value) && "absolute Windows path",
        /^file:\/\//i.test(value) && "file URL",
        /\/Users\//.test(value) && "macOS user directory",
        localHome && value.includes(localHome) && "home directory",
        value.includes(repositoryRoot) && "private repository path",
      ].filter(Boolean);
      if (reasons.length > 0) violations.push({ location, reasons, value });
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((entry, index) => visit(entry, `${location}[${index}]`));
      return;
    }
    if (value && typeof value === "object") {
      Object.entries(value).forEach(([key, entry]) => visit(entry, `${location}.${key}`));
    }
  };
  visit(manifest);
  assert.deepEqual(
    violations,
    [],
    `persisted evidence manifest contains private local paths: ${JSON.stringify(violations)}`,
  );
}

function parseRgb(value) {
  const channels = Array.isArray(value)
    ? value
    : String(value).match(/[\d.]+/g)?.slice(0, 3).map(Number);
  assert.equal(channels?.length, 3, `cannot parse RGB color: ${value}`);
  return channels;
}

function luminance(rgb) {
  const channels = rgb.map((channel) => {
    const value = channel / 255;
    return value <= 0.04045
      ? value / 12.92
      : ((value + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

function contrastRatio(foreground, background) {
  const light = luminance(parseRgb(foreground));
  const dark = luminance(parseRgb(background));
  return (Math.max(light, dark) + 0.05) / (Math.min(light, dark) + 0.05);
}

function composite(foreground, background, opacity) {
  return foreground.map(
    (channel, index) => channel * opacity + background[index] * (1 - opacity),
  );
}

function rectanglesOverlap(left, right, tolerance = 1) {
  return left.left < right.right - tolerance
    && right.left < left.right - tolerance
    && left.top < right.bottom - tolerance
    && right.top < left.bottom - tolerance;
}

async function createContext(browser, {
  theme = "dark",
  viewport = { width: 1440, height: 900 },
  touch = false,
  hasTouch = touch,
  isMobile = touch,
  reducedMotion = "no-preference",
} = {}) {
  const context = await browser.newContext({
    viewport,
    colorScheme: theme,
    reducedMotion,
    isMobile,
    hasTouch,
    deviceScaleFactor: isMobile ? 2 : 1,
  });
  await context.addInitScript((explicitTheme) => {
    localStorage.setItem("granted-hours-theme", explicitTheme);
  }, theme);
  return context;
}

function monitorPage(
  page,
  scenario,
  expectedRequestFailurePatterns = [],
  expectedConsoleErrorPatterns = [],
) {
  const responses = new Map();
  pageResponses.set(page, responses);
  const record = {
    scenario,
    consoleErrors: [],
    pageErrors: [],
    requestFailures: [],
  };
  page.on("pageerror", (error) => record.pageErrors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") {
      const text = message.text();
      record.consoleErrors.push({
        text,
        expected: expectedConsoleErrorPatterns.some((pattern) => pattern.test(text)),
      });
    }
  });
  page.on("requestfailed", (request) => {
    const url = request.url();
    record.requestFailures.push({
      url,
      expected: expectedRequestFailurePatterns.some((pattern) => pattern.test(url)),
    });
  });
  page.on("response", (response) => {
    responses.set(response.url(), {
      url: response.url(),
      status: response.status(),
      ok: response.ok(),
      contentType: response.headers()["content-type"] || "",
    });
  });
  diagnostics.push(record);
  return record;
}

function assertNoUnexpectedDiagnostics(record) {
  assert.deepEqual(record.pageErrors, [], `${record.scenario}: page errors`);
  assert.deepEqual(
    record.consoleErrors.filter((entry) => !entry.expected),
    [],
    `${record.scenario}: unexpected console errors`,
  );
  assert.deepEqual(
    record.requestFailures.filter((failure) => !failure.expected),
    [],
    `${record.scenario}: unexpected request failures`,
  );
}

async function openDay(page, date) {
  const url = new URL(baseUrl);
  url.searchParams.set("date", date);
  await page.goto(url.href, { waitUntil: "networkidle" });
  const dialog = page.locator("#dayDialog");
  if (
    !(await dialog.isVisible())
    || await dialog.getAttribute("data-selected-date") !== date
  ) {
    await page.locator(`.calendar-day-button[data-date="${date}"]`).click();
  }
  await page.waitForSelector("#dayDialog.is-open");
  await page.waitForFunction(
    () => document.querySelector(".timeline-reading-layer.is-placed")
      && document.querySelectorAll(".event-reading-card").length > 0,
  );
}

async function lensState(page) {
  return page.locator("#inspectionLens").evaluate((lens) => {
    const rect = lens.getBoundingClientRect();
    const style = getComputedStyle(lens);
    const media = lens.querySelector("video, img");
    const trigger = document.querySelector(
      `.event-reading-card[data-reading-id="${CSS.escape(lens.dataset.readingId || "")}"]`,
    );
    const triggerRect = trigger?.getBoundingClientRect();
    return {
      hidden: lens.hidden,
      visible: !lens.hidden
        && lens.classList.contains("is-visible")
        && style.visibility !== "hidden"
        && Number(style.opacity) > 0,
      readingId: lens.dataset.readingId || "",
      category: lens.dataset.category || "",
      mediaKind: lens.dataset.mediaKind || "",
      mediaState: lens.dataset.mediaState || "",
      mediaDecodeState: lens.dataset.mediaDecodeState || "",
      capability: {
        rootClass: document.documentElement.classList.contains("inspection-lens-capable"),
        rootState: document.documentElement.dataset.inspectionLensCapability || "",
        fineHover: matchMedia("(hover: hover) and (pointer: fine)").matches,
        anyCoarse: matchMedia("(any-pointer: coarse)").matches,
      },
      pointerEvents: style.pointerEvents,
      display: style.display,
      transitionDuration: style.transitionDuration,
      rect: {
        left: rect.left,
        top: rect.top,
        right: rect.right,
        bottom: rect.bottom,
        width: rect.width,
        height: rect.height,
      },
      triggerRect: triggerRect
        ? {
          left: triggerRect.left,
          top: triggerRect.top,
          right: triggerRect.right,
          bottom: triggerRect.bottom,
        }
        : null,
      viewport: { width: innerWidth, height: innerHeight },
      overflow: document.documentElement.scrollWidth
        - document.documentElement.clientWidth,
      media: media
        ? {
          tag: media.tagName,
          src: media.currentSrc || media.getAttribute("src") || "",
          complete: media instanceof HTMLImageElement ? media.complete : null,
          naturalWidth: media instanceof HTMLImageElement ? media.naturalWidth : null,
          naturalHeight: media instanceof HTMLImageElement ? media.naturalHeight : null,
          readyState: media instanceof HTMLMediaElement ? media.readyState : null,
          autoplay: media instanceof HTMLMediaElement ? media.autoplay : false,
          paused: media instanceof HTMLMediaElement ? media.paused : null,
        }
        : null,
    };
  });
}

async function waitForOpenLens(page, readingId = null) {
  await page.waitForFunction(
    (expectedReadingId) => {
      const lens = document.querySelector("#inspectionLens");
      return lens
        && !lens.hidden
        && lens.classList.contains("is-visible")
        && Number(getComputedStyle(lens).opacity) >= 0.99
        && (!expectedReadingId || lens.dataset.readingId === expectedReadingId);
    },
    readingId,
  );
  return lensState(page);
}

async function waitForClosedLens(page) {
  await page.waitForFunction(() => {
    const lens = document.querySelector("#inspectionLens");
    return lens?.hidden === true;
  });
}

async function focusReadingCardWithKeyboard(page, key, label) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await page.keyboard.press(key);
    const readingId = await page.evaluate(() => (
      document.activeElement instanceof Element
        ? document.activeElement.closest(".event-reading-card")?.dataset.readingId || ""
        : ""
    ));
    if (!readingId) continue;
    const lens = await waitForOpenLens(page, readingId);
    return { readingId, lens };
  }
  assert.fail(`${label}: ${key} did not reach a reading card`);
}

async function dispatchPenActivation(cdpSession, card, afterPointerdown = null) {
  const box = await card.boundingBox();
  assert.ok(box, "pen activation target has no bounding box");
  const point = {
    x: box.x + box.width / 2,
    y: box.y + box.height / 2,
  };
  await cdpSession.send("Input.dispatchMouseEvent", {
    type: "mousePressed",
    ...point,
    button: "left",
    buttons: 1,
    clickCount: 1,
    pointerType: "pen",
  });
  if (afterPointerdown) await afterPointerdown();
  await cdpSession.send("Input.dispatchMouseEvent", {
    type: "mouseReleased",
    ...point,
    button: "left",
    buttons: 0,
    clickCount: 1,
    pointerType: "pen",
  });
}

async function resetLensForNonHoverCapture(page, label) {
  const neutral = page.locator("#timelineTitle:visible, .dialog-toolbar:visible, #themeToggle:visible")
    .first();
  if (await neutral.count()) {
    const box = await neutral.boundingBox();
    if (box) await page.mouse.move(box.x + Math.min(8, box.width / 2), box.y + 4);
  } else {
    await page.mouse.move(2, 2);
  }
  await page.evaluate(() => {
    const active = document.activeElement;
    if (active instanceof HTMLElement && active.closest(".event-reading-card")) active.blur();
  });
  await page.waitForTimeout(330);
  const state = await lensState(page);
  assert.equal(state.visible, false, `${label}: unintended inspection lens visible`);
  assert.equal(state.hidden, true, `${label}: inspection lens did not finish hiding`);
  assert.equal(state.readingId, "", `${label}: stale inspection trigger`);
  assert.equal(state.mediaKind, "", `${label}: stale inspection media`);
  return state;
}

async function capture(page, fileName, { intentionalHover = false } = {}) {
  if (intentionalHover) {
    assert.equal((await lensState(page)).visible, true, `${fileName}: intentional lens missing`);
  } else {
    await resetLensForNonHoverCapture(page, fileName);
  }
  const destination = path.join(screenshotRoot, fileName);
  const bytes = await page.screenshot({
    path: destination,
    fullPage: false,
    animations: "disabled",
    scale: "css",
  });
  screenshots.push({
    path: repositoryRelativeArtifactPath(destination),
    type: intentionalHover ? "intentional-hover" : "non-hover",
    bytes: bytes.length,
    sha256: sha256(bytes),
  });
}

async function proveAnimatedFrameProgression(page) {
  const media = page.locator("#inspectionLens .inspection-lens-media");
  const source = await page.locator("#inspectionLens img").evaluate((image) => ({
    src: image.currentSrc,
    sameOrigin: new URL(image.currentSrc).origin === location.origin,
    complete: image.complete,
    naturalWidth: image.naturalWidth,
    naturalHeight: image.naturalHeight,
  }));
  const canonicalMetadataUrl = await page.locator("#selfPreview").getAttribute(
    "data-animated-preview-url",
  );
  assert.ok(canonicalMetadataUrl, "audited canonical visual_preview_url metadata is missing");

  const pageUrl = new URL(page.url());
  const sourceUrl = new URL(source.src);
  const metadataUrl = new URL(canonicalMetadataUrl);
  const isLocalQa = localQaHosts.has(pageUrl.hostname);
  const expectedMetadataPath = auditedCanonicalPaths.get(metadataUrl.hostname);

  assert.equal(metadataUrl.protocol, "https:", "canonical visual_preview_url must use HTTPS");
  assert.ok(
    expectedMetadataPath,
    `canonical visual_preview_url host is not public-safe: ${metadataUrl.hostname}`,
  );
  assert.equal(metadataUrl.username, "", "canonical visual_preview_url must not contain a username");
  assert.equal(metadataUrl.password, "", "canonical visual_preview_url must not contain a password");
  assert.equal(metadataUrl.port, "", "canonical visual_preview_url must use the default HTTPS port");
  assert.equal(metadataUrl.pathname, expectedMetadataPath);
  assert.equal(metadataUrl.search, "", "canonical visual_preview_url must not contain a query");
  assert.equal(metadataUrl.hash, "", "canonical visual_preview_url must not contain a fragment");

  assert.equal(sourceUrl.username, "", "rendered GIF URL must not contain a username");
  assert.equal(sourceUrl.password, "", "rendered GIF URL must not contain a password");
  assert.equal(sourceUrl.search, "", "rendered GIF URL must not contain a query");
  assert.equal(sourceUrl.hash, "", "rendered GIF URL must not contain a fragment");
  if (isLocalQa) {
    assert.ok(
      ["http:", "https:"].includes(sourceUrl.protocol),
      "local rendered GIF URL must use HTTP or HTTPS",
    );
    assert.ok(localQaHosts.has(sourceUrl.hostname), "local rendered GIF URL left localhost");
    assert.equal(sourceUrl.origin, pageUrl.origin, "local rendered GIF URL is not same-origin");
    assert.equal(sourceUrl.pathname, animatedSamplePath);
  } else {
    assert.equal(sourceUrl.protocol, "https:", "deployed rendered GIF URL must use HTTPS");
    assert.ok(
      auditedCanonicalPaths.has(sourceUrl.hostname),
      `deployed rendered GIF host is not public-safe: ${sourceUrl.hostname}`,
    );
    assert.equal(sourceUrl.port, "", "deployed rendered GIF URL must use the default HTTPS port");
    assert.equal(
      sourceUrl.href,
      metadataUrl.href,
      "deployed rendered GIF URL does not exactly match canonical timetable metadata",
    );
  }

  assert.equal(source.complete, true, "animated GIF did not finish loading");
  assert.ok(
    source.naturalWidth > 0 && source.naturalHeight > 0,
    `animated GIF did not decode to positive dimensions: ${source.naturalWidth}x${source.naturalHeight}`,
  );
  const network = pageResponses.get(page)?.get(sourceUrl.href);
  assert.ok(network, `no browser network response observed for animated GIF: ${sourceUrl.href}`);
  assert.equal(network.ok, true, `animated GIF network response failed: ${network?.status}`);
  assert.ok(
    network.status >= 200 && network.status < 300,
    `animated GIF network response was not successful: ${network.status}`,
  );
  assert.match(network.contentType, /^image\/gif(?:;|$)/i);

  source.canonicalMetadataUrl = metadataUrl.href;
  source.localQa = isLocalQa;
  source.exactCanonicalMetadataMatch = isLocalQa
    ? sourceUrl.pathname === animatedSamplePath
    : sourceUrl.href === metadataUrl.href;
  source.network = network;
  const firstElapsedMs = await page.evaluate(() => performance.now());
  const firstBytes = await media.screenshot({ type: "png", scale: "css" });
  const firstHash = sha256(firstBytes);
  let secondElapsedMs = firstElapsedMs;
  let secondBytes = firstBytes;
  let secondHash = firstHash;
  for (let attempt = 1; attempt <= 6 && secondHash === firstHash; attempt += 1) {
    await page.waitForTimeout(230);
    secondElapsedMs = await page.evaluate(() => performance.now());
    secondBytes = await media.screenshot({ type: "png", scale: "css" });
    secondHash = sha256(secondBytes);
  }
  assert.notEqual(firstHash, secondHash, "animated GIF pixels did not progress");
  const firstPath = path.join(screenshotRoot, "2026-07-21-autonomous-gif-frame-a.png");
  const secondPath = path.join(screenshotRoot, "2026-07-21-autonomous-gif-frame-b.png");
  await Promise.all([
    writeFile(firstPath, firstBytes),
    writeFile(secondPath, secondBytes),
  ]);
  screenshots.push(
    {
      path: repositoryRelativeArtifactPath(firstPath),
      type: "intentional-hover-gif-frame",
      bytes: firstBytes.length,
      sha256: firstHash,
    },
    {
      path: repositoryRelativeArtifactPath(secondPath),
      type: "intentional-hover-gif-frame",
      bytes: secondBytes.length,
      sha256: secondHash,
    },
  );
  return {
    method: "two timed rendered lens-media PNG crops with SHA-256",
    source,
    first: {
      path: repositoryRelativeArtifactPath(firstPath),
      elapsedMs: firstElapsedMs,
      sha256: firstHash,
    },
    second: {
      path: repositoryRelativeArtifactPath(secondPath),
      elapsedMs: secondElapsedMs,
      sha256: secondHash,
    },
    changed: true,
  };
}

async function assertRoundedAndSemantic(page, label) {
  const result = await page.evaluate(() => {
    const colorCanvas = document.createElement("canvas");
    colorCanvas.width = 1;
    colorCanvas.height = 1;
    const colorContext = colorCanvas.getContext("2d", { willReadFrequently: true });
    const rgb = (value) => {
      colorContext.clearRect(0, 0, 1, 1);
      colorContext.fillStyle = "#000";
      colorContext.fillStyle = value;
      colorContext.fillRect(0, 0, 1, 1);
      return Array.from(colorContext.getImageData(0, 0, 1, 1).data.slice(0, 3));
    };
    const pageBackground = rgb(
      getComputedStyle(document.documentElement).getPropertyValue("--page-bg").trim(),
    );
    const cards = [...document.querySelectorAll(".event-reading-card")].map((card) => {
      const style = getComputedStyle(card);
      const background = rgb(style.backgroundColor);
      const opacity = Number(style.opacity);
      const roles = [
        ...card.querySelectorAll([
          ".reading-title",
          ".reading-summary",
          ".assigned-time",
          ".assigned-category",
          ".pulse-time",
          ".pulse-count",
          ".pulse-duration",
          ".autonomous-time",
          ".autonomous-kicker",
          ".autonomous-open-copy",
        ].join(",")),
      ].filter((role) => {
        const roleStyle = getComputedStyle(role);
        return roleStyle.display !== "none"
          && roleStyle.visibility !== "hidden"
          && role.textContent.trim();
      }).map((role) => ({
        className: role.className,
        text: role.textContent.trim().slice(0, 80),
        color: rgb(getComputedStyle(role).color),
      }));
      return {
        readingId: card.dataset.readingId,
        layer: card.dataset.layer,
        category: card.dataset.category,
        radius: Number.parseFloat(style.borderTopLeftRadius),
        accent: style.getPropertyValue("--category-accent").trim(),
        textColorVariable: style.getPropertyValue("--category-text").trim(),
        background,
        pageBackground,
        opacity,
        zIndex: Number(style.zIndex),
        borderColor: style.borderColor,
        boxShadow: style.boxShadow,
        backgroundImage: style.backgroundImage,
        roles,
      };
    });
    const footprints = [...document.querySelectorAll(".event-footprint")].map((footprint) => ({
      radius: Number.parseFloat(getComputedStyle(footprint).borderTopLeftRadius),
    }));
    return {
      cards,
      footprints,
      overflow: document.documentElement.scrollWidth
        - document.documentElement.clientWidth,
    };
  });

  assert.ok(result.cards.length > 0, `${label}: no reading cards`);
  assert.ok(
    result.cards.every((card) => card.radius >= 12 && card.radius <= 20),
    `${label}: reading-card radius ${JSON.stringify(result.cards)}`,
  );
  assert.ok(
    result.footprints.every((footprint) => footprint.radius >= 3 && footprint.radius <= 6),
    `${label}: footprint radius ${JSON.stringify(result.footprints)}`,
  );
  assert.ok(result.cards.every((card) => card.category), `${label}: missing semantic category`);
  assert.ok(result.cards.every((card) => card.accent), `${label}: missing semantic accent`);
  assert.ok(
    result.cards.every((card) => card.textColorVariable),
    `${label}: missing category text color variable`,
  );
  const roleContrast = result.cards.flatMap((card) => card.roles.map((role) => {
    const effectiveForeground = composite(role.color, card.pageBackground, card.opacity);
    const effectiveBackground = composite(card.background, card.pageBackground, card.opacity);
    return {
      readingId: card.readingId,
      layer: card.layer,
      category: card.category,
      className: role.className,
      ratio: contrastRatio(effectiveForeground, effectiveBackground),
    };
  }));
  assert.ok(roleContrast.length > 0, `${label}: no descendant text roles sampled`);
  const climateContrastSamples = roleContrast.filter((sample) => sample.layer === "climate");
  const foregroundContrastSamples = roleContrast.filter((sample) => sample.layer !== "climate");
  assert.ok(
    foregroundContrastSamples.every((sample) => sample.ratio >= 4.5),
    `${label}: descendant role contrast ${JSON.stringify(
      foregroundContrastSamples.filter((sample) => sample.ratio < 4.5),
    )}`,
  );
  assert.ok(
    climateContrastSamples.every((sample) => sample.ratio >= 3.0),
    `${label}: frosted climate role contrast ${JSON.stringify(
      climateContrastSamples.filter((sample) => sample.ratio < 3.0),
    )}`,
  );
  for (const layer of ["event", "climate", "beacon"]) {
    assert.ok(
      roleContrast.some((sample) => sample.layer === layer),
      `${label}: no descendant contrast sample for ${layer}`,
    );
  }
  for (const category of [
    "assigned-work",
    "ah-market-scan",
    "service-support",
    "autonomous-artwork",
  ]) {
    assert.ok(
      roleContrast.some((sample) => sample.category === category),
      `${label}: no descendant contrast sample for ${category}`,
    );
  }
  const representatives = new Map(
    result.cards.map((card) => [card.category, card.accent]),
  );
  const requiredCategories = [
    "assigned-work",
    "ah-market-scan",
    "us-market-scan",
    "service-support",
    "autonomous-artwork",
  ];
  // The daily AI brief folds into the background rollup family (2026-08-06
  // standard), so an ai-brief card is optional rather than required.
  if (representatives.has("ai-brief")) {
    requiredCategories.push("ai-brief");
  }
  // Alert-bearing support windows are rolled into the daily background card;
  // a warning-exception card is therefore optional rather than required.
  if (representatives.has("daily-reminder")) {
    requiredCategories.push("daily-reminder");
  }
  for (const category of requiredCategories) {
    assert.ok(representatives.has(category), `${label}: missing category ${category}`);
  }
  // Assigned collaboration cards may carry an explicit task color; validate
  // the fixed category families independently of that intentional override.
  const fixedAccentCategories = requiredCategories.filter((category) => category !== "assigned-work");
  const requiredAccents = fixedAccentCategories.map((category) => representatives.get(category));
  assert.equal(
    new Set(requiredAccents).size,
    requiredAccents.length,
    `${label}: fixed category accents are not distinct`,
  );
  const climate = result.cards.filter((card) => card.layer === "climate");
  const foreground = result.cards.filter((card) => ["event", "beacon"].includes(card.layer));
  assert.ok(
    climate.every((card) => card.opacity === 1),
    `${label}: climate cards must recede without transparency`,
  );
  assert.ok(
    Math.max(...climate.map((card) => card.zIndex))
      < Math.min(...foreground.map((card) => card.zIndex)),
    `${label}: climate stacking outranks foreground`,
  );
  assert.ok(
    climate.every((card) => foreground.some(
      (foregroundCard) => card.boxShadow !== foregroundCard.boxShadow,
    )),
    `${label}: climate lacks distinct recessed shadow treatment`,
  );
  assert.ok(result.overflow <= 1, `${label}: horizontal overflow ${result.overflow}`);
  evidence.contrast[label] = {
    minimumRatio: Math.min(...roleContrast.map((sample) => sample.ratio)),
    samples: roleContrast,
    climate: climate.map((card) => ({
      category: card.category,
      opacity: card.opacity,
      zIndex: card.zIndex,
      borderColor: card.borderColor,
      boxShadow: card.boxShadow,
      backgroundImage: card.backgroundImage,
    })),
  };
}

async function inspectPrivateSurface(page) {
  return page.evaluate((fixtures) => {
    const lens = document.querySelector("#inspectionLens");
    const attributes = lens
      ? [...lens.attributes].map((attribute) => `${attribute.name}=${attribute.value}`).join(" ")
      : "";
    const surface = `${document.documentElement.innerHTML}\n${document.body.innerText}\n${attributes}`;
    return fixtures.filter((fixture) => surface.includes(fixture));
  }, privateFixtures);
}

const browser = await chromium.launch({ headless: true });
const results = [];
let failure = null;

try {
  for (const theme of ["dark", "light"]) {
    const context = await createContext(browser, { theme });
    const page = await context.newPage();
    const diagnostic = monitorPage(page, `desktop-${theme}`);
    await openDay(page, animatedSampleDate);
    await assertRoundedAndSemantic(page, `desktop-${theme}`);
    assert.deepEqual(
      await page.evaluate(() => ({
        rootClass: document.documentElement.classList.contains("inspection-lens-capable"),
        rootState: document.documentElement.dataset.inspectionLensCapability,
        fineHover: matchMedia("(hover: hover) and (pointer: fine)").matches,
      })),
      { rootClass: true, rootState: "fine-hover", fineHover: true },
      `${theme}: root capability was not positively synchronized`,
    );

    const assigned = page.locator(
      '.event-reading-card[data-category="assigned-work"]',
    ).first();
    await assigned.scrollIntoViewIfNeeded();
    const assignedReadingId = await assigned.getAttribute("data-reading-id");
    await assigned.hover();
    const assignedLens = await waitForOpenLens(page, assignedReadingId);
    assert.equal(assignedLens.category, "assigned-work");
    assert.equal(assignedLens.mediaKind, "typographic");
    assert.equal(assignedLens.pointerEvents, "none");
    assert.ok(assignedLens.rect.left >= 12 && assignedLens.rect.top >= 12);
    assert.ok(assignedLens.rect.right <= assignedLens.viewport.width - 12);
    assert.ok(assignedLens.rect.bottom <= assignedLens.viewport.height - 12);
    assert.ok(assignedLens.overflow <= 1);
    assert.ok(
      !rectanglesOverlap(assignedLens.rect, assignedLens.triggerRect),
      `${theme}: inspection lens covers assigned trigger`,
    );
    if (theme === "dark") {
      await capture(page, "2026-07-21-desktop-dark-assigned-lens.png", {
        intentionalHover: true,
      });
      evidence.lenses.assigned = assignedLens;
    }

    const autonomous = page.locator(
      '.event-reading-card[data-category="autonomous-artwork"]',
    );
    await autonomous.scrollIntoViewIfNeeded();
    const autonomousReadingId = await autonomous.getAttribute("data-reading-id");
    await autonomous.hover();
    await page.waitForFunction(() => {
      const lens = document.querySelector("#inspectionLens");
      const image = lens?.querySelector("img");
      return lens?.dataset.mediaKind === "animated-image"
        && lens.dataset.mediaState === "ready"
        && lens.dataset.mediaDecodeState === "decoded"
        && image?.complete
        && image.naturalWidth > 0
        && image.naturalHeight > 0;
    });
    const autonomousLens = await waitForOpenLens(page, autonomousReadingId);
    assert.equal(autonomousLens.mediaKind, "animated-image");
    assert.equal(autonomousLens.mediaState, "ready");
    assert.equal(autonomousLens.mediaDecodeState, "decoded");
    assert.equal(autonomousLens.media?.tag, "IMG");
    assert.match(autonomousLens.media?.src || "", /visual-preview\.gif(?:\?.*)?$/);
    assert.ok(
      autonomousLens.media?.complete
        && autonomousLens.media?.naturalWidth > 0
        && autonomousLens.media?.naturalHeight > 0,
    );
    assert.ok(
      !rectanglesOverlap(autonomousLens.rect, autonomousLens.triggerRect),
      `${theme}: inspection lens covers autonomous trigger`,
    );
    if (theme === "dark") {
      evidence.gifFrameProgression = await proveAnimatedFrameProgression(page);
      await capture(page, "2026-07-21-desktop-dark-autonomous-motion-lens.png", {
        intentionalHover: true,
      });
      evidence.lenses.autonomousMotion = autonomousLens;
    }
    assert.notEqual(assignedLens.readingId, autonomousLens.readingId);

    await page.mouse.move(2, 2);
    await waitForClosedLens(page);
    await assigned.evaluate((card) => new Promise((resolve) => {
      const panel = document.querySelector("#dayDialogPanel");
      let settledTimer = 0;
      const finish = () => {
        panel.removeEventListener("scroll", settle);
        resolve();
      };
      const settle = () => {
        clearTimeout(settledTimer);
        settledTimer = setTimeout(finish, 120);
      };
      panel.addEventListener("scroll", settle);
      card.scrollIntoView({ block: "center" });
      settle();
      setTimeout(finish, 600);
    }));
    await assigned.evaluate((card) => card.focus({ preventScroll: true }));
    const focusedLens = await waitForOpenLens(page, assignedReadingId);
    assert.equal(focusedLens.readingId, assignedReadingId);
    await page.keyboard.press("Enter");
    await page.waitForSelector("#taskDialog.is-open");
    await waitForClosedLens(page);
    await page.keyboard.press("Escape");
    assert.equal(
      await assigned.evaluate((card) => document.activeElement === card),
      true,
      `${theme}: task-detail focus did not return`,
    );
    await waitForOpenLens(page, assignedReadingId);

    await page.locator("#dayDialogPanel").evaluate((panel) => {
      panel.scrollTop += 28;
    });
    await waitForClosedLens(page);
    await assigned.scrollIntoViewIfNeeded();
    await assigned.hover();
    await waitForOpenLens(page, assignedReadingId);
    await page.keyboard.press("Escape");
    await waitForClosedLens(page);
    assert.equal(await page.locator("#dayDialog").isHidden(), true);

    assert.deepEqual(await inspectPrivateSurface(page), []);
    assertNoUnexpectedDiagnostics(diagnostic);
    results.push({ mode: `desktop-${theme}`, assignedReadingId, autonomousReadingId });
    await context.close();
  }

  const lightContext = await createContext(browser, { theme: "light" });
  const lightPage = await lightContext.newPage();
  const lightDiagnostic = monitorPage(lightPage, "light-market-support-lens");
  await openDay(lightPage, "2026-07-22");
  const support = lightPage.locator(
    '.event-reading-card[data-category="service-support"]',
  ).first();
  await support.scrollIntoViewIfNeeded();
  await support.hover();
  const lightSupportLens = await waitForOpenLens(
    lightPage,
    await support.getAttribute("data-reading-id"),
  );
  await capture(lightPage, "2026-07-22-desktop-light-market-support-lens.png", {
    intentionalHover: true,
  });
  evidence.lenses.lightMarketSupport = lightSupportLens;
  assertNoUnexpectedDiagnostics(lightDiagnostic);
  await lightContext.close();

  const fallbackContext = await createContext(browser, { theme: "dark" });
  await fallbackContext.route("**/visual-preview.gif", (route) => route.abort("failed"));
  const fallbackPage = await fallbackContext.newPage();
  const fallbackDiagnostic = monitorPage(
    fallbackPage,
    "animated-load-failure-static-fallback",
    [/visual-preview\.gif(?:\?.*)?$/],
    [/Failed to load resource: net::ERR_FAILED/],
  );
  await openDay(fallbackPage, "2026-07-21");
  const fallbackAutonomous = fallbackPage.locator(
    '.event-reading-card[data-category="autonomous-artwork"]',
  );
  await fallbackAutonomous.scrollIntoViewIfNeeded();
  await fallbackAutonomous.hover();
  await fallbackPage.waitForFunction(() => {
    const lens = document.querySelector("#inspectionLens");
    const image = lens?.querySelector("img");
    return lens?.dataset.mediaKind === "static-image"
      && lens.dataset.mediaState === "ready"
      && lens.dataset.mediaDecodeState === "decoded"
      && image?.complete
      && image.naturalWidth > 0
      && image.naturalHeight > 0;
  });
  const fallbackLens = await lensState(fallbackPage);
  assert.match(fallbackLens.media?.src || "", /visual-preview\.webp(?:\?.*)?$/);
  evidence.mediaFallbacks.loadFailure = fallbackLens;
  assertNoUnexpectedDiagnostics(fallbackDiagnostic);
  await fallbackContext.close();

  const plateContext = await createContext(browser, { theme: "dark" });
  await plateContext.route("**/visual-preview.gif", (route) => route.abort("failed"));
  await plateContext.route("**/visual-preview.webp", (route) => route.abort("failed"));
  const platePage = await plateContext.newPage();
  const plateDiagnostic = monitorPage(
    platePage,
    "animated-and-static-load-failure-plate-fallback",
    [/visual-preview\.(?:gif|webp)(?:\?.*)?$/],
    [/Failed to load resource: net::ERR_FAILED/],
  );
  await openDay(platePage, "2026-07-21");
  const plateAutonomous = platePage.locator(
    '.event-reading-card[data-category="autonomous-artwork"]',
  );
  await plateAutonomous.scrollIntoViewIfNeeded();
  await plateAutonomous.hover();
  await platePage.waitForFunction(() => (
    document.querySelector("#inspectionLens")?.dataset.mediaKind === "typographic"
  ));
  const loadFailurePlate = await lensState(platePage);
  assert.equal(loadFailurePlate.mediaKind, "typographic");
  evidence.mediaFallbacks.allLoadFailure = loadFailurePlate;
  assertNoUnexpectedDiagnostics(plateDiagnostic);
  await plateContext.close();

  const decodeContext = await createContext(browser, { theme: "dark" });
  await decodeContext.addInitScript(() => {
    const nativeDecode = HTMLImageElement.prototype.decode;
    HTMLImageElement.prototype.decode = function decodeWithGifFailure() {
      if (
        this.closest("#inspectionLens")
        && new URL(this.src, location.href).pathname.endsWith(".gif")
      ) {
        return Promise.reject(new DOMException("forced GIF decode failure", "EncodingError"));
      }
      return nativeDecode.call(this);
    };
  });
  const decodePage = await decodeContext.newPage();
  const decodeDiagnostic = monitorPage(decodePage, "animated-decode-failure-static-fallback");
  await openDay(decodePage, "2026-07-21");
  const decodeAutonomous = decodePage.locator(
    '.event-reading-card[data-category="autonomous-artwork"]',
  );
  await decodeAutonomous.scrollIntoViewIfNeeded();
  await decodeAutonomous.hover();
  await decodePage.waitForFunction(() => {
    const lens = document.querySelector("#inspectionLens");
    return lens?.dataset.mediaKind === "static-image"
      && lens.dataset.mediaState === "ready"
      && lens.dataset.mediaDecodeState === "decoded";
  });
  const decodeFallbackLens = await lensState(decodePage);
  assert.match(decodeFallbackLens.media?.src || "", /visual-preview\.webp(?:\?.*)?$/);
  evidence.mediaFallbacks.decodeFailure = decodeFallbackLens;
  assertNoUnexpectedDiagnostics(decodeDiagnostic);
  await decodeContext.close();

  const decodePlateContext = await createContext(browser, { theme: "dark" });
  await decodePlateContext.addInitScript(() => {
    const nativeDecode = HTMLImageElement.prototype.decode;
    HTMLImageElement.prototype.decode = function decodeWithLensFailure() {
      if (this.closest("#inspectionLens")) {
        return Promise.reject(new DOMException("forced lens decode failure", "EncodingError"));
      }
      return nativeDecode.call(this);
    };
  });
  const decodePlatePage = await decodePlateContext.newPage();
  const decodePlateDiagnostic = monitorPage(
    decodePlatePage,
    "animated-and-static-decode-failure-plate-fallback",
  );
  await openDay(decodePlatePage, "2026-07-21");
  const decodePlateAutonomous = decodePlatePage.locator(
    '.event-reading-card[data-category="autonomous-artwork"]',
  );
  await decodePlateAutonomous.scrollIntoViewIfNeeded();
  await decodePlateAutonomous.hover();
  await decodePlatePage.waitForFunction(() => (
    document.querySelector("#inspectionLens")?.dataset.mediaKind === "typographic"
  ));
  const decodeFailurePlate = await lensState(decodePlatePage);
  evidence.mediaFallbacks.allDecodeFailure = decodeFailurePlate;
  assertNoUnexpectedDiagnostics(decodePlateDiagnostic);
  await decodePlateContext.close();

  const staleContext = await createContext(browser, { theme: "dark" });
  await staleContext.addInitScript(() => {
    const nativeDecode = HTMLImageElement.prototype.decode;
    let releaseDecode;
    window.__inspectionDecodeGate = {
      started: 0,
      release() {
        releaseDecode?.();
      },
    };
    HTMLImageElement.prototype.decode = function decodeWithGate() {
      if (
        this.closest("#inspectionLens")
        && new URL(this.src, location.href).pathname.endsWith(".gif")
      ) {
        window.__inspectionDecodeGate.started += 1;
        return new Promise((resolve) => {
          releaseDecode = resolve;
        });
      }
      return nativeDecode.call(this);
    };
  });
  const stalePage = await staleContext.newPage();
  const staleDiagnostic = monitorPage(stalePage, "decode-pending-and-stale-completion");
  await openDay(stalePage, "2026-07-21");
  const staleAutonomous = stalePage.locator(
    '.event-reading-card[data-category="autonomous-artwork"]',
  );
  await staleAutonomous.scrollIntoViewIfNeeded();
  await staleAutonomous.hover();
  await stalePage.waitForFunction(() => {
    const lens = document.querySelector("#inspectionLens");
    const image = lens?.querySelector("img");
    return window.__inspectionDecodeGate?.started > 0
      && lens?.dataset.mediaState === "loading"
      && lens.dataset.mediaDecodeState === "pending"
      && image?.complete
      && image.naturalWidth > 0
      && image.naturalHeight > 0;
  });
  const pendingAfterLoad = await lensState(stalePage);
  assert.equal(pendingAfterLoad.mediaState, "loading", "load alone marked GIF ready");
  const staleAssigned = stalePage.locator(
    '.event-reading-card[data-category="assigned-work"]',
  ).first();
  await staleAssigned.scrollIntoViewIfNeeded();
  await staleAssigned.hover();
  const staleAssignedReadingId = await staleAssigned.getAttribute("data-reading-id");
  await waitForOpenLens(stalePage, staleAssignedReadingId);
  await stalePage.evaluate(() => window.__inspectionDecodeGate.release());
  await stalePage.waitForTimeout(120);
  const afterStaleDecode = await lensState(stalePage);
  assert.equal(afterStaleDecode.readingId, staleAssignedReadingId);
  assert.equal(afterStaleDecode.mediaKind, "typographic");
  evidence.mediaFallbacks.decodeReadinessAndStaleGuard = {
    pendingAfterLoad,
    afterStaleDecode,
    passed: true,
  };
  assertNoUnexpectedDiagnostics(staleDiagnostic);
  await staleContext.close();

  const reducedContext = await createContext(browser, {
    theme: "dark",
    reducedMotion: "reduce",
  });
  const reducedPage = await reducedContext.newPage();
  const reducedDiagnostic = monitorPage(reducedPage, "reduced-motion-static");
  await openDay(reducedPage, "2026-07-21");
  const reducedAutonomous = reducedPage.locator(
    '.event-reading-card[data-category="autonomous-artwork"]',
  );
  await reducedAutonomous.scrollIntoViewIfNeeded();
  await reducedAutonomous.hover();
  await reducedPage.waitForFunction(() => {
    const lens = document.querySelector("#inspectionLens");
    const image = lens?.querySelector("img");
    return lens?.dataset.mediaKind === "static-image"
      && lens.dataset.mediaState === "ready"
      && lens.dataset.mediaDecodeState === "decoded"
      && image?.complete
      && image.naturalWidth > 0
      && image.naturalHeight > 0;
  });
  const reducedLens = await lensState(reducedPage);
  assert.match(reducedLens.media?.src || "", /visual-preview\.webp(?:\?.*)?$/);
  assert.equal(reducedLens.media?.autoplay, false);
  assert.ok(
    reducedLens.transitionDuration
      .split(",")
      .every((duration) => Number.parseFloat(duration) <= 0.000001),
    `reduced-motion lens transition: ${reducedLens.transitionDuration}`,
  );
  evidence.reducedMotion = {
    prefersReducedMotion: await reducedPage.evaluate(
      () => matchMedia("(prefers-reduced-motion: reduce)").matches,
    ),
    media: reducedLens,
    animatedAssetUsed: /visual-preview\.gif(?:\?.*)?$/.test(reducedLens.media?.src || ""),
    autoplay: reducedLens.media?.autoplay,
    transitionDuration: reducedLens.transitionDuration,
    passed: true,
  };
  assert.equal(evidence.reducedMotion.animatedAssetUsed, false);
  assertNoUnexpectedDiagnostics(reducedDiagnostic);
  await reducedContext.close();

  const hybridContext = await createContext(browser, {
    theme: "dark",
    hasTouch: true,
    isMobile: false,
  });
  await hybridContext.addInitScript(() => {
    const nativeMatchMedia = window.matchMedia.bind(window);
    const overrides = new Map();
    const createOverride = (media, initial) => {
      let matches = initial;
      const listeners = new Set();
      const mediaQueryList = {
        media,
        get matches() {
          return matches;
        },
        onchange: null,
        addEventListener(type, listener) {
          if (type === "change") listeners.add(listener);
        },
        removeEventListener(type, listener) {
          if (type === "change") listeners.delete(listener);
        },
        addListener(listener) {
          listeners.add(listener);
        },
        removeListener(listener) {
          listeners.delete(listener);
        },
        dispatchEvent(event) {
          for (const listener of listeners) listener.call(mediaQueryList, event);
          mediaQueryList.onchange?.call(mediaQueryList, event);
          return true;
        },
        setMatches(next) {
          if (matches === next) return;
          matches = next;
          mediaQueryList.dispatchEvent(new Event("change"));
        },
      };
      overrides.set(media, mediaQueryList);
      return mediaQueryList;
    };
    createOverride("(hover: hover) and (pointer: fine)", true);
    window.matchMedia = (query) => overrides.get(query) || nativeMatchMedia(query);
    window.__setFineHover = (matches) => {
      overrides.get("(hover: hover) and (pointer: fine)").setMatches(matches);
    };
  });
  const hybridPage = await hybridContext.newPage();
  const hybridDiagnostic = monitorPage(hybridPage, "fine-primary-coarse-secondary-hybrid");
  await openDay(hybridPage, "2026-07-21");
  const hybridCapability = await hybridPage.evaluate(() => ({
    fineHover: matchMedia("(hover: hover) and (pointer: fine)").matches,
    anyCoarse: matchMedia("(any-pointer: coarse)").matches,
    maxTouchPoints: navigator.maxTouchPoints,
    rootClass: document.documentElement.classList.contains("inspection-lens-capable"),
    rootState: document.documentElement.dataset.inspectionLensCapability,
  }));
  assert.deepEqual(hybridCapability, {
    fineHover: true,
    anyCoarse: true,
    maxTouchPoints: 1,
    rootClass: true,
    rootState: "fine-hover",
  });
  const hybridTouchCard = hybridPage.locator(
    '.event-reading-card[data-category="service-support"]',
  ).first();
  await hybridTouchCard.scrollIntoViewIfNeeded();
  await hybridTouchCard.hover();
  const hybridOpenLens = await waitForOpenLens(
    hybridPage,
    await hybridTouchCard.getAttribute("data-reading-id"),
  );
  assert.equal(hybridOpenLens.display, "block");
  await hybridPage.evaluate(() => window.__setFineHover(false));
  await hybridPage.waitForFunction(() => (
    document.documentElement.dataset.inspectionLensCapability === "unavailable"
    && document.querySelector("#inspectionLens")?.hidden
  ));
  const hybridDisabled = await lensState(hybridPage);
  assert.equal(hybridDisabled.visible, false);
  await hybridPage.evaluate(() => window.__setFineHover(true));
  const hybridReenabled = await waitForOpenLens(
    hybridPage,
    await hybridTouchCard.getAttribute("data-reading-id"),
  );
  await hybridTouchCard.tap();
  const touchFirstLens = await lensState(hybridPage);
  assert.equal(await hybridTouchCard.getAttribute("aria-pressed"), "true");
  assert.equal(await hybridPage.locator("#taskDialog").isHidden(), true);
  assert.equal(touchFirstLens.visible, false);
  assert.equal(touchFirstLens.hidden, true);
  await hybridTouchCard.tap();
  await hybridPage.waitForSelector("#taskDialog.is-open");
  const touchSecondLens = await lensState(hybridPage);
  assert.equal(touchSecondLens.visible, false);
  assert.equal(touchSecondLens.hidden, true);
  await hybridPage.locator("#closeTaskDetail").tap();
  await hybridPage.waitForFunction(() => document.querySelector("#taskDialog")?.hidden);
  await waitForClosedLens(hybridPage);
  const touchCloseLens = await lensState(hybridPage);
  assert.equal(
    await hybridTouchCard.evaluate((card) => document.activeElement === card),
    true,
    "hybrid touch: focus did not return to the coarse-activated card",
  );
  assert.equal(touchCloseLens.visible, false);
  assert.equal(touchCloseLens.hidden, true);
  const touchKeyboardForward = await focusReadingCardWithKeyboard(
    hybridPage,
    "Tab",
    "hybrid touch keyboard recovery",
  );
  const touchKeyboardReverse = await focusReadingCardWithKeyboard(
    hybridPage,
    "Shift+Tab",
    "hybrid touch reverse keyboard recovery",
  );
  await hybridPage.locator("#closeDetail").focus();
  await hybridPage.locator(".dialog-toolbar").hover();
  await waitForClosedLens(hybridPage);
  await hybridPage.waitForTimeout(inspectionSettleMs);
  await hybridTouchCard.hover();
  const touchMouseRecovery = await waitForOpenLens(
    hybridPage,
    await hybridTouchCard.getAttribute("data-reading-id"),
  );

  const hybridPenCard = hybridPage.locator(
    '.event-reading-card[data-category="assigned-work"]',
  ).first();
  await hybridPenCard.scrollIntoViewIfNeeded();
  const penSession = await hybridContext.newCDPSession(hybridPage);
  await dispatchPenActivation(penSession, hybridPenCard, async () => {
    const pointerdownLens = await lensState(hybridPage);
    assert.equal(pointerdownLens.visible, false);
    assert.equal(pointerdownLens.hidden, true);
  });
  const penFirstLens = await lensState(hybridPage);
  assert.equal(await hybridPenCard.getAttribute("aria-pressed"), "true");
  assert.equal(await hybridPage.locator("#taskDialog").isHidden(), true);
  assert.equal(penFirstLens.visible, false);
  assert.equal(penFirstLens.hidden, true);
  await dispatchPenActivation(penSession, hybridPenCard, async () => {
    const pointerdownLens = await lensState(hybridPage);
    assert.equal(pointerdownLens.visible, false);
    assert.equal(pointerdownLens.hidden, true);
  });
  await hybridPage.waitForSelector("#taskDialog.is-open");
  const penSecondLens = await lensState(hybridPage);
  assert.equal(penSecondLens.visible, false);
  assert.equal(penSecondLens.hidden, true);
  await hybridPage.locator("#closeTaskDetail").tap();
  await hybridPage.waitForFunction(() => document.querySelector("#taskDialog")?.hidden);
  await waitForClosedLens(hybridPage);
  const penCloseLens = await lensState(hybridPage);
  assert.equal(
    await hybridPenCard.evaluate((card) => document.activeElement === card),
    true,
    "hybrid pen: focus did not return to the coarse-activated card",
  );
  assert.equal(penCloseLens.visible, false);
  assert.equal(penCloseLens.hidden, true);
  const penKeyboardForward = await focusReadingCardWithKeyboard(
    hybridPage,
    "Tab",
    "hybrid pen keyboard recovery",
  );
  const penKeyboardReverse = await focusReadingCardWithKeyboard(
    hybridPage,
    "Shift+Tab",
    "hybrid pen reverse keyboard recovery",
  );
  await hybridPage.locator("#closeDetail").focus();
  await hybridPage.locator(".dialog-toolbar").hover();
  await waitForClosedLens(hybridPage);
  await hybridPage.waitForTimeout(inspectionSettleMs);
  await hybridPenCard.hover();
  const penMouseRecovery = await waitForOpenLens(
    hybridPage,
    await hybridPenCard.getAttribute("data-reading-id"),
  );
  await penSession.detach();
  evidence.pointerCapabilities.hybrid = {
    mediaQueries: hybridCapability,
    mouseHoverWithCoarseSecondary: hybridOpenLens.visible,
    synchronizedDisable: !hybridDisabled.visible
      && !hybridDisabled.capability.rootClass,
    synchronizedReenable: hybridReenabled.visible
      && hybridReenabled.capability.rootClass,
    touch: {
      firstTapSelected: true,
      firstTapDialogHidden: true,
      firstTapLensHidden: touchFirstLens.hidden && !touchFirstLens.visible,
      secondTapOpened: true,
      secondTapLensHidden: touchSecondLens.hidden && !touchSecondLens.visible,
      focusReturnLensHidden: touchCloseLens.hidden && !touchCloseLens.visible,
      keyboardForwardReadingId: touchKeyboardForward.readingId,
      keyboardReverseReadingId: touchKeyboardReverse.readingId,
      keyboardLensVisible: touchKeyboardForward.lens.visible
        && touchKeyboardReverse.lens.visible,
      laterMouseLensVisible: touchMouseRecovery.visible,
    },
    pen: {
      compatibilityPointerdownLensHidden: true,
      firstTapSelected: true,
      firstTapDialogHidden: true,
      firstTapLensHidden: penFirstLens.hidden && !penFirstLens.visible,
      secondTapOpened: true,
      secondTapLensHidden: penSecondLens.hidden && !penSecondLens.visible,
      focusReturnLensHidden: penCloseLens.hidden && !penCloseLens.visible,
      keyboardForwardReadingId: penKeyboardForward.readingId,
      keyboardReverseReadingId: penKeyboardReverse.readingId,
      keyboardLensVisible: penKeyboardForward.lens.visible
        && penKeyboardReverse.lens.visible,
      laterMouseLensVisible: penMouseRecovery.visible,
    },
    passed: true,
  };
  assertNoUnexpectedDiagnostics(hybridDiagnostic);
  await hybridContext.close();

  for (const viewport of [
    { width: 390, height: 844, label: "390x844" },
    { width: 421, height: 386, label: "421x386" },
  ]) {
    const context = await createContext(browser, {
      theme: "dark",
      viewport: { width: viewport.width, height: viewport.height },
      touch: true,
    });
    const page = await context.newPage();
    const diagnostic = monitorPage(page, `coarse-${viewport.label}`);
    await openDay(page, "2026-07-21");
    await assertRoundedAndSemantic(page, viewport.label);
    const coarseCapability = await page.evaluate(() => ({
      fineHover: matchMedia("(hover: hover) and (pointer: fine)").matches,
      anyCoarse: matchMedia("(any-pointer: coarse)").matches,
      rootClass: document.documentElement.classList.contains("inspection-lens-capable"),
      rootState: document.documentElement.dataset.inspectionLensCapability,
    }));
    assert.deepEqual(coarseCapability, {
      fineHover: false,
      anyCoarse: true,
      rootClass: false,
      rootState: "unavailable",
    });
    const card = page.locator(
      '.event-reading-card[data-category="service-support"]',
    ).first();
    await card.scrollIntoViewIfNeeded();
    await card.tap();
    assert.equal(await card.getAttribute("aria-pressed"), "true");
    assert.equal(await page.locator("#taskDialog").isHidden(), true);
    assert.equal((await lensState(page)).visible, false);
    await card.tap();
    await page.waitForSelector("#taskDialog.is-open");
    assert.equal((await lensState(page)).visible, false);
    await page.keyboard.press("Escape");
    assert.equal(
      await card.evaluate((element) => document.activeElement === element),
      true,
      `${viewport.label}: focus did not return after second-tap dialog`,
    );
    assert.equal((await lensState(page)).visible, false);
    await card.evaluate((element) => element.blur());
    await capture(page, `2026-07-21-${viewport.label}-no-hover-resting.png`);
    assert.ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth
          - document.documentElement.clientWidth <= 1,
      ),
      `${viewport.label}: horizontal overflow`,
    );
    assertNoUnexpectedDiagnostics(diagnostic);
    evidence.pointerCapabilities[viewport.label] = {
      mediaQueries: coarseCapability,
      firstTapSelected: true,
      firstTapDialogHidden: true,
      secondTapOpened: true,
      lensVisible: false,
      focusReturned: true,
      passed: true,
    };
    results.push({ mode: viewport.label, touchContract: "first-select-second-open" });
    await context.close();
  }

  for (const screenshot of screenshots) {
    assert.equal(
      (await stat(path.resolve(repositoryRoot, screenshot.path))).size,
      screenshot.bytes,
    );
  }
  assert.equal(screenshots.length, 7, "durable screenshot inventory changed");
  assert.ok(evidence.gifFrameProgression?.changed, "GIF progression evidence missing");
  assert.ok(evidence.reducedMotion?.passed, "reduced-motion evidence missing");
  assert.ok(evidence.pointerCapabilities.hybrid?.passed, "hybrid evidence missing");
  assert.ok(evidence.pointerCapabilities["390x844"]?.passed, "390x844 evidence missing");
  assert.ok(evidence.pointerCapabilities["421x386"]?.passed, "421x386 evidence missing");
  evidence.passed = true;
} catch (error) {
  failure = error;
  evidence.errors.push(error instanceof Error ? error.message : String(error));
} finally {
  await browser.close();
  assertPublicManifestPaths(evidence);
  await writeFile(manifestPath, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  assertPublicManifestPaths(JSON.parse(await readFile(manifestPath, "utf8")));
}

if (failure) throw failure;

console.log(JSON.stringify({
  passed: true,
  baseUrl,
  manifest: manifestPath,
  results,
  screenshots,
}, null, 2));
