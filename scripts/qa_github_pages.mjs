import { chromium } from "@playwright/test";

const base = "https://shengyu-meng.github.io/granted-hours/timetable/";
const browser = await chromium.launch({ headless: true });
const errors = [];

async function check(label, opts) {
  const ctx = await browser.newContext(opts);
  const page = await ctx.newPage();
  page.on("pageerror", e => errors.push(`${label}:page:${e.message}`));
  page.on("console", m => { if (m.type() === "error" && !/ERR_ABORTED|bgm/i.test(m.text())) errors.push(`${label}:console:${m.text()}`); });
  page.on("response", r => { if (r.status() >= 400) errors.push(`${label}:http:${r.status()}:${r.url()}`); });
  await page.goto(base, { waitUntil: "networkidle" });
  await page.waitForFunction(() => !!document.querySelector(".calendar-day-button"));
  const month = await page.evaluate(() => ({
    cellCount: document.querySelectorAll(".date-cell").length,
    publicDays: document.querySelectorAll(".calendar-day-button").length,
    month: monthTitle.textContent.trim(),
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    samples: Array.from(document.querySelectorAll(".cell-date-number, .empty-date-number")).slice(0, 12).map(n => n.textContent.trim()),
  }));
  const date = await page.locator(".calendar-day-button").last().getAttribute("data-date");
  if (opts.isMobile) {
    await page.tap(`.calendar-day-button[data-date="${date}"]`);
  } else {
    await page.click(`.calendar-day-button[data-date="${date}"]`);
  }
  await page.waitForTimeout(280);
  const detail = await page.evaluate(() => {
    const panel = dayDialogPanel;
    const last = document.querySelector(".assigned-item:last-child");
    const self = document.querySelector(".self-detail");
    const r1 = last.getBoundingClientRect();
    const r2 = self.getBoundingClientRect();
    panel.scrollTo({ top: panel.scrollHeight, behavior: "instant" });
    return {
      panelOverflow: getComputedStyle(panel).overflowY,
      panelTouchAction: getComputedStyle(panel).touchAction,
      overlap: Math.max(0, r1.bottom - r2.top),
      maxScroll: panel.scrollHeight - panel.clientHeight,
      reached: panel.scrollTop,
      enterVisible: (() => { const r = enterAutonomous.getBoundingClientRect(); return r.top < innerHeight && r.bottom > 0; })(),
      focused: document.activeElement?.id,
    };
  });
  await page.keyboard.press("Escape");
  const after = await page.evaluate(() => ({ hidden: dayDialog.hidden }));
  await ctx.close();
  return { label, month, date, detail, after };
}

const desktop = await check("desktop", { viewport: { width: 1440, height: 900 } });
const tall = await check("mobileTall", { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2.75, isMobile: true, hasTouch: true });
const shortM = await check("mobileShort", { viewport: { width: 421, height: 386 }, deviceScaleFactor: 2.75, isMobile: true, hasTouch: true });
await browser.close();

const failures = [];
if (desktop.month.overflow !== 0 || tall.month.overflow !== 0 || shortM.month.overflow !== 0) failures.push("overflow");
if (desktop.detail.overlap > 0.5 || tall.detail.overlap > 0.5 || shortM.detail.overlap > 0.5) failures.push("overlap");
if (tall.detail.maxScroll <= 0) failures.push("mobile-tall-no-scroll");
if (!tall.detail.enterVisible) failures.push("mobile-tall-button-not-reachable");
if (shortM.detail.maxScroll <= 0) failures.push("mobile-short-no-scroll");
if (!shortM.detail.enterVisible) failures.push("mobile-short-button-not-reachable");
if (!desktop.after.hidden || !tall.after.hidden || !shortM.after.hidden) failures.push("escape-fail");
if (errors.length) failures.push(`errors=${errors.length}`);
console.log(JSON.stringify({ failures, errors, desktop, tall, shortM }, null, 2));
process.exit(failures.length ? 1 : 0);