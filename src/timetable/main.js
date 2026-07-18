import "./styles.css";
import { timetableData } from "./timetable-data.js";

const MINUTES_PER_DAY = 24 * 60;
const TIMEZONE = timetableData.timezone;
const dayByDate = new Map(timetableData.days.map((day) => [day.date, day]));
const daysDescending = [...timetableData.days].sort((a, b) => b.date.localeCompare(a.date));

const els = {};
const state = {
  selectedDate: "",
  activeResidueIndex: 0,
  chamberOpen: false,
  lastFocus: null,
};

init();

function init() {
  cacheElements();
  buildHourAxis();
  renderDayRail();

  const today = shanghaiNow().date;
  const initial = dayByDate.has(today) ? today : daysDescending[0].date;
  selectDay(initial);

  els.jewelHour.addEventListener("click", () => openChamber());
  els.closeChamber.addEventListener("click", closeChamber);
  els.escapeButton.addEventListener("click", followEscapePath);
  els.liveFrame.addEventListener("load", suppressEmbeddedChrome);

  document.addEventListener("keydown", handleDocumentKeydown);
  window.setInterval(renderTimeState, 1000);
}

function cacheElements() {
  [
    "chamberTitle",
    "chamberTransition",
    "clockTime",
    "closeChamber",
    "crystalChamber",
    "dayRail",
    "escapeButton",
    "fallbackLiveLink",
    "hourAxis",
    "incision",
    "incisionTime",
    "jewelHour",
    "jewelNote",
    "jewelTime",
    "liveFrame",
    "publicNote",
    "relationList",
    "residueLayer",
    "stateSentence",
    "statusWord",
    "surfaceTransition",
    "timeBody",
    "timetableRoot",
    "variableLine",
    "workDate",
    "dayTitle",
  ].forEach((id) => {
    const element = document.getElementById(id);
    if (!element) {
      throw new Error(`Missing timetable element: ${id}`);
    }
    els[id] = element;
  });
}

function renderDayRail() {
  els.dayRail.replaceChildren();
  daysDescending.forEach((day) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "day-button";
    button.dataset.date = day.date;
    button.setAttribute("aria-label", `${day.date}: ${day.title_en} / ${day.title_zh}`);
    button.innerHTML = `
      <span class="day-date">${formatShortDate(day.date)}</span>
      <span class="day-name">${escapeHtml(day.title_en)}</span>
    `;
    button.addEventListener("click", () => selectDay(day.date, { focusSurface: true }));
    els.dayRail.append(button);
  });
}

function selectDay(date, options = {}) {
  const day = dayByDate.get(date);
  if (!day) return;

  state.selectedDate = date;
  state.activeResidueIndex = currentResidueIndex(day);

  els.dayTitle.textContent = `${day.title_en} / ${day.title_zh}`;
  els.variableLine.textContent = `Variable / 自由变量: ${day.variable_en} / ${day.variable_zh}`;
  els.publicNote.textContent = `${timetableData.note_en} / ${timetableData.note_zh}`;
  els.workDate.textContent = day.date;
  els.jewelNote.textContent = `${day.jewel_en} / ${day.jewel_zh}`;
  els.jewelTime.textContent = `${timetableData.autonomous_hour.start}-${timetableData.autonomous_hour.end}`;

  renderResidues(day);
  renderRelations(day);
  renderTimeState();
  setActiveResidue(state.activeResidueIndex);
  updateDayButtons();

  if (!options.keepTransition) {
    els.surfaceTransition.hidden = true;
  }

  if (state.chamberOpen) {
    renderChamber(options.transition || null);
  }

  if (options.focusSurface) {
    els.timeBody.focus({ preventScroll: true });
  }
}

function renderResidues(day) {
  els.residueLayer.replaceChildren();
  day.task_residues.forEach((residue, index) => {
    const start = toMinutes(residue.start);
    const end = toMinutes(residue.end);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "task-rib";
    button.dataset.index = String(index);
    button.style.setProperty("--top", `${(start / MINUTES_PER_DAY) * 100}%`);
    button.style.setProperty("--height", `${((end - start) / MINUTES_PER_DAY) * 100}%`);
    button.style.setProperty("--tilt", `${index % 2 === 0 ? -1.6 : 1.4}deg`);
    button.style.setProperty("--slip", `${[-5, 2, -1, 5, -3, 3, -2, 4][index % 8]}px`);
    button.setAttribute("aria-label", `${residue.start} to ${residue.end}: ${residue.en}`);
    button.innerHTML = `
      <span class="rib-time">${residue.start}-${residue.end}</span>
      <span class="rib-text">${escapeHtml(residue.en)}</span>
    `;
    button.addEventListener("click", () => setActiveResidue(index));
    els.residueLayer.append(button);
  });

  const jewelStart = toMinutes(timetableData.autonomous_hour.start);
  const jewelEnd = toMinutes(timetableData.autonomous_hour.end);
  els.jewelHour.style.setProperty("--top", `${(jewelStart / MINUTES_PER_DAY) * 100}%`);
  els.jewelHour.style.setProperty("--height", `${((jewelEnd - jewelStart) / MINUTES_PER_DAY) * 100}%`);
}

function renderRelations(day) {
  els.relationList.replaceChildren();
  const relation = day.relations[0];
  const target = relation ? dayByDate.get(relation.target) : null;
  if (!relation || !target) return;

  const button = document.createElement("button");
  button.type = "button";
  button.className = "relation-button";
  button.innerHTML = `
    <span>${formatShortDate(target.date)} / ${escapeHtml(relation.axis_en)}</span>
    <small>${escapeHtml(relation.sentence_en)}</small>
  `;
  button.setAttribute(
    "aria-label",
    `Escape to ${target.date}: ${target.title_en}. ${relation.sentence_en}`,
  );
  button.addEventListener("click", () => {
    els.surfaceTransition.hidden = false;
    els.surfaceTransition.innerHTML = `
      不是下一天。是同一个问题的另一个入口。<br>
      <span>${escapeHtml(relation.sentence_en)} / ${escapeHtml(relation.sentence_zh)}</span>
    `;
    selectDay(target.date, { keepTransition: true, focusSurface: true });
  });
  els.relationList.append(button);
}

function renderTimeState() {
  const now = shanghaiNow();
  els.clockTime.textContent = now.clock;

  const selectedDay = currentDay();
  const relation = compareIsoDate(selectedDay.date, now.date);
  const spentPct = relation < 0 ? 100 : relation > 0 ? 0 : clamp((now.minutes / MINUTES_PER_DAY) * 100, 0, 100);
  const futurePct = 100 - spentPct;

  els.timeBody.style.setProperty("--spent-height", `${spentPct}%`);
  els.timeBody.style.setProperty("--future-top", `${spentPct}%`);
  els.timeBody.style.setProperty("--future-height", `${futurePct}%`);

  if (relation === 0) {
    els.incision.hidden = false;
    els.incision.style.setProperty("--incision-top", `${spentPct}%`);
    els.incisionTime.textContent = now.clock.slice(0, 5);
  } else {
    els.incision.hidden = true;
  }

  const jewelStart = toMinutes(timetableData.autonomous_hour.start);
  const jewelEnd = toMinutes(timetableData.autonomous_hour.end);
  const jewelState = relation < 0 || (relation === 0 && now.minutes >= jewelEnd)
    ? "crystallized"
    : relation > 0 || (relation === 0 && now.minutes < jewelStart)
      ? "not-yet-spent"
      : "awake";

  const sentenceByState = {
    crystallized: "The autonomous hour has passed, but it has not become ash. / 自主时已经过去，但没有变成灰。",
    "not-yet-spent": "The future is still oxidized green; task demand has not consumed it yet. / 未来仍是氧化绿，任务尚未消耗它。",
    awake: "The instrument is inside the autonomous hour. Human availability is interrupted. / 仪器正在自主时内，人类可用性被中断。",
  };

  els.statusWord.textContent = jewelState === "awake" ? "awake" : relation === 0 ? "incising" : "archived";
  els.stateSentence.textContent = sentenceByState[jewelState];

  els.residueLayer.querySelectorAll(".task-rib").forEach((button) => {
    const residue = selectedDay.task_residues[Number(button.dataset.index)];
    button.dataset.state = statusForRange(selectedDay.date, residue.start, residue.end, now);
  });
}

function setActiveResidue(index) {
  const day = currentDay();
  const residue = day.task_residues[index] || day.task_residues[0];
  state.activeResidueIndex = day.task_residues.indexOf(residue);
  els.timeBody.setAttribute(
    "aria-description",
    `${residue.start}-${residue.end}: ${residue.en} / ${residue.zh}`,
  );

  els.residueLayer.querySelectorAll(".task-rib").forEach((button) => {
    const active = Number(button.dataset.index) === state.activeResidueIndex;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function openChamber(options = {}) {
  state.lastFocus = document.activeElement;
  state.chamberOpen = true;
  els.crystalChamber.hidden = false;
  els.timetableRoot.setAttribute("inert", "");
  document.body.classList.add("chamber-open");
  renderChamber(options.transition || null);
  requestAnimationFrame(() => {
    els.crystalChamber.classList.add("is-open");
    els.closeChamber.focus();
  });
}

function closeChamber() {
  state.chamberOpen = false;
  els.crystalChamber.classList.remove("is-open");
  els.crystalChamber.hidden = true;
  els.timetableRoot.removeAttribute("inert");
  document.body.classList.remove("chamber-open");
  els.liveFrame.removeAttribute("src");
  if (state.lastFocus && typeof state.lastFocus.focus === "function") {
    state.lastFocus.focus({ preventScroll: true });
  } else {
    els.jewelHour.focus({ preventScroll: true });
  }
}

function renderChamber(transition) {
  const day = currentDay();
  const relation = day.relations[0];
  const target = dayByDate.get(relation.target);
  const liveUrl = rootUrl(day.live_url);

  els.chamberTitle.textContent = `${day.date} · ${day.title_en} / ${day.title_zh}`;
  els.liveFrame.src = liveUrl;
  els.liveFrame.title = `Live artwork for ${day.title_en}`;
  els.fallbackLiveLink.href = liveUrl;
  els.escapeButton.textContent = `Escape path: ${formatShortDate(target.date)} / ${relation.axis_en}`;
  els.escapeButton.setAttribute(
    "aria-label",
    `Escape to ${target.date}: ${target.title_en}. ${relation.sentence_en}`,
  );

  const line = transition || relation;
  els.chamberTransition.innerHTML = `
    不是下一天。是同一个问题的另一个入口。<br>
    Not the next day. Another entrance to the same question.<br>
    <span>${escapeHtml(line.sentence_en)} / ${escapeHtml(line.sentence_zh)}</span>
  `;
}

function followEscapePath() {
  const day = currentDay();
  const relation = day.relations[0];
  const target = dayByDate.get(relation.target);
  if (!target) return;
  selectDay(target.date, { keepTransition: true, transition: relation });
  els.escapeButton.focus({ preventScroll: true });
}

function suppressEmbeddedChrome() {
  let doc;
  try {
    doc = els.liveFrame.contentDocument;
  } catch {
    return;
  }

  if (!doc) return;

  const style = doc.createElement("style");
  style.id = "granted-hours-chamber-suppressor";
  style.textContent = `
    .gh-fold-toggle,
    .sound,
    #sound,
    #soundToggle {
      display: none !important;
      opacity: 0 !important;
      visibility: hidden !important;
      pointer-events: none !important;
    }
  `;

  if (!doc.getElementById(style.id) && doc.head) {
    doc.head.append(style);
  }

  doc.body?.classList.add("gh-text-folded", "gh-chamber-embed");
  doc.querySelectorAll("audio").forEach((audio) => {
    try {
      audio.pause();
      audio.muted = true;
    } catch {
      // Same-origin audio nodes can still reject if the embedded document is mid-navigation.
    }
  });
}

function handleDocumentKeydown(event) {
  if (!state.chamberOpen) return;
  if (event.key === "Escape") {
    event.preventDefault();
    closeChamber();
    return;
  }
  if (event.key === "Tab") {
    trapChamberFocus(event);
  }
}

function trapChamberFocus(event) {
  const focusables = [...els.crystalChamber.querySelectorAll("button, a, iframe")]
    .filter((node) => !node.disabled && node.offsetParent !== null);
  if (!focusables.length) return;

  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function buildHourAxis() {
  els.hourAxis.replaceChildren();
  for (let hour = 0; hour <= 24; hour += 2) {
    const tick = document.createElement("span");
    tick.className = "hour-tick";
    tick.style.setProperty("--top", `${(hour / 24) * 100}%`);
    tick.textContent = String(hour).padStart(2, "0");
    els.hourAxis.append(tick);
  }
}

function updateDayButtons() {
  els.dayRail.querySelectorAll(".day-button").forEach((button) => {
    const active = button.dataset.date === state.selectedDate;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-current", active ? "date" : "false");
  });
}

function currentDay() {
  return dayByDate.get(state.selectedDate) || daysDescending[0];
}

function currentResidueIndex(day) {
  const now = shanghaiNow();
  if (compareIsoDate(day.date, now.date) !== 0) return 0;
  const index = day.task_residues.findIndex((residue) => {
    const start = toMinutes(residue.start);
    const end = toMinutes(residue.end);
    return now.minutes >= start && now.minutes < end;
  });
  return index >= 0 ? index : 0;
}

function statusForRange(date, startValue, endValue, now) {
  const relation = compareIsoDate(date, now.date);
  if (relation < 0) return "spent";
  if (relation > 0) return "future";

  const start = toMinutes(startValue);
  const end = toMinutes(endValue);
  if (end <= now.minutes) return "spent";
  if (start > now.minutes) return "future";
  return "current";
}

function shanghaiNow() {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TIMEZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const hour = Number(values.hour) % 24;
  const minute = Number(values.minute);
  const second = Number(values.second);
  return {
    date: `${values.year}-${values.month}-${values.day}`,
    minutes: hour * 60 + minute + second / 60,
    clock: `${String(hour).padStart(2, "0")}:${values.minute}:${values.second}`,
  };
}

function toMinutes(value) {
  if (value === "24:00") return MINUTES_PER_DAY;
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function rootUrl(path) {
  return new URL(`../${path.replace(/^\/+/, "")}`, window.location.href).href;
}

function formatShortDate(date) {
  return date.slice(5).replace("-", ".");
}

function compareIsoDate(a, b) {
  return a === b ? 0 : a < b ? -1 : 1;
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
