import "./styles.css";
import { timetableData } from "./timetable-data.js";

const MINUTES_PER_DAY = 24 * 60;
const TIMEZONE = timetableData.timezone;
const WEEKDAYS = [
  ["Mon", "一"],
  ["Tue", "二"],
  ["Wed", "三"],
  ["Thu", "四"],
  ["Fri", "五"],
  ["Sat", "六"],
  ["Sun", "日"],
];

const dayByDate = new Map(timetableData.days.map((day) => [day.date, day]));
const daysAscending = [...timetableData.days].sort((a, b) => a.date.localeCompare(b.date));
const daysDescending = [...daysAscending].reverse();
const publicMonths = new Set(daysAscending.map((day) => monthKey(day.date)));

const els = {};
const state = {
  visibleYear: 0,
  visibleMonth: 0,
  selectedDate: "",
  detailOpen: false,
  chamberOpen: false,
  detailLastFocus: null,
  chamberLastFocus: null,
  clockDate: "",
};

init();

function init() {
  cacheElements();
  setStaticCopy();
  setInitialMonth();
  renderMonth();
  renderTimeState();

  els.prevMonth.addEventListener("click", () => moveMonth(-1));
  els.nextMonth.addEventListener("click", () => moveMonth(1));
  els.todayButton.addEventListener("click", goToToday);
  els.closeDetail.addEventListener("click", closeDayDetail);
  els.enterAutonomous.addEventListener("click", () => openChamber());
  els.closeChamber.addEventListener("click", closeChamber);
  els.escapeButton.addEventListener("click", followEscapePath);
  els.liveFrame.addEventListener("load", suppressEmbeddedChrome);

  document.addEventListener("keydown", handleDocumentKeydown);
  window.setInterval(renderTimeState, 1000);
}

function cacheElements() {
  [
    "assignedList",
    "chamberTitle",
    "chamberTransition",
    "clockTime",
    "closeChamber",
    "closeDetail",
    "crystalChamber",
    "dayDialog",
    "dayDialogPanel",
    "dialogBoundary",
    "dialogDate",
    "dialogTitle",
    "dialogVariable",
    "enterAutonomous",
    "escapeButton",
    "fallbackLiveLink",
    "liveFrame",
    "monthGrid",
    "monthTitle",
    "nextMonth",
    "prevMonth",
    "publicNote",
    "sedimentTrack",
    "selfArtwork",
    "selfNote",
    "selfTime",
    "stateSentence",
    "timetableRoot",
    "todayButton",
  ].forEach((id) => {
    const element = document.getElementById(id);
    if (!element) {
      throw new Error(`Missing timetable element: ${id}`);
    }
    els[id] = element;
  });
}

function setStaticCopy() {
  els.publicNote.textContent = `${timetableData.note_en} / ${timetableData.note_zh}`;
}

function setInitialMonth() {
  const today = shanghaiNow().date;
  const todayMonth = monthKey(today);
  const initialMonth = publicMonths.has(todayMonth) ? todayMonth : monthKey(daysDescending[0].date);
  setVisibleMonth(initialMonth);
  state.selectedDate = dayByDate.has(today)
    ? today
    : latestDateInMonth(initialMonth) || daysDescending[0].date;
}

function setVisibleMonth(key) {
  const [year, month] = key.split("-").map(Number);
  state.visibleYear = year;
  state.visibleMonth = month;
}

function moveMonth(delta) {
  const next = new Date(Date.UTC(state.visibleYear, state.visibleMonth - 1 + delta, 1));
  state.visibleYear = next.getUTCFullYear();
  state.visibleMonth = next.getUTCMonth() + 1;
  renderMonth({ transition: delta < 0 ? "previous" : "next" });
}

function goToToday() {
  const today = shanghaiNow().date;
  const todayMonth = monthKey(today);
  const targetMonth = publicMonths.has(todayMonth) ? todayMonth : monthKey(daysDescending[0].date);
  setVisibleMonth(targetMonth);
  if (dayByDate.has(today)) {
    state.selectedDate = today;
  } else {
    state.selectedDate = latestDateInMonth(targetMonth) || daysDescending[0].date;
  }
  renderMonth({ transition: "today" });
  focusDayButton(state.selectedDate);
}

function renderMonth(options = {}) {
  const monthKeyValue = isoMonth(state.visibleYear, state.visibleMonth);
  const today = shanghaiNow().date;
  els.monthTitle.textContent = formatMonthTitle(state.visibleYear, state.visibleMonth);
  els.monthGrid.setAttribute("aria-label", `${els.monthTitle.textContent} month calendar`);
  els.monthGrid.dataset.motion = options.transition || "";
  els.monthGrid.replaceChildren();

  WEEKDAYS.forEach(([en, zh]) => {
    const header = document.createElement("div");
    header.className = "weekday-cell";
    header.setAttribute("role", "columnheader");
    header.textContent = `${zh} / ${en}`;
    els.monthGrid.append(header);
  });

  const firstDate = `${monthKeyValue}-01`;
  const leading = mondayLeadingCount(state.visibleYear, state.visibleMonth);
  const daysInMonth = daysInUtcMonth(state.visibleYear, state.visibleMonth);
  const cellCount = Math.ceil((leading + daysInMonth) / 7) * 7;
  const gridStart = addDays(firstDate, -leading);

  for (let index = 0; index < cellCount; index += 1) {
    const cellDate = addDays(gridStart, index);
    const day = dayByDate.get(cellDate);
    const inMonth = monthKey(cellDate) === monthKeyValue;
    const cell = document.createElement("div");
    cell.className = "date-cell";
    cell.setAttribute("role", "gridcell");
    cell.dataset.date = cellDate;
    cell.classList.toggle("is-muted", !inMonth);
    cell.classList.toggle("is-today", cellDate === today);
    cell.classList.toggle("is-selected", cellDate === state.selectedDate);
    if (cellDate === today && !day) {
      cell.setAttribute("aria-current", "date");
    }

    if (day) {
      cell.append(buildDayButton(day, cellDate === today, !inMonth));
    } else {
      const dateNumber = document.createElement("span");
      dateNumber.className = "empty-date-number";
      dateNumber.textContent = formatMonthDay(cellDate);
      dateNumber.setAttribute("aria-hidden", "true");
      cell.setAttribute("aria-label", formatLongDate(cellDate));
      cell.append(dateNumber);
    }
    els.monthGrid.append(cell);
  }
}

function buildDayButton(day, isToday, isMuted) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "calendar-day-button";
  button.dataset.date = day.date;
  button.classList.toggle("is-muted", isMuted);
  button.setAttribute("aria-label", dayCellLabel(day));
  if (isToday) {
    button.setAttribute("aria-current", "date");
  }

  const assigned = day.cell_assigned.slice(0, 2).map((marker) => `
    <span class="cell-mark assigned-mark">
      <span class="cell-mark-line"><span class="marker-zh">${escapeHtml(marker.short_zh)}</span><span class="marker-divider"> / </span><span class="marker-en">${escapeHtml(marker.short_en)}</span></span>
    </span>
  `).join("");

  button.innerHTML = `
    <span class="cell-date-number">${formatMonthDay(day.date)}</span>
    <span class="cell-material">
      <span class="assigned-marks">${assigned}</span>
      <span class="cell-mark self-mark">
        <span class="cell-mark-line"><span class="marker-zh">${escapeHtml(day.cell_self.short_zh)}</span><span class="marker-divider"> / </span><span class="marker-en">${escapeHtml(day.cell_self.short_en)}</span></span>
        <strong><span class="title-zh">${escapeHtml(day.title_zh)}</span><span class="title-divider"> / </span><span class="title-en">${escapeHtml(compactEnglishTitle(day.title_en))}</span></strong>
      </span>
    </span>
  `;
  button.addEventListener("click", () => openDayDetail(day.date));
  return button;
}

function openDayDetail(date) {
  const day = dayByDate.get(date);
  if (!day) return;

  state.detailLastFocus = document.activeElement;
  state.selectedDate = date;
  const targetMonth = monthKey(date);
  if (targetMonth !== isoMonth(state.visibleYear, state.visibleMonth)) {
    setVisibleMonth(targetMonth);
  }
  renderMonth();
  renderDayDetail(day);

  state.detailOpen = true;
  els.dayDialog.hidden = false;
  els.dayDialogPanel.scrollTop = 0;
  els.dayDialogPanel.querySelector(".detail-layout").scrollTop = 0;
  els.timetableRoot.setAttribute("inert", "");
  document.body.classList.add("detail-open");
  document.documentElement.classList.add("detail-open");
  requestAnimationFrame(() => {
    els.dayDialog.classList.add("is-open");
    els.closeDetail.focus({ preventScroll: true });
  });
}

function closeDayDetail() {
  state.detailOpen = false;
  els.dayDialog.classList.remove("is-open");
  els.dayDialog.hidden = true;
  els.timetableRoot.removeAttribute("inert");
  document.body.classList.remove("detail-open");
  document.documentElement.classList.remove("detail-open");
  if (state.detailLastFocus && typeof state.detailLastFocus.focus === "function" && document.contains(state.detailLastFocus)) {
    state.detailLastFocus.focus({ preventScroll: true });
  } else {
    focusDayButton(state.selectedDate);
  }
}

function renderDayDetail(day) {
  const self = day.autonomous_work;
  els.dialogTitle.textContent = `${day.title_en} / ${day.title_zh}`;
  els.dialogDate.textContent = formatLongDate(day.date);
  els.dialogVariable.textContent = `Variable / 自由变量: ${day.variable_en} / ${day.variable_zh}`;
  els.dialogBoundary.textContent = `${timetableData.note_en} / ${timetableData.note_zh}`;
  els.selfTime.textContent = `${self.start}-${self.end}`;
  els.selfArtwork.textContent = `${self.title_en} / ${self.title_zh}`;
  els.selfNote.textContent = `${self.note_en} / ${self.note_zh}`;
  els.enterAutonomous.setAttribute("aria-label", `Enter live artwork for ${day.title_en}`);

  els.assignedList.replaceChildren();
  day.task_residues.forEach((task) => {
    const item = document.createElement("li");
    item.className = "assigned-item";
    item.innerHTML = `
      <span class="assigned-time">${task.start}-${task.end}</span>
      <span class="assigned-category">${escapeHtml(task.label_zh)} / ${escapeHtml(task.label_en)}</span>
      <span class="assigned-copy">${escapeHtml(task.zh)} / ${escapeHtml(task.en)}</span>
    `;
    els.assignedList.append(item);
  });

  renderSedimentTrack(day);
}

function renderSedimentTrack(day) {
  els.sedimentTrack.replaceChildren();
  day.task_residues.forEach((task, index) => {
    const segment = document.createElement("span");
    segment.className = "sediment-segment assigned";
    segment.style.setProperty("--top", `${(toMinutes(task.start) / MINUTES_PER_DAY) * 100}%`);
    segment.style.setProperty("--height", `${((toMinutes(task.end) - toMinutes(task.start)) / MINUTES_PER_DAY) * 100}%`);
    segment.style.setProperty("--shade", String((index % 4) + 1));
    els.sedimentTrack.append(segment);
  });

  const self = day.autonomous_work;
  const selfSegment = document.createElement("span");
  selfSegment.className = "sediment-segment self";
  selfSegment.style.setProperty("--top", `${(toMinutes(self.start) / MINUTES_PER_DAY) * 100}%`);
  selfSegment.style.setProperty("--height", `${((toMinutes(self.end) - toMinutes(self.start)) / MINUTES_PER_DAY) * 100}%`);
  els.sedimentTrack.append(selfSegment);
}

function openChamber(options = {}) {
  const day = currentDay();
  if (!day) return;

  state.chamberLastFocus = document.activeElement;
  state.chamberOpen = true;
  els.crystalChamber.hidden = false;
  els.timetableRoot.setAttribute("inert", "");
  if (state.detailOpen) {
    els.dayDialog.setAttribute("inert", "");
  }
  document.body.classList.add("chamber-open");
  document.documentElement.classList.add("chamber-open");
  renderChamber(options.transition || null);
  requestAnimationFrame(() => {
    els.crystalChamber.classList.add("is-open");
    els.closeChamber.focus({ preventScroll: true });
  });
}

function closeChamber() {
  state.chamberOpen = false;
  els.crystalChamber.classList.remove("is-open");
  els.crystalChamber.hidden = true;
  document.body.classList.remove("chamber-open");
  document.documentElement.classList.remove("chamber-open");
  els.liveFrame.removeAttribute("src");

  if (state.detailOpen) {
    els.dayDialog.removeAttribute("inert");
    if (state.chamberLastFocus && typeof state.chamberLastFocus.focus === "function") {
      state.chamberLastFocus.focus({ preventScroll: true });
    } else {
      els.enterAutonomous.focus({ preventScroll: true });
    }
  } else {
    els.timetableRoot.removeAttribute("inert");
    focusDayButton(state.selectedDate);
  }
}

function renderChamber(transition) {
  const day = currentDay();
  const relation = day.relations[0];
  const target = relation ? dayByDate.get(relation.target) : null;
  const liveUrl = absoluteUrl(day.autonomous_work.live_url || day.live_url);

  els.chamberTitle.textContent = `${day.date} · ${day.title_en} / ${day.title_zh}`;
  els.liveFrame.src = liveUrl;
  els.liveFrame.title = `Live artwork for ${day.title_en}`;
  els.fallbackLiveLink.href = liveUrl;

  if (target && relation) {
    els.escapeButton.textContent = `Escape path: ${formatShortDate(target.date)} / ${relation.axis_en}`;
    els.escapeButton.disabled = false;
    els.escapeButton.setAttribute(
      "aria-label",
      `Escape to ${target.date}: ${target.title_en}. ${relation.sentence_en}`,
    );
  } else {
    els.escapeButton.textContent = "Escape path / 逃历";
    els.escapeButton.disabled = true;
  }

  const line = transition || relation;
  els.chamberTransition.innerHTML = `
    不是下一天。是同一个问题的另一个入口。<br>
    Not the next day. Another entrance to the same question.
    ${line ? `<br><span>${escapeHtml(line.sentence_en)} / ${escapeHtml(line.sentence_zh)}</span>` : ""}
  `;
}

function followEscapePath() {
  const day = currentDay();
  const relation = day.relations[0];
  const target = relation ? dayByDate.get(relation.target) : null;
  if (!target) return;

  state.selectedDate = target.date;
  setVisibleMonth(monthKey(target.date));
  renderMonth({ transition: "escape" });
  if (state.detailOpen) {
    renderDayDetail(target);
  }
  if (state.chamberOpen) {
    renderChamber(relation);
    els.escapeButton.focus({ preventScroll: true });
  }
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
  if (event.key === "Escape") {
    if (state.chamberOpen) {
      event.preventDefault();
      closeChamber();
      return;
    }
    if (state.detailOpen) {
      event.preventDefault();
      closeDayDetail();
      return;
    }
  }

  if (event.key !== "Tab") return;
  if (state.chamberOpen) {
    trapFocus(event, els.crystalChamber);
  } else if (state.detailOpen) {
    trapFocus(event, els.dayDialog);
  }
}

function trapFocus(event, container) {
  const focusables = [...container.querySelectorAll("button, a, iframe")]
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

function renderTimeState() {
  const now = shanghaiNow();
  els.clockTime.textContent = now.clock;
  if (state.clockDate && state.clockDate !== now.date) {
    renderMonth();
  }
  state.clockDate = now.date;

  const selectedDay = currentDay();
  const self = selectedDay?.autonomous_work;
  if (!selectedDay || !self) {
    els.stateSentence.textContent = "";
    return;
  }

  const relation = compareIsoDate(selectedDay.date, now.date);
  const start = toMinutes(self.start);
  const end = toMinutes(self.end);
  const selfState = relation < 0 || (relation === 0 && now.minutes >= end)
    ? "crystallized"
    : relation > 0 || (relation === 0 && now.minutes < start)
      ? "not-yet-spent"
      : "awake";

  const sentenceByState = {
    crystallized: "The autonomous hour is archived as a live work, not as available labor. / 自主时被归档为实时作品，而不是可用劳动。",
    "not-yet-spent": "The calendar marks the hour before the dream enters it. / 日历先标出这一小时，梦稍后进入。",
    awake: "The instrument is inside the autonomous hour. Human availability is interrupted. / 仪器正在自主时内，人类可用性被中断。",
  };
  els.stateSentence.textContent = sentenceByState[selfState];
}

function currentDay() {
  return dayByDate.get(state.selectedDate) || daysDescending[0];
}

function focusDayButton(date) {
  const button = els.monthGrid.querySelector(`.calendar-day-button[data-date="${date}"]`);
  if (button) {
    button.focus({ preventScroll: true });
  }
}

function latestDateInMonth(key) {
  const day = daysDescending.find((item) => monthKey(item.date) === key);
  return day ? day.date : "";
}

function dayCellLabel(day) {
  const assigned = day.cell_assigned
    .map((marker) => `${marker.label_en} / ${marker.label_zh}`)
    .join("; ");
  return `${formatLongDate(day.date)}: ${day.title_en} / ${day.title_zh}. ASSIGNED: ${assigned}. SELF: ${day.title_en} / ${day.title_zh}.`;
}

function formatMonthTitle(year, month) {
  const dateForMonth = new Date(Date.UTC(year, month - 1, 1));
  const en = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" }).format(dateForMonth);
  return `${en} / ${year}年${month}月`;
}

function formatLongDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  return `${value} / ${year}年${month}月${day}日`;
}

function formatShortDate(value) {
  return value.slice(5).replace("-", ".");
}

function formatMonthDay(value) {
  const [, month, day] = value.split("-").map(Number);
  return `${month}/${day}`;
}

function compactEnglishTitle(title) {
  const parts = title.split(/\s+/).filter(Boolean);
  return parts.length > 3 ? `${parts.slice(0, 3).join(" ")}...` : title;
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

function mondayLeadingCount(year, month) {
  const first = new Date(Date.UTC(year, month - 1, 1));
  return (first.getUTCDay() + 6) % 7;
}

function daysInUtcMonth(year, month) {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function addDays(value, delta) {
  const [year, month, day] = value.split("-").map(Number);
  const dateValue = new Date(Date.UTC(year, month - 1, day + delta));
  return [
    dateValue.getUTCFullYear(),
    String(dateValue.getUTCMonth() + 1).padStart(2, "0"),
    String(dateValue.getUTCDate()).padStart(2, "0"),
  ].join("-");
}

function isoMonth(year, month) {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function monthKey(value) {
  return value.slice(0, 7);
}

function toMinutes(value) {
  if (value === "24:00") return MINUTES_PER_DAY;
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
}

function absoluteUrl(value) {
  return new URL(value, window.location.href).href;
}

function compareIsoDate(a, b) {
  return a === b ? 0 : a < b ? -1 : 1;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
