#!/usr/bin/env node
import assert from "node:assert/strict";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "@playwright/test";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const baseUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8894/timetable/";
const phase = process.env.SOFT_PALETTE_PHASE || "after";
const auditRoot = path.join(repositoryRoot, "audits", "soft-palette-typography");
const phaseRoot = path.join(auditRoot, phase);
const metricsPath = path.join(phaseRoot, "metrics.json");
const baselinePath = path.join(auditRoot, "baseline", "metrics.json");
const sampleDate = "2026-07-21";
const settleMs = 360;

assert.ok(["baseline", "after"].includes(phase), `unsupported phase: ${phase}`);

const configurations = [
  {
    label: "desktop-dark",
    theme: "dark",
    viewport: { width: 1440, height: 900 },
    touch: false,
    captureTask: true,
  },
  {
    label: "desktop-light",
    theme: "light",
    viewport: { width: 1440, height: 900 },
    touch: false,
    captureTask: false,
  },
  {
    label: "390x844-dark",
    theme: "dark",
    viewport: { width: 390, height: 844 },
    touch: true,
    captureTask: true,
  },
  {
    label: "421x386-dark",
    theme: "dark",
    viewport: { width: 421, height: 386 },
    touch: true,
    captureTask: false,
  },
];

const representativeCategories = [
  "assigned-work",
  "ah-market-scan",
  "us-market-scan",
  "ai-brief",
  "service-support",
  "warning-exception",
  "autonomous-artwork",
];

const typographySelectors = {
  homeDisplay: "#monthTitle",
  homeKicker: ".section-mark",
  homeSupporting: ".thesis-line",
  homeLegend: ".calendar-legend",
  dayHeading: "#dialogTitle",
  dayDate: "#dialogDate",
  dayVariable: "#dialogVariable",
  daySupporting: ".dialog-mode-thesis",
  dayBoundary: "#dialogBoundary",
  timelineHeading: "#timelineTitle",
  timelineSupporting: ".timeline-help",
  assignedTitle: '.event-reading-card[data-category="assigned-work"] .reading-title',
  assignedSummary: '.event-reading-card[data-category="assigned-work"] .reading-summary',
  assignedTime: '.event-reading-card[data-category="assigned-work"] .assigned-time',
  assignedMeta: '.event-reading-card[data-category="assigned-work"] .assigned-category',
  climateTitle: '.event-reading-card[data-layer="climate"] .reading-title',
  climateSummary: '.event-reading-card[data-layer="climate"] .reading-summary',
  climateTime: '.event-reading-card[data-layer="climate"] .pulse-time',
  climateMeta: '.event-reading-card[data-layer="climate"] .pulse-duration',
  beaconTitle: '.event-reading-card[data-layer="beacon"] .reading-title',
  beaconSummary: '.event-reading-card[data-layer="beacon"] .reading-summary',
  beaconTime: '.event-reading-card[data-layer="beacon"] .autonomous-time',
  beaconMeta: '.event-reading-card[data-layer="beacon"] .autonomous-kicker',
};

const taskTypographySelectors = {
  taskHeading: "#taskDetailTitle",
  taskKicker: ".task-detail-kicker",
  taskTime: "#taskDetailTime",
  taskType: "#taskDetailType",
  taskSectionHeading: ".task-detail-copy h3",
  taskBody: ".task-detail-body",
};

const lensTypographySelectors = {
  lensHeading: ".inspection-lens-title",
  lensSummary: ".inspection-lens-summary",
  lensTime: ".inspection-lens-time",
  lensKicker: ".inspection-lens-kicker",
  lensPlateHeading: ".inspection-plate-title",
  lensPlateSummary: ".inspection-plate-summary",
  lensPlateTime: ".inspection-plate-time",
  lensPlateKicker: ".inspection-plate-marker",
};

const dayFitSelectors = [
  "#monthTitle",
  ".thesis-line",
  "#dialogTitle",
  ".dialog-date",
  ".dialog-variable",
  ".dialog-mode-thesis",
  ".dialog-boundary",
  ".timeline-help",
  ".reading-title",
  ".reading-summary",
  ".assigned-time",
  ".assigned-category",
  ".record-provenance",
  ".pulse-time",
  ".pulse-count",
  ".pulse-duration",
  ".autonomous-time",
  ".autonomous-kicker",
];

const taskFitSelectors = [
  "#taskDetailTitle",
  ".task-detail-kicker",
  "#taskDetailTime",
  "#taskDetailType",
  ".task-detail-copy h3",
  ".task-detail-body",
  ".task-detail-occurrences > h3",
  ".task-occurrence h4",
  ".task-occurrence p",
];

const lensFitSelectors = [
  ".inspection-lens-title",
  ".inspection-lens-summary",
  ".inspection-lens-time",
  ".inspection-lens-kicker",
  ".inspection-plate-title",
  ".inspection-plate-summary",
  ".inspection-plate-time",
  ".inspection-plate-marker",
];

const results = {
  schema: "timetable-visual-balance-evidence-v1",
  phase,
  passed: false,
  baseUrl,
  sampleDate,
  screenshots: [],
  configurations: {},
  comparisons: null,
  errors: [],
};

await mkdir(phaseRoot, { recursive: true });

function repositoryRelative(artifactPath) {
  const relativePath = path.relative(repositoryRoot, path.resolve(artifactPath));
  assert.ok(
    relativePath
      && relativePath !== ".."
      && !relativePath.startsWith(`..${path.sep}`)
      && !path.isAbsolute(relativePath),
    `artifact must remain inside repository: ${artifactPath}`,
  );
  return relativePath.split(path.sep).join(path.posix.sep);
}

function round(value, places = 3) {
  const factor = 10 ** places;
  return Math.round(value * factor) / factor;
}

function parseCssColor(value) {
  const source = String(value || "").trim().toLowerCase();
  if (source.startsWith("#")) {
    const normalized = source.length === 4
      ? source.slice(1).split("").map((character) => character.repeat(2)).join("")
      : source.slice(1, 7);
    assert.match(normalized, /^[0-9a-f]{6}$/, `invalid hex color: ${value}`);
    return [
      Number.parseInt(normalized.slice(0, 2), 16),
      Number.parseInt(normalized.slice(2, 4), 16),
      Number.parseInt(normalized.slice(4, 6), 16),
      1,
    ];
  }
  const srgbMatch = source.match(/^color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)$/);
  if (srgbMatch) {
    return [
      Number(srgbMatch[1]) * 255,
      Number(srgbMatch[2]) * 255,
      Number(srgbMatch[3]) * 255,
      srgbMatch[4] === undefined ? 1 : Number(srgbMatch[4]),
    ];
  }
  const rgbMatch = source.match(/^rgba?\((.+)\)$/);
  assert.ok(rgbMatch, `cannot parse CSS color: ${value}`);
  const channels = rgbMatch[1]
    .replaceAll(",", " ")
    .replace("/", " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((channel) => Number.parseFloat(channel.replace("%", "")));
  assert.ok(channels.length >= 3, `cannot parse RGB channels: ${value}`);
  const usesPercent = rgbMatch[1].includes("%");
  return [
    usesPercent ? channels[0] * 2.55 : channels[0],
    usesPercent ? channels[1] * 2.55 : channels[1],
    usesPercent ? channels[2] * 2.55 : channels[2],
    channels[3] ?? 1,
  ];
}

function compositeColor(foreground, background) {
  const alpha = foreground[3] ?? 1;
  return [
    foreground[0] * alpha + background[0] * (1 - alpha),
    foreground[1] * alpha + background[1] * (1 - alpha),
    foreground[2] * alpha + background[2] * (1 - alpha),
  ];
}

function colorDistance(left, right) {
  return Math.sqrt(
    (left[0] - right[0]) ** 2
      + (left[1] - right[1]) ** 2
      + (left[2] - right[2]) ** 2,
  );
}

function luminance(color) {
  const channels = color.slice(0, 3).map((channel) => {
    const normalized = channel / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

function contrastRatio(foreground, background) {
  const foregroundLuminance = luminance(foreground);
  const backgroundLuminance = luminance(background);
  return (
    (Math.max(foregroundLuminance, backgroundLuminance) + 0.05)
    / (Math.min(foregroundLuminance, backgroundLuminance) + 0.05)
  );
}

function average(values) {
  assert.ok(values.length > 0, "cannot average an empty collection");
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function minimumPairwiseDistance(samples, colorKey) {
  let minimum = Number.POSITIVE_INFINITY;
  let pair = [];
  for (let leftIndex = 0; leftIndex < samples.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < samples.length; rightIndex += 1) {
      const distance = colorDistance(samples[leftIndex][colorKey], samples[rightIndex][colorKey]);
      if (distance < minimum) {
        minimum = distance;
        pair = [samples[leftIndex].category, samples[rightIndex].category];
      }
    }
  }
  return { value: round(minimum), pair };
}

function validatePortableEvidence(value, location = "$", violations = []) {
  if (typeof value === "string") {
    if (
      path.posix.isAbsolute(value)
      || path.win32.isAbsolute(value)
      || /^file:/i.test(value)
      || value.includes("/Users/")
      || value.includes(repositoryRoot)
    ) {
      violations.push({ location, value });
    }
    return violations;
  }
  if (Array.isArray(value)) {
    value.forEach((entry, index) => validatePortableEvidence(entry, `${location}[${index}]`, violations));
    return violations;
  }
  if (value && typeof value === "object") {
    Object.entries(value).forEach(([key, entry]) => {
      validatePortableEvidence(entry, `${location}.${key}`, violations);
    });
  }
  return violations;
}

async function screenshot(page, label) {
  const artifactPath = path.join(phaseRoot, `${label}.png`);
  const bytes = await page.screenshot({ path: artifactPath, fullPage: false });
  results.screenshots.push({
    label,
    path: repositoryRelative(artifactPath),
    bytes: bytes.length,
  });
}

async function cleanRestingState(page, label) {
  const neutral = page.locator("#closeDetail:visible, #themeToggle:visible").first();
  const box = await neutral.boundingBox();
  if (box && !page.context().browser()?.isConnected()) {
    throw new Error(`${label}: browser disconnected`);
  }
  if (box && !(await page.evaluate(() => matchMedia("(any-pointer: coarse)").matches))) {
    await page.mouse.move(
      Math.max(2, box.x + Math.min(6, box.width / 2)),
      Math.max(2, box.y + Math.min(4, box.height / 2)),
    );
  }
  await page.evaluate(() => {
    const active = document.activeElement;
    if (active instanceof HTMLElement) active.blur();
    document.querySelectorAll(".event-reading-card").forEach((card) => {
      card.classList.remove("is-selected", "is-linked-active");
      if (card instanceof HTMLButtonElement) card.setAttribute("aria-pressed", "false");
    });
  });
  await page.waitForTimeout(settleMs);
  const lens = await page.locator("#inspectionLens").evaluate((element) => ({
    hidden: element.hidden,
    visible: element.classList.contains("is-visible")
      && Number.parseFloat(getComputedStyle(element).opacity) > 0,
    readingId: element.dataset.readingId || "",
  }));
  assert.equal(lens.hidden, true, `${label}: resting lens hidden state`);
  assert.equal(lens.visible, false, `${label}: resting lens visibility`);
  assert.equal(lens.readingId, "", `${label}: stale resting lens reading id`);
}

async function inspectStyles(page, selectors) {
  return page.evaluate((selectorMap) => {
    const output = {};
    for (const [name, selector] of Object.entries(selectorMap)) {
      const element = document.querySelector(selector);
      if (!element) {
        output[name] = null;
        continue;
      }
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      output[name] = {
        selector,
        fontSize: Number.parseFloat(style.fontSize),
        lineHeight: Number.parseFloat(style.lineHeight),
        ratio: Number.parseFloat(style.lineHeight) / Number.parseFloat(style.fontSize),
        color: style.color,
        fontFamily: style.fontFamily,
        fontWeight: style.fontWeight,
        rect: {
          width: rect.width,
          height: rect.height,
        },
      };
    }
    return output;
  }, selectors);
}

async function inspectTextFit(page, selectors) {
  return page.evaluate((fitSelectors) => {
    const visible = (element) => {
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== "none"
        && style.visibility !== "hidden"
        && Number(style.opacity) > 0
        && rect.width > 0
        && rect.height > 0;
    };
    const samples = [];
    for (const element of document.querySelectorAll(fitSelectors.join(","))) {
      if (!visible(element)) continue;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      const container = element.closest(
        ".event-reading-card, .task-dialog-panel, #inspectionLens",
      );
      const containerRect = container?.getBoundingClientRect();
      const containerStyle = container ? getComputedStyle(container) : null;
      const containerScrollsVertically = Boolean(
        container
          && container.scrollHeight > container.clientHeight + 1
          && ["auto", "scroll"].includes(containerStyle.overflowY),
      );
      const outsideHorizontally = containerRect
        ? rect.left < containerRect.left - 1 || rect.right > containerRect.right + 1
        : false;
      const outsideVertically = containerRect
        ? rect.top < containerRect.top - 1 || rect.bottom > containerRect.bottom + 1
        : false;
      const visibleChildren = [...element.children].filter(visible);
      const childClamp = visibleChildren.length > 0
        && visibleChildren.every((child) => getComputedStyle(child).webkitLineClamp !== "none");
      const compactMarkdownPreview = element.classList.contains("pulse-summary")
        && element.closest(".pulse-item")?.classList.contains("has-markdown")
        && style.overflowY === "hidden";
      samples.push({
        selector: element.id ? `#${element.id}` : `.${[...element.classList].join(".")}`,
        readingId: element.closest(".event-reading-card")?.dataset.readingId || "",
        horizontalOverflow: element.scrollWidth - element.clientWidth,
        verticalOverflow: element.scrollHeight - element.clientHeight,
        intentionalClamp: style.webkitLineClamp !== "none" || childClamp || compactMarkdownPreview,
        overflowY: style.overflowY,
        outsideHorizontally,
        outsideVertically,
        containerScrollsVertically,
        outsideContainer: outsideHorizontally
          || (outsideVertically && !containerScrollsVertically),
      });
    }
    const documentElement = document.documentElement;
    const panel = document.querySelector("#dayDialogPanel");
    return {
      viewport: {
        width: innerWidth,
        height: innerHeight,
      },
      pageHorizontalOverflow: documentElement.scrollWidth - documentElement.clientWidth,
      panelHorizontalOverflow: panel ? panel.scrollWidth - panel.clientWidth : 0,
      samples,
      failures: samples.filter((sample) => (
        sample.horizontalOverflow > 1
        || sample.outsideContainer
        || (
          !sample.intentionalClamp
          && ["hidden", "clip"].includes(sample.overflowY)
          && sample.verticalOverflow > 1
        )
      )),
    };
  }, selectors);
}

function assertTextFit(label, textFit) {
  assert.ok(textFit.pageHorizontalOverflow <= 1, `${label}: page horizontal overflow`);
  assert.ok(textFit.panelHorizontalOverflow <= 1, `${label}: panel horizontal overflow`);
  if (phase === "after") {
    assert.deepEqual(
      textFit.failures,
      [],
      `${label}: text overflow/clipping ${JSON.stringify(textFit.failures)}`,
    );
  }
}

async function medianPngColor(page, pngBytes) {
  return page.evaluate(async (base64) => {
    const image = new Image();
    image.src = `data:image/png;base64,${base64}`;
    await image.decode();
    const canvas = document.createElement("canvas");
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    context.drawImage(image, 0, 0);
    const insetX = Math.max(2, Math.floor(canvas.width * 0.12));
    const insetY = Math.max(2, Math.floor(canvas.height * 0.12));
    const width = Math.max(1, canvas.width - insetX * 2);
    const height = Math.max(1, canvas.height - insetY * 2);
    const pixels = context.getImageData(insetX, insetY, width, height).data;
    const channels = [[], [], []];
    for (let index = 0; index < pixels.length; index += 4) {
      channels[0].push(pixels[index]);
      channels[1].push(pixels[index + 1]);
      channels[2].push(pixels[index + 2]);
    }
    return channels.map((channel) => {
      channel.sort((left, right) => left - right);
      return channel[Math.floor(channel.length / 2)];
    });
  }, pngBytes.toString("base64"));
}

async function inspectPanelColor(page) {
  const clip = await page.locator(".timeline-list").evaluate((timeline) => {
    const rect = timeline.getBoundingClientRect();
    const x = Math.min(innerWidth - 22, Math.max(1, rect.left + rect.width * 0.55));
    const y = Math.min(innerHeight - 22, Math.max(1, rect.top + 22));
    return { x: Math.floor(x), y: Math.floor(y), width: 20, height: 20 };
  });
  const png = await page.screenshot({ clip });
  return medianPngColor(page, png);
}

async function inspectCategoryColors(page) {
  const panelColor = await inspectPanelColor(page);
  const samples = [];
  const categories = [];
  for (const category of [...representativeCategories, "daily-reminder"]) {
    if (await page.locator(`.event-reading-card[data-category="${category}"]`).count()) {
      categories.push(category);
    }
  }
  assert.ok(categories.length >= 3, `too few representative categories present: ${categories.join(",")}`);
  for (const category of categories) {
    const card = page.locator(`.event-reading-card[data-category="${category}"]`).first();
    assert.equal(await card.count(), 1, `missing representative category: ${category}`);
    await card.scrollIntoViewIfNeeded();
    const surfaceTarget = category === "autonomous-artwork"
      ? card.locator(".autonomous-copy")
      : card;
    const png = await surfaceTarget.screenshot();
    const surfaceColor = await medianPngColor(page, png);
    const computed = await card.evaluate((element) => {
      const style = getComputedStyle(element);
      const textElements = [
        element.querySelector(".reading-title"),
        element.querySelector(".reading-summary"),
        element.querySelector(".pulse-time, .assigned-time, .autonomous-time"),
        element.querySelector(".pulse-duration, .assigned-category, .autonomous-kicker"),
      ].filter(Boolean);
      return {
        category: element.dataset.category,
        layer: element.dataset.layer,
        accent: style.getPropertyValue("--category-accent").trim(),
        backgroundColor: style.backgroundColor,
        borderColor: style.borderTopColor,
        boxShadow: style.boxShadow,
        opacity: style.opacity,
        text: textElements.map((textElement) => {
          const textStyle = getComputedStyle(textElement);
          return {
            className: textElement.className,
            color: textStyle.color,
            fontSize: Number.parseFloat(textStyle.fontSize),
            lineHeight: Number.parseFloat(textStyle.lineHeight),
          };
        }),
      };
    });
    const accentColor = parseCssColor(computed.accent).slice(0, 3);
    const borderColor = compositeColor(parseCssColor(computed.borderColor), panelColor);
    const text = computed.text.map((textSample) => {
      const foreground = compositeColor(parseCssColor(textSample.color), surfaceColor);
      return {
        ...textSample,
        compositeColor: foreground.map((channel) => round(channel)),
        contrast: round(contrastRatio(foreground, surfaceColor)),
      };
    });
    const surfaceDistance = colorDistance(surfaceColor, panelColor);
    const borderDistance = colorDistance(borderColor, panelColor);
    samples.push({
      ...computed,
      panelColor,
      surfaceColor,
      accentColor,
      borderCompositeColor: borderColor.map((channel) => round(channel)),
      surfaceDistance: round(surfaceDistance),
      borderDistance: round(borderDistance),
      salience: round(surfaceDistance * 0.52 + borderDistance * 0.48),
      text,
    });
  }
  const contrasts = samples.flatMap((sample) => sample.text.map((textSample) => ({
    category: sample.category,
    layer: sample.layer,
    className: textSample.className,
    fontSize: textSample.fontSize,
    contrast: textSample.contrast,
  })));
  const layerSalience = Object.fromEntries(
    [...new Set(samples.map((sample) => sample.layer))].map((layer) => [
      layer,
      round(average(samples.filter((sample) => sample.layer === layer).map((sample) => sample.salience))),
    ]),
  );
  return {
    panelColor,
    samples,
    minimumContrast: Math.min(...contrasts.map((sample) => sample.contrast)),
    minimumAccentDistance: minimumPairwiseDistance(samples, "accentColor"),
    minimumBorderDistance: minimumPairwiseDistance(samples, "borderCompositeColor"),
    meanSurfaceDistance: round(average(samples.map((sample) => sample.surfaceDistance))),
    layerSalience,
    contrasts,
  };
}

async function inspectGeometry(page) {
  return page.evaluate(() => {
    const layerRect = document.querySelector(".timeline-events-layer").getBoundingClientRect();
    return [...document.querySelectorAll(".timeline-event")].map((event) => {
      const rect = event.getBoundingClientRect();
      return {
        footprintId: event.dataset.footprintId,
        start: event.dataset.start,
        end: event.dataset.end,
        durationMinutes: Number(event.dataset.durationMinutes),
        lane: Number(event.dataset.lane),
        laneCount: Number(event.dataset.laneCount),
        top: Math.round((rect.top - layerRect.top) * 1000) / 1000,
        height: Math.round(rect.height * 1000) / 1000,
        left: Math.round((rect.left - layerRect.left) * 1000) / 1000,
        width: Math.round(rect.width * 1000) / 1000,
      };
    });
  });
}

async function openDay(page, touch) {
  const selector = `.calendar-day-button[data-date="${sampleDate}"]`;
  if (touch) {
    await page.tap(selector);
  } else {
    await page.click(selector);
  }
  await page.waitForSelector("#dayDialog.is-open");
  await page.waitForFunction(
    () => document.querySelector(".timeline-reading-layer.is-placed")
      && document.querySelectorAll(".event-reading-card").length > 0,
  );
}

async function openAssignedTask(page, touch) {
  const card = page.locator('.event-reading-card[data-category="assigned-work"]').first();
  await card.scrollIntoViewIfNeeded();
  if (touch) {
    await card.tap();
    assert.equal(await card.getAttribute("aria-pressed"), "true");
    assert.equal(await page.locator("#taskDialog").getAttribute("hidden"), "");
    await card.tap();
  } else {
    await card.click();
  }
  await page.waitForSelector("#taskDialog.is-open");
}

async function inspectLens(page) {
  await page.locator("#closeTaskDetail").click();
  await page.waitForSelector("#taskDialog", { state: "hidden" });
  const card = page.locator('.event-reading-card[data-category="assigned-work"]').first();
  await card.scrollIntoViewIfNeeded();
  await card.hover();
  await page.waitForFunction(() => {
    const lens = document.querySelector("#inspectionLens");
    return lens && !lens.hidden && lens.classList.contains("is-visible")
      && Number.parseFloat(getComputedStyle(lens).opacity) > 0;
  });
  return {
    typography: await inspectStyles(page, lensTypographySelectors),
    textFit: await inspectTextFit(page, lensFitSelectors),
    state: await page.locator("#inspectionLens").evaluate((lens) => ({
      hidden: lens.hidden,
      visible: lens.classList.contains("is-visible")
        && Number.parseFloat(getComputedStyle(lens).opacity) > 0,
      readingId: lens.dataset.readingId,
      category: lens.dataset.category,
      mediaKind: lens.dataset.mediaKind,
    })),
  };
}

function assertGeometryUnchanged(baselineGeometry, afterGeometry) {
  const baselineById = new Map(
    baselineGeometry.map((footprint) => [footprint.footprintId, footprint]),
  );
  assert.ok(
    afterGeometry.length <= baselineGeometry.length,
    "the corrected projection unexpectedly added non-baseline footprints",
  );
  const scaleCandidates = afterGeometry
    .map((after) => {
      const before = baselineById.get(after.footprintId);
      return before?.height > 0 ? after.height / before.height : null;
    })
    .filter((value) => Number.isFinite(value))
    .sort((left, right) => left - right);
  const geometryScale = scaleCandidates[Math.floor(scaleCandidates.length / 2)] || 1;
  for (const after of afterGeometry) {
    const before = baselineById.get(after.footprintId);
    assert.ok(before, `new footprint appeared outside the baseline: ${after.footprintId}`);
    assert.deepEqual(
      {
        footprintId: after.footprintId,
        start: after.start,
        end: after.end,
        durationMinutes: after.durationMinutes,
      },
      {
        footprintId: before.footprintId,
        start: before.start,
        end: before.end,
        durationMinutes: before.durationMinutes,
      },
      `footprint timing changed for ${after.footprintId}`,
    );
    for (const measurement of ["top", "height"]) {
      assert.ok(
        Math.abs(after[measurement] - before[measurement] * geometryScale) <= 0.75,
        `${after.footprintId} ${measurement} changed non-uniformly: `
          + `${before[measurement]} -> ${after[measurement]} at scale ${geometryScale}`,
      );
    }
  }
}

function assertAfterComparisons(baseline) {
  const beforeDark = baseline.configurations["desktop-dark"];
  const afterDark = results.configurations["desktop-dark"];
  const sourceFor = (configuration, source) => (
    source === "lens" ? configuration.lens.typography : configuration[source]
  );
  const compareGrowth = (label, beforeSource, afterSource, keys, minimum = 0.1) => {
    const beforeValues = keys.map((key) => {
      assert.ok(beforeSource[key], `${label}: missing baseline ${key}`);
      return beforeSource[key].fontSize;
    });
    const afterValues = keys.map((key) => {
      assert.ok(afterSource[key], `${label}: missing after ${key}`);
      return afterSource[key].fontSize;
    });
    const beforeMean = average(beforeValues);
    const afterMean = average(afterValues);
    const growth = afterMean / beforeMean - 1;
    assert.ok(
      growth >= minimum,
      `${label} growth is insufficient: ${round(beforeMean)} -> ${round(afterMean)} (${round(growth)})`,
    );
    return {
      keys,
      beforeMean: round(beforeMean),
      afterMean: round(afterMean),
      growth: round(growth),
    };
  };

  const headingSpecifications = [
    ["desktop-dark.home", "desktop-dark", "typography", "homeDisplay"],
    ["desktop-dark.day", "desktop-dark", "typography", "dayHeading"],
    ["desktop-dark.task", "desktop-dark", "taskTypography", "taskHeading"],
    ["desktop-dark.lens", "desktop-dark", "lens", "lensPlateHeading"],
    ["desktop-light.home", "desktop-light", "typography", "homeDisplay"],
    ["desktop-light.day", "desktop-light", "typography", "dayHeading"],
    ["390x844-dark.home", "390x844-dark", "typography", "homeDisplay"],
    ["390x844-dark.day", "390x844-dark", "typography", "dayHeading"],
    ["390x844-dark.task", "390x844-dark", "taskTypography", "taskHeading"],
    ["421x386-dark.home", "421x386-dark", "typography", "homeDisplay"],
    ["421x386-dark.day", "421x386-dark", "typography", "dayHeading"],
  ];
  const headingComparisons = {};
  for (const [label, configurationLabel, source, key] of headingSpecifications) {
    const before = sourceFor(baseline.configurations[configurationLabel], source)[key].fontSize;
    const after = sourceFor(results.configurations[configurationLabel], source)[key].fontSize;
    const reduction = 1 - after / before;
    assert.ok(
      reduction >= 0.1,
      `${label} heading is not materially smaller: ${before} -> ${after}`,
    );
    headingComparisons[label] = { before, after, reduction: round(reduction) };
  }

  const responsiveGroups = {
    supporting: [
      "homeSupporting",
      "dayDate",
      "dayVariable",
      "daySupporting",
      "timelineSupporting",
    ],
    cardTitles: [
      "assignedTitle",
      "climateTitle",
      "beaconTitle",
    ],
    cardBody: [
      "assignedSummary",
      "climateSummary",
      "beaconSummary",
    ],
    cardMeta: [
      "assignedTime",
      "assignedMeta",
      "climateTime",
      "climateMeta",
      "beaconTime",
      "beaconMeta",
    ],
  };
  const responsiveTypography = {};
  for (const configurationLabel of [
    "desktop-dark",
    "desktop-light",
    "390x844-dark",
    "421x386-dark",
  ]) {
    responsiveTypography[configurationLabel] = {};
    for (const [group, keys] of Object.entries(responsiveGroups)) {
      responsiveTypography[configurationLabel][group] = compareGrowth(
        `${configurationLabel}.${group}`,
        baseline.configurations[configurationLabel].typography,
        results.configurations[configurationLabel].typography,
        keys,
      );
    }
  }

  const taskSupportingKeys = [
    "taskKicker",
    "taskTime",
    "taskType",
    "taskSectionHeading",
    "taskBody",
  ];
  const taskSupporting = {};
  for (const configurationLabel of ["desktop-dark", "390x844-dark"]) {
    taskSupporting[configurationLabel] = compareGrowth(
      `${configurationLabel}.taskSupporting`,
      baseline.configurations[configurationLabel].taskTypography,
      results.configurations[configurationLabel].taskTypography,
      taskSupportingKeys,
    );
  }

  const lensSupporting = compareGrowth(
    "desktop-dark.lensSupporting",
    beforeDark.lens.typography,
    afterDark.lens.typography,
    ["lensPlateSummary", "lensPlateTime", "lensPlateKicker"],
  );

  const colorComparisons = {};
  for (const themeLabel of ["desktop-dark", "desktop-light"]) {
    const before = baseline.configurations[themeLabel].colors;
    const after = results.configurations[themeLabel].colors;
    const baselineCategories = new Set(before.samples.map((sample) => sample.category));
    const comparableAfterSamples = after.samples.filter(
      (sample) => baselineCategories.has(sample.category),
    );
    const comparableAfterMean = comparableAfterSamples.reduce(
      (total, sample) => total + sample.surfaceDistance,
      0,
    ) / comparableAfterSamples.length;
    const closenessReduction = 1 - comparableAfterMean / before.meanSurfaceDistance;
    assert.ok(
      closenessReduction >= 0.22,
      `${themeLabel}: surfaces did not materially approach panel: ${before.meanSurfaceDistance} -> ${after.meanSurfaceDistance}`,
    );
    assert.ok(after.minimumContrast >= 4.5, `${themeLabel}: small text contrast ${after.minimumContrast}`);
    assert.ok(
      after.minimumAccentDistance.value >= 24,
      `${themeLabel}: category accents collapsed ${JSON.stringify(after.minimumAccentDistance)}`,
    );
    assert.ok(
      after.minimumBorderDistance.value >= 8,
      `${themeLabel}: rendered category edges collapsed ${JSON.stringify(after.minimumBorderDistance)}`,
    );
    const perCategorySurface = {};
    for (const afterSample of after.samples) {
      const beforeSample = before.samples.find(
        (sample) => sample.category === afterSample.category,
      );
      if (!beforeSample) {
        perCategorySurface[afterSample.category] = {
          before: null,
          after: afterSample.surfaceDistance,
          reduction: null,
          baselineStatus: "new-authorized-category",
        };
        continue;
      }
      const reduction = 1 - afterSample.surfaceDistance / beforeSample.surfaceDistance;
      assert.ok(
        reduction >= 0.03,
        `${themeLabel}: ${afterSample.category} did not approach panel materially: `
          + `${beforeSample.surfaceDistance} -> ${afterSample.surfaceDistance}`,
      );
      perCategorySurface[afterSample.category] = {
        before: beforeSample.surfaceDistance,
        after: afterSample.surfaceDistance,
        reduction: round(reduction),
      };
    }
    const climateSamples = after.samples.filter((sample) => sample.layer === "climate");
    const activeSamples = after.samples.filter(
      (sample) => ["assigned-work", "warning-exception", "autonomous-artwork"].includes(sample.category),
    );
    const maximumClimateSalience = Math.max(...climateSamples.map((sample) => sample.salience));
    const activeSalience = {};
    for (const sample of activeSamples) {
      assert.ok(
        sample.salience >= maximumClimateSalience * 1.025,
        `${themeLabel}: ${sample.category} salience ${sample.salience} is not above `
          + `the loudest climate sample ${maximumClimateSalience}`,
      );
      activeSalience[sample.category] = sample.salience;
    }
    colorComparisons[themeLabel] = {
      surfaceDistance: {
        before: before.meanSurfaceDistance,
        after: after.meanSurfaceDistance,
        reduction: round(closenessReduction),
      },
      minimumContrast: after.minimumContrast,
      minimumAccentDistance: after.minimumAccentDistance,
      minimumBorderDistance: after.minimumBorderDistance,
      layerSalience: after.layerSalience,
      perCategorySurface,
      maximumClimateSalience,
      activeSalience,
    };
  }

  assertGeometryUnchanged(beforeDark.geometry, afterDark.geometry);
  results.comparisons = {
    headings: headingComparisons,
    responsiveTypography,
    taskSupporting,
    lensSupporting,
    colors: colorComparisons,
    geometryUnchanged: true,
  };
}

const browser = await chromium.launch({ headless: true });
try {
  for (const configuration of configurations) {
    const context = await browser.newContext({
      viewport: configuration.viewport,
      colorScheme: configuration.theme,
      isMobile: configuration.touch,
      hasTouch: configuration.touch,
      deviceScaleFactor: configuration.touch ? 2 : 1,
    });
    await context.addInitScript((theme) => {
      localStorage.setItem("granted-hours-theme", theme);
    }, configuration.theme);
    const page = await context.newPage();
    const diagnostics = {
      pageErrors: [],
      consoleErrors: [],
      requestFailures: [],
    };
    page.on("pageerror", (error) => diagnostics.pageErrors.push(error.message));
    page.on("console", (message) => {
      if (message.type() === "error") diagnostics.consoleErrors.push(message.text());
    });
    page.on("requestfailed", (request) => diagnostics.requestFailures.push(request.url()));
    await page.goto(baseUrl, { waitUntil: "networkidle" });
    await page.click("#prevMonth");
    await page.waitForSelector(`.calendar-day-button[data-date="${sampleDate}"]`);
    assert.equal(await page.locator("html").getAttribute("data-theme"), configuration.theme);

    const result = {
      theme: configuration.theme,
      viewport: configuration.viewport,
      touch: configuration.touch,
      typography: await inspectStyles(page, {
        homeDisplay: typographySelectors.homeDisplay,
        homeKicker: typographySelectors.homeKicker,
        homeSupporting: typographySelectors.homeSupporting,
        homeLegend: typographySelectors.homeLegend,
      }),
      taskTypography: null,
      lens: null,
      textFit: {
        day: null,
        task: null,
        lens: null,
      },
      colors: null,
      geometry: null,
      diagnostics,
    };

    await cleanRestingState(page, `${configuration.label}-calendar`);
    await screenshot(page, `${configuration.label}-calendar-resting`);
    await openDay(page, configuration.touch);
    result.typography = {
      ...result.typography,
      ...await inspectStyles(page, typographySelectors),
    };
    result.textFit.day = await inspectTextFit(page, dayFitSelectors);
    assertTextFit(`${configuration.label}.day`, result.textFit.day);

    if (configuration.label === "desktop-dark") {
      result.geometry = await inspectGeometry(page);
    }
    if (configuration.label.startsWith("desktop-")) {
      result.colors = await inspectCategoryColors(page);
    }

    await page.locator("#dayDialogPanel").evaluate((panel) => {
      panel.scrollTop = 0;
    });
    await cleanRestingState(page, `${configuration.label}-day`);
    await screenshot(page, `${configuration.label}-day-resting`);

    await openAssignedTask(page, configuration.touch);
    result.taskTypography = await inspectStyles(page, taskTypographySelectors);
    result.textFit.task = await inspectTextFit(page, taskFitSelectors);
    assertTextFit(`${configuration.label}.task`, result.textFit.task);
    if (configuration.captureTask) {
      await cleanRestingState(page, `${configuration.label}-task`);
      await screenshot(page, `${configuration.label}-task-resting`);
    }
    if (configuration.label === "desktop-dark") {
      result.lens = await inspectLens(page);
      result.textFit.lens = result.lens.textFit;
      assertTextFit(`${configuration.label}.lens`, result.textFit.lens);
      await screenshot(page, `${configuration.label}-intentional-lens`);
    } else {
      await page.locator("#closeTaskDetail").click();
      await page.waitForSelector("#taskDialog", { state: "hidden" });
    }

    assert.deepEqual(diagnostics.pageErrors, [], `${configuration.label}: page errors`);
    assert.deepEqual(diagnostics.consoleErrors, [], `${configuration.label}: console errors`);
    assert.deepEqual(diagnostics.requestFailures, [], `${configuration.label}: request failures`);
    results.configurations[configuration.label] = result;
    await context.close();
  }

  if (phase === "after") {
    const baseline = JSON.parse(await readFile(baselinePath, "utf8"));
    assert.equal(baseline.phase, "baseline", "baseline evidence phase");
    assertAfterComparisons(baseline);
  }
  results.passed = true;
} catch (error) {
  results.errors.push(error.message);
  throw error;
} finally {
  await browser.close();
  const violations = validatePortableEvidence(results);
  assert.deepEqual(violations, [], `evidence contains private paths: ${JSON.stringify(violations)}`);
  await writeFile(metricsPath, `${JSON.stringify(results, null, 2)}\n`, "utf8");
}

console.log(JSON.stringify({
  phase,
  passed: results.passed,
  metrics: repositoryRelative(metricsPath),
  screenshots: results.screenshots.map((entry) => entry.path),
  comparisons: results.comparisons,
}, null, 2));
