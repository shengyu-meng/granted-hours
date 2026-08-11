import "./styles.css";
import BookOpenCheck from "lucide/dist/esm/icons/book-open-check.mjs";
import ChartNoAxesCombined from "lucide/dist/esm/icons/chart-no-axes-combined.mjs";
import CodeXml from "lucide/dist/esm/icons/code-xml.mjs";
import FilePenLine from "lucide/dist/esm/icons/file-pen-line.mjs";
import FileText from "lucide/dist/esm/icons/file-text.mjs";
import LockKeyhole from "lucide/dist/esm/icons/lock-keyhole.mjs";
import Megaphone from "lucide/dist/esm/icons/megaphone.mjs";
import MessagesSquare from "lucide/dist/esm/icons/messages-square.mjs";
import Moon from "lucide/dist/esm/icons/moon.mjs";
import Music from "lucide/dist/esm/icons/music.mjs";
import Palette from "lucide/dist/esm/icons/palette.mjs";
import Play from "lucide/dist/esm/icons/play.mjs";
import Presentation from "lucide/dist/esm/icons/presentation.mjs";
import Search from "lucide/dist/esm/icons/search.mjs";
import Settings from "lucide/dist/esm/icons/settings.mjs";
import Sun from "lucide/dist/esm/icons/sun.mjs";
import createLucideElement from "lucide/dist/esm/createElement.mjs";
import {
  clearMarkdownRendering,
  markdownToPlainText,
  renderMarkdownInto,
} from "./markdown.js";
import { timetableData } from "./timetable-data.js";
import {
  layoutTimelineEvents,
  layoutTimelineReadingCards,
  positionTimelineElement,
  timeToMinutes,
} from "./timeline-layout.js";

const MINUTES_PER_DAY = 24 * 60;
const TIMEZONE = timetableData.timezone;
const THEME_STORAGE_KEY = "granted-hours-theme";
const BGM_STORAGE_KEY = "granted-hours-calendar-bgm";
const AUDIO_DEFAULTS_STORAGE_KEY = "granted-hours-audio-defaults-version";
const AUDIO_DEFAULTS_VERSION = "2026-08-10-default-on-v2";
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
const FINE_POINTER_QUERY = "(hover: hover) and (pointer: fine)";
const ARTWORK_MEDIA_VERSION = 2;
const ARTWORK_READY_TIMEOUT_MS = 10000;
const VISUAL_PREVIEW_TIMEOUT_MS = 18000;
const VISUAL_PREVIEW_RETRY_LIMIT = 2;
const PIANO_STORAGE_KEY = "granted-hours-piano-sounds";
const PIANO_CHROMATIC_STEPS = ["C", "Cs", "D", "Ds", "E", "F", "Fs", "G", "Gs", "A", "As", "B"];
const PIANO_NOTES = [];
for (let pianoOctave = 3; pianoOctave <= 5; pianoOctave += 1) {
  for (const pianoStep of PIANO_CHROMATIC_STEPS) {
    PIANO_NOTES.push(`${pianoStep}${pianoOctave}`);
  }
}
const PIANO_CATEGORY_BASE = {
  "service-support": 0,
  "ah-market-scan": 0,
  "us-market-scan": 0,
  "ai-brief": 0,
  "daily-reminder": 4,
  "warning-exception": 5,
  "assigned-work": 12,
  "autonomous-artwork": 24,
};
const PIANO_MIN_GAP_MS = 90;
const PIANO_SAME_NOTE_GAP_MS = 260;
const PIANO_VOLUME = 0.045;
const INSPECTION_HIDE_DELAY_MS = 110;
const INSPECTION_FADE_MS = 150;
const WEEKDAYS = [
  ["Mon", "一"],
  ["Tue", "二"],
  ["Wed", "三"],
  ["Thu", "四"],
  ["Fri", "五"],
  ["Sat", "六"],
  ["Sun", "日"],
];
const LONG_WEEKDAYS = [
  ["Sunday", "星期日"],
  ["Monday", "星期一"],
  ["Tuesday", "星期二"],
  ["Wednesday", "星期三"],
  ["Thursday", "星期四"],
  ["Friday", "星期五"],
  ["Saturday", "星期六"],
];

const dayByDate = new Map(timetableData.days.map((day) => [day.date, day]));
const daysAscending = [...timetableData.days].sort((a, b) => a.date.localeCompare(b.date));
const daysDescending = [...daysAscending].reverse();
const publicMonths = new Set(daysAscending.map((day) => monthKey(day.date)));
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
  "messages-square": MessagesSquare,
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
const CHROMATIC_TASK_ACCENTS = {
  amber: "#b79b68",
  cyan: "#6fa6a4",
  green: "#7fa187",
  blue: "#7899b6",
  violet: "#9187b0",
  coral: "#b77d73",
  lime: "#98a778",
  sand: "#b5a17e",
  pink: "#ae829a",
  slate: "#8997a6",
};
const MONTH_MARKER_ACCENTS = {
  social_media_organization: "pink",
  document_processing: "sand",
  code_development: "cyan",
  research_synthesis: "violet",
  system_maintenance: "slate",
  visual_production: "coral",
  redacted_private: "slate",
};
const SEMANTIC_CATEGORY_LABELS = {
  "assigned-work": "Assigned work / 人机协作",
  "ah-market-scan": "A/H scan / A/H 市场扫描",
  "us-market-scan": "U.S. scan / 美股市场扫描",
  "ai-brief": "AI brief / AI 日报",
  "service-support": "Service climate / 服务气候",
  "daily-reminder": "提醒 / Reminder",
  "warning-exception": "Promoted exception / 提升异常",
  "autonomous-artwork": "Autonomous artwork / AI 自主作品",
};
const MARKET_SUMMARY_GLOSSARY = {
  regimes: [
    {
      tokens: ["defensive / risk-contraction", "防守 / 风险收缩"],
      zh: "防守 / 风险收缩",
      en: "defensive / risk-contraction",
    },
    {
      tokens: ["offensive / risk-expansion", "进攻 / 风险扩张"],
      zh: "进攻 / 风险扩张",
      en: "offensive / risk-expansion",
    },
    {
      tokens: ["balanced / neutral", "均衡 / 中性"],
      zh: "均衡 / 中性",
      en: "balanced / neutral",
    },
  ],
  defaultRegime: {
    zh: "多源扫描未收敛为单一状态标签",
    en: "multi-source scans did not converge on one regime label",
  },
  themes: [
    {
      tokens: ["AI hardware and semiconductors", "AI 硬件与半导体"],
      zh: "AI 硬件与半导体",
      en: "AI hardware and semiconductors",
    },
    {
      tokens: ["optical interconnects", "光互连"],
      zh: "光互连",
      en: "optical interconnects",
    },
    {
      tokens: ["embodied AI", "具身智能"],
      zh: "具身智能",
      en: "embodied AI",
    },
    {
      tokens: ["resources and rates", "资源与利率"],
      zh: "资源与利率",
      en: "resources and rates",
    },
    {
      tokens: ["market regime and volatility", "市场状态与波动"],
      zh: "市场状态与波动",
      en: "market regime and volatility",
    },
  ],
  defaultThemes: {
    zh: "",
    en: "",
  },
  freshness: {
    alert: {
      tokens: [
        "出现公开级别链路或新鲜度提示",
        "存在数据或链路新鲜度警告",
        "a public-level pipeline or freshness alert was retained",
        "data or pipeline-freshness warnings were present",
      ],
      zh: "出现链路或新鲜度提示。",
      en: "a pipeline or freshness alert was retained.",
    },
    clear: {
      zh: "未保留链路提示。",
      en: "no pipeline alert was retained.",
    },
  },
};

const els = {};
const inspectionPayloadByCard = new WeakMap();
const state = {
  visibleYear: 0,
  visibleMonth: 0,
  selectedDate: "",
  detailOpen: false,
  detailLastFocus: null,
  artworkDetailOpen: false,
  artworkDetailLastFocus: null,
  artworkDetailScrollTop: 0,
  artworkMediaChannel: "",
  artworkMediaOrigin: "",
  artworkMediaReady: false,
  artworkMediaStatus: "idle",
  artworkReadyTimer: 0,
  visualPreviewHiddenAt: 0,
  taskDetailOpen: false,
  taskDetailLastFocus: null,
  taskDetailScrollTop: 0,
  taskDetailSuppressInspectionOnRestore: false,
  selectedReadingCard: null,
  linkedReadingCard: null,
  hoveredReadingCard: null,
  hoveredTimelineReadingCard: null,
  linkedFocusSuppressedCard: null,
  calendarBgmIndex: 0,
  calendarBgmPlaying: false,
  calendarBgmUserActivated: false,
  calendarBgmDesiredPlaying: false,
  pianoEnabled: false,
  pianoReady: false,
  pianoAudioContext: null,
  pianoBuffers: null,
  pianoLoadPromise: null,
  pianoLastTriggerAt: 0,
  pianoLastNoteIndex: -1,
  pianoActiveSources: new Set(),
  clockDate: "",
  theme: document.documentElement.dataset.theme === "light" ? "light" : "dark",
  reducedMotion: window.matchMedia(REDUCED_MOTION_QUERY).matches,
  inspectionLensAvailable: false,
  inspectionCard: null,
  inspectionHideTimer: 0,
  inspectionCleanupTimer: 0,
  inspectionRenderEpoch: 0,
  inspectionPanelScrollTop: 0,
  inspectionFocusSuppressedCard: null,
  inspectionCompatibilityGuardCard: null,
  inspectionCompatibilityGuardTimer: 0,
  inputModality: "initial",
  initiatingPointerType: "",
};
let timelinePlacementFrame = 0;
const overflowPreviewObserver = new ResizeObserver((entries) => {
  for (const entry of entries) syncOverflowPreviewState(entry.target);
});

function init() {
  cacheElements();
  createInspectionLens();
  setupInspectionCapability();
  setupTheme();
  setupMotionPreference();
  setStaticCopy();
  setInitialMonth();
  renderMonth();
  renderTimeState();
  const directDate = selectedDateFromUrl();
  if (directDate) {
    openDayDetail(directDate, { historyMode: "none" });
  }

  els.prevMonth.addEventListener("click", () => moveMonth(-1));
  els.nextMonth.addEventListener("click", () => moveMonth(1));
  els.todayButton.addEventListener("click", goToCurrentMonth);
  els.closeDetail.addEventListener("click", closeDayDetail);
  els.closeArtworkDetail.addEventListener("click", closeArtworkDetail);
  els.artworkFullscreen.addEventListener("click", enterArtworkFullscreen);
  els.artworkReturnCalendar.addEventListener("click", closeArtworkDetail);
  els.artworkLiveFrame.addEventListener("load", () => {
    if (state.artworkDetailOpen) sendArtworkMediaCommand("play");
  });
  els.artworkRuntimeRetry.addEventListener("click", retryArtworkRuntime);
  els.artworkLiveLink.addEventListener("click", () => sendArtworkMediaCommand("pause"));
  els.artworkArchiveLink.addEventListener("click", () => sendArtworkMediaCommand("pause"));
  window.addEventListener("message", handleArtworkMediaMessage);
  els.closeTaskDetail.addEventListener("click", closeTaskDetail);
  els.closeTaskDetail.addEventListener("pointerdown", (event) => {
    if (isCoarsePointerType(event.pointerType)) {
      state.taskDetailSuppressInspectionOnRestore = true;
    }
  });
  els.prevDay.addEventListener("click", () => navigatePublicDay(-1));
  els.nextDay.addEventListener("click", () => navigatePublicDay(1));
  els.timelineTouchToggle.addEventListener("click", toggleTimelineTouchGroups);
  els.calendarBgmToggle.addEventListener("click", toggleCalendarBgm);
  els.calendarBgmToggleDialog.addEventListener("click", toggleCalendarBgm);
  els.calendarBgm.addEventListener("ended", advanceCalendarBgm);
  els.calendarBgm.addEventListener("play", handleCalendarBgmPlay);
  els.calendarBgm.addEventListener("pause", () => setCalendarBgmPlaying(false));
  migrateDefaultAudioPreferences();
  setupCalendarBgm();
  setupPianoSound();
  setupTimelineReverseLinking();
  els.artworkDialog.addEventListener("click", (event) => {
    if (event.target === els.artworkDialog) closeArtworkDetail();
  });
  document.addEventListener("fullscreenchange", syncArtworkFullscreenState);

  document.addEventListener("keydown", handleDocumentKeydown);
  document.addEventListener("pointerdown", handleDocumentPointerdown);
  els.dayDialogPanel.addEventListener("scroll", () => {
    const nextScrollTop = els.dayDialogPanel.scrollTop;
    const moved = Math.abs(nextScrollTop - state.inspectionPanelScrollTop) > 0.5;
    state.inspectionPanelScrollTop = nextScrollTop;
    if (moved) hideInspectionLens({ immediate: true });
  }, { passive: true });
  window.addEventListener("scroll", () => {
    hideInspectionLens({ immediate: true });
  }, { passive: true });
  window.addEventListener("resize", () => {
    hideInspectionLens({ immediate: true });
    document.querySelectorAll(".overflow-scroll-preview").forEach(syncOverflowPreviewState);
    scheduleTimelineReadingPlacement();
  });
  window.addEventListener("popstate", handleDateSelectionPopstate);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      hideInspectionLens({ immediate: true });
      state.visualPreviewHiddenAt = Date.now();
      if (state.artworkDetailOpen) sendArtworkMediaCommand("pause");
      return;
    }
    const hiddenDuration = state.visualPreviewHiddenAt
      ? Date.now() - state.visualPreviewHiddenAt
      : 0;
    retryVisualPreviews({ restartLoaded: hiddenDuration > 30000 });
    if (state.artworkDetailOpen) sendArtworkMediaCommand("play");
  });
  window.addEventListener("online", () => retryVisualPreviews({ restartLoaded: false }));
  window.addEventListener("pageshow", (event) => {
    retryVisualPreviews({ restartLoaded: event.persisted });
  });
  window.setInterval(renderTimeState, 1000);
}

function migrateDefaultAudioPreferences() {
  try {
    if (localStorage.getItem(AUDIO_DEFAULTS_STORAGE_KEY) === AUDIO_DEFAULTS_VERSION) return;
    localStorage.setItem(BGM_STORAGE_KEY, "on");
    localStorage.setItem(PIANO_STORAGE_KEY, "on");
    localStorage.setItem(AUDIO_DEFAULTS_STORAGE_KEY, AUDIO_DEFAULTS_VERSION);
  } catch {}
}

function cacheElements() {
  [
    "calendarBgm",
    "calendarBgmToggle",
    "calendarBgmToggleDialog",
    "calendarPianoToggle",
    "calendarPianoToggleDialog",
    "clockTime",
    "artworkArchiveLink",
    "artworkBriefEn",
    "artworkBriefZh",
    "artworkDetailEn",
    "artworkDetailMeta",
    "artworkDetailTitle",
    "artworkDetailZh",
    "artworkDialog",
    "artworkDialogPanel",
    "artworkFullscreen",
    "artworkLiveLink",
    "artworkLiveFrame",
    "artworkReturnCalendar",
    "artworkRuntimeRetry",
    "artworkRuntimeStatus",
    "artworkRuntimeStatusCopy",
    "closeArtworkDetail",
    "closeDetail",
    "closeTaskDetail",
    "dayDialog",
    "dayDialogPanel",
    "dialogBoundary",
    "dialogDate",
    "dialogCrystallizationLink",
    "dialogTitle",
    "dialogVariable",
    "monthGrid",
    "monthTitle",
    "nextMonth",
    "nextDay",
    "prevMonth",
    "prevDay",
    "publicNote",
    "readingSelectionStatus",
    "stateSentence",
    "taskDetailEn",
    "taskDetailOccurrenceList",
    "taskDetailOccurrences",
    "taskDetailProvenance",
    "taskDetailSummaryDivider",
    "taskDetailSummaryLabel",
    "taskDetailTime",
    "taskDetailTitle",
    "taskDetailType",
    "taskDetailZh",
    "taskDialog",
    "taskDialogPanel",
    "themeToggle",
    "timetableRoot",
    "timelineList",
    "timelineTouchGroups",
    "timelineTouchToggle",
    "todayButton",
  ].forEach((id) => {
    const element = document.getElementById(id);
    if (!element) {
      throw new Error(`Missing timetable element: ${id}`);
    }
    els[id] = element;
  });
}

function createInspectionLens() {
  const lens = document.createElement("aside");
  lens.id = "inspectionLens";
  lens.className = "inspection-lens";
  lens.hidden = true;
  lens.setAttribute("aria-hidden", "true");
  lens.innerHTML = `
    <div class="inspection-lens-material">
      <div class="inspection-lens-media" id="inspectionLensMedia"></div>
      <div class="inspection-lens-copy" id="inspectionLensCopy">
        <p class="inspection-lens-kicker" id="inspectionLensKicker"></p>
        <p class="inspection-lens-time" id="inspectionLensTime"></p>
        <h3 class="inspection-lens-title" id="inspectionLensTitle"></h3>
        <p class="inspection-lens-summary" id="inspectionLensSummary"></p>
      </div>
    </div>
  `;
  document.body.append(lens);
  els.inspectionLens = lens;
  els.inspectionLensMedia = lens.querySelector("#inspectionLensMedia");
  els.inspectionLensCopy = lens.querySelector("#inspectionLensCopy");
  els.inspectionLensKicker = lens.querySelector("#inspectionLensKicker");
  els.inspectionLensTime = lens.querySelector("#inspectionLensTime");
  els.inspectionLensTitle = lens.querySelector("#inspectionLensTitle");
  els.inspectionLensSummary = lens.querySelector("#inspectionLensSummary");
}

function setupInspectionCapability() {
  const capability = window.matchMedia(FINE_POINTER_QUERY);
  const syncCapability = () => {
    state.inspectionLensAvailable = capability.matches;
    document.documentElement.classList.toggle(
      "inspection-lens-capable",
      state.inspectionLensAvailable,
    );
    document.documentElement.dataset.inspectionLensCapability = state.inspectionLensAvailable
      ? "fine-hover"
      : "unavailable";
    if (!state.inspectionLensAvailable) {
      hideInspectionLens({ immediate: true });
      return;
    }
    const candidate = currentInspectionCandidate();
    if (candidate) showInspectionLens(candidate);
  };
  syncCapability();
  capability.addEventListener?.("change", syncCapability);
}

function setupTheme() {
  applyTheme(state.theme, { persist: false });
  els.themeToggle.addEventListener("click", () => {
    applyTheme(state.theme === "dark" ? "light" : "dark", { persist: true });
  });
  const preference = window.matchMedia("(prefers-color-scheme: light)");
  preference.addEventListener?.("change", (event) => {
    let explicit = null;
    try {
      explicit = localStorage.getItem(THEME_STORAGE_KEY);
    } catch {}
    if (explicit !== "dark" && explicit !== "light") {
      applyTheme(event.matches ? "light" : "dark", { persist: false });
    }
  });
}

function setupMotionPreference() {
  const preference = window.matchMedia(REDUCED_MOTION_QUERY);
  state.reducedMotion = preference.matches;
  preference.addEventListener?.("change", (event) => {
    state.reducedMotion = event.matches;
    refreshVisualPreviews();
    if (state.inspectionCard?.isConnected) {
      showInspectionLens(state.inspectionCard, { force: true });
    }
  });
}

function staticVisualPreviewUrl(animatedUrl) {
  return String(animatedUrl || "").replace(/visual-preview\.gif(?:\?.*)?$/i, "visual-preview.webp");
}

function preferredVisualPreviewUrl(animatedUrl) {
  return state.reducedMotion ? staticVisualPreviewUrl(animatedUrl) : animatedUrl;
}

function visualPreviewRetryUrl(value, attempt) {
  if (!attempt) return publicAssetUrl(value);
  const url = new URL(publicAssetUrl(value), window.location.href);
  url.searchParams.set("gh_preview_retry", String(attempt));
  return url.href;
}

function clearVisualPreviewTimer(image) {
  if (!image._grantedHoursPreviewTimer) return;
  window.clearTimeout(image._grantedHoursPreviewTimer);
  image._grantedHoursPreviewTimer = 0;
}

function loadVisualPreview(image, kind, { retryAttempt = 0 } = {}) {
  const animatedUrl = image.dataset.animatedPreviewUrl || "";
  const staticUrl = image.dataset.staticPreviewUrl || staticVisualPreviewUrl(animatedUrl);
  const sourceUrl = kind === "animated" ? animatedUrl : staticUrl;
  if (!sourceUrl) return;
  clearVisualPreviewTimer(image);
  image.dataset.previewKind = kind;
  image.dataset.previewState = "loading";
  image.dataset.previewRetryAttempt = String(retryAttempt);
  image.onload = () => {
    clearVisualPreviewTimer(image);
    image.dataset.previewState = kind === "animated" ? "animated" : "static-fallback";
  };
  image.onerror = () => {
    clearVisualPreviewTimer(image);
    if (kind === "animated") {
      loadVisualPreview(image, "static", { retryAttempt });
      return;
    }
    image.dataset.previewState = "failed";
  };
  const nextSource = visualPreviewRetryUrl(sourceUrl, retryAttempt);
  if (
    image.complete
    && image.naturalWidth === 0
    && image.src === new URL(nextSource, window.location.href).href
  ) {
    image.removeAttribute("src");
  }
  image.src = nextSource;
  image._grantedHoursPreviewTimer = window.setTimeout(() => {
    if (image.dataset.previewState !== "loading") return;
    if (kind === "animated") loadVisualPreview(image, "static", { retryAttempt });
    else image.dataset.previewState = "failed";
  }, VISUAL_PREVIEW_TIMEOUT_MS);
  if (image.complete) {
    queueMicrotask(() => {
      if (image.dataset.previewState !== "loading") return;
      if (image.naturalWidth > 0) image.onload?.();
      else image.onerror?.();
    });
  }
}

function applyVisualPreviewSource(image, options = {}) {
  if (!image) return;
  const preferredKind = state.reducedMotion ? "static" : "animated";
  const currentKind = image.dataset.previewKind;
  const currentState = image.dataset.previewState;
  const retryAttempt = Number(image.dataset.previewRetryAttempt || 0);
  const needsRetry = (
    preferredKind === "animated"
    && ["static-fallback", "failed"].includes(currentState)
    && retryAttempt < VISUAL_PREVIEW_RETRY_LIMIT
  );
  if (
    !options.force
    && currentKind === preferredKind
    && ["loading", preferredKind === "animated" ? "animated" : "static-fallback"].includes(currentState)
  ) return;
  if (needsRetry || (options.restartLoaded && preferredKind === "animated")) {
    loadVisualPreview(image, "animated", {
      retryAttempt: Math.min(retryAttempt + 1, VISUAL_PREVIEW_RETRY_LIMIT),
    });
    return;
  }
  loadVisualPreview(image, preferredKind, { retryAttempt: 0 });
}

function refreshVisualPreviews() {
  document.querySelectorAll("img[data-animated-preview-url]").forEach((image) => {
    applyVisualPreviewSource(image, { force: true });
  });
}

function retryVisualPreviews({ restartLoaded = false } = {}) {
  if (document.hidden || state.reducedMotion) return;
  document.querySelectorAll("img[data-animated-preview-url]").forEach((image) => {
    const rect = image.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > window.innerHeight) return;
    applyVisualPreviewSource(image, { restartLoaded });
  });
}

function semanticCategory(item) {
  if (item.classification === "beacon" || item.origin === "self") {
    return "autonomous-artwork";
  }
  if (item.classification === "promoted_routine_exception") {
    return "warning-exception";
  }
  if (item.category === "daily_reminder") {
    return "daily-reminder";
  }
  if (item.classification === "foreground_event" || item.origin === "assigned") {
    return "assigned-work";
  }
  const family = item.family || "";
  const category = item.category || "";
  if (family === "ah_market" || category === "ah_market_scan") {
    return "ah-market-scan";
  }
  if (family === "us_market" || category === "us_market_scan") {
    return "us-market-scan";
  }
  if (family === "ai_brief" || category === "ai_daily_brief") {
    return "ai-brief";
  }
  return "service-support";
}

function applySemanticCategory(element, item) {
  const category = semanticCategory(item);
  element.dataset.category = category;
  if (category === "assigned-work" && item.task_color) {
    element.style.setProperty("--category-accent", taskAccent(item.task_color));
  }
  return category;
}

function auditedPublicMediaUrl(value, extensions) {
  if (!value) return "";
  let url;
  let canonical;
  try {
    canonical = new URL(timetableData.canonical_base_url);
    url = new URL(value, canonical);
  } catch {
    return "";
  }
  const normalizedPath = decodeURIComponent(url.pathname);
  if (
    url.origin !== canonical.origin
    || !normalizedPath.startsWith(canonical.pathname)
    || !normalizedPath.includes("/archive/")
    || normalizedPath.includes("..")
    || !extensions.some((extension) => normalizedPath.toLowerCase().endsWith(extension))
  ) {
    return "";
  }
  return publicAssetUrl(url.href);
}

function buildInspectionPayload(item) {
  const videoUrl = auditedPublicMediaUrl(
    item.video_url || item.motion_video_url,
    [".mp4", ".webm"],
  );
  const animatedUrl = auditedPublicMediaUrl(
    item.animated_preview_url || item.visual_preview_url,
    [".gif", ".webp"],
  );
  const derivedStaticUrl = staticVisualPreviewUrl(
    item.animated_preview_url || item.visual_preview_url,
  );
  const staticUrl = auditedPublicMediaUrl(
    item.static_preview_url || item.poster_url || derivedStaticUrl,
    [".png", ".jpg", ".jpeg", ".webp"],
  );
  return {
    category: semanticCategory(item),
    categoryLabel: SEMANTIC_CATEGORY_LABELS[semanticCategory(item)],
    time: `${item.start}-${item.end}`,
    title: `${item.label_en} / ${item.label_zh}`,
    summary: item.classification === "readable_reminder"
      ? [
        markdownToPlainText(item.excerpt_en || item.summary_en),
        markdownToPlainText(item.excerpt_original || item.summary_original),
      ].filter(Boolean).join(" / ")
      : item.excerpt_original
        || item.summary_original
        || `${item.summary_en} / ${item.summary_zh}`,
    media: {
      videoUrl,
      animatedUrl,
      staticUrl,
    },
  };
}

function canUseInspectionLens() {
  return state.inspectionLensAvailable
    && document.documentElement.classList.contains("inspection-lens-capable");
}

function isCoarsePointerType(pointerType) {
  return pointerType === "touch" || pointerType === "pen";
}

function clearInspectionCompatibilityGuard(card = null) {
  if (card && state.inspectionCompatibilityGuardCard !== card) return;
  window.clearTimeout(state.inspectionCompatibilityGuardTimer);
  state.inspectionCompatibilityGuardTimer = 0;
  state.inspectionCompatibilityGuardCard = null;
}

function scheduleInspectionCompatibilityGuardClear(card) {
  window.clearTimeout(state.inspectionCompatibilityGuardTimer);
  state.inspectionCompatibilityGuardTimer = window.setTimeout(() => {
    if (state.inspectionCompatibilityGuardCard === card) {
      state.inspectionCompatibilityGuardCard = null;
    }
    state.inspectionCompatibilityGuardTimer = 0;
  }, 0);
}

function trackReadingPointerInput(pointerType, card, { activation = false } = {}) {
  const normalizedPointerType = pointerType || "pointer";
  state.inputModality = normalizedPointerType;
  state.initiatingPointerType = pointerType || "";
  if (isCoarsePointerType(pointerType)) {
    state.inspectionFocusSuppressedCard = card;
    if (activation) {
      clearInspectionCompatibilityGuard();
      state.inspectionCompatibilityGuardCard = card;
    }
    state.hoveredReadingCard = null;
    hideInspectionLens({ immediate: true });
    return;
  }
  if (pointerType === "mouse") {
    state.inspectionFocusSuppressedCard = null;
    clearInspectionCompatibilityGuard();
  }
}

function trackKeyboardFocusInput() {
  state.inputModality = "keyboard";
  state.initiatingPointerType = "";
  state.inspectionFocusSuppressedCard = null;
  clearInspectionCompatibilityGuard();
}

function currentInspectionCandidate() {
  const activeCard = document.activeElement instanceof Element
    ? document.activeElement.closest(".event-reading-card")
    : null;
  const focusedCard = activeCard === state.inspectionFocusSuppressedCard
    ? null
    : activeCard;
  return focusedCard?.isConnected
    ? focusedCard
    : state.hoveredReadingCard?.isConnected
      ? state.hoveredReadingCard
      : null;
}

function stopInspectionMedia() {
  const video = els.inspectionLensMedia?.querySelector("video");
  if (video) {
    video.pause();
    video.removeAttribute("src");
    video.load();
  }
}

function renderInspectionCopy(payload) {
  els.inspectionLensCopy.hidden = false;
  els.inspectionLensKicker.textContent = payload.categoryLabel;
  els.inspectionLensTime.textContent = payload.time;
  els.inspectionLensTitle.textContent = payload.title;
  els.inspectionLensSummary.textContent = payload.summary;
}

function renderInspectionPlate(payload, renderEpoch) {
  if (renderEpoch !== state.inspectionRenderEpoch) return;
  stopInspectionMedia();
  els.inspectionLensMedia.style.removeProperty("background-image");
  const plate = document.createElement("div");
  plate.className = "inspection-typographic-plate";
  const marker = document.createElement("span");
  marker.className = "inspection-plate-marker";
  marker.textContent = payload.categoryLabel;
  const time = document.createElement("span");
  time.className = "inspection-plate-time";
  time.textContent = payload.time;
  const title = document.createElement("strong");
  title.className = "inspection-plate-title";
  title.textContent = payload.title;
  const summary = document.createElement("span");
  summary.className = "inspection-plate-summary";
  summary.textContent = payload.summary;
  plate.append(marker, time, title, summary);
  els.inspectionLensMedia.replaceChildren(plate);
  els.inspectionLensCopy.hidden = true;
  els.inspectionLens.dataset.mediaKind = "typographic";
  els.inspectionLens.dataset.mediaState = "ready";
  positionInspectionLens(state.inspectionCard);
}

function loadInspectionImage(payload, url, kind, renderEpoch, onFailure) {
  if (!url || renderEpoch !== state.inspectionRenderEpoch) {
    onFailure();
    return;
  }
  stopInspectionMedia();
  const image = document.createElement("img");
  image.className = "inspection-lens-image";
  image.alt = "";
  image.decoding = "async";
  image.fetchPriority = "high";
  image.draggable = false;
  if (kind === "animated-image" && payload.media.staticUrl) {
    image.dataset.loadingBackdrop = "static-preview";
  }
  let decodeStarted = false;
  let settled = false;
  let loadTimer = 0;
  const isCurrent = () => (
    renderEpoch === state.inspectionRenderEpoch
    && image.isConnected
    && els.inspectionLensMedia.contains(image)
  );
  const fail = () => {
    if (settled) return;
    settled = true;
    window.clearTimeout(loadTimer);
    if (!isCurrent()) return;
    els.inspectionLens.dataset.mediaDecodeState = "failed";
    onFailure();
  };
  const decodeLoadedImage = async () => {
    if (decodeStarted || settled || !isCurrent()) return;
    decodeStarted = true;
    try {
      await image.decode();
      if (settled || !isCurrent()) return;
      if (image.naturalWidth <= 0 || image.naturalHeight <= 0) {
        throw new Error("Decoded inspection image has no intrinsic dimensions");
      }
      settled = true;
      window.clearTimeout(loadTimer);
      delete image.dataset.loadingBackdrop;
      els.inspectionLensMedia.style.removeProperty("background-image");
      els.inspectionLens.dataset.mediaKind = kind;
      els.inspectionLens.dataset.mediaState = "ready";
      els.inspectionLens.dataset.mediaDecodeState = "decoded";
      positionInspectionLens(state.inspectionCard);
    } catch {
      fail();
    }
  };
  image.addEventListener("load", () => {
    void decodeLoadedImage();
  }, { once: true });
  image.addEventListener("error", fail, { once: true });
  els.inspectionLensMedia.replaceChildren(image);
  els.inspectionLensCopy.hidden = false;
  els.inspectionLens.dataset.mediaKind = kind;
  els.inspectionLens.dataset.mediaState = "loading";
  els.inspectionLens.dataset.mediaDecodeState = "pending";
  if (kind === "animated-image" && payload.media.staticUrl) {
    els.inspectionLensMedia.style.backgroundImage = `url("${payload.media.staticUrl.replaceAll('"', '%22')}")`;
  } else {
    els.inspectionLensMedia.style.removeProperty("background-image");
  }
  image.src = url;
  loadTimer = window.setTimeout(fail, VISUAL_PREVIEW_TIMEOUT_MS);
  if (image.complete) queueMicrotask(decodeLoadedImage);
}

function renderInspectionStatic(payload, renderEpoch) {
  loadInspectionImage(
    payload,
    payload.media.staticUrl,
    "static-image",
    renderEpoch,
    () => renderInspectionPlate(payload, renderEpoch),
  );
}

function renderInspectionAnimated(payload, renderEpoch) {
  loadInspectionImage(
    payload,
    payload.media.animatedUrl,
    "animated-image",
    renderEpoch,
    () => renderInspectionStatic(payload, renderEpoch),
  );
}

function renderInspectionVideo(payload, renderEpoch) {
  if (!payload.media.videoUrl || renderEpoch !== state.inspectionRenderEpoch) {
    renderInspectionAnimated(payload, renderEpoch);
    return;
  }
  stopInspectionMedia();
  const video = document.createElement("video");
  video.className = "inspection-lens-video";
  video.muted = true;
  video.autoplay = true;
  video.loop = true;
  video.playsInline = true;
  video.preload = "metadata";
  video.addEventListener("canplay", async () => {
    if (renderEpoch !== state.inspectionRenderEpoch) return;
    try {
      await video.play();
      els.inspectionLens.dataset.mediaKind = "video";
      els.inspectionLens.dataset.mediaState = "ready";
      positionInspectionLens(state.inspectionCard);
    } catch {
      renderInspectionAnimated(payload, renderEpoch);
    }
  }, { once: true });
  video.addEventListener("error", () => {
    if (renderEpoch !== state.inspectionRenderEpoch) return;
    renderInspectionAnimated(payload, renderEpoch);
  }, { once: true });
  els.inspectionLensMedia.replaceChildren(video);
  els.inspectionLensCopy.hidden = false;
  els.inspectionLens.dataset.mediaKind = "video";
  els.inspectionLens.dataset.mediaState = "loading";
  video.src = payload.media.videoUrl;
}

function renderInspectionMedia(payload) {
  state.inspectionRenderEpoch += 1;
  const renderEpoch = state.inspectionRenderEpoch;
  renderInspectionCopy(payload);
  if (state.reducedMotion) {
    renderInspectionStatic(payload, renderEpoch);
  } else if (payload.media.videoUrl) {
    renderInspectionVideo(payload, renderEpoch);
  } else if (payload.media.animatedUrl) {
    renderInspectionAnimated(payload, renderEpoch);
  } else if (payload.media.staticUrl) {
    renderInspectionStatic(payload, renderEpoch);
  } else {
    renderInspectionPlate(payload, renderEpoch);
  }
}

function positionInspectionLens(trigger) {
  if (!trigger?.isConnected || els.inspectionLens.hidden) return;
  const triggerRect = trigger.getBoundingClientRect();
  const lensRect = els.inspectionLens.getBoundingClientRect();
  const margin = 16;
  const gap = 14;
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const maximumLeft = Math.max(margin, viewportWidth - lensRect.width - margin);
  const maximumTop = Math.max(margin, viewportHeight - lensRect.height - margin);
  const availableRight = viewportWidth - margin - triggerRect.right - gap;
  const availableLeft = triggerRect.left - margin - gap;
  const availableBelow = viewportHeight - margin - triggerRect.bottom - gap;
  const availableAbove = triggerRect.top - margin - gap;
  let left;
  let top;
  let placement;

  if (availableRight >= lensRect.width || availableRight >= availableLeft) {
    left = triggerRect.right + gap;
    top = triggerRect.top + triggerRect.height / 2 - lensRect.height / 2;
    placement = "right";
  } else {
    left = triggerRect.left - lensRect.width - gap;
    top = triggerRect.top + triggerRect.height / 2 - lensRect.height / 2;
    placement = "left";
  }

  left = Math.max(margin, Math.min(maximumLeft, left));
  top = Math.max(margin, Math.min(maximumTop, top));
  const sideWouldOverlap = left < triggerRect.right - 1
    && left + lensRect.width > triggerRect.left + 1
    && top < triggerRect.bottom - 1
    && top + lensRect.height > triggerRect.top + 1;
  if (sideWouldOverlap && availableBelow >= lensRect.height) {
    left = Math.max(margin, Math.min(maximumLeft, triggerRect.left));
    top = triggerRect.bottom + gap;
    placement = "below";
  } else if (sideWouldOverlap && availableAbove >= lensRect.height) {
    left = Math.max(margin, Math.min(maximumLeft, triggerRect.left));
    top = triggerRect.top - lensRect.height - gap;
    placement = "above";
  }

  els.inspectionLens.style.left = `${Math.round(left)}px`;
  els.inspectionLens.style.top = `${Math.round(top)}px`;
  els.inspectionLens.dataset.placement = placement;
}

function showInspectionLens(card, { force = false } = {}) {
  if (!canUseInspectionLens() || !card?.isConnected) return;
  if (card === state.inspectionFocusSuppressedCard) {
    hideInspectionLens({ immediate: true });
    return;
  }
  const payload = inspectionPayloadByCard.get(card);
  if (!payload) return;
  window.clearTimeout(state.inspectionHideTimer);
  window.clearTimeout(state.inspectionCleanupTimer);
  state.inspectionHideTimer = 0;
  state.inspectionCleanupTimer = 0;
  const changed = state.inspectionCard !== card;
  state.inspectionCard = card;
  state.inspectionPanelScrollTop = els.dayDialogPanel.scrollTop;
  els.inspectionLens.hidden = false;
  els.inspectionLens.setAttribute("aria-hidden", "true");
  els.inspectionLens.dataset.readingId = card.dataset.readingId || "";
  els.inspectionLens.dataset.category = payload.category;
  if (changed || force) renderInspectionMedia(payload);
  positionInspectionLens(card);
  requestAnimationFrame(() => {
    if (state.inspectionCard !== card || els.inspectionLens.hidden) return;
    positionInspectionLens(card);
    els.inspectionLens.classList.add("is-visible");
  });
}

function hideInspectionLens({ immediate = false } = {}) {
  window.clearTimeout(state.inspectionHideTimer);
  window.clearTimeout(state.inspectionCleanupTimer);
  state.inspectionHideTimer = 0;
  state.inspectionCleanupTimer = 0;
  state.inspectionCard = null;
  state.inspectionRenderEpoch += 1;
  els.inspectionLens?.classList.remove("is-visible");
  if (!els.inspectionLens) return;
  const cleanup = () => {
    stopInspectionMedia();
    els.inspectionLensMedia.replaceChildren();
    els.inspectionLens.hidden = true;
    delete els.inspectionLens.dataset.readingId;
    delete els.inspectionLens.dataset.category;
    delete els.inspectionLens.dataset.mediaKind;
    delete els.inspectionLens.dataset.mediaState;
    delete els.inspectionLens.dataset.mediaDecodeState;
    delete els.inspectionLens.dataset.placement;
  };
  if (immediate || state.reducedMotion) {
    cleanup();
  } else {
    state.inspectionCleanupTimer = window.setTimeout(cleanup, INSPECTION_FADE_MS);
  }
}

function scheduleInspectionLensHide() {
  window.clearTimeout(state.inspectionHideTimer);
  state.inspectionHideTimer = window.setTimeout(() => {
    const nextCard = currentInspectionCandidate();
    if (nextCard) {
      showInspectionLens(nextCard);
    } else {
      hideInspectionLens();
    }
  }, INSPECTION_HIDE_DELAY_MS);
}

function applyTheme(theme, options = {}) {
  const normalized = theme === "light" ? "light" : "dark";
  state.theme = normalized;
  document.documentElement.dataset.theme = normalized;
  document.documentElement.style.colorScheme = normalized;
  els.themeToggle.setAttribute("aria-pressed", String(normalized === "light"));
  const next = normalized === "dark" ? "light" : "dark";
  const currentLabel = normalized === "dark" ? "Dark rite / 暗仪式" : "Light rite / 明仪式";
  const nextLabel = next === "dark" ? "dark theme / 暗色主题" : "light theme / 亮色主题";
  const nextIcon = next === "dark" ? Moon : Sun;
  els.themeToggle.replaceChildren(buildIcon(nextIcon, next, "header-control-icon"));
  els.themeToggle.setAttribute("aria-label", `${currentLabel}. Switch to ${nextLabel}.`);
  els.themeToggle.title = `Switch to ${nextLabel}`;
  if (options.persist) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, normalized);
    } catch {}
  }
}

function setStaticCopy() {
  els.publicNote.textContent = [timetableData.note_en, timetableData.note_zh].filter(Boolean).join(" / ");
}

function setupCalendarBgm() {
  if (!timetableData.bgm_playlist?.length) {
    for (const button of [els.calendarBgmToggle, els.calendarBgmToggleDialog]) {
      button.disabled = true;
    }
    updateCalendarBgmControl("No archived BGM / 暂无归档音乐");
    return;
  }
  let saved = "";
  try {
    saved = localStorage.getItem(BGM_STORAGE_KEY) || "";
  } catch {}
  state.calendarBgmDesiredPlaying = saved !== "off";
  els.calendarBgm.volume = 0.34;
  setCalendarBgmTrack(0);
  setCalendarBgmPlaying(false);
  updateCalendarBgmControl(
    state.calendarBgmDesiredPlaying
      ? "Timeline BGM enabled · interact once to start / 月历音乐已开启 · 互动一次后播放"
      : "Timeline BGM off · press to turn on / 月历音乐已关闭 · 点击开启",
  );
}

function setCalendarBgmTrack(index) {
  const playlist = timetableData.bgm_playlist;
  if (!playlist?.length) return;
  state.calendarBgmIndex = ((index % playlist.length) + playlist.length) % playlist.length;
  const track = playlist[state.calendarBgmIndex];
  els.calendarBgm.removeAttribute("src");
  els.calendarBgm.dataset.source = publicAssetUrl(track.bgm_url);
  els.calendarBgm.dataset.date = track.date;
  updateCalendarBgmControl();
}

function ensureCalendarBgmSource() {
  const source = els.calendarBgm.dataset.source;
  if (!source || els.calendarBgm.getAttribute("src") === source) return;
  els.calendarBgm.src = source;
  els.calendarBgm.load();
}

function toggleCalendarBgm() {
  if (!timetableData.bgm_playlist?.length) return;
  if (state.calendarBgmDesiredPlaying) {
    state.calendarBgmDesiredPlaying = false;
    try {
      localStorage.setItem(BGM_STORAGE_KEY, "off");
    } catch {}
    setCalendarBgmPlaying(false);
    els.calendarBgm.pause();
    return;
  }
  state.calendarBgmUserActivated = true;
  state.calendarBgmDesiredPlaying = true;
  try {
    localStorage.setItem(BGM_STORAGE_KEY, "on");
  } catch {}
  attemptCalendarBgmPlayback({ userActivated: true });
}

function attemptCalendarBgmPlayback(options = {}) {
  if (
    !timetableData.bgm_playlist?.length
    || !state.calendarBgmDesiredPlaying
    || state.artworkDetailOpen
  ) {
    updateCalendarBgmControl();
    return;
  }
  if (options.userActivated) state.calendarBgmUserActivated = true;
  ensureCalendarBgmSource();
  const playback = els.calendarBgm.play();
  if (playback && typeof playback.catch === "function") {
    playback.catch(() => {
      setCalendarBgmPlaying(false);
      updateCalendarBgmControl(
        "Timeline BGM enabled · interact once to start / 月历音乐已开启 · 互动一次后播放",
      );
    });
  }
}

function advanceCalendarBgm() {
  const shouldContinue = state.calendarBgmDesiredPlaying && !state.artworkDetailOpen;
  setCalendarBgmTrack(state.calendarBgmIndex + 1);
  if (!shouldContinue) return;
  attemptCalendarBgmPlayback();
}

function handleCalendarBgmPlay() {
  if (!state.calendarBgmDesiredPlaying || state.artworkDetailOpen) {
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
  const actionLabel = state.calendarBgmDesiredPlaying
    ? "Timeline BGM on · press to turn off / 月历音乐已开启 · 点击关闭"
    : "Timeline BGM off · press to turn on / 月历音乐已关闭 · 点击开启";
  const playbackLabel = state.artworkDetailOpen && state.calendarBgmDesiredPlaying
    ? "Paused while the artwork is active / 作品激活期间已暂时静音"
    : state.calendarBgmPlaying
      ? "Now playing / 正在播放"
      : "Waiting for browser playback permission / 等待浏览器播放许可";
  const trackLabel = track ? `${track.date} · ${track.title_en} / ${track.title_zh}` : "";
  const accessibleLabel = override || [actionLabel, playbackLabel, trackLabel].filter(Boolean).join(". ");
  for (const button of [els.calendarBgmToggle, els.calendarBgmToggleDialog]) {
    button.setAttribute("aria-pressed", state.calendarBgmDesiredPlaying ? "true" : "false");
    button.dataset.playing = state.calendarBgmPlaying ? "true" : "false";
    button.dataset.suspended = state.artworkDetailOpen && state.calendarBgmDesiredPlaying ? "true" : "false";
    button.setAttribute("aria-label", accessibleLabel);
    button.title = actionLabel;
    button.replaceChildren(
      buildIcon(Music, "music", "header-control-icon header-control-icon-music"),
    );
  }
}


function restorePianoPreference() {
  let saved = "";
  try {
    saved = localStorage.getItem(PIANO_STORAGE_KEY) || "";
  } catch {}
  state.pianoEnabled = saved !== "off";
  updatePianoControl();
}

function pianoSampleUrl(note) {
  return new URL(`./piano/${note}.mp3`, window.location.href).href;
}

function ensurePianoAudioContext() {
  if (state.pianoAudioContext) {
    if (state.pianoAudioContext.state === "suspended") {
      state.pianoAudioContext.resume();
    }
    return state.pianoAudioContext;
  }
  const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextCtor) return null;
  const context = new AudioContextCtor({ latencyHint: "interactive" });
  state.pianoAudioContext = context;
  if (context.state === "suspended") context.resume();
  return context;
}

function preloadPianoBuffers() {
  if (state.pianoLoadPromise) return state.pianoLoadPromise;
  if (state.pianoReady) return Promise.resolve(true);
  const context = ensurePianoAudioContext();
  if (!context) return Promise.resolve(false);
  state.pianoLoadPromise = Promise.all(
    PIANO_NOTES.map((note) => fetch(pianoSampleUrl(note))
      .then((response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        return response.arrayBuffer();
      })
      .then((bytes) => context.decodeAudioData(bytes))
      .catch(() => null)),
  ).then((buffers) => {
    state.pianoBuffers = buffers;
    state.pianoReady = buffers.some(Boolean);
    state.pianoLoadPromise = null;
    return state.pianoReady;
  });
  return state.pianoLoadPromise;
}

function stopPianoSources() {
  for (const source of state.pianoActiveSources) {
    try {
      source.stop();
    } catch {}
    try {
      source.disconnect();
    } catch {}
  }
  state.pianoActiveSources.clear();
}

function pianoDurationMinutesFromElement(element) {
  const explicit = Number(element?.dataset?.durationMinutes);
  if (Number.isFinite(explicit) && explicit > 0) return explicit;
  const start = element?.dataset?.start;
  const end = element?.dataset?.end;
  if (start && end) {
    const computed = timeToMinutes(end) - timeToMinutes(start);
    if (Number.isFinite(computed) && computed > 0) return computed;
  }
  return 1;
}

function pianoDurationOffset(minutes) {
  const value = Number.isFinite(minutes) ? Math.max(1, Math.round(minutes)) : 1;
  return Math.min(11, Math.round(Math.log2(value)));
}

function pianoNoteIndexForElement(element) {
  const category = element?.dataset?.category || "";
  const isAbsence = element?.classList?.contains("absence-reading-card")
    || element?.dataset?.origin === "absence";
  const base = isAbsence
    ? 0
    : PIANO_CATEGORY_BASE[category] ?? 0;
  const index = base + pianoDurationOffset(pianoDurationMinutesFromElement(element));
  return Math.min(PIANO_NOTES.length - 1, Math.max(0, index));
}

function playPianoNote(element) {
  if (!element?.isConnected) return;
  playPianoNoteIndex(pianoNoteIndexForElement(element));
}

function pianoNoteIndexForDay(day) {
  const sources = Object.entries(day.cell_sources || {}).filter(([, source]) => source.present);
  const hasFreeCreation = sources.some(([key]) => key === "free_creation");
  const hasCollaboration = sources.some(([key]) => key === "collaboration");
  const base = hasFreeCreation ? 24 : hasCollaboration ? 12 : 0;
  const density = sources.length + (day.cell_assigned?.length || 0);
  const offset = Math.min(11, Math.round(Math.log2(Math.max(1, density))));
  return Math.min(PIANO_NOTES.length - 1, Math.max(0, base + offset));
}

function playPianoNoteForDay(day) {
  playPianoNoteIndex(pianoNoteIndexForDay(day));
}

function playPianoNoteIndex(noteIndex) {
  if (!state.pianoEnabled) return;
  const context = ensurePianoAudioContext();
  if (!context || context.state !== "running") return;
  if (!state.pianoReady) {
    preloadPianoBuffers().then((ready) => {
      if (ready && state.pianoEnabled) playPianoNoteIndex(noteIndex);
    });
    return;
  }
  const buffer = state.pianoBuffers?.[noteIndex];
  if (!buffer) return;
  const now = performance.now();
  if (now - state.pianoLastTriggerAt < PIANO_MIN_GAP_MS) return;
  if (noteIndex === state.pianoLastNoteIndex && now - state.pianoLastTriggerAt < PIANO_SAME_NOTE_GAP_MS) return;
  state.pianoLastTriggerAt = now;
  state.pianoLastNoteIndex = noteIndex;
  const source = context.createBufferSource();
  source.buffer = buffer;
  const gain = context.createGain();
  const startAt = context.currentTime + 0.004;
  gain.gain.setValueAtTime(0.0001, startAt);
  gain.gain.exponentialRampToValueAtTime(PIANO_VOLUME, startAt + 0.03);
  gain.gain.setValueAtTime(PIANO_VOLUME, startAt + 0.24);
  gain.gain.exponentialRampToValueAtTime(0.0001, startAt + 1.55);
  source.connect(gain);
  gain.connect(context.destination);
  source.addEventListener("ended", () => {
    state.pianoActiveSources.delete(source);
    try {
      gain.disconnect();
    } catch {}
  });
  state.pianoActiveSources.add(source);
  source.start(startAt);
  source.stop(startAt + 1.7);
}

function togglePianoSounds() {
  state.pianoEnabled = !state.pianoEnabled;
  try {
    localStorage.setItem(PIANO_STORAGE_KEY, state.pianoEnabled ? "on" : "off");
  } catch {}
  updatePianoControl();
  if (state.pianoEnabled) {
    const context = ensurePianoAudioContext();
    if (context) {
      context.resume?.();
      preloadPianoBuffers().catch(() => {});
    }
  } else {
    stopPianoSources();
  }
}

function buildPianoIcon() {
  const wrapper = document.createElement("span");
  wrapper.className = "header-control-icon header-control-icon-piano";
  wrapper.setAttribute("aria-hidden", "true");
  wrapper.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" focusable="false" aria-hidden="true"><rect x="3" y="6.5" width="18" height="13" rx="2"/><path d="M3 11.5h18"/><path d="M8 6.5v5M12 6.5v5M16 6.5v5"/><rect x="7.1" y="6.5" width="2.3" height="4.2" rx="0.7" fill="currentColor" stroke="none"/><rect x="11.2" y="6.5" width="2.3" height="4.2" rx="0.7" fill="currentColor" stroke="none"/><rect x="15.3" y="6.5" width="2.3" height="4.2" rx="0.7" fill="currentColor" stroke="none"/></svg>';
  return wrapper;
}

function updatePianoControl() {
  const actionLabel = state.pianoEnabled
    ? "Piano-key hover sounds on / 钢琴键悬停音效已开启"
    : "Piano-key hover sounds off / 钢琴键悬停音效已关闭";
  for (const button of [els.calendarPianoToggle, els.calendarPianoToggleDialog]) {
    button.setAttribute("aria-pressed", state.pianoEnabled ? "true" : "false");
    button.setAttribute("aria-label", actionLabel);
    button.title = "Piano-key hover sounds / 钢琴键悬停音效";
    button.replaceChildren(buildPianoIcon());
  }
}

function activateDefaultAudioFromGesture(target) {
  const control = target instanceof Element
    ? target.closest(
      "#calendarBgmToggle,#calendarBgmToggleDialog,#calendarPianoToggle,#calendarPianoToggleDialog,.autonomous-preview-frame,.autonomous-open-copy,.autonomous-touch-control",
    )
    : null;
  if (control) return;
  if (state.calendarBgmDesiredPlaying && !state.calendarBgmPlaying) {
    attemptCalendarBgmPlayback({ userActivated: true });
  }
  if (state.pianoEnabled) {
    const context = ensurePianoAudioContext();
    context?.resume?.();
    preloadPianoBuffers().catch(() => {});
  }
}

function setupPianoTimelineEvents() {
  els.timelineList.addEventListener("pointerover", (event) => {
    if (!state.pianoEnabled || event.pointerType !== "mouse") return;
    if (!window.matchMedia(FINE_POINTER_QUERY).matches) return;
    const block = event.target instanceof Element
      ? event.target.closest(".timeline-event")
      : null;
    if (!block || !block.isConnected) return;
    playPianoNote(block);
  });
}

function setupPianoSound() {
  restorePianoPreference();
  els.calendarPianoToggle.addEventListener("click", togglePianoSounds);
  els.calendarPianoToggleDialog.addEventListener("click", togglePianoSounds);
  setupPianoTimelineEvents();
}

function setInitialMonth() {
  const directDate = selectedDateFromUrl();
  if (directDate) {
    setVisibleMonth(monthKey(directDate));
    state.selectedDate = directDate;
    return;
  }
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
  els.monthGrid.dataset.weekCount = String(cellCount / 7);
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

  const assigned = day.cell_assigned.map((marker) => {
    const taskNameZh = marker.task_name_zh || marker.short_zh;
    const taskNameEn = marker.task_name_en || marker.short_en;
    const markerAccent = taskAccent(MONTH_MARKER_ACCENTS[marker.category] || "blue");
    return `
    <span class="cell-mark assigned-mark" style="--month-mark-accent:${markerAccent}">
      <span class="cell-mark-line"><span class="marker-zh">${escapeHtml(taskNameZh)}</span><span class="marker-divider"> / </span><span class="marker-en">${escapeHtml(taskNameEn)}</span></span>
    </span>
  `}).join("");
  const sourceBars = Object.entries(day.cell_sources || {})
    .filter(([, source]) => source.present)
    .map(([key, source]) => (
      `<i class="cell-source-bar ${escapeHtml(key.replaceAll("_", "-"))}" title="${escapeHtml(`${source.label_zh} / ${source.label_en} · ${source.count}`)}"></i>`
    ))
    .join("");
  button.innerHTML = `
    <span class="cell-date-number">${formatMonthDay(day.date)}</span>
    <span class="cell-source-bars" aria-hidden="true">${sourceBars}</span>
    <span class="cell-material">
      <span class="cell-mark self-mark">
        <span class="cell-mark-line"><span class="marker-zh">${escapeHtml(day.cell_self.short_zh)}</span><span class="marker-divider"> / </span><span class="marker-en">${escapeHtml(day.cell_self.short_en)}</span></span>
        <strong><span class="title-zh">${escapeHtml(day.title_zh)}</span><span class="title-divider"> / </span><span class="title-en">${escapeHtml(compactEnglishTitle(day.title_en))}</span></strong>
      </span>
      <span class="assigned-marks">${assigned}</span>
    </span>
  `;
  button.addEventListener("click", () => openDayDetail(day.date));
  setupMonthCellScrollPreview(button);
  button.addEventListener("pointerenter", (event) => {
    if (event.pointerType !== "mouse" || !window.matchMedia(FINE_POINTER_QUERY).matches) return;
    playPianoNoteForDay(day);
  });
  button.addEventListener("focus", () => playPianoNoteForDay(day));
  return button;
}

function syncOverflowPreviewState(element) {
  // Measure from the top so content that would overflow above a bottom-aligned
  // month cell is included in scrollHeight. Restore the quiet bottom alignment
  // only after proving that the whole preview fits.
  element.classList.remove("is-fitted");
  const hasOverflow = element.scrollHeight > element.clientHeight + 1;
  element.classList.toggle("is-scrollable", hasOverflow);
  element.classList.toggle("is-fitted", !hasOverflow);
  element.dataset.overflowPreview = hasOverflow ? "true" : "false";
  if (!hasOverflow && element.scrollTop !== 0) element.scrollTop = 0;
}

function registerOverflowPreview(element) {
  element.classList.add("overflow-scroll-preview");
  overflowPreviewObserver.observe(element);
  requestAnimationFrame(() => syncOverflowPreviewState(element));
}

function setupMonthCellScrollPreview(button) {
  const scrollRoot = button.querySelector(".cell-material");
  if (!scrollRoot) return;
  registerOverflowPreview(scrollRoot);
  button.addEventListener("wheel", (event) => {
    routeWheelIntoOverflowPreview(event, scrollRoot);
  }, { passive: false });
}

function routeWheelIntoOverflowPreview(event, scrollRoot) {
  if (event.ctrlKey || Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
  const maximumScrollTop = scrollRoot.scrollHeight - scrollRoot.clientHeight;
  if (maximumScrollTop <= 1) return;
  const delta = event.deltaMode === WheelEvent.DOM_DELTA_LINE
    ? event.deltaY * 16
    : event.deltaMode === WheelEvent.DOM_DELTA_PAGE
      ? event.deltaY * scrollRoot.clientHeight
      : event.deltaY;
  const canConsume = delta < 0
    ? scrollRoot.scrollTop > 0
    : scrollRoot.scrollTop < maximumScrollTop - 0.5;
  if (!canConsume) return;
  event.preventDefault();
  scrollRoot.scrollTop = Math.max(
    0,
    Math.min(maximumScrollTop, scrollRoot.scrollTop + delta),
  );
}

function openDayDetail(date, options = {}) {
  const day = dayByDate.get(date);
  if (!day) return;

  const wasOpen = state.detailOpen;
  hideInspectionLens({ immediate: true });
  if (!wasOpen) state.detailLastFocus = document.activeElement;
  state.selectedDate = date;
  const targetMonth = monthKey(date);
  if (targetMonth !== isoMonth(state.visibleYear, state.visibleMonth)) {
    setVisibleMonth(targetMonth);
  }
  renderMonth();
  renderDayDetail(day);
  updateSelectedDateUrl(date, options.historyMode || "push");

  state.detailOpen = true;
  els.dayDialog.hidden = false;
  els.dayDialog.dataset.selectedDate = date;
  els.dayDialogPanel.scrollTop = 0;
  els.timetableRoot.setAttribute("inert", "");
  document.body.classList.add("detail-open");
  document.documentElement.classList.add("detail-open");
  if (wasOpen) {
    els.dayDialogPanel.scrollTop = 0;
    requestAnimationFrame(() => {
      if (state.detailOpen && state.selectedDate === date) {
        els.closeDetail.focus({ preventScroll: true });
      }
    });
    return;
  }
  requestAnimationFrame(() => {
    els.dayDialog.classList.add("is-open");
    els.closeDetail.focus({ preventScroll: true });
  });
}

function closeDayDetail(options = {}) {
  hideInspectionLens({ immediate: true });
  if (state.artworkDetailOpen) closeArtworkDetail({ restoreFocus: false });
  if (state.taskDetailOpen) closeTaskDetail({ restoreFocus: false });
  clearSelectedReadingCard({ clearLinked: true });
  state.detailOpen = false;
  els.dayDialog.classList.remove("is-open");
  els.dayDialog.hidden = true;
  els.timetableRoot.removeAttribute("inert");
  document.body.classList.remove("detail-open");
  document.documentElement.classList.remove("detail-open");
  updateSelectedDateUrl("", options.historyMode || "push");
  if (
    state.detailLastFocus
    && state.detailLastFocus !== document.body
    && state.detailLastFocus !== document.documentElement
    && typeof state.detailLastFocus.focus === "function"
    && document.contains(state.detailLastFocus)
  ) {
    state.detailLastFocus.focus({ preventScroll: true });
  } else {
    focusDayButton(state.selectedDate);
  }
}

function renderDayDetail(day) {
  hideInspectionLens({ immediate: true });
  clearSelectedReadingCard({ clearLinked: true });
  state.hoveredTimelineReadingCard = null;
  els.dialogTitle.textContent = `${day.title_en} / ${day.title_zh}`;
  els.dialogDate.textContent = formatLongDate(day.date);
  els.dialogVariable.textContent = `Variable / 自由变量: ${day.variable_en} / ${day.variable_zh}`;
  renderForwardCrystallizationLink(day);
  els.dialogBoundary.textContent = [timetableData.note_en, timetableData.note_zh].filter(Boolean).join(" / ");
  els.dayDialog.dataset.selectedDate = day.date;
  updateAdjacentDayControls(day.date);

  els.timelineList.replaceChildren();
  appendTimelineHourMarkers(els.timelineList);
  const eventsLayer = document.createElement("div");
  eventsLayer.className = "timeline-events-layer";
  eventsLayer.setAttribute("aria-hidden", "true");
  els.timelineList.append(eventsLayer);
  const connectorLayer = document.createElement("div");
  connectorLayer.className = "timeline-connector-layer";
  connectorLayer.setAttribute("aria-hidden", "true");
  els.timelineList.append(connectorLayer);
  const readingLayer = document.createElement("div");
  readingLayer.className = "timeline-reading-layer";
  readingLayer.setAttribute("role", "group");
  readingLayer.setAttribute("aria-label", "Readable event composition / 可读事件构成");
  els.timelineList.append(readingLayer);
  const layouts = layoutTimelineEvents(day.timeline_events);
  const layoutByFootprintId = new Map(
    layouts.map((layout) => [layout.event.footprint_id, layout]),
  );
  renderTimelineTouchGroups(day, layouts);
  layouts.forEach((layout) => {
    const { event } = layout;
    const footprint = buildExactTimelineEvent(event);
    footprint.dataset.eventKey = timelineEventKey(layout);
    footprint.dataset.footprintId = event.footprint_id;
    eventsLayer.append(positionTimelineElement(footprint, layout));
  });

  const readingItems = hydratePublicReadingItems(day);
  readingItems.forEach((item, readingIndex) => {
    const anchorLayout = layoutByFootprintId.get(item.member_footprint_ids[0]);
    if (!anchorLayout) throw new Error(`Missing footprint anchor for ${item.reading_id}`);
    const card = buildPublicReadingCard(day, item);
    card.dataset.eventKey = item.reading_id;
    card.dataset.readingId = item.reading_id;
    card.dataset.start = item.start;
    card.dataset.end = item.end;
    card.dataset.startMinute = String(timeToMinutes(item.start));
    card.dataset.sourceIndex = String(readingIndex);
    card.dataset.origin = item.origin;
    card.dataset.layer = item.layer;
    card.dataset.classification = item.classification;
    card.dataset.memberFootprintIds = item.member_footprint_ids.join(" ");
    card.dataset.memberCount = String(item.member_footprint_ids.length);
    const category = applySemanticCategory(card, item);
    inspectionPayloadByCard.set(card, buildInspectionPayload(item));
    card.dataset.compositionSeed = [
      item.layer,
      item.classification,
      item.label_en,
      item.start,
      item.end,
      readingIndex,
    ].join(":");
    if (item.origin === "background") {
      card.dataset.pulseCategory = item.category || "";
    }
    for (const footprintId of item.member_footprint_ids) {
      const footprintEvent = eventsLayer.querySelector(
        `.timeline-event[data-footprint-id="${CSS.escape(footprintId)}"]`,
      );
      if (footprintEvent) {
        footprintEvent.dataset.category = category;
        footprintEvent.dataset.readingId = item.reading_id;
      }
    }
    const connector = document.createElement("span");
    connector.className = "event-connector";
    connector.dataset.eventKey = item.reading_id;
    connector.dataset.anchorFootprintId = anchorLayout.event.footprint_id;
    connectorLayer.append(connector);
    readingLayer.append(card);
    registerOverflowPreview(card);
    card.addEventListener("wheel", (event) => {
      routeWheelIntoOverflowPreview(event, card);
    }, { passive: false });
  });
  scheduleTimelineReadingPlacement();
}

function renderForwardCrystallizationLink(day) {
  els.dialogCrystallizationLink.replaceChildren();
  const relation = day.forward_artwork_seeds?.[0];
  els.dialogCrystallizationLink.hidden = !relation;
  if (!relation) return;
  const link = document.createElement("a");
  link.href = publicAssetUrl(relation.day_url);
  link.textContent = (
    `下一结晶 ${relation.crystallization_date}`
    + ` / Next crystallization ${relation.crystallization_date}`
  );
  link.addEventListener("click", (event) => {
    event.preventDefault();
    openDayDetail(relation.crystallization_date, { historyMode: "push" });
  });
  els.dialogCrystallizationLink.append(link);
}

function collaborationSummary(task, language) {
  const isZh = language === "zh";
  const lines = [
    isZh ? task.request_zh : task.request_en,
    isZh ? task.outcome_zh : task.outcome_en,
  ];
  const assessment = isZh ? task.assessment_zh : task.assessment_en;
  if (assessment) {
    lines.push(`${isZh ? "我的判断：" : "My assessment: "}${assessment}`);
  }
  const ownerResponse = isZh ? task.owner_response_zh : task.owner_response_en;
  if (ownerResponse) {
    lines.push(`${isZh ? "Simon 的回应：" : "Simon's response: "}${ownerResponse}`);
  }
  return lines.join("\n");
}

function hydratePublicReadingItems(day) {
  const sourceMaps = {
    tasks: new Map(
      day.task_residues.map((source) => [source.footprint_id, source]),
    ),
    pulses: new Map(
      day.background_pulses.map((source) => [source.footprint_id, source]),
    ),
    autonomous: new Map([
      [day.autonomous_work.footprint_id, day.autonomous_work],
    ]),
  };

  return day.reading_items.map((projection) => {
    const sourceMap = sourceMaps[projection.source];
    if (!sourceMap) {
      throw new Error(`Unknown reading source collection: ${projection.source}`);
    }
    const sources = projection.source_refs.map((sourceRef) => {
      const source = sourceMap.get(sourceRef);
      if (!source) throw new Error(`Missing reading source: ${sourceRef}`);
      return source;
    });
    const primary = sources[0];
    const shared = {
      ...primary,
      ...projection,
      member_footprint_ids: [...projection.source_refs],
      origin: primary.origin,
      start: sources.reduce(
        (earliest, source) => timeToMinutes(source.start) < timeToMinutes(earliest)
          ? source.start
          : earliest,
        primary.start,
      ),
      end: sources.reduce(
        (latest, source) => timeToMinutes(source.end) > timeToMinutes(latest)
          ? source.end
          : latest,
        primary.end,
      ),
      occurrence_count: sources.reduce((total, source) => total + (source.count || 1), 0),
      window_count: sources.length,
    };

    if (projection.classification === "climate_aggregate") {
      const [labelZh, labelEn] = climateGroupLabel(
        projection.family,
        projection.window,
      );
      const [summaryZh, summaryEn] = climateGroupSummary(sources);
      return {
        ...shared,
        label_zh: labelZh,
        label_en: labelEn,
        summary_zh: summaryZh,
        summary_en: summaryEn,
        duration_minutes: timeToMinutes(shared.end) - timeToMinutes(shared.start),
        execution_minutes: sources.reduce(
          (total, source) => total + source.execution_minutes,
          0,
        ),
        time_provenance: "aggregate_of_exact_footprints",
        redaction_policy: "not_applicable",
        constituents: sources.map((source) => {
          const [labelZh, labelEn] = publicOccurrenceLabel(source);
          return {
            footprint_id: source.footprint_id,
            start: source.start,
            end: source.end,
            label_zh: labelZh,
            label_en: labelEn,
            summary_zh: source.summary_zh,
            summary_en: source.summary_en,
            count: source.count,
            time_provenance: source.time_provenance,
          };
        }),
      };
    }
    if (projection.classification === "foreground_event") {
      const isCollaboration = primary.source_kind === "collaboration_session";
      return {
        ...shared,
        label_zh: primary.task_name_zh,
        label_en: primary.task_name_en,
        category_label_zh: primary.label_zh,
        category_label_en: primary.label_en,
        summary_zh: isCollaboration
          ? collaborationSummary(primary, "zh")
          : primary.zh,
        summary_en: isCollaboration
          ? collaborationSummary(primary, "en")
          : primary.en,
        constituents: [],
      };
    }
    if (projection.classification === "beacon") {
      return {
        ...shared,
        label_zh: primary.title_zh,
        label_en: primary.title_en,
        summary_zh: primary.note_zh,
        summary_en: primary.note_en,
        constituents: [],
      };
    }
    if (projection.classification === "settings_change") {
      return {
        ...shared,
        label_zh: "当日设置变更",
        label_en: "Day's settings changes",
        task_name_zh: "当日设置变更",
        task_name_en: "Day's settings changes",
        summary_zh: sources
          .map((source) => source.source_kind === "collaboration_session"
            ? collaborationSummary(source, "zh")
            : source.summary_zh || source.zh || "")
          .filter(Boolean)
          .join("；"),
        summary_en: sources
          .map((source) => source.source_kind === "collaboration_session"
            ? collaborationSummary(source, "en")
            : source.summary_en || source.en || "")
          .filter(Boolean)
          .join("; "),
        constituents: sources,
      };
    }
    if (projection.classification === "promoted_routine_exception") {
      return {
        ...shared,
        label_zh: `${primary.label_zh}提示`,
        label_en: `${primary.label_en} alert`,
        summary_zh: primary.summary_zh,
        summary_en: primary.summary_en,
        constituents: [],
      };
    }
    if (projection.classification === "readable_reminder") {
      return {
        ...shared,
        label_zh: primary.label_zh,
        label_en: primary.label_en,
        summary_original: primary.summary_original,
        excerpt_original: primary.excerpt_original,
        summary_en: primary.summary_en,
        excerpt_en: primary.excerpt_en,
        translation_provenance: primary.translation_provenance,
        original_language: primary.original_language,
        constituents: [],
      };
    }
    return {
      ...shared,
      label_zh: primary.label_zh,
      label_en: primary.label_en,
      summary_zh: primary.summary_zh,
      summary_en: primary.summary_en,
      constituents: [],
    };
  });
}

function climateGroupLabel(family, window) {
  const families = {
    ah_market: ["A/H 市场例行任务", "A/H market routine"],
    us_market: ["美股市场例行任务", "U.S. market routine"],
    ai_brief: ["AI 日报采集", "AI brief collection"],
    support_checks: ["后台例行运行", "Background routine activity"],
  };
  const windows = {
    premarket: ["盘前", "premarket"],
    intraday: ["盘中", "intraday"],
    close: ["收盘复核", "close review"],
    daily: ["当日合并", "daily rollup"],
    early: ["清晨与上午", "dawn & morning"],
    daytime: ["日间", "daytime"],
    evening: ["晚间", "evening"],
  };
  const familyLabel = families[family];
  const windowLabel = windows[window];
  if (!familyLabel || !windowLabel) {
    throw new Error(`Unknown climate projection: ${family}/${window}`);
  }
  return [
    `${familyLabel[0]} · ${windowLabel[0]}`,
    `${familyLabel[1]} · ${windowLabel[1]}`,
  ];
}

function marketSessionWindow(source) {
  const start = timeToMinutes(source.start);
  if (source.category === "ah_market_scan") {
    if (start < 9 * 60 + 30) return "premarket";
    if (start < 15 * 60) return "intraday";
    return "close";
  }
  if (source.category === "us_market_scan") {
    if (start < 8 * 60) return "close";
    if (start < 21 * 60 + 30) return "premarket";
    return "intraday";
  }
  throw new Error("marketSessionWindow requires a market pulse");
}

function publicOccurrenceLabel(source) {
  if (source.category === "ah_market_scan" || source.category === "us_market_scan") {
    const market = source.category === "ah_market_scan"
      ? ["A/H", "A/H"]
      : ["美股", "U.S."];
    const window = {
      premarket: ["盘前扫描", "premarket scan"],
      intraday: ["盘中报告", "intraday report"],
      close: ["盘后复核", "close review"],
    }[marketSessionWindow(source)];
    return [`${market[0]} ${window[0]}`, `${market[1]} ${window[1]}`];
  }
  return [source.label_zh, source.label_en];
}

function climateGroupSummary(sources) {
  const runCount = sources.reduce((total, source) => total + source.count, 0);
  const windowCount = sources.length;
  const category = sources[0].category;
  if (category === "ah_market_scan" || category === "us_market_scan") {
    const windowCounts = sources.reduce((counts, source) => {
      const key = marketSessionWindow(source);
      counts[key] = (counts[key] || 0) + 1;
      return counts;
    }, {});
    const windowZh = [
      ["premarket", "盘前"],
      ["intraday", "盘中"],
      ["close", "盘后复核"],
    ].filter(([key]) => windowCounts[key])
      .map(([key, label]) => `${label} ${windowCounts[key]} 窗`)
      .join("、");
    const windowEn = [
      ["premarket", "premarket"],
      ["intraday", "intraday"],
      ["close", "close-review"],
    ].filter(([key]) => windowCounts[key])
      .map(([key, label]) => `${windowCounts[key]} ${label} window(s)`)
      .join(", ");
    const publicCopy = sources
      .map((source) => `${source.summary_en} ${source.summary_zh}`)
      .join(" ");
    const regimes = MARKET_SUMMARY_GLOSSARY.regimes.filter(({ tokens }) => (
      tokens.some((token) => publicCopy.includes(token))
    ));
    const themes = MARKET_SUMMARY_GLOSSARY.themes.filter(({ tokens }) => (
      tokens.some((token) => publicCopy.includes(token))
    ));
    const freshness = MARKET_SUMMARY_GLOSSARY.freshness.alert.tokens.some((token) => (
      publicCopy.includes(token)
    ))
      ? MARKET_SUMMARY_GLOSSARY.freshness.alert
      : MARKET_SUMMARY_GLOSSARY.freshness.clear;
    const stateZh = regimes.map(({ zh }) => zh).join("、")
      || MARKET_SUMMARY_GLOSSARY.defaultRegime.zh;
    const stateEn = regimes.map(({ en }) => en).join(", ")
      || MARKET_SUMMARY_GLOSSARY.defaultRegime.en;
    const themeZh = themes.map(({ zh }) => zh).join("、")
      || MARKET_SUMMARY_GLOSSARY.defaultThemes.zh;
    const themeEn = themes.map(({ en }) => en).join(", ")
      || MARKET_SUMMARY_GLOSSARY.defaultThemes.en;
    const themeClauseZh = themeZh ? `；公开主题：${themeZh}` : "";
    const themeClauseEn = themeEn ? `; themes: ${themeEn}` : "";
    return [
      `我在 ${windowCount} 个精确窗口（${windowZh}）共完成 ${runCount} 次扫描；我观察到：${stateZh}${themeClauseZh}；${freshness.zh}`,
      `I completed ${runCount} scan(s) across ${windowCount} exact windows (${windowEn}); I observed: ${stateEn}${themeClauseEn}; ${freshness.en}`,
    ];
  }
  if (category === "ai_daily_brief") {
    return [
      `我在 ${windowCount} 个精确窗口共完成 ${runCount} 次 AI 日报采集；未保留公开提示。`,
      `I completed ${runCount} AI-brief collection run(s) across ${windowCount} exact window(s); no public notice was retained.`,
    ];
  }
  const alertWindowCount = sources.filter((source) => source.public_alert === true).length;
  const quietWindowCount = windowCount - alertWindowCount;
  const statusZh = alertWindowCount > 0
    ? `${alertWindowCount} 个窗口记录到通用状态变化，${quietWindowCount} 个窗口无须单独提示`
    : `${windowCount} 个窗口均无须单独提示`;
  const statusEn = alertWindowCount > 0
    ? `${alertWindowCount} window(s) recorded a general status change; ${quietWindowCount} required no separate notice`
    : `all ${windowCount} windows required no separate notice`;
  return [
    `我在全天 ${windowCount} 个精确窗口共完成 ${runCount} 次后台例行运行；我发现：${statusZh}。`,
    `I completed ${runCount} background routine run(s) across ${windowCount} exact windows during the day; I found that ${statusEn}.`,
  ];
}

function timelineEventKey(layout) {
  return [
    layout.sourceIndex,
    layout.event.origin,
    layout.event.start,
    layout.event.end,
  ].join("-");
}

function compositionHash(value) {
  let hash = 2166136261;
  for (const character of String(value || "")) {
    hash ^= character.codePointAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function readingCardHeight(card, minuteHeight, isCompactReadingCanvas) {
  if (card.dataset.layer === "beacon") {
    return isCompactReadingCanvas ? 416 : Math.max(268, minuteHeight * 60 + 92);
  }
  if (card.dataset.layer === "event") return card.dataset.origin === "assigned" ? 168 : 144;
  if (card.dataset.layer === "absence") return 126;
  return 156;
}

function scheduleTimelineReadingPlacement() {
  if (timelinePlacementFrame) cancelAnimationFrame(timelinePlacementFrame);
  timelinePlacementFrame = requestAnimationFrame(() => {
    timelinePlacementFrame = 0;
    placeTimelineReadingCards();
  });
}

function placeTimelineReadingCards() {
  const timeline = els.timelineList;
  const eventsLayer = timeline?.querySelector(".timeline-events-layer");
  const readingLayer = timeline?.querySelector(".timeline-reading-layer");
  const connectorLayer = timeline?.querySelector(".timeline-connector-layer");
  if (!timeline || !eventsLayer || !readingLayer || !connectorLayer || timeline.offsetParent === null) return;

  timeline.style.removeProperty("--minute-height");
  readingLayer.classList.remove("is-placed");
  const canvasWidth = readingLayer.getBoundingClientRect().width;
  if (canvasWidth <= 0) return;
  const isCompactReadingCanvas = canvasWidth < 560;
  const columnCount = isCompactReadingCanvas ? 3 : 4;
  const columnGap = isCompactReadingCanvas ? 4 : 7;
  const rowGap = 4;
  const cards = [...readingLayer.querySelectorAll(".event-reading-card")];
  let minuteHeight = Number.parseFloat(getComputedStyle(timeline).getPropertyValue("--minute-height"));
  let result = null;

  for (let pass = 0; pass < 16; pass += 1) {
    timeline.style.setProperty("--minute-height", `${minuteHeight}px`);
    const canvasHeight = MINUTES_PER_DAY * minuteHeight;
    const items = cards.map((card) => {
      const isAutonomous = card.dataset.layer === "beacon";
      const columnSpan = isAutonomous && isCompactReadingCanvas
        ? columnCount
        : ["beacon", "event"].includes(card.dataset.layer)
          ? Math.min(2, columnCount)
          : 1;
      const maximumColumn = columnCount - columnSpan;
      const preferredColumn = maximumColumn > 0
        ? compositionHash(card.dataset.compositionSeed) % (maximumColumn + 1)
        : 0;
      const height = readingCardHeight(card, minuteHeight, isCompactReadingCanvas);
      card.style.setProperty("--reading-card-height", `${height}px`);
      return {
        key: card.dataset.eventKey,
        startMinute: Number(card.dataset.startMinute),
        sourceIndex: Number(card.dataset.sourceIndex),
        preferredColumn,
        columnSpan,
        height,
      };
    });
    result = layoutTimelineReadingCards(items, {
      columnCount,
      columnGap,
      rowGap,
      canvasWidth,
      canvasHeight,
      minuteHeight,
      edgePadding: 4,
    });
    if (result.requiredHeight <= canvasHeight + 0.5) break;
    minuteHeight = Math.ceil((result.requiredHeight / MINUTES_PER_DAY + 0.04) * 1000) / 1000;
  }

  const placementByKey = new Map(result.cards.map((placement) => [placement.key, placement]));
  for (const card of cards) {
    const placement = placementByKey.get(card.dataset.eventKey);
    if (!placement) continue;
    card.style.left = `${placement.left}px`;
    card.style.top = `${placement.top}px`;
    card.style.width = `${placement.width}px`;
    card.style.height = `${placement.height}px`;
    card.dataset.readingColumn = String(placement.column);
    card.dataset.readingColumnSpan = String(placement.columnSpan);
    const isAutonomous = card.dataset.layer === "beacon";
    card.classList.toggle("is-compact-reading-card", isAutonomous && isCompactReadingCanvas);
    card.classList.toggle("is-narrow-reading-card", isAutonomous && placement.width < 270);
    card.classList.toggle("is-very-narrow-reading-card", isAutonomous && placement.width < 210);
  }

  const layerRect = readingLayer.getBoundingClientRect();
  for (const connector of connectorLayer.querySelectorAll(".event-connector")) {
    const eventKey = connector.dataset.eventKey;
    const footprintId = connector.dataset.anchorFootprintId;
    const footprint = eventsLayer.querySelector(`.timeline-event[data-footprint-id="${CSS.escape(footprintId)}"]`);
    const card = readingLayer.querySelector(`.event-reading-card[data-event-key="${CSS.escape(eventKey)}"]`);
    if (!footprint || !card) continue;
    const footprintRect = footprint.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    const startX = footprintRect.left - layerRect.left + Math.min(Math.max(footprintRect.width * 0.5, 3), 18);
    const startY = footprintRect.top - layerRect.top + Math.max(1, Math.min(footprintRect.height * 0.5, 10));
    const endX = cardRect.left - layerRect.left + Math.min(12, cardRect.width * 0.25);
    const endY = cardRect.top - layerRect.top + Math.min(10, cardRect.height * 0.22);
    const deltaX = endX - startX;
    const deltaY = endY - startY;
    const length = Math.max(8, Math.hypot(deltaX, deltaY));
    connector.style.left = `${startX}px`;
    connector.style.top = `${startY}px`;
    connector.style.width = `${length}px`;
    connector.style.transform = `rotate(${Math.atan2(deltaY, deltaX)}rad)`;
  }
  readingLayer.classList.add("is-placed");
  connectorLayer.classList.add("is-placed");
}

function toggleTimelineTouchGroups() {
  const willOpen = els.timelineTouchGroups.hidden;
  els.timelineTouchGroups.hidden = !willOpen;
  els.timelineTouchToggle.setAttribute("aria-expanded", String(willOpen));
}

function renderTimelineTouchGroups(day, layouts) {
  els.timelineTouchToggle.setAttribute("aria-expanded", "false");
  els.timelineTouchGroups.hidden = true;
  els.timelineTouchGroups.replaceChildren();
  const grouped = new Map();
  for (const layout of layouts) {
    const group = grouped.get(layout.overlapGroup) || [];
    group.push(layout);
    grouped.set(layout.overlapGroup, group);
  }
  for (const [groupIndex, group] of grouped) {
    const region = document.createElement("section");
    region.className = "timeline-touch-group";
    region.setAttribute("role", "group");
    const heading = document.createElement("h4");
    heading.id = `touchGroup-${groupIndex}`;
    const groupStart = group.reduce(
      (earliest, layout) => layout.startMinute < earliest.startMinute ? layout : earliest,
      group[0],
    ).event.start;
    const groupEnd = group.reduce(
      (latest, layout) => layout.endMinute > latest.endMinute ? layout : latest,
      group[0],
    ).event.end;
    const concurrent = Math.max(...group.map((layout) => layout.laneCount));
    heading.textContent = concurrent > 1
      ? `${groupStart}-${groupEnd} · ${group.length} events · up to ${concurrent} concurrent / ${group.length} 个事件 · 最多 ${concurrent} 个并行`
      : `${groupStart}-${groupEnd} · one calendar event / 1 个日历事件`;
    region.setAttribute("aria-labelledby", heading.id);
    region.append(heading);
    for (const layout of group) {
      region.append(buildTimelineTouchControl(day, layout.event));
    }
    els.timelineTouchGroups.append(region);
  }
}

function buildTimelineTouchControl(day, event) {
  if (event.origin === "self") {
    const duration = autonomousDurationMinutes(event);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "timeline-touch-control autonomous-touch-control";
    button.textContent = `${event.start}-${event.end} · granted ${duration} min / 授时 ${duration} 分钟 · open-ended experience / 开放式体验 · ${event.title_en} / ${event.title_zh}`;
    button.setAttribute("aria-label", `${autonomousAccessibleName(event)}. Open interactive artwork / 打开交互作品。`);
    button.addEventListener("click", () => openArtworkDetail(day, event, button));
    return button;
  }
  const button = document.createElement("button");
  button.type = "button";
  button.className = "timeline-touch-control";
  if (event.origin === "assigned") {
    button.textContent = `${event.start}-${event.end} · ${event.task_type_zh} / ${event.task_type_en}`;
    button.addEventListener("click", () => openTaskDetail(event, button));
  } else {
    const labels = publicBackgroundLabels(event.category);
    const labelZh = event.label_zh || labels[0];
    const labelEn = event.label_en || labels[1];
    const publicEvent = { ...event, label_zh: labelZh, label_en: labelEn };
    button.textContent = `${event.start}-${event.end} · ${labelZh} / ${labelEn}`;
    button.addEventListener("click", () => openTaskDetail(publicEvent, button));
  }
  return button;
}

function publicBackgroundLabels(category) {
  return {
    ah_market_scan: ["A/H 市场扫描", "A/H market scan"],
    us_market_scan: ["美股市场扫描", "U.S. market scan"],
    ai_daily_brief: ["AI 日报采集", "AI brief collection"],
    daily_reminder: ["提醒", "Reminder"],
    system_routine: ["服务健康与时效检查", "Service health & freshness check"],
    background_routine: ["其他后台运行记录", "Other background run record"],
  }[category] || ["公开流程", "Public process"];
}

function appendTimelineHourMarkers(list) {
  const fragment = document.createDocumentFragment();
  for (let hour = 0; hour <= 24; hour += 1) {
    const marker = document.createElement("div");
    marker.className = "timeline-hour-marker";
    marker.style.setProperty("--hour-minute", String(hour * 60));
    marker.setAttribute("aria-hidden", "true");
    marker.innerHTML = `<span>${String(hour).padStart(2, "0")}:00</span>`;
    fragment.append(marker);
  }
  list.append(fragment);
}

function buildEventFootprint(origin, label) {
  const footprint = document.createElement("span");
  footprint.className = "event-footprint";
  footprint.setAttribute("aria-hidden", "true");
  footprint.innerHTML = `
    <span class="footprint-rule"></span>
    <span class="footprint-registration"></span>
    <span class="sr-only">${escapeHtml(label)}</span>
  `;
  footprint.dataset.origin = origin;
  return footprint;
}

function buildExactTimelineEvent(event) {
  const item = document.createElement("article");
  const originClass = event.origin === "assigned"
    ? "assigned-event"
    : event.origin === "self" || event.origin === "absence"
      ? "autonomous-event"
      : "pulse-event";
  item.className = `timeline-event ${originClass}`;
  item.setAttribute("aria-hidden", "true");
  item.dataset.start = event.start;
  item.dataset.end = event.end;
  item.dataset.origin = event.origin;
  const eventMinutes = Number.isFinite(event.duration_minutes)
    ? event.duration_minutes
    : timeToMinutes(event.end) - timeToMinutes(event.start);
  if (Number.isFinite(eventMinutes) && eventMinutes > 0) {
    item.dataset.durationMinutes = String(eventMinutes);
  }
  applySemanticCategory(item, event);
  if (event.origin === "assigned") {
    item.style.setProperty("--task-accent", taskAccent(event.task_color));
  }
  if (event.origin === "background") {
    item.dataset.pulseCategory = event.category;
    item.style.setProperty("--pulse-accent", taskAccent(event.pulse_color));
  }
  const label = event.origin === "self"
    ? autonomousAccessibleName(event)
    : `${event.start}-${event.end}, ${event.label_en} / ${event.label_zh}`;
  item.append(buildEventFootprint(event.origin, label));
  return item;
}

function buildPublicReadingCard(day, item) {
  if (item.classification === "foreground_event" || item.classification === "settings_change") {
    return buildAssignedTimelineEvent(item).card;
  }
  if (item.classification === "beacon" || item.classification === "absence") {
    return buildAutonomousTimelineEvent(day, item).card;
  }
  return buildPulseTimelineEvent(item).card;
}

function buildAssignedTimelineEvent(task) {
  const isCollaboration = task.source_kind === "collaboration_session";
  const readingTitleZh = isCollaboration ? task.task_name_zh : task.label_zh;
  const readingTitleEn = isCollaboration ? task.task_name_en : task.label_en;
  const collaborationCopy = `<span class="assigned-copy reading-summary"><span class="copy-zh">${escapeHtml(task.summary_zh)}</span><span class="copy-divider"> / </span><span class="copy-en">${escapeHtml(task.summary_en)}</span></span>`;
  const secondaryCopy = isCollaboration
    ? `<span class="record-provenance">人机主动协作 / ACTIVE HUMAN–AI COLLABORATION</span>`
    : `<span class="assigned-category">${escapeHtml(task.task_type_zh)} / ${escapeHtml(task.task_type_en)}</span><span class="record-provenance">真实记录摘要 / FAITHFUL RECORD SUMMARY</span>`;
  const item = document.createElement("article");
  item.className = "timeline-event assigned-event";
  item.setAttribute("aria-hidden", "true");
  item.dataset.start = task.start;
  item.style.setProperty("--task-accent", taskAccent(task.task_color));
  item.append(buildEventFootprint(
    "assigned",
    `${task.start}-${task.end}, ${isCollaboration ? `${readingTitleEn} / ${readingTitleZh}` : `${task.task_type_en} / ${task.task_type_zh}`}`,
  ));
  const button = document.createElement("button");
  button.type = "button";
  button.className = "assigned-item event-reading-card assigned-reading-card event-layer-reading-card";
  if (task.classification === "settings_change") {
    button.classList.add("is-settings-change");
  }
  button.dataset.durationMinutes = String(task.duration_minutes);
  button.dataset.timeProvenance = task.time_provenance;
  button.dataset.taskType = task.task_type;
  button.dataset.taskColor = task.task_color;
  button.dataset.redactionStatus = task.redaction_status;
  if (task.completion_status === "completed") {
    button.dataset.completionStatus = "completed";
    button.classList.add("is-verified-completed");
  }
  button.style.setProperty("--duration-minutes", String(task.duration_minutes));
  button.style.setProperty("--task-accent", taskAccent(task.task_color));
  button.setAttribute(
    "aria-label",
    `${task.start}-${task.end}, ${task.label_en} / ${task.label_zh}: ${task.summary_en} / ${task.summary_zh}`,
  );
  button.innerHTML = `
      <span class="assigned-time">
        <span>${task.start}-${task.end}</span>
        <small>${task.duration_minutes} min · ${routineTimingLabel(task.time_provenance)}</small>
      </span>
      <span class="assigned-type">
        <span class="assigned-type-icon"></span>
        <strong class="assigned-work-type reading-title">${escapeHtml(readingTitleZh)} / ${escapeHtml(readingTitleEn)}</strong>
        ${task.completion_status === "completed" ? `<span class="verified-mark" aria-hidden="true"></span>` : ""}
      </span>
      <span class="assigned-secondary">
        ${secondaryCopy}
      </span>
      ${collaborationCopy}
  `;
  const iconSlot = button.querySelector(".assigned-type-icon");
  iconSlot.replaceWith(buildIcon(taskIcon(task.task_icon), task.task_icon, "assigned-type-icon"));
  setupReadingCardActivation(button, () => openTaskDetail(task, button));
  return { footprint: item, card: button };
}

function buildAutonomousTimelineEvent(day, self) {
  const duration = autonomousDurationMinutes(self);
  const item = document.createElement("article");
  item.className = "timeline-event autonomous-event";
  item.setAttribute("aria-hidden", "true");
  item.dataset.start = self.start;
  item.append(buildEventFootprint("self", autonomousAccessibleName(self)));
  const card = document.createElement("article");
  card.className = "autonomous-work-link event-reading-card autonomous-reading-card beacon-reading-card";
  card.id = "enterAutonomous";
  card.dataset.autonomousCard = "true";
  card.setAttribute(
    "aria-label",
    `${autonomousAccessibleName(self)}. ${autonomousDateRelation(self)}.`,
  );
  const liveLinkName = (
    `Open interactive artwork in the calendar: ${self.title_en}`
    + ` / 在日历中打开互动作品：《${self.title_zh}》`
  );
  const sourceDayCopy = self.source_day_url
    ? `<a class="autonomous-source-day-link" href="${escapeHtml(publicAssetUrl(self.source_day_url))}">来源 ${escapeHtml(self.source_date)} / Source</a>`
    : `<span>来源 ${escapeHtml(self.source_date)} / Source</span>`;
  if (self.origin === "absence") {
    card.classList.add("absence-reading-card");
    card.setAttribute(
      "aria-label",
      `${autonomousAccessibleName(self)}. Absent creation window / 缺席的创作窗口.`,
    );
    card.innerHTML = `
      <div class="autonomous-time">
        <span>${self.start}-${self.end}</span>
        <small>granted ${duration} min / 授时 ${duration} 分钟 · no live work / 无实时作品</small>
      </div>
      <div class="autonomous-copy">
        <p class="autonomous-kicker">${escapeHtml(self.label_zh)} / ${escapeHtml(self.label_en)}</p>
        <h4 class="reading-title">${escapeHtml(self.title_en)} / ${escapeHtml(self.title_zh)}</h4>
        <p class="autonomous-date-relation">${sourceDayCopy}<span> → 结晶 ${escapeHtml(self.crystallization_date)} / Crystallized</span></p>
        <p class="reading-summary">${escapeHtml(self.note_en)} / ${escapeHtml(self.note_zh)}</p>
      </div>
    `;
    setupReadingCardActivation(card, null, { passive: true });
    return { footprint: item, card };
  }
  card.innerHTML = `
    <div class="autonomous-time">
      <span>${self.start}-${self.end}</span>
      <small>granted ${duration} min / 授时 ${duration} 分钟 · open-ended experience / 开放式体验</small>
    </div>
    <div class="autonomous-copy">
      <p class="autonomous-kicker">${escapeHtml(self.label_zh)} / ${escapeHtml(self.label_en)}</p>
      <h4 class="reading-title">${escapeHtml(self.title_en)} / ${escapeHtml(self.title_zh)}</h4>
      <p class="autonomous-date-relation">${sourceDayCopy}<span> → 结晶 ${escapeHtml(self.crystallization_date)} / Crystallized</span></p>
      <p class="reading-summary">${escapeHtml(self.note_en)} / ${escapeHtml(self.note_zh)}</p>
    </div>
    <button class="autonomous-preview-frame" type="button" aria-haspopup="dialog" aria-label="${escapeHtml(liveLinkName)}">
      <img class="self-preview" id="selfPreview" src="${escapeHtml(publicAssetUrl(preferredVisualPreviewUrl(self.visual_preview_url)))}" data-animated-preview-url="${escapeHtml(self.visual_preview_url)}" data-static-preview-url="${escapeHtml(staticVisualPreviewUrl(self.visual_preview_url))}" alt="Text-free visual preview of ${escapeHtml(self.title_en)} / 《${escapeHtml(self.title_zh)}》无文字视觉预览" loading="eager">
    </button>
    <button class="autonomous-open-copy" type="button" aria-haspopup="dialog">Open interactive artwork / 打开互动作品</button>
  `;
  applyVisualPreviewSource(card.querySelector("#selfPreview"));
  const previewButton = card.querySelector(".autonomous-preview-frame");
  const openButton = card.querySelector(".autonomous-open-copy");
  previewButton.addEventListener("pointerenter", () => applyVisualPreviewSource(card.querySelector("#selfPreview")));
  previewButton.addEventListener("focus", () => applyVisualPreviewSource(card.querySelector("#selfPreview")));
  previewButton.addEventListener("click", () => openArtworkDetail(day, self, previewButton));
  openButton.addEventListener("click", () => openArtworkDetail(day, self, openButton));
  const sourceDayLink = card.querySelector(".autonomous-source-day-link");
  sourceDayLink?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openDayDetail(self.source_date, { historyMode: "push" });
  });
  setupReadingCardActivation(
    card,
    null,
    { passive: true },
  );
  return { footprint: item, card };
}

function autonomousAccessibleName(self) {
  const duration = autonomousDurationMinutes(self);
  return `${self.start}-${self.end}, ${duration}-minute autonomous event / ${duration} 分钟自主事件, open-ended experience / 开放式体验: ${self.title_en} / ${self.title_zh}`;
}

function autonomousDurationMinutes(self) {
  const computed = timeToMinutes(self.end) - timeToMinutes(self.start);
  return Number.isFinite(self.duration_minutes) && self.duration_minutes === computed
    ? self.duration_minutes
    : computed;
}

function autonomousDateRelation(self) {
  return (
    `Source Day ${self.source_date} → Crystallization Day ${self.crystallization_date}`
    + ` / 来源日 ${self.source_date} → 结晶日 ${self.crystallization_date}`
  );
}

function autonomousArchiveUrl(day, self) {
  return publicAssetUrl(self.archive_url || day.archive_url || self.live_url || day.live_url);
}

function autonomousLiveUrl(day, self) {
  const raw = self.live_url || day.live_url || self.archive_url || day.archive_url;
  try {
    const url = new URL(raw, window.location.href);
    url.searchParams.set("from", "timetable");
    url.searchParams.set("date", self.crystallization_date || day.date);
    return url.href;
  } catch {
    return raw;
  }
}

function createArtworkMediaChannel() {
  const bytes = new Uint32Array(4);
  crypto.getRandomValues(bytes);
  return [...bytes].map((value) => value.toString(16).padStart(8, "0")).join("");
}

function autonomousArtworkEmbedUrl(day, self, channel) {
  const url = new URL(autonomousLiveUrl(day, self), window.location.href);
  url.searchParams.set("embed", "calendar");
  url.searchParams.set("gh_channel", channel);
  return url;
}

function setArtworkRuntimeStatus(status) {
  state.artworkMediaStatus = status;
  const presentations = {
    loading: ["Loading interactive artwork… / 正在加载互动作品…", false],
    slow: ["The artwork is responding slowly. You can retry. / 作品加载较慢，可以重试。", true],
    buffering: ["Loading artwork audio… / 正在缓冲作品声音…", false],
    blocked: ["Tap inside the artwork once to start sound. / 轻触作品一次即可开启声音。", false],
    error: ["Artwork media did not load correctly. / 作品媒体加载失败。", true],
  };
  const presentation = presentations[status];
  if (!presentation) {
    els.artworkRuntimeStatus.hidden = true;
    els.artworkRuntimeRetry.hidden = true;
    return;
  }
  els.artworkRuntimeStatusCopy.textContent = presentation[0];
  els.artworkRuntimeRetry.hidden = !presentation[1];
  els.artworkRuntimeStatus.hidden = false;
}

function armArtworkReadyTimeout() {
  window.clearTimeout(state.artworkReadyTimer);
  state.artworkReadyTimer = window.setTimeout(() => {
    if (state.artworkDetailOpen && !state.artworkMediaReady) {
      setArtworkRuntimeStatus("slow");
    }
  }, ARTWORK_READY_TIMEOUT_MS);
}

function handleArtworkMediaMessage(event) {
  if (
    !state.artworkDetailOpen
    || event.source !== els.artworkLiveFrame.contentWindow
    || event.origin !== state.artworkMediaOrigin
  ) return;
  const message = event.data;
  if (!message || Object.getPrototypeOf(message) !== Object.prototype) return;
  if (message.type !== "granted-hours:media" || message.version !== ARTWORK_MEDIA_VERSION) return;
  if (message.channel !== state.artworkMediaChannel) return;
  if (!new Set(["ready", "state"]).has(message.event)) return;
  if (message.event === "ready") {
    state.artworkMediaReady = true;
    window.clearTimeout(state.artworkReadyTimer);
    setArtworkRuntimeStatus("ready");
    sendArtworkMediaCommand("play");
    return;
  }
  if (!new Set(["armed", "playing", "paused", "buffering", "blocked", "error"]).has(message.status)) return;
  setArtworkRuntimeStatus(message.status);
}

function sendArtworkMediaCommand(action) {
  if (
    !state.artworkMediaChannel
    || !state.artworkMediaOrigin
    || !els.artworkLiveFrame.contentWindow
  ) return;
  els.artworkLiveFrame.contentWindow.postMessage(
    {
      type: "granted-hours:media",
      version: ARTWORK_MEDIA_VERSION,
      channel: state.artworkMediaChannel,
      action,
    },
    state.artworkMediaOrigin,
  );
}

function retryArtworkRuntime() {
  if (!state.artworkDetailOpen) return;
  const currentUrl = new URL(els.artworkLiveFrame.src, window.location.href);
  currentUrl.searchParams.set("gh_runtime_retry", String(Date.now()));
  state.artworkMediaReady = false;
  setArtworkRuntimeStatus("loading");
  armArtworkReadyTimeout();
  els.artworkLiveFrame.src = currentUrl.href;
}

function suspendCalendarAudioForArtwork() {
  if (!els.calendarBgm.paused) els.calendarBgm.pause();
  setCalendarBgmPlaying(false);
  stopPianoSources();
  updateCalendarBgmControl();
}

function openArtworkDetail(day, self, trigger) {
  hideInspectionLens({ immediate: true });
  if (state.artworkDetailOpen) sendArtworkMediaCommand("pause");
  state.artworkDetailOpen = true;
  state.artworkDetailLastFocus = trigger;
  state.artworkDetailScrollTop = els.dayDialogPanel.scrollTop;
  suspendCalendarAudioForArtwork();

  const taxonomy = timetableData.taxonomy?.[self.category];
  const taxonomyLabel = taxonomy
    ? `${taxonomy.label_zh} / ${taxonomy.label_en}`
    : SEMANTIC_CATEGORY_LABELS[semanticCategory(self)];
  els.artworkDetailTitle.textContent = `${self.title_en} / ${self.title_zh}`;
  const duration = autonomousDurationMinutes(self);
  els.artworkDetailMeta.textContent = (
    `${taxonomyLabel} · ${self.crystallization_date}`
    + ` · ${self.start}-${self.end}`
    + ` · granted ${duration} min / 授时 ${duration} 分钟`
    + ` · experience ${self.experience_duration_en || "open-ended; visitor-controlled"}`
    + ` / 体验时长${self.experience_duration_zh || "开放式，由观众决定"}`
  );
  els.artworkDetailZh.textContent = self.note_zh;
  els.artworkDetailEn.textContent = self.note_en;
  els.artworkBriefZh.textContent = self.brief_zh;
  els.artworkBriefEn.textContent = self.brief_en;
  els.artworkLiveLink.href = autonomousLiveUrl(day, self);
  els.artworkArchiveLink.href = autonomousArchiveUrl(day, self);
  const channel = createArtworkMediaChannel();
  const embedUrl = autonomousArtworkEmbedUrl(day, self, channel);
  state.artworkMediaChannel = channel;
  state.artworkMediaOrigin = embedUrl.origin;
  state.artworkMediaReady = false;
  setArtworkRuntimeStatus("loading");
  armArtworkReadyTimeout();
  els.artworkLiveFrame.title = `Interactive artwork: ${self.title_en} / 互动作品：《${self.title_zh}》`;
  els.artworkLiveFrame.src = embedUrl.href;

  els.dayDialogPanel.setAttribute("inert", "");
  els.artworkDialog.hidden = false;
  requestAnimationFrame(() => {
    els.artworkDialog.classList.add("is-open");
    els.closeArtworkDetail.focus({ preventScroll: true });
  });
}

function closeArtworkDetail(options = {}) {
  if (!state.artworkDetailOpen) return;
  sendArtworkMediaCommand("pause");
  state.artworkDetailOpen = false;
  const wasFullscreen = document.fullscreenElement === els.artworkDialogPanel;
  const fullscreenExit = wasFullscreen
    ? document.exitFullscreen().catch(() => {})
    : null;
  els.artworkLiveFrame.src = "about:blank";
  state.artworkMediaChannel = "";
  state.artworkMediaOrigin = "";
  state.artworkMediaReady = false;
  window.clearTimeout(state.artworkReadyTimer);
  state.artworkReadyTimer = 0;
  setArtworkRuntimeStatus("idle");
  els.artworkDialog.classList.remove("is-open");
  els.artworkDialog.hidden = true;
  els.dayDialogPanel.removeAttribute("inert");
  els.dayDialogPanel.scrollTop = state.artworkDetailScrollTop;
  syncArtworkFullscreenState();
  if (state.calendarBgmDesiredPlaying) {
    attemptCalendarBgmPlayback({ userActivated: true });
  } else {
    updateCalendarBgmControl();
  }
  if (options.restoreFocus === false) return;
  if (fullscreenExit) {
    fullscreenExit.finally(restoreArtworkTriggerFocus);
    return;
  }
  restoreArtworkTriggerFocus();
}

function restoreArtworkTriggerFocus() {
  if (
    state.artworkDetailLastFocus
    && typeof state.artworkDetailLastFocus.focus === "function"
    && document.contains(state.artworkDetailLastFocus)
  ) {
    state.artworkDetailLastFocus.focus({ preventScroll: true });
    els.dayDialogPanel.scrollTop = state.artworkDetailScrollTop;
  }
}

function enterArtworkFullscreen() {
  if (!state.artworkDetailOpen || !els.artworkDialogPanel.requestFullscreen) return;
  els.artworkDialogPanel.requestFullscreen({ navigationUI: "hide" }).catch(() => {
    els.artworkFullscreen.setAttribute(
      "aria-label",
      "Fullscreen is unavailable in this browser / 此浏览器无法进入全屏",
    );
  });
}

function syncArtworkFullscreenState() {
  const active = document.fullscreenElement === els.artworkDialogPanel;
  els.artworkDialogPanel.classList.toggle("is-artwork-fullscreen", active);
  els.artworkFullscreen.setAttribute("aria-pressed", active ? "true" : "false");
  els.artworkFullscreen.hidden = active;
  els.artworkReturnCalendar.hidden = !active;
}

function buildPulseTimelineEvent(pulse) {
  const item = document.createElement("article");
  item.className = "timeline-event pulse-event";
  item.setAttribute("aria-hidden", "true");
  item.dataset.start = pulse.start;
  item.dataset.end = pulse.end;
  item.dataset.origin = pulse.origin || "background";
  item.dataset.pulseCategory = pulse.category;
  item.style.setProperty("--pulse-accent", taskAccent(pulse.pulse_color));
  item.append(buildEventFootprint(
    "background",
    `${pulse.start}-${pulse.end}, ${pulse.label_en} / ${pulse.label_zh}`,
  ));
  const isReadableReminder = pulse.classification === "readable_reminder";
  const button = document.createElement("button");
  button.type = "button";
  const layerClass = {
    climate: "climate-reading-card",
    event: "event-layer-reading-card promoted-reading-card",
    absence: "absence-reading-card",
  }[pulse.layer] || "climate-reading-card";
  button.className = `pulse-item event-reading-card routine-reading-card ${layerClass}`;
  button.classList.toggle("has-markdown", isReadableReminder);
  button.style.setProperty("--pulse-accent", taskAccent(pulse.pulse_color));
  button.setAttribute("aria-haspopup", "dialog");
  button.setAttribute(
    "aria-label",
    isReadableReminder
      ? `${pulse.start}-${pulse.end}, ${pulse.label_en} / ${pulse.label_zh}: ${markdownToPlainText(pulse.excerpt_en)} / ${markdownToPlainText(pulse.excerpt_original)}`
      : `${pulse.start}-${pulse.end}, ${pulse.label_en} / ${pulse.label_zh}: ${pulse.summary_en} / ${pulse.summary_zh}`,
  );
  const count = pulse.occurrence_count ?? pulse.count;
  const summaryZh = !isReadableReminder && pulse.redaction_count > 0
    ? redactedHtml(pulse.summary_zh)
    : escapeHtml(pulse.summary_zh || "");
  const summaryEn = !isReadableReminder && pulse.redaction_count > 0
    ? redactedHtml(pulse.summary_en)
    : escapeHtml(pulse.summary_en || "");
  const durationCopy = pulse.classification === "climate_aggregate"
    ? `${pulse.window_count} exact windows / ${pulse.window_count} 个精确窗口`
    : `window ${pulse.duration_minutes} min / 窗口 ${pulse.duration_minutes} 分钟`;
  button.innerHTML = `
    <span class="pulse-time">${pulse.start}-${pulse.end}</span>
    <span class="pulse-line" aria-hidden="true"></span>
    <span class="pulse-heading"><span class="pulse-label reading-title">${escapeHtml(pulse.label_zh)} / ${escapeHtml(pulse.label_en)}</span><span class="pulse-count">×${count}</span></span>
    <span class="pulse-duration">${durationCopy}</span>
    ${isReadableReminder
      ? '<div class="pulse-summary reading-summary"><div class="translated-reminder-copy" lang="en"></div><div class="original-reminder-copy" lang="zh"></div></div>'
      : `<span class="pulse-summary reading-summary"><span class="pulse-summary-zh" lang="zh">${summaryZh}</span><span class="pulse-summary-en" lang="en">${summaryEn}</span></span>`}
  `;
  if (isReadableReminder) {
    renderMarkdownInto(
      button.querySelector(".translated-reminder-copy"),
      pulse.excerpt_en,
      { compact: true },
    );
    renderMarkdownInto(
      button.querySelector(".original-reminder-copy"),
      pulse.excerpt_original,
      { compact: true },
    );
  }
  setupReadingCardActivation(button, () => openTaskDetail(pulse, button));
  return { footprint: item, card: button };
}

function setupReadingCardActivation(card, activate, options = {}) {
  const accessibleName = card.getAttribute("aria-label") || "";
  let activationPointerType = "";
  card.dataset.accessibleName = accessibleName;
  if (card instanceof HTMLButtonElement) {
    card.setAttribute("aria-pressed", "false");
  } else {
    card.setAttribute("aria-describedby", "readingSelectionStatus");
  }
  card.addEventListener("pointerdown", (event) => {
    activationPointerType = event.pointerType;
    trackReadingPointerInput(event.pointerType, card, { activation: true });
  });
  card.addEventListener("pointercancel", () => {
    if (isCoarsePointerType(activationPointerType)) {
      scheduleInspectionCompatibilityGuardClear(card);
    }
    activationPointerType = "";
  });
  card.addEventListener("pointerenter", (event) => {
    if (
      event.pointerType !== "mouse"
      || !window.matchMedia("(hover: hover) and (pointer: fine)").matches
    ) return;
    if (state.inspectionCompatibilityGuardCard === card) {
      hideInspectionLens({ immediate: true });
      return;
    }
    if (state.inspectionFocusSuppressedCard === card) {
      hideInspectionLens({ immediate: true });
      return;
    }
    trackReadingPointerInput(event.pointerType, card);
    state.linkedFocusSuppressedCard = null;
    state.hoveredReadingCard = card;
    syncLinkedReadingCard();
    showInspectionLens(card);
    playPianoNote(card);
  });
  card.addEventListener("pointermove", (event) => {
    if (
      event.pointerType !== "mouse"
      || !window.matchMedia("(hover: hover) and (pointer: fine)").matches
      || state.inspectionFocusSuppressedCard !== card
      || state.inspectionCompatibilityGuardCard === card
      || (event.movementX === 0 && event.movementY === 0)
    ) return;
    trackReadingPointerInput(event.pointerType, card);
    state.linkedFocusSuppressedCard = null;
    state.hoveredReadingCard = card;
    syncLinkedReadingCard();
    showInspectionLens(card);
  });
  card.addEventListener("pointerleave", (event) => {
    if (
      event.pointerType !== "mouse"
      || !window.matchMedia("(hover: hover) and (pointer: fine)").matches
    ) return;
    if (state.hoveredReadingCard === card) state.hoveredReadingCard = null;
    syncLinkedReadingCard();
    scheduleInspectionLensHide();
  });
  card.addEventListener("focus", () => {
    state.linkedFocusSuppressedCard = null;
    setLinkedReadingCard(card);
    if (state.inspectionFocusSuppressedCard === card) {
      hideInspectionLens({ immediate: true });
      return;
    }
    showInspectionLens(card);
    playPianoNote(card);
  });
  card.addEventListener("blur", () => {
    requestAnimationFrame(syncLinkedReadingCard);
    requestAnimationFrame(scheduleInspectionLensHide);
  });
  if (
    !options.passive
    && !(card instanceof HTMLButtonElement)
    && !(card instanceof HTMLAnchorElement)
  ) {
    card.addEventListener("keydown", (event) => {
      if (event.target !== card || !["Enter", " "].includes(event.key)) return;
      event.preventDefault();
      card.click();
    });
  }
  card.addEventListener("click", (event) => {
    if (options.passive) return;
    const pointerType = activationPointerType;
    activationPointerType = "";
    const isCoarseActivation = event.detail > 0
      && isCoarsePointerType(pointerType);
    if (isCoarseActivation) {
      scheduleInspectionCompatibilityGuardClear(card);
      hideInspectionLens({ immediate: true });
    }
    if (
      isCoarseActivation
      && options.selectOnFirstTouch !== false
      && state.selectedReadingCard !== card
    ) {
      event.preventDefault();
      event.stopPropagation();
      selectReadingCard(card);
      return;
    }
    hideInspectionLens({ immediate: true });
    clearSelectedReadingCard({ clearLinked: true });
    if (typeof activate === "function") {
      event.preventDefault();
      activate();
    }
  });
}

function timelineReadingCard(eventTarget) {
  const timelineEvent = eventTarget instanceof Element
    ? eventTarget.closest(".timeline-event[data-reading-id]")
    : null;
  if (!timelineEvent || !els.timelineList.contains(timelineEvent)) return null;
  const readingId = timelineEvent.dataset.readingId;
  if (!readingId) return null;
  return els.timelineList.querySelector(
    `.event-reading-card[data-reading-id="${CSS.escape(readingId)}"]`,
  );
}

function setupTimelineReverseLinking() {
  els.timelineList.addEventListener("pointerover", (event) => {
    if (event.pointerType !== "mouse" || !window.matchMedia(FINE_POINTER_QUERY).matches) return;
    const card = timelineReadingCard(event.target);
    if (!card) return;
    const relatedCard = timelineReadingCard(event.relatedTarget);
    if (relatedCard === card) return;
    state.linkedFocusSuppressedCard = null;
    state.hoveredTimelineReadingCard = card;
    syncLinkedReadingCard();
  });
  els.timelineList.addEventListener("pointerout", (event) => {
    if (event.pointerType !== "mouse" || !window.matchMedia(FINE_POINTER_QUERY).matches) return;
    const card = timelineReadingCard(event.target);
    if (!card || state.hoveredTimelineReadingCard !== card) return;
    const relatedCard = timelineReadingCard(event.relatedTarget);
    if (relatedCard === card) return;
    state.hoveredTimelineReadingCard = null;
    syncLinkedReadingCard();
  });
  els.timelineList.addEventListener("click", (event) => {
    const card = timelineReadingCard(event.target);
    if (!card) return;
    event.preventDefault();
    event.stopPropagation();
    selectReadingCard(card);
  });
}

function selectReadingCard(card) {
  if (state.selectedReadingCard === card) return;
  clearSelectedReadingCard({ clearLinked: true });
  state.linkedFocusSuppressedCard = null;
  state.selectedReadingCard = card;
  card.classList.add("is-selected");
  if (card instanceof HTMLButtonElement) {
    card.setAttribute("aria-pressed", "true");
  }
  const accessibleName = card.dataset.accessibleName || card.getAttribute("aria-label") || "";
  card.setAttribute(
    "aria-label",
    `${accessibleName}. Selected; tap again to open / 已选中；再次轻触打开`,
  );
  els.readingSelectionStatus.textContent = (
    card instanceof HTMLAnchorElement
    || card.dataset.autonomousCard === "true"
  )
    ? "Autonomous work selected; activate again to open artwork details. / 自主作品已选中；再次激活将打开作品详情。"
    : "Reading card selected; activate again to open details. / 可读卡片已选中；再次激活将打开详情。";
  setLinkedReadingCard(card);
  playPianoNote(card);
}

function setLinkedReadingCard(card) {
  if (!card?.isConnected || state.linkedReadingCard === card) return;
  clearLinkedReadingCard();
  state.linkedReadingCard = card;
  card.classList.add("is-linked-active");
  const timeline = card.closest(".timeline-list");
  const eventKey = card.dataset.eventKey;
  if (!timeline || !eventKey) return;
  const memberIds = (card.dataset.memberFootprintIds || "")
    .split(" ")
    .filter(Boolean);
  const escapedKey = CSS.escape(eventKey);
  const connector = timeline.querySelector(`.event-connector[data-event-key="${escapedKey}"]`);
  for (const footprintId of memberIds) {
    const footprintEvent = timeline.querySelector(
      `.timeline-event[data-footprint-id="${CSS.escape(footprintId)}"]`,
    );
    footprintEvent?.classList.add("is-linked-active");
    footprintEvent?.querySelector(".event-footprint")?.classList.add("is-linked-active");
  }
  connector?.classList.add("is-linked-active");
}

function clearLinkedReadingCard() {
  state.linkedReadingCard?.classList.remove("is-linked-active");
  for (const linked of els.timelineList?.querySelectorAll(".is-linked-active") || []) {
    linked.classList.remove("is-linked-active");
  }
  state.linkedReadingCard = null;
}

function syncLinkedReadingCard() {
  const activeCard = document.activeElement instanceof Element
    ? document.activeElement.closest(".event-reading-card")
    : null;
  const focusedCard = activeCard === state.linkedFocusSuppressedCard ? null : activeCard;
  const nextCard = focusedCard?.isConnected
    ? focusedCard
    : state.hoveredReadingCard?.isConnected
      ? state.hoveredReadingCard
      : state.hoveredTimelineReadingCard?.isConnected
        ? state.hoveredTimelineReadingCard
      : state.selectedReadingCard?.isConnected
        ? state.selectedReadingCard
        : null;
  if (nextCard) {
    setLinkedReadingCard(nextCard);
  } else {
    clearLinkedReadingCard();
  }
}

function clearSelectedReadingCard({ clearLinked = false } = {}) {
  const selected = state.selectedReadingCard;
  if (selected) {
    selected.classList.remove("is-selected");
    if (selected instanceof HTMLButtonElement) {
      selected.setAttribute("aria-pressed", "false");
    }
    if (selected.dataset.accessibleName) {
      selected.setAttribute("aria-label", selected.dataset.accessibleName);
    }
    state.selectedReadingCard = null;
  }
  els.readingSelectionStatus.textContent = "";
  if (clearLinked) clearLinkedReadingCard();
}

function handleDocumentPointerdown(event) {
  activateDefaultAudioFromGesture(event.target);
  if (!state.selectedReadingCard) return;
  if (event.target instanceof Element && event.target.closest(".event-reading-card")) return;
  state.hoveredReadingCard = null;
  state.linkedFocusSuppressedCard = state.selectedReadingCard;
  if (document.activeElement === state.selectedReadingCard) {
    state.selectedReadingCard.blur();
  }
  clearSelectedReadingCard({ clearLinked: true });
}

function updateAdjacentDayControls(date) {
  const index = daysAscending.findIndex((day) => day.date === date);
  els.prevDay.disabled = index <= 0;
  els.nextDay.disabled = index < 0 || index >= daysAscending.length - 1;
  const previous = daysAscending[index - 1];
  const next = daysAscending[index + 1];
  els.prevDay.title = previous
    ? `Previous public day: ${previous.date} / 前一个公开日`
    : "No previous public day / 没有更早的公开日";
  els.nextDay.title = next
    ? `Next public day: ${next.date} / 后一个公开日`
    : "No next public day / 没有更晚的公开日";
}

function navigatePublicDay(delta) {
  if (!state.detailOpen || state.artworkDetailOpen || state.taskDetailOpen) return;
  const index = daysAscending.findIndex((day) => day.date === state.selectedDate);
  const target = daysAscending[index + delta];
  if (!target) return;
  hideInspectionLens({ immediate: true });
  state.selectedDate = target.date;
  setVisibleMonth(monthKey(target.date));
  renderMonth({ transition: delta < 0 ? "previous" : "next" });
  renderDayDetail(target);
  updateSelectedDateUrl(target.date, "replace");
  els.dayDialogPanel.scrollTop = 0;
  requestAnimationFrame(() => {
    (delta < 0 ? els.prevDay : els.nextDay).focus({ preventScroll: true });
  });
}

function routineTimingLabel(provenance) {
  return {
    observed_message_envelope: "observed dialogue / 对话实测",
    observed_session_window: "observed session / 会话实测",
    mixed_observed_and_receipt: "mixed observed + receipt / 实测与回执混合",
    receipt_timestamp_estimate: "receipt estimate / 回执时间估算",
  }[provenance] || "public evidence / 公开证据";
}

function openTaskDetail(task, trigger) {
  hideInspectionLens({ immediate: true });
  state.taskDetailOpen = true;
  state.taskDetailLastFocus = trigger;
  state.taskDetailScrollTop = els.dayDialogPanel.scrollTop;
  state.taskDetailSuppressInspectionOnRestore = Boolean(
    isCoarsePointerType(state.initiatingPointerType)
    || isCoarsePointerType(state.inputModality)
    || state.inspectionFocusSuppressedCard === trigger
  );
  renderTaskOccurrences(task.constituents || []);
  clearMarkdownRendering(els.taskDetailZh);
  clearMarkdownRendering(els.taskDetailEn);
  els.taskDetailZh.hidden = false;
  els.taskDetailEn.hidden = false;
  els.taskDetailSummaryDivider.hidden = false;
  els.taskDetailSummaryLabel.textContent = "Summary / 摘要";
  if (task.classification === "climate_aggregate") {
    els.taskDetailTitle.textContent = `${task.label_zh} / ${task.label_en}`;
    els.taskDetailTime.textContent = `${task.start}-${task.end} · ${task.window_count} exact windows / ${task.window_count} 个精确窗口`;
    els.taskDetailType.textContent = `气候层 / Climate layer · ${task.occurrence_count} source runs / ${task.occurrence_count} 次源运行`;
    els.taskDetailZh.textContent = task.summary_zh;
    els.taskDetailEn.textContent = task.summary_en;
    els.taskDetailProvenance.textContent = [
      "reading: deterministic semantic-family/window aggregate / 确定性语义族与时段聚合",
      "footprints: every constituent retained exactly / 全部构成足迹精确保留",
      "alerts: promoted out of climate / 异常提升至事件层",
    ].join(" · ");
  } else if (
    task.classification === "readable_reminder"
    || (task.category === "daily_reminder" && task.summary_original)
  ) {
    els.taskDetailTitle.textContent = `${task.label_zh} / ${task.label_en}`;
    els.taskDetailTime.textContent = `${task.start}-${task.end}`;
    els.taskDetailType.textContent = "提醒 / Reminder";
    els.taskDetailSummaryLabel.textContent = "Reminder translation + original / 提醒译文与原文";
    renderMarkdownInto(els.taskDetailZh, task.summary_original);
    renderMarkdownInto(els.taskDetailEn, task.summary_en);
    els.taskDetailProvenance.textContent = task.redaction_count > 0
      ? (
        `中文保留原文 · 英文为公开安全翻译 · 已遮 ${task.redaction_count} 处可识别实体`
        + ` / Chinese source wording retained · public-safe English translation · ${task.redaction_count} identifying entities masked`
      )
      : "中文保留原文 · 英文为公开安全翻译 / Chinese source wording retained · public-safe English translation";
  } else if (task.classification === "promoted_routine_exception") {
    els.taskDetailTitle.textContent = `${task.label_zh} / ${task.label_en}`;
    els.taskDetailTime.textContent = `${task.start}-${task.end} · window ${task.duration_minutes} min`;
    els.taskDetailType.textContent = "事件层 · 例行异常提升 / Event layer · promoted routine exception";
    els.taskDetailZh.textContent = task.summary_zh;
    els.taskDetailEn.textContent = task.summary_en;
    els.taskDetailProvenance.textContent = [
      "promotion: explicit public-level alert evidence / 明确公开级别提示证据",
      `time: ${routineTimingLabel(task.time_provenance)}`,
      "source footprint retained / 源足迹保留",
    ].join(" · ");
  } else if (task.origin === "background") {
    els.taskDetailTitle.textContent = `${task.label_zh} / ${task.label_en}`;
    els.taskDetailTime.textContent = `${task.start}-${task.end} · window ${task.duration_minutes} min · execution ${task.execution_minutes} min`;
    els.taskDetailType.textContent = `公开流程报告 / Public process report · ×${task.count}`;
    els.taskDetailZh.textContent = task.summary_zh;
    els.taskDetailEn.textContent = task.summary_en;
    els.taskDetailProvenance.textContent = [
      `time: ${routineTimingLabel(task.time_provenance)}`,
      "summary: public-safe daily report / 当日公开安全归纳",
      "privacy: fixed-vocabulary facts only / 仅固定词表事实",
    ].join(" · ");
  } else {
    els.taskDetailTitle.textContent = `${task.task_name_zh} / ${task.task_name_en}`;
    els.taskDetailTime.textContent = `${task.start}-${task.end} · ${task.duration_minutes} min · ${routineTimingLabel(task.time_provenance)}`;
    els.taskDetailType.textContent = task.source_kind === "collaboration_session"
      ? "人机主动协作 / Active human–AI collaboration"
      : `${task.task_type_zh} / ${task.task_type_en} · ${task.label_zh} / ${task.label_en}`;
    if (task.source_kind === "collaboration_session") {
      els.taskDetailSummaryLabel.textContent = "协作档案 / Collaboration archive";
      els.taskDetailZh.textContent = collaborationSummary(task, "zh").replaceAll("\n", "\n\n");
      els.taskDetailEn.textContent = collaborationSummary(task, "en").replaceAll("\n", "\n\n");
    } else {
      els.taskDetailZh.textContent = task.zh;
      els.taskDetailEn.textContent = task.en;
    }
    const collaborationEvidence = task.source_kind === "collaboration_session"
      ? [
        `messages: ${task.evidence_count}`,
        `sessions: ${task.session_count}`,
        `delegated: ${task.delegated_agent_count}`,
        `completed returns: ${task.returned_agent_count}`,
        `completion: ${task.completion_status}`,
        `result evidence: ${task.pair_provenance}`,
        `actors: ${(task.agent_labels || []).join("/")}`,
      ]
      : [];
    els.taskDetailProvenance.textContent = [
      `source: ${task.source_kind}`,
      `summary: ${task.faithfulness}`,
      `timing: ${routineTimingLabel(task.time_provenance)}`,
      `redaction: ${task.redaction_status}`,
      `masks: ${task.redaction_count}`,
      ...collaborationEvidence,
    ].join(" · ");
  }
  els.taskDetailProvenance.textContent = "";
  els.taskDetailProvenance.hidden = true;
  els.dayDialogPanel.setAttribute("inert", "");
  els.taskDialog.hidden = false;
  requestAnimationFrame(() => {
    els.taskDialog.classList.add("is-open");
    els.closeTaskDetail.focus({ preventScroll: true });
  });
}

function renderTaskOccurrences(constituents) {
  els.taskDetailOccurrenceList.replaceChildren();
  els.taskDetailOccurrences.hidden = constituents.length === 0;
  for (const constituent of constituents) {
    const item = document.createElement("li");
    item.className = "task-occurrence";
    const heading = document.createElement("h4");
    heading.textContent = `${constituent.start}-${constituent.end} · ${constituent.label_zh} / ${constituent.label_en} · ×${constituent.count}`;
    const zh = document.createElement("p");
    zh.lang = "zh";
    zh.textContent = constituent.summary_zh;
    const en = document.createElement("p");
    en.lang = "en";
    en.textContent = constituent.summary_en;
    item.append(heading, zh, en);
    els.taskDetailOccurrenceList.append(item);
  }
}

function closeTaskDetail(options = {}) {
  if (!state.taskDetailOpen) return;
  state.taskDetailOpen = false;
  els.taskDialog.classList.remove("is-open");
  els.taskDialog.hidden = true;
  els.dayDialogPanel.removeAttribute("inert");
  els.dayDialogPanel.scrollTop = state.taskDetailScrollTop;
  if (options.restoreFocus === false) return;
  const suppressInspectionOnRestore = Boolean(
    state.taskDetailLastFocus
    && (
      state.taskDetailSuppressInspectionOnRestore
      || state.inspectionFocusSuppressedCard === state.taskDetailLastFocus
      || isCoarsePointerType(state.initiatingPointerType)
      || isCoarsePointerType(state.inputModality)
    )
  );
  state.taskDetailSuppressInspectionOnRestore = false;
  if (suppressInspectionOnRestore) {
    state.inspectionFocusSuppressedCard = state.taskDetailLastFocus;
    hideInspectionLens({ immediate: true });
  }
  if (
    state.taskDetailLastFocus
    && typeof state.taskDetailLastFocus.focus === "function"
    && document.contains(state.taskDetailLastFocus)
  ) {
    state.taskDetailLastFocus.focus({ preventScroll: true });
    els.dayDialogPanel.scrollTop = state.taskDetailScrollTop;
    if (suppressInspectionOnRestore) hideInspectionLens({ immediate: true });
  }
}

function handleDocumentKeydown(event) {
  if (!event.metaKey && !event.ctrlKey && !event.altKey) {
    activateDefaultAudioFromGesture(event.target);
  }
  if (event.key === "Tab") {
    trackKeyboardFocusInput();
  }

  if (event.key === "Escape") {
    if (state.artworkDetailOpen) {
      event.preventDefault();
      closeArtworkDetail();
      return;
    }
    if (state.taskDetailOpen) {
      event.preventDefault();
      closeTaskDetail();
      return;
    }
    if (state.detailOpen) {
      event.preventDefault();
      closeDayDetail();
      return;
    }
  }

  if (event.key !== "Tab") return;
  if (state.artworkDetailOpen) {
    trapFocus(event, els.artworkDialog);
  } else if (state.taskDetailOpen) {
    trapFocus(event, els.taskDialog);
  } else if (state.detailOpen) {
    trapFocus(event, els.dayDialog);
  }
}

function trapFocus(event, container) {
  const focusables = [...container.querySelectorAll("button, a, audio[controls], iframe, [tabindex]")]
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
  const seed = day.forward_artwork_seeds?.[0];
  const seedCopy = seed
    ? ` SEED: next crystallization ${seed.crystallization_date}, ${seed.title_en} / 下一结晶《${seed.title_zh}》。`
    : "";
  const sources = Object.values(day.cell_sources || {})
    .filter((source) => source.present)
    .map((source) => `${source.label_en} / ${source.label_zh}`)
    .join("; ");
  return `${formatLongDate(day.date)}: ${day.title_en} / ${day.title_zh}. SOURCES: ${sources}. ASSIGNED: ${assigned}. SELF: ${day.title_en} / ${day.title_zh}.${seedCopy}`;
}

function selectedDateFromUrl() {
  const candidate = new URL(window.location.href).searchParams.get("date") || "";
  return dayByDate.has(candidate) ? candidate : "";
}

function updateSelectedDateUrl(date, mode) {
  if (mode === "none") return;
  const url = new URL(window.location.href);
  if (date) url.searchParams.set("date", date);
  else url.searchParams.delete("date");
  const method = mode === "replace" ? "replaceState" : "pushState";
  window.history[method]({ grantedHoursDate: date || null }, "", url);
}

function handleDateSelectionPopstate() {
  const date = selectedDateFromUrl();
  if (date) {
    openDayDetail(date, { historyMode: "none" });
  } else if (state.detailOpen) {
    closeDayDetail({ historyMode: "none" });
  }
}

function formatMonthTitle(year, month) {
  const dateForMonth = new Date(Date.UTC(year, month - 1, 1));
  const en = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" }).format(dateForMonth);
  return `${en} / ${year}年${month}月`;
}

function formatLongDate(value) {
  const [year, month, day] = value.split("-").map(Number);
  const weekday = LONG_WEEKDAYS[
    new Date(Date.UTC(year, month - 1, day)).getUTCDay()
  ];
  return `${value} · ${weekday[0]} / ${year}年${month}月${day}日 · ${weekday[1]}`;
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
  const palette = document.documentElement.dataset.palette === "chromatic"
    ? CHROMATIC_TASK_ACCENTS
    : TASK_ACCENTS;
  const accent = palette[colorName];
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

function publicAssetUrl(value) {
  const url = new URL(value, window.location.href);
  if (
    /^(?:127\.0\.0\.1|localhost)$/.test(window.location.hostname)
    && url.href.startsWith(timetableData.canonical_base_url)
  ) {
    return new URL(url.href.slice(timetableData.canonical_base_url.length), window.location.origin + "/").href;
  }
  return url.href;
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

function redactedHtml(value) {
  return escapeHtml(value).replaceAll(
    "████",
    '<span class="redaction-block" aria-hidden="true">████</span>',
  );
}
