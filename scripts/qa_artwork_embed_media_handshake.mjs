#!/usr/bin/env node
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import { timetableData } from "../src/timetable/timetable-data.js";

const timetableUrl = process.env.TIMETABLE_URL || "http://127.0.0.1:8891/timetable/";
const siteOrigin = new URL(timetableUrl).origin;
const day = [...timetableData.days]
  .reverse()
  .find((candidate) => candidate.autonomous_work?.origin !== "absence" && candidate.bgm);
assert.ok(day, "No autonomous artwork with BGM is available for the media handshake audit");

const channel = "runtime_audit_2026_x";
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage();
  await page.goto(timetableUrl, { waitUntil: "domcontentloaded", timeout: 45000 });
  const [year, month] = day.date.split("-");
  const embedPath = `/archive/${year}/${month}/${day.date}/live/?embed=calendar&gh_channel=${channel}`;
  await page.setContent(`<!doctype html>
    <iframe id="work" allow="autoplay" src="${embedPath}"></iframe>
    <script>
      window.mediaEvents = [];
      addEventListener("message", (event) => {
        const message = event.data;
        if (
          message?.type !== "granted-hours:media"
          || message.version !== 2
          || message.channel !== "${channel}"
        ) return;
        mediaEvents.push(message);
        if (message.event === "ready") {
          document.querySelector("#work").contentWindow.postMessage({
            type: "granted-hours:media",
            version: 2,
            channel: "${channel}",
            action: "play",
          }, location.origin);
        }
      });
    <\/script>`);

  await page.waitForFunction(
    () => mediaEvents.some(({ event }) => event === "ready")
      && mediaEvents.some(({ event }) => event === "state"),
    null,
    { timeout: 45000 },
  );
  const frame = page.frames().find((candidate) => candidate.url().includes("embed=calendar"));
  assert.ok(frame, "Artwork iframe did not load");
  await frame.waitForFunction(
    () => document.body?.dataset.ghAudioEnabled === "1",
    null,
    { timeout: 45000 },
  );
  // The historical race reset audio at DOM init, window.load, and 250 ms.
  // Staying enabled beyond that boundary proves the parent command won.
  await page.waitForTimeout(650);
  assert.equal(await frame.locator("body").getAttribute("data-gh-audio-enabled"), "1");
  assert.equal(await frame.locator(".gh-media-unlock").count(), 1);

  await page.locator("#work").evaluate((iframe, command) => {
    iframe.contentWindow.postMessage(command, location.origin);
  }, {
    type: "granted-hours:media",
    version: 2,
    channel,
    action: "pause",
  });
  await frame.waitForFunction(() => document.body?.dataset.ghAudioEnabled === "0");

  const statuses = await page.evaluate(() => mediaEvents.map(({ event, status }) => ({ event, status })));
  assert.ok(statuses.some(({ event }) => event === "ready"));
  assert.ok(statuses.some(({ status }) => ["armed", "buffering", "playing"].includes(status)));
  assert.ok(statuses.some(({ status }) => status === "paused"));
  console.log(JSON.stringify({ passed: true, date: day.date, statuses }, null, 2));
} finally {
  await browser.close();
}
