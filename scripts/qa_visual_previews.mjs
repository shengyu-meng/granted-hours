#!/usr/bin/env node
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, statSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { timetableData } from "../src/timetable/timetable-data.js";

const ROOT = fileURLToPath(new URL("../", import.meta.url));
const MAX_BYTES = 700 * 1024;
const MAX_CORPUS_BYTES_PER_TREE = 35 * 1024 * 1024;
const MIN_MOTION_YAVG = 0.04;
const inventory = [];
const temporary = mkdtempSync(path.join(os.tmpdir(), "granted-hours-gif-qa-"));

function hash(filePath) {
  return createHash("sha256").update(readFileSync(filePath)).digest("hex");
}

function run(command, args) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  assert.equal(result.status, 0, `${command} failed:\n${result.stderr || result.stdout}`);
  return result.stdout;
}

function probeGif(filePath) {
  const output = run("ffprobe", [
    "-v", "error", "-count_frames", "-select_streams", "v:0",
    "-show_entries", "stream=width,height,nb_read_frames,duration:format=duration,size",
    "-of", "json", filePath,
  ]);
  const result = JSON.parse(output);
  return {
    width: Number(result.streams?.[0]?.width),
    height: Number(result.streams?.[0]?.height),
    frames: Number(result.streams?.[0]?.nb_read_frames),
    duration: Number(result.format?.duration || result.streams?.[0]?.duration),
    bytes: Number(result.format?.size),
  };
}

function inspectMotion(filePath) {
  const output = run("ffmpeg", [
    "-v", "error", "-i", filePath,
    "-vf", "tblend=all_mode=difference,signalstats,metadata=print:file=-",
    "-f", "null", "-",
  ]);
  const values = [...output.matchAll(/lavfi\.signalstats\.YAVG=([0-9.]+)/g)]
    .map((match) => Number(match[1]))
    .filter(Number.isFinite);
  return {
    changedFrames: values.filter((value) => value >= MIN_MOTION_YAVG).length,
    averageYavg: values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0,
    maximumYavg: values.length ? Math.max(...values) : 0,
  };
}

function representativeContactSheet(entry) {
  const middle = Math.floor(entry.frames / 2);
  const output = path.join(temporary, `${entry.date}.png`);
  run("ffmpeg", [
    "-y", "-v", "error", "-i", entry.archivePath,
    "-vf", `select='eq(n,0)+eq(n,${middle})+eq(n,${entry.frames - 1})',scale=400:225:flags=lanczos,tile=3x1`,
    "-frames:v", "1", output,
  ]);
  return output;
}

try {
  for (const day of timetableData.days) {
    const [year, month] = day.date.split("-");
    const relative = `archive/${year}/${month}/${day.date}/assets/visual-preview.gif`;
    const archivePath = `${ROOT}${relative}`;
    const docsPath = `${ROOT}docs/${relative}`;
    const archiveBytes = readFileSync(archivePath);
    const signature = archiveBytes.subarray(0, 6).toString("ascii");
    assert.ok(["GIF87a", "GIF89a"].includes(signature), `${day.date} has invalid GIF signature ${signature}`);
    assert.ok(archiveBytes.includes(Buffer.from("NETSCAPE2.0")), `${day.date} GIF is not marked to loop`);
    assert.equal(hash(archivePath), hash(docsPath), `${day.date} mirrors differ`);
    assert.ok(statSync(archivePath).size <= MAX_BYTES, `${day.date} visual preview is too large`);
    assert.equal(day.visual_preview, `${timetableData.canonical_base_url}${relative}`);
    assert.equal(day.autonomous_work.visual_preview_url, `${timetableData.canonical_base_url}${relative}`);

    const probe = probeGif(archivePath);
    assert.ok(
      (probe.width === 400 && probe.height === 225) || (probe.width === 360 && probe.height === 203),
      `${day.date} dimensions ${probe.width}x${probe.height}`,
    );
    assert.ok(probe.frames >= 12, `${day.date} must have at least 12 frames`);
    assert.ok(probe.duration >= 2 && probe.duration <= 4, `${day.date} duration ${probe.duration}`);
    assert.equal(probe.bytes, statSync(archivePath).size, `${day.date} size probe mismatch`);

    const motion = inspectMotion(archivePath);
    assert.ok(motion.changedFrames >= 2, `${day.date} changes too few frames: ${JSON.stringify(motion)}`);
    assert.ok(motion.averageYavg >= MIN_MOTION_YAVG, `${day.date} lacks visible motion: ${JSON.stringify(motion)}`);
    inventory.push({
      date: day.date,
      archivePath,
      docsPath,
      ...probe,
      ...motion,
    });
  }

  assert.equal(inventory.length, 78, "public GIF corpus must contain exactly 78 days");
  assert.equal(inventory.length, timetableData.days.length);
  assert.equal(new Set(inventory.map((entry) => entry.date)).size, timetableData.days.length);

  let ocrFindingCount = 0;
  for (const entry of inventory) {
    const contactSheet = representativeContactSheet(entry);
    const result = spawnSync(
      "tesseract",
      [contactSheet, "stdout", "-l", "eng", "--psm", "11", "tsv"],
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
      throw new Error(`${entry.date} representative GIF frames contain OCR-like text: ${words.join(", ")}`);
    }
  }

  const totalBytesPerTree = inventory.reduce((total, entry) => total + entry.bytes, 0);
  assert.ok(totalBytesPerTree <= MAX_CORPUS_BYTES_PER_TREE, `GIF corpus is too large: ${totalBytesPerTree}`);
  console.log(JSON.stringify({
    passed: true,
    count: inventory.length,
    mirroredCount: inventory.length * 2,
    totalBytesPerTree,
    largestBytes: Math.max(...inventory.map((entry) => entry.bytes)),
    smallestBytes: Math.min(...inventory.map((entry) => entry.bytes)),
    averageBytes: Math.round(totalBytesPerTree / inventory.length),
    minimumFrames: Math.min(...inventory.map((entry) => entry.frames)),
    maximumFrames: Math.max(...inventory.map((entry) => entry.frames)),
    durationRange: [
      Math.min(...inventory.map((entry) => entry.duration)),
      Math.max(...inventory.map((entry) => entry.duration)),
    ],
    minimumMotionYavg: Math.min(...inventory.map((entry) => entry.averageYavg)),
    ocrFindingCount,
    dimensions: [...new Set(inventory.map((entry) => `${entry.width}x${entry.height}`))],
  }, null, 2));
} finally {
  rmSync(temporary, { recursive: true, force: true });
}
