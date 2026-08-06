#!/usr/bin/env node
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import {
  mkdir,
  mkdtemp,
  readFile,
  readdir,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { gzipSync } from "node:zlib";
import { timetableData } from "../src/timetable/timetable-data.js";

const execFileAsync = promisify(execFile);
const root = path.resolve(new URL("..", import.meta.url).pathname);
const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "timetable-release-evidence-"));
const canonicalDirectory = path.join(root, "docs", "timetable");
const auditDirectory = path.join(root, "audits", "public-readable-hierarchy");
const evidencePath = path.join(auditDirectory, "release-evidence.json");
const sourceBudgetBytes = 6_100_000;
const builtJsBudgetBytes = 4_800_000;
const translatedReminderCount = timetableData.days.reduce(
  (count, day) => count + day.background_pulses.filter(
    (pulse) => pulse.category === "daily_reminder"
      && pulse.translation_provenance === "public_mask_preserving_translation_v1",
  ).length,
  0,
);
const translatedReminderGzipBudgetBytes = translatedReminderCount * 650;
const collaborationPairCount = timetableData.days.reduce(
  (count, day) => count + day.task_residues.reduce(
    (taskCount, task) => taskCount + (
      task.source_kind === "collaboration_session" ? 1 : 0
    ),
    0,
  ),
  0,
);
const collaborationPairGzipBudgetBytes = collaborationPairCount * 900;
const builtJsGzipBudgetBytes = 340_000
  + Math.max(0, timetableData.days.length - 78) * 5_000
  + translatedReminderGzipBudgetBytes
  + collaborationPairGzipBudgetBytes;

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

function isProjectedPublicPulse(pulse) {
  if (pulse.category !== "daily_reminder") return true;
  return (
    pulse.disclosure_policy === "semantic_abstraction_entity_masked_reminder_v3"
    && pulse.disclosure_authorization === "explicit_user_authorization_2026-07-29"
    && ["self", "self_scheduler_residue"].includes(pulse.owner_scope)
    && ["explicit_user_authorization", "explicit_import_authorization"].includes(
      pulse.ownership_provenance,
    )
  );
}

async function filesUnder(directory) {
  const result = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const candidate = path.join(directory, entry.name);
    if (entry.isDirectory()) result.push(...await filesUnder(candidate));
    else result.push(candidate);
  }
  return result;
}

async function buildManifest(directory) {
  const entries = [];
  for (const filePath of await filesUnder(directory)) {
    const bytes = await readFile(filePath);
    const relativePath = path.relative(directory, filePath).split(path.sep).join("/");
    entries.push({
      path: relativePath,
      bytes: bytes.length,
      ...(relativePath.endsWith(".js") || relativePath.endsWith(".css")
        ? { gzipBytes: gzipSync(bytes, { level: 9 }).length }
        : {}),
      sha256: sha256(bytes),
    });
  }
  return entries.sort((left, right) => left.path.localeCompare(right.path));
}

function manifestBytes(manifest) {
  return Buffer.from(`${JSON.stringify(manifest, null, 2)}\n`);
}

async function compareDirectories(expectedDirectory, actualDirectory, expected, actual) {
  const expectedByPath = new Map(expected.map((entry) => [entry.path, entry]));
  const actualByPath = new Map(actual.map((entry) => [entry.path, entry]));
  const missing = expected
    .filter((entry) => !actualByPath.has(entry.path))
    .map((entry) => entry.path);
  const extra = actual
    .filter((entry) => !expectedByPath.has(entry.path))
    .map((entry) => entry.path);
  const stale = [];
  for (const entry of expected) {
    const actualEntry = actualByPath.get(entry.path);
    if (!actualEntry) continue;
    const [expectedBytes, actualBytes] = await Promise.all([
      readFile(path.join(expectedDirectory, entry.path)),
      readFile(path.join(actualDirectory, entry.path)),
    ]);
    if (!expectedBytes.equals(actualBytes)) {
      stale.push({
        path: entry.path,
        expectedSha256: entry.sha256,
        actualSha256: actualEntry.sha256,
      });
    }
  }
  return {
    exact: missing.length === 0 && extra.length === 0 && stale.length === 0,
    byteForByte: manifestBytes(expected).equals(manifestBytes(actual)),
    manifestHashEqual: sha256(manifestBytes(expected)) === sha256(manifestBytes(actual)),
    missing,
    extra,
    stale,
  };
}

async function runCommand(executable, args) {
  try {
    const result = await execFileAsync(executable, args, {
      cwd: root,
      encoding: "utf8",
      maxBuffer: 10 * 1024 * 1024,
    });
    return {
      passed: true,
      exitCode: 0,
      stdout: result.stdout,
      stderr: result.stderr,
    };
  } catch (error) {
    return {
      passed: false,
      exitCode: Number.isInteger(error.code) ? error.code : null,
      stdout: typeof error.stdout === "string" ? error.stdout : "",
      stderr: typeof error.stderr === "string" ? error.stderr : "",
      error: errorMessage(error),
    };
  }
}

function commandEvidence(result, { includeParsedJson = false } = {}) {
  let parsed = null;
  if (includeParsedJson && result.stdout) {
    try {
      parsed = JSON.parse(result.stdout);
    } catch {}
  }
  return {
    passed: result.passed,
    exitCode: result.exitCode,
    stdoutBytes: Buffer.byteLength(result.stdout),
    stdoutSha256: sha256(Buffer.from(result.stdout)),
    stderrBytes: Buffer.byteLength(result.stderr),
    stderrSha256: sha256(Buffer.from(result.stderr)),
    ...(result.passed && result.stdout.trim()
      ? { summary: result.stdout.trim() }
      : {}),
    ...(parsed
      ? {
        metadata: parsed.metadata ?? null,
        vulnerabilities: parsed.metadata?.vulnerabilities ?? null,
      }
      : {}),
  };
}

const evidence = {
  schema: "timetable-release-evidence-v1",
  passed: false,
  evidencePath: path.relative(root, evidencePath),
  sourceData: null,
  bundle: null,
  publicSafety: null,
  npmAudit: null,
  errors: [],
};
let failure = null;

try {
  const [publicSafetyRun, npmAuditRun] = await Promise.all([
    runCommand("python3", [path.join(root, "scripts", "check_public_safety.py"), "--root", root]),
    runCommand("npm", ["audit", "--omit=dev", "--audit-level=high", "--json"]),
  ]);
  evidence.publicSafety = {
    command: "python3 scripts/check_public_safety.py --root .",
    ...commandEvidence(publicSafetyRun),
  };
  evidence.npmAudit = {
    command: "npm audit --omit=dev --audit-level=high --json",
    auditLevel: "high",
    omit: "dev",
    ...commandEvidence(npmAuditRun, { includeParsedJson: true }),
  };

  const canonicalDataPath = path.join(root, "src", "timetable", "timetable-data.js");
  const generatedPaths = [
    path.join(temporaryRoot, "timetable-data-a.js"),
    path.join(temporaryRoot, "timetable-data-b.js"),
  ];
  for (const outputPath of generatedPaths) {
    await execFileAsync(
      "python3",
      [
        path.join(root, "scripts", "build_timetable_data.py"),
        "--output",
        outputPath,
      ],
      { cwd: root },
    );
  }
  const [canonicalBytes, generatedABytes, generatedBBytes] = await Promise.all([
    readFile(canonicalDataPath),
    readFile(generatedPaths[0]),
    readFile(generatedPaths[1]),
  ]);
  const sourceHash = sha256(canonicalBytes);
  evidence.sourceData = {
    path: path.relative(root, canonicalDataPath),
    bytes: canonicalBytes.length,
    gzipBytes: gzipSync(canonicalBytes, { level: 9 }).length,
    sha256: sourceHash,
    budgetBytes: sourceBudgetBytes,
    deterministicBuilds: [
      {
        label: "data-build-a",
        bytes: generatedABytes.length,
        sha256: sha256(generatedABytes),
      },
      {
        label: "data-build-b",
        bytes: generatedBBytes.length,
        sha256: sha256(generatedBBytes),
      },
    ],
    deterministicParity:
      generatedABytes.equals(generatedBBytes)
      && generatedABytes.equals(canonicalBytes),
  };

  const publicDays = JSON.parse(
    await readFile(path.join(root, "metadata", "days.json"), "utf8"),
  );
  const history = JSON.parse(
    await readFile(path.join(root, "metadata", "timetable-history.json"), "utf8"),
  );
  const pulses = JSON.parse(
    await readFile(path.join(root, "metadata", "timetable-pulses.json"), "utf8"),
  );
  assert.equal(timetableData.days.length, publicDays.length, "public-day/generated parity");
  assert.equal(timetableData.days.length, history.days.length, "history/generated parity");
  assert.equal(timetableData.days.length, pulses.days.length, "pulse/generated parity");
  const historyByDate = new Map(history.days.map((day) => [day.date, day]));
  const pulsesByDate = new Map(pulses.days.map((day) => [
    day.date,
    day.pulses.filter(isProjectedPublicPulse),
  ]));
  for (const day of timetableData.days) {
    const historyDay = historyByDate.get(day.date);
    assert.ok(
      day.task_residues.length <= historyDay.assigned_residues.length,
      `${day.date}: task source/generated privacy-filter parity`,
    );
    assert.equal(
      day.history_provenance,
      historyDay.provenance,
      `${day.date}: history provenance parity`,
    );
    assert.equal(
      day.background_pulses.length,
      pulsesByDate.get(day.date).length,
      `${day.date}: pulse source/generated parity`,
    );
    assert.equal(
      day.timeline_events.length,
      day.task_residues.length + day.background_pulses.length + 1,
      `${day.date}: generated footprint parity`,
    );
    const footprintIds = day.timeline_events.map((event) => event.footprint_id);
    const projectedIds = day.reading_items.flatMap((item) => item.source_refs);
    assert.deepEqual(
      [...projectedIds].sort(),
      [...footprintIds].sort(),
      `${day.date}: reading/source reference parity`,
    );
    for (const item of day.reading_items) {
      const compactFields = new Set([
        "reading_id",
        "source",
        "source_refs",
        "layer",
        "classification",
        ...(item.classification === "climate_aggregate" ? ["family", "window"] : []),
      ]);
      assert.deepEqual(
        new Set(Object.keys(item)),
        compactFields,
        `${day.date}: reading item duplicates source payload`,
      );
    }
  }

  const buildDirectories = [
    path.join(temporaryRoot, "build-a"),
    path.join(temporaryRoot, "build-b"),
  ];
  for (const outputDirectory of buildDirectories) {
    await execFileAsync(
      path.join(root, "node_modules", ".bin", "vite"),
      [
        "build",
        "--config",
        path.join(root, "vite.timetable.config.mjs"),
        "--outDir",
        outputDirectory,
        "--emptyOutDir",
      ],
      { cwd: root },
    );
  }
  const [manifestA, manifestB, canonicalManifest] = await Promise.all([
    buildManifest(buildDirectories[0]),
    buildManifest(buildDirectories[1]),
    buildManifest(canonicalDirectory),
  ]);
  const [deterministicParity, canonicalParity] = await Promise.all([
    compareDirectories(
      buildDirectories[0],
      buildDirectories[1],
      manifestA,
      manifestB,
    ),
    compareDirectories(
      buildDirectories[0],
      canonicalDirectory,
      manifestA,
      canonicalManifest,
    ),
  ]);
  const javascript = manifestA.filter((entry) => entry.path.endsWith(".js"));
  const css = manifestA.filter((entry) => entry.path.endsWith(".css"));
  const javascriptTotals = {
    bytes: javascript.reduce((total, entry) => total + entry.bytes, 0),
    gzipBytes: javascript.reduce((total, entry) => total + entry.gzipBytes, 0),
    budgetBytes: builtJsBudgetBytes,
    gzipBudgetBytes: builtJsGzipBudgetBytes,
    translatedReminderCount,
    translatedReminderGzipBudgetBytes,
    collaborationPairCount,
    collaborationPairGzipBudgetBytes,
  };
  const cssTotals = {
    bytes: css.reduce((total, entry) => total + entry.bytes, 0),
    gzipBytes: css.reduce((total, entry) => total + entry.gzipBytes, 0),
  };
  evidence.bundle = {
    deterministicBuilds: [
      {
        label: "isolated-build-a",
        manifestBytes: manifestBytes(manifestA).length,
        manifestSha256: sha256(manifestBytes(manifestA)),
        files: manifestA,
      },
      {
        label: "isolated-build-b",
        manifestBytes: manifestBytes(manifestB).length,
        manifestSha256: sha256(manifestBytes(manifestB)),
        files: manifestB,
      },
    ],
    deterministicParity,
    canonical: {
      directory: "docs/timetable",
      manifestBytes: manifestBytes(canonicalManifest).length,
      manifestSha256: sha256(manifestBytes(canonicalManifest)),
      files: canonicalManifest,
    },
    canonicalParity,
    assets: {
      javascript: {
        files: javascript,
        totals: javascriptTotals,
      },
      css: {
        files: css,
        totals: cssTotals,
      },
    },
    dataParity: {
      publicDays: publicDays.length,
      generatedDays: timetableData.days.length,
      pulseSchema: pulses.schema,
    },
  };

  assert.ok(publicSafetyRun.passed, "public-safety scan failed");
  assert.ok(npmAuditRun.passed, "npm audit failed at high severity");
  assert.ok(
    generatedABytes.equals(generatedBBytes),
    "two data builds differ byte-for-byte",
  );
  assert.ok(
    generatedABytes.equals(canonicalBytes),
    "canonical generated data is stale",
  );
  assert.ok(
    canonicalBytes.length <= sourceBudgetBytes,
    `generated source exceeds ${sourceBudgetBytes} bytes`,
  );
  assert.ok(
    deterministicParity.exact
      && deterministicParity.byteForByte
      && deterministicParity.manifestHashEqual,
    `two production bundle manifests differ: ${JSON.stringify(deterministicParity)}`,
  );
  assert.ok(
    canonicalParity.exact
      && canonicalParity.byteForByte
      && canonicalParity.manifestHashEqual,
    `docs/timetable is not exact build output: ${JSON.stringify(canonicalParity)}`,
  );
  assert.ok(javascript.length > 0, "production bundle has no JavaScript asset");
  assert.ok(css.length > 0, "production bundle has no CSS asset");
  assert.ok(
    javascriptTotals.bytes <= builtJsBudgetBytes,
    `built JavaScript exceeds ${builtJsBudgetBytes} bytes`,
  );
  assert.ok(
    javascriptTotals.gzipBytes <= builtJsGzipBudgetBytes,
    `built JavaScript gzip exceeds ${builtJsGzipBudgetBytes} bytes`,
  );
  const builtText = (
    await Promise.all(
      javascript.map((entry) => readFile(path.join(buildDirectories[0], entry.path), "utf8")),
    )
  ).join("\n");
  for (const token of [
    "granted-hours-timetable-v2",
    "2026-07-21",
    "2026-07-22",
    "public_mask_preserving_translation_v1",
    "translated-reminder-copy",
  ]) {
    assert.ok(builtText.includes(token), `built/source parity missing ${token}`);
  }
  evidence.passed = true;
} catch (error) {
  failure = error;
  evidence.errors.push(errorMessage(error));
} finally {
  await mkdir(auditDirectory, { recursive: true });
  await writeFile(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
  await rm(temporaryRoot, { recursive: true, force: true });
}

console.log(JSON.stringify(evidence, null, 2));
if (failure) throw failure;
