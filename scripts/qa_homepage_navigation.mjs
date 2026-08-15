#!/usr/bin/env node

import assert from "node:assert/strict";
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "playwright";

const baseUrl = process.env.HOMEPAGE_URL || "http://127.0.0.1:8788/";
const screenshotDir = process.env.HOMEPAGE_QA_DIR || "tmp/homepage-navigation-qa";

const viewports = [
  { name: "desktop", width: 1440, height: 900, touch: false },
  { name: "mobile", width: 390, height: 844, touch: true },
];

const browser = await chromium.launch({ headless: true });
const results = [];

await fs.mkdir(screenshotDir, { recursive: true });

try {
  for (const viewport of viewports) {
    const context = await browser.newContext({
      viewport: { width: viewport.width, height: viewport.height },
      isMobile: viewport.touch,
      hasTouch: viewport.touch,
    });
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(String(error)));
    await page.route(/\.(?:gif|png|webp|mp3)(?:\?.*)?$/i, (route) => route.abort());

    await page.goto(baseUrl, { waitUntil: "domcontentloaded" });

    const actions = page.locator(".hero .actions > .button");
    assert.equal(await actions.count(), 5, `${viewport.name}: expected five hero actions`);

    const timetableAction = actions.nth(2);
    assert.equal(
      (await timetableAction.textContent()).trim(),
      "Enter non-human timetable / 进入非人时间表",
      `${viewport.name}: the third hero action must be the timetable`,
    );
    assert.match(
      await timetableAction.getAttribute("href"),
      /^\.\/timetable\/$/,
      `${viewport.name}: timetable action has the wrong destination`,
    );

    assert.equal(
      await page.locator('a[href*="maze"], .maze-portal').count(),
      0,
      `${viewport.name}: an Interior or maze entrance remains`,
    );
    const bodyText = await page.locator("body").innerText();
    for (const residue of [
      "Granted Interior",
      "Enter the maze diary",
      "进入授时内景",
      "进入迷宫日记",
    ]) {
      assert.equal(
        bodyText.includes(residue),
        false,
        `${viewport.name}: homepage still exposes ${residue}`,
      );
    }

    const geometry = await page.evaluate(() => {
      const heroActions = [...document.querySelectorAll(".hero .actions > .button")];
      return {
        overflowX: document.documentElement.scrollWidth > document.documentElement.clientWidth,
        clippedActions: heroActions.filter((action) => {
          const rect = action.getBoundingClientRect();
          return rect.left < 0 || rect.right > window.innerWidth || rect.width <= 0 || rect.height <= 0;
        }).length,
      };
    });
    assert.equal(geometry.overflowX, false, `${viewport.name}: page overflows horizontally`);
    assert.equal(geometry.clippedActions, 0, `${viewport.name}: a hero action is clipped`);

    await page.screenshot({
      path: path.join(screenshotDir, `${viewport.name}.png`),
      fullPage: false,
    });

    if (viewport.touch) {
      await timetableAction.tap();
    } else {
      await timetableAction.focus();
      await page.keyboard.press("Enter");
    }
    await page.waitForURL(/\/timetable\/$/);
    assert.equal(pageErrors.length, 0, `${viewport.name}: ${pageErrors.join("; ")}`);

    results.push({ viewport: viewport.name, passed: true, geometry });
    await context.close();
  }
} finally {
  await browser.close();
}

console.log(JSON.stringify({ passed: true, baseUrl, results }, null, 2));
