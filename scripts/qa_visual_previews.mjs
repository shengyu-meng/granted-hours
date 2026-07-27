#!/usr/bin/env node
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, statSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const inventory = [];

function hash(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

for (const day of timetableData.days) {
  const [year, month] = day.date.split("-");
  const relative = `archive/${year}/${month}/${day.date}/assets/visual-preview.webp`;
  const archivePath = `${ROOT}${relative}`;
  const docsPath = `${ROOT}docs/${relative}`;
  const archiveBytes = readFileSync(archivePath);
  const docsBytes = readFileSync(docsPath);
  assert.equal(archiveBytes.subarray(0, 4).toString("ascii"), "RIFF", `${day.date} is not RIFF WebP`);
  assert.equal(archiveBytes.subarray(8, 12).toString("ascii"), "WEBP", `${day.date} is not WebP`);
  assert.equal(hash(archivePath), hash(docsPath), `${day.date} mirrors differ`);
  assert.ok(statSync(archivePath).size <= 600 * 1024, `${day.date} visual preview is too large`);
  assert.equal(day.autonomous_work.visual_preview_url, `${timetableData.canonical_base_url}${relative}`);
  inventory.push({
    date: day.date,
    archivePath,
    docsPath,
    bytes: statSync(archivePath).size,
  });
}

assert.equal(inventory.length, timetableData.days.length);
assert.equal(new Set(inventory.map((entry) => entry.date)).size, timetableData.days.length);

const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  for (const entry of inventory) {
    await page.goto(pathToFileURL(entry.archivePath).href, { waitUntil: "load" });
    const dimensions = await page.locator("img").evaluate(async (image) => {
      await image.decode();
      return { width: image.naturalWidth, height: image.naturalHeight };
    });
    assert.ok(dimensions.width >= 320 && dimensions.height >= 180, `${entry.date} dimensions ${JSON.stringify(dimensions)}`);
    assert.ok(dimensions.width <= 960 && dimensions.height <= 960, `${entry.date} oversized ${JSON.stringify(dimensions)}`);
    entry.dimensions = dimensions;
  }
} finally {
  await browser.close();
}

let ocrFindingCount = 0;
for (const entry of inventory) {
  const result = spawnSync(
    "tesseract",
    [entry.archivePath, "stdout", "-l", "eng", "--psm", "11", "tsv"],
    { encoding: "utf8" },
  );
  assert.equal(result.status, 0, `${entry.date} tesseract failed: ${result.stderr}`);
  const words = result.stdout
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.split("\t"))
    .filter((columns) => columns.length >= 12 && Number(columns[10]) >= 60)
    .map((columns) => columns[11])
    .filter((word) => /[A-Za-z]{4,}/.test(word));
  if (words.length) {
    ocrFindingCount += words.length;
    throw new Error(`${entry.date} visual preview contains OCR-like text: ${words.join(", ")}`);
  }
}

const totalBytesPerTree = inventory.reduce((total, entry) => total + entry.bytes, 0);
console.log(JSON.stringify({
  passed: true,
  count: inventory.length,
  mirroredCount: inventory.length * 2,
  totalBytesPerTree,
  largestBytes: Math.max(...inventory.map((entry) => entry.bytes)),
  ocrFindingCount,
  dimensions: [...new Set(inventory.map((entry) => `${entry.dimensions.width}x${entry.dimensions.height}`))],
}, null, 2));
