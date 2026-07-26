import "./styles.css";
import AppWindow from "lucide/dist/esm/icons/app-window.mjs";
import BookOpenCheck from "lucide/dist/esm/icons/book-open-check.mjs";
import ChartNoAxesCombined from "lucide/dist/esm/icons/chart-no-axes-combined.mjs";
import CircleOff from "lucide/dist/esm/icons/circle-off.mjs";
import Clock3 from "lucide/dist/esm/icons/clock-3.mjs";
import CloudSun from "lucide/dist/esm/icons/cloud-sun.mjs";
import CodeXml from "lucide/dist/esm/icons/code-xml.mjs";
import FilePenLine from "lucide/dist/esm/icons/file-pen-line.mjs";
import FileText from "lucide/dist/esm/icons/file-text.mjs";
import House from "lucide/dist/esm/icons/house.mjs";
import LockKeyhole from "lucide/dist/esm/icons/lock-keyhole.mjs";
import Megaphone from "lucide/dist/esm/icons/megaphone.mjs";
import Palette from "lucide/dist/esm/icons/palette.mjs";
import Presentation from "lucide/dist/esm/icons/presentation.mjs";
import Radio from "lucide/dist/esm/icons/radio.mjs";
import Search from "lucide/dist/esm/icons/search.mjs";
import Settings from "lucide/dist/esm/icons/settings.mjs";
import Split from "lucide/dist/esm/icons/split.mjs";
import Sun from "lucide/dist/esm/icons/sun.mjs";
import Waypoints from "lucide/dist/esm/icons/waypoints.mjs";
import createLucideElement from "lucide/dist/esm/createElement.mjs";
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
const THEME_ICONS = {
  window: ["app-window", AppWindow],
  seam: ["split", Split],
  bridge: ["waypoints", Waypoints],
  echo: ["radio", Radio],
  weather: ["cloud-sun", CloudSun],
  time: ["clock-3", Clock3],
  room: ["house", House],
  light: ["sun", Sun],
  void: ["circle-off", CircleOff],
};
const TASK_ICONS = {
  "file-pen-line": FilePenLine,
  megaphone: Megaphone,
  "chart-no-axes-combined": ChartNoAxesCombined,
  "code-xml": CodeXml,
  "book-open-check": BookOpenCheck,
  presentation: Presentation,
  search: Search,
  "file-text": FileText,
  palette: Palette,
  settings: Settings,
  "lock-keyhole": LockKeyhole,
};
const TASK_ACCENTS = {
  amber: "#f6c85f",
  cyan: "#67d7d1",
  green: "#8fd18a",
  blue: "#85b9ff",
  violet: "#d3a3ff",
  coral: "#ff9f85",
  lime: "#c0d477",
  sand: "#e6c990",
  pink: "#ff98c8",
  slate: "#bdc5d2",
};

const els = {};
const state = {
  visibleYear: 0,
  visibleMonth: 0,
  selectedDate: "",
  detailOpen: false,
  detailLastFocus: null,
  calendarBgmIndex: 0,
  calendarBgmPlaying: false,
  calendarBgmUserActivated: false,
  calendarBgmDesiredPlaying: false,
  clockDate: "",
};

function init() {
  cacheElements();
  setStaticCopy();
  setInitialMonth();
  renderMonth();
  renderTimeState();

  els.prevMonth.addEventListener("click", () => moveMonth(-1));
  els.nextMonth.addEventListener("click", () => moveMonth(1));
  els.todayButton.addEventListener("click", goToCurrentMonth);
  els.closeDetail.addEventListener("click", closeDayDetail);
  els.calendarBgmToggle.addEventListener("click", toggleCalendarBgm);
  els.calendarBgm.addEventListener("ended", advanceCalendarBgm);
  els.calendarBgm.addEventListener("play", handleCalendarBgmPlay);
  els.calendarBgm.addEventListener("pause", () => setCalendarBgmPlaying(false));
  setupCalendarBgm();

  document.addEventListener("keydown", handleDocumentKeydown);
  window.setInterval(renderTimeState, 1000);
}

function cacheElements() {
  [
    "assignedList",
    "calendarBgm",
    "calendarBgmStatus",
    "calendarBgmToggle",
    "clockTime",
    "closeDetail",
    "dayDialog",
    "dayDialogPanel",
    "dialogBoundary",
    "dialogDate",
    "dialogTitle",
    "dialogVariable",
    "enterAutonomous",
    "monthGrid",
    "monthTitle",
    "nextMonth",
    "prevMonth",
    "publicNote",
    "selfArtwork",
    "selfNote",
    "selfPreview",
    "selfPreviewLink",
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

function setupCalendarBgm() {
  if (!timetableData.bgm_playlist?.length) {
    els.calendarBgmToggle.disabled = true;
    els.calendarBgmStatus.textContent = "No archived BGM / 暂无归档音乐";
    return;
  }
  els.calendarBgm.volume = 0.34;
  setCalendarBgmTrack(0);
  setCalendarBgmPlaying(false);
  updateCalendarBgmControl("Latest track ready · click to play / 最新作品音乐已就绪");
}

function setCalendarBgmTrack(index) {
  const playlist = timetableData.bgm_playlist;
  if (!playlist?.length) return;
  state.calendarBgmIndex = ((index % playlist.length) + playlist.length) % playlist.length;
  const track = playlist[state.calendarBgmIndex];
  els.calendarBgm.src = track.bgm_url;
  els.calendarBgm.dataset.date = track.date;
  els.calendarBgm.load();
  updateCalendarBgmControl();
}

function toggleCalendarBgm() {
  if (!timetableData.bgm_playlist?.length) return;
  if (!els.calendarBgm.paused && !els.calendarBgm.ended) {
    state.calendarBgmDesiredPlaying = false;
    setCalendarBgmPlaying(false);
    els.calendarBgm.pause();
    return;
  }
  state.calendarBgmUserActivated = true;
  state.calendarBgmDesiredPlaying = true;
  const playback = els.calendarBgm.play();
  if (playback && typeof playback.catch === "function") {
    playback.catch(() => {
      state.calendarBgmDesiredPlaying = false;
      setCalendarBgmPlaying(false);
      updateCalendarBgmControl("Playback blocked · tap again / 浏览器阻止播放，请再次点击");
    });
  }
}

function advanceCalendarBgm() {
  const shouldContinue = state.calendarBgmUserActivated && state.calendarBgmDesiredPlaying;
  setCalendarBgmTrack(state.calendarBgmIndex + 1);
  if (!shouldContinue) return;
  const playback = els.calendarBgm.play();
  if (playback && typeof playback.catch === "function") {
    playback.catch(() => {
      state.calendarBgmDesiredPlaying = false;
      setCalendarBgmPlaying(false);
    });
  }
}

function handleCalendarBgmPlay() {
  if (!state.calendarBgmDesiredPlaying) {
    els.calendarBgm.pause();
    setCalendarBgmPlaying(false);
    return;
  }
  setCalendarBgmPlaying(true);
}

function setCalendarBgmPlaying(playing) {
  state.calendarBgmPlaying = playing;
  updateCalendarBgmControl();
}

function updateCalendarBgmControl(override = "") {
  const track = timetableData.bgm_playlist?.[state.calendarBgmIndex];
  els.calendarBgmToggle.setAttribute("aria-pressed", state.calendarBgmPlaying ? "true" : "false");
  els.calendarBgmToggle.textContent = state.calendarBgmPlaying
    ? "Pause timeline BGM / 暂停月历音乐"
    : "Play timeline BGM / 播放月历音乐";
  els.calendarBgmStatus.textContent = override || (track
    ? `${track.date} · ${track.title_en} / ${track.title_zh}`
    : "");
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

function goToCurrentMonth() {
  const today = shanghaiNow().date;
  const todayMonth = monthKey(today);
  const targetMonth = publicMonths.has(todayMonth) ? todayMonth : monthKey(daysDescending[0].date);
  setVisibleMonth(targetMonth);
  if (dayByDate.has(today)) {
    state.selectedDate = today;
  } else {
    state.selectedDate = latestDateInMonth(targetMonth) || daysDescending[0].date;
  }
  renderMonth({ transition: "month-reset" });
  focusDayButton(state.selectedDate);
}

function renderMonth(options = {}) {
  const monthKeyValue = isoMonth(state.visibleYear, state.visibleMonth);
  const today = shanghaiNow().date;
  const visibleMonthLabel = formatMonthTitle(state.visibleYear, state.visibleMonth);
  els.monthTitle.textContent = visibleMonthLabel;
  els.todayButton.textContent = visibleMonthLabel;
  els.todayButton.setAttribute("aria-label", `Visible month: ${visibleMonthLabel}. Return to the latest public month.`);
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

  const motif = day.theme_motif;
  const themeIcon = THEME_ICONS[motif];
  if (!themeIcon) throw new Error(`Missing semantic theme motif for ${day.date}`);

  const assigned = day.cell_assigned.slice(0, 2).map((marker) => {
    const taskNameZh = marker.task_name_zh || marker.short_zh;
    const taskNameEn = marker.task_name_en || marker.short_en;
    return `
    <span class="cell-mark assigned-mark">
      <span class="cell-mark-line"><span class="marker-zh">${escapeHtml(taskNameZh)}</span><span class="marker-divider"> / </span><span class="marker-en">${escapeHtml(taskNameEn)}</span></span>
    </span>
  `}).join("");

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
  button.prepend(buildIcon(themeIcon[1], themeIcon[0], "theme-icon"));
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
  const directLiveUrlObject = new URL(absoluteUrl(self.live_url || day.live_url));
  directLiveUrlObject.searchParams.set("from", "timetable");
  const directLiveUrl = directLiveUrlObject.href;
  els.enterAutonomous.href = directLiveUrl;
  els.selfPreviewLink.href = directLiveUrl;
  els.selfPreview.src = self.gif_url || self.preview_url || day.gif || day.preview;
  els.selfPreview.alt = `Animated preview of ${self.title_en} / 《${self.title_zh}》动态预览`;

  els.assignedList.replaceChildren();
  day.task_residues.forEach((task) => {
    const item = document.createElement("li");
    item.className = "assigned-item";
    item.dataset.durationMinutes = String(task.duration_minutes);
    item.dataset.timeProvenance = task.time_provenance;
    item.dataset.taskType = task.task_type;
    item.dataset.taskColor = task.task_color;
    item.dataset.redactionStatus = task.redaction_status;
    item.style.setProperty("--duration-minutes", String(task.duration_minutes));
    item.style.setProperty("--task-accent", taskAccent(task.task_color));
    item.innerHTML = `
      <span class="assigned-time">
        <span>${task.start}-${task.end}</span>
        <small>${task.duration_minutes} min · estimated / 估算</small>
      </span>
      <span class="assigned-type">
        <span class="assigned-type-icon"></span>
        <strong class="assigned-work-type">${escapeHtml(task.task_type_zh)} / ${escapeHtml(task.task_type_en)}</strong>
      </span>
      <span class="assigned-secondary">
        <span class="assigned-category">${escapeHtml(task.label_zh)} / ${escapeHtml(task.label_en)}</span>
        <span class="record-provenance">真实记录摘要 / FAITHFUL RECORD SUMMARY</span>
      </span>
      <span class="assigned-copy"><span class="copy-zh">${escapeHtml(task.zh)}</span><span class="copy-divider"> / </span><span class="copy-en">${escapeHtml(task.en)}</span></span>
      ${task.redaction_status !== "none"
        ? `<span class="redaction-badge">${task.redaction_status === "withheld" ? "记录未公开 / RECORD WITHHELD" : `部分打码 ${task.redaction_count} / ${task.redaction_count} REDACTION${task.redaction_count === 1 ? "" : "S"}`}</span>`
        : ""}
    `;
    const iconSlot = item.querySelector(".assigned-type-icon");
    iconSlot.replaceWith(buildIcon(taskIcon(task.task_icon), task.task_icon, "assigned-type-icon"));
    els.assignedList.append(item);
  });

}

function handleDocumentKeydown(event) {
  if (event.key === "Escape") {
    if (state.detailOpen) {
      event.preventDefault();
      closeDayDetail();
      return;
    }
  }

  if (event.key !== "Tab") return;
  if (state.detailOpen) {
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

function formatMonthDay(value) {
  const [, month, day] = value.split("-").map(Number);
  return `${month}/${day}`;
}

function compactEnglishTitle(title) {
  const parts = title.split(/\s+/).filter(Boolean);
  return parts.length > 3 ? `${parts.slice(0, 3).join(" ")}...` : title;
}

function buildIcon(iconNode, iconName, className) {
  if (!iconNode) throw new Error(`Unknown allowlisted Lucide icon: ${iconName}`);
  const wrapper = document.createElement("span");
  wrapper.className = className;
  wrapper.setAttribute("aria-hidden", "true");
  wrapper.append(
    createLucideElement(iconNode, {
      "data-lucide": iconName,
      "stroke-width": "1.5",
      "aria-hidden": "true",
      focusable: "false",
    }),
  );
  return wrapper;
}

function taskIcon(iconName) {
  return TASK_ICONS[iconName];
}

function taskAccent(colorName) {
  const accent = TASK_ACCENTS[colorName];
  if (!accent) throw new Error(`Unknown task color: ${colorName}`);
  return accent;
}

init();

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
