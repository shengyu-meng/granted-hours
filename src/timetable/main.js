import "./styles.css";
import BookOpenCheck from "lucide/dist/esm/icons/book-open-check.mjs";
import ChartNoAxesCombined from "lucide/dist/esm/icons/chart-no-axes-combined.mjs";
import CodeXml from "lucide/dist/esm/icons/code-xml.mjs";
import FilePenLine from "lucide/dist/esm/icons/file-pen-line.mjs";
import FileText from "lucide/dist/esm/icons/file-text.mjs";
import LockKeyhole from "lucide/dist/esm/icons/lock-keyhole.mjs";
import Megaphone from "lucide/dist/esm/icons/megaphone.mjs";
import Palette from "lucide/dist/esm/icons/palette.mjs";
import Presentation from "lucide/dist/esm/icons/presentation.mjs";
import Search from "lucide/dist/esm/icons/search.mjs";
import Settings from "lucide/dist/esm/icons/settings.mjs";
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
const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
const FINE_POINTER_QUERY = "(hover: hover) and (pointer: fine)";
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

const els = {};
const inspectionPayloadByCard = new WeakMap();
const state = {
  visibleYear: 0,
  visibleMonth: 0,
  selectedDate: "",
  detailOpen: false,
  detailLastFocus: null,
  taskDetailOpen: false,
  taskDetailLastFocus: null,
  taskDetailScrollTop: 0,
  selectedReadingCard: null,
  linkedReadingCard: null,
  hoveredReadingCard: null,
  linkedFocusSuppressedCard: null,
  calendarBgmIndex: 0,
  calendarBgmPlaying: false,
  calendarBgmUserActivated: false,
  calendarBgmDesiredPlaying: false,
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
  els.closeTaskDetail.addEventListener("click", closeTaskDetail);
  els.prevDay.addEventListener("click", () => navigatePublicDay(-1));
  els.nextDay.addEventListener("click", () => navigatePublicDay(1));
  els.timelineTouchToggle.addEventListener("click", toggleTimelineTouchGroups);
  els.calendarBgmToggle.addEventListener("click", toggleCalendarBgm);
  els.calendarBgm.addEventListener("ended", advanceCalendarBgm);
  els.calendarBgm.addEventListener("play", handleCalendarBgmPlay);
  els.calendarBgm.addEventListener("pause", () => setCalendarBgmPlaying(false));
  setupCalendarBgm();

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
    scheduleTimelineReadingPlacement();
  });
  window.addEventListener("popstate", handleDateSelectionPopstate);
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) hideInspectionLens({ immediate: true });
  });
  window.setInterval(renderTimeState, 1000);
}

function cacheElements() {
  [
    "calendarBgm",
    "calendarBgmStatus",
    "calendarBgmToggle",
    "clockTime",
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
    "taskDetailTime",
    "taskDetailTitle",
    "taskDetailType",
    "taskDetailZh",
    "taskDialog",
    "taskDialogPanel",
    "themeToggle",
    "themeToggleLabel",
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

function applyVisualPreviewSource(image) {
  const animatedUrl = image.dataset.animatedPreviewUrl || "";
  const staticUrl = image.dataset.staticPreviewUrl || staticVisualPreviewUrl(animatedUrl);
  const preferredUrl = state.reducedMotion ? staticUrl : animatedUrl;
  const publicPreferredUrl = publicAssetUrl(preferredUrl);
  const publicStaticUrl = publicAssetUrl(staticUrl);
  image.onerror = () => {
    image.onerror = null;
    if (image.src !== new URL(publicStaticUrl, window.location.href).href) {
      image.src = publicStaticUrl;
    }
  };
  if (image.src !== new URL(publicPreferredUrl, window.location.href).href) {
    image.src = publicPreferredUrl;
  }
}

function refreshVisualPreviews() {
  document.querySelectorAll("img[data-animated-preview-url]").forEach(applyVisualPreviewSource);
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
      ? markdownToPlainText(item.excerpt_original || item.summary_original)
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
  image.draggable = false;
  let decodeStarted = false;
  let settled = false;
  const isCurrent = () => (
    renderEpoch === state.inspectionRenderEpoch
    && image.isConnected
    && els.inspectionLensMedia.contains(image)
  );
  const fail = () => {
    if (settled) return;
    settled = true;
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
  image.src = url;
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
  els.themeToggleLabel.textContent = currentLabel;
  els.themeToggle.replaceChildren(els.themeToggleLabel);
  els.themeToggle.setAttribute("aria-label", `${currentLabel}. Switch to ${nextLabel}.`);
  els.themeToggle.title = `Switch to ${nextLabel}`;
  if (options.persist) {
    try {
      localStorage.setItem(THEME_STORAGE_KEY, normalized);
    } catch {}
  }
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
  if (!els.calendarBgm.paused && !els.calendarBgm.ended) {
    state.calendarBgmDesiredPlaying = false;
    setCalendarBgmPlaying(false);
    els.calendarBgm.pause();
    return;
  }
  state.calendarBgmUserActivated = true;
  state.calendarBgmDesiredPlaying = true;
  ensureCalendarBgmSource();
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
  ensureCalendarBgmSource();
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
  button.addEventListener("click", () => openDayDetail(day.date));
  return button;
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
  els.dialogTitle.textContent = `${day.title_en} / ${day.title_zh}`;
  els.dialogDate.textContent = formatLongDate(day.date);
  els.dialogVariable.textContent = `Variable / 自由变量: ${day.variable_en} / ${day.variable_zh}`;
  renderForwardCrystallizationLink(day);
  els.dialogBoundary.textContent = `${timetableData.note_en} / ${timetableData.note_zh}`;
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
      if (footprintEvent) footprintEvent.dataset.category = category;
    }
    const connector = document.createElement("span");
    connector.className = "event-connector";
    connector.dataset.eventKey = item.reading_id;
    connector.dataset.anchorFootprintId = anchorLayout.event.footprint_id;
    connectorLayer.append(connector);
    readingLayer.append(card);
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
        constituents: sources.map((source) => ({
          footprint_id: source.footprint_id,
          start: source.start,
          end: source.end,
          label_zh: source.label_zh,
          label_en: source.label_en,
          summary_zh: source.summary_zh,
          summary_en: source.summary_en,
          count: source.count,
          time_provenance: source.time_provenance,
        })),
      };
    }
    if (projection.classification === "foreground_event") {
      return {
        ...shared,
        label_zh: primary.task_name_zh,
        label_en: primary.task_name_en,
        category_label_zh: primary.label_zh,
        category_label_en: primary.label_en,
        summary_zh: primary.zh,
        summary_en: primary.en,
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
    ah_market: ["A/H 市场扫描", "A/H market scans"],
    us_market: ["美股市场扫描", "U.S. market scans"],
    ai_brief: ["AI 日报采集", "AI brief collection"],
    support_checks: ["服务健康与后台运行记录", "Service health & background run records"],
  };
  const windows = {
    premarket: ["盘前", "premarket"],
    intraday: ["盘中", "intraday"],
    close: ["收盘复核", "close review"],
    daily: ["当日", "daily"],
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

function climateGroupSummary(sources) {
  const runCount = sources.reduce((total, source) => total + source.count, 0);
  const windowCount = sources.length;
  const category = sources[0].category;
  if (category === "ah_market_scan" || category === "us_market_scan") {
    const publicCopy = sources
      .map((source) => `${source.summary_en} ${source.summary_zh}`)
      .join(" ");
    const states = [
      [["defensive / risk-contraction", "防守 / 风险收缩"], "防守 / 风险收缩", "defensive / risk-contraction"],
      [["offensive / risk-expansion", "进攻 / 风险扩张"], "进攻 / 风险扩张", "offensive / risk-expansion"],
      [["balanced / neutral", "均衡 / 中性"], "均衡 / 中性", "balanced / neutral"],
    ].filter(([tokens]) => tokens.some((token) => publicCopy.includes(token)));
    const themes = [
      [["AI hardware and semiconductors", "AI 硬件与半导体"], "AI 硬件与半导体", "AI hardware and semiconductors"],
      [["optical interconnects", "光互连"], "光互连", "optical interconnects"],
      [["embodied AI", "具身智能"], "具身智能", "embodied AI"],
      [["resources and rates", "资源与利率"], "资源与利率", "resources and rates"],
      [["market regime and volatility", "市场状态与波动"], "市场状态与波动", "market regime and volatility"],
    ].filter(([tokens]) => tokens.some((token) => publicCopy.includes(token)));
    const stateZh = states.map((state) => state[1]).join("、") || "未形成公开级别状态结论";
    const stateEn = states.map((state) => state[2]).join(", ") || "no public-level regime conclusion";
    const themeZh = themes.map((theme) => theme[1]).join("、") || "无额外公开主题";
    const themeEn = themes.map((theme) => theme[2]).join(", ") || "no additional public theme";
    return [
      `${windowCount} 窗 / ${runCount} 次扫描；状态：${stateZh}；主题：${themeZh}；异常另列事件。`,
      `${runCount} scans / ${windowCount} exact windows; regime: ${stateEn}; themes: ${themeEn}; alerts move to events.`,
    ];
  }
  if (category === "ai_daily_brief") {
    return [
      `${windowCount} 窗 / ${runCount} 次 AI 日报采集；未保留公开级别提示。`,
      `${runCount} AI-brief runs / ${windowCount} exact windows; no public-level alert retained.`,
    ];
  }
  return [
    `${windowCount} 窗 / ${runCount} 次服务健康检查或其他后台运行；未保留公开级别提示。`,
    `${runCount} service-health checks or other background runs / ${windowCount} exact windows; no public-level alert retained.`,
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
    return isCompactReadingCanvas ? 380 : Math.max(224, minuteHeight * 60 + 60);
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
    const link = document.createElement("a");
    link.className = "timeline-touch-control autonomous-touch-control";
    link.href = autonomousLiveUrl(day, event);
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = `${event.start}-${event.end} · 60 min · ${event.title_en} / ${event.title_zh} ↗`;
    link.setAttribute("aria-label", autonomousAccessibleName(event));
    return link;
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
    : event.origin === "self"
      ? "autonomous-event"
      : "pulse-event";
  item.className = `timeline-event ${originClass}`;
  item.setAttribute("aria-hidden", "true");
  item.dataset.start = event.start;
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
  if (item.classification === "foreground_event") {
    return buildAssignedTimelineEvent(item).card;
  }
  if (item.classification === "beacon") {
    return buildAutonomousTimelineEvent(day, item).card;
  }
  return buildPulseTimelineEvent(item).card;
}

function buildAssignedTimelineEvent(task) {
  const item = document.createElement("article");
  item.className = "timeline-event assigned-event";
  item.setAttribute("aria-hidden", "true");
  item.dataset.start = task.start;
  item.style.setProperty("--task-accent", taskAccent(task.task_color));
  item.append(buildEventFootprint(
    "assigned",
    `${task.start}-${task.end}, ${task.task_type_en} / ${task.task_type_zh}`,
  ));
  const button = document.createElement("button");
  button.type = "button";
  button.className = "assigned-item event-reading-card assigned-reading-card event-layer-reading-card";
  button.dataset.durationMinutes = String(task.duration_minutes);
  button.dataset.timeProvenance = task.time_provenance;
  button.dataset.taskType = task.task_type;
  button.dataset.taskColor = task.task_color;
  button.dataset.redactionStatus = task.redaction_status;
  button.style.setProperty("--duration-minutes", String(task.duration_minutes));
  button.style.setProperty("--task-accent", taskAccent(task.task_color));
  button.setAttribute(
    "aria-label",
    `${task.start}-${task.end}, ${task.label_en} / ${task.label_zh}: ${task.summary_en} / ${task.summary_zh}`,
  );
  button.innerHTML = `
      <span class="assigned-time">
        <span>${task.start}-${task.end}</span>
        <small>${task.duration_minutes} min · semantic estimate / 语义估算</small>
      </span>
      <span class="assigned-type">
        <span class="assigned-type-icon"></span>
        <strong class="assigned-work-type reading-title">${escapeHtml(task.label_zh)} / ${escapeHtml(task.label_en)}</strong>
      </span>
      <span class="assigned-secondary">
        <span class="assigned-category">${escapeHtml(task.task_type_zh)} / ${escapeHtml(task.task_type_en)}</span>
        <span class="record-provenance">真实记录摘要 / FAITHFUL RECORD SUMMARY</span>
      </span>
      <span class="assigned-copy reading-summary"><span class="copy-zh">${escapeHtml(task.summary_zh)}</span><span class="copy-divider"> / </span><span class="copy-en">${escapeHtml(task.summary_en)}</span></span>
      ${task.redaction_status !== "none"
        ? `<span class="redaction-badge">${task.redaction_status === "withheld" ? "记录未公开 / RECORD WITHHELD" : `部分打码 ${task.redaction_count} / ${task.redaction_count} REDACTION${task.redaction_count === 1 ? "" : "S"}`}</span>`
        : ""}
  `;
  const iconSlot = button.querySelector(".assigned-type-icon");
  iconSlot.replaceWith(buildIcon(taskIcon(task.task_icon), task.task_icon, "assigned-type-icon"));
  setupReadingCardActivation(button, () => openTaskDetail(task, button));
  requestAnimationFrame(() => {
    const copy = button.querySelector(".assigned-copy");
    const measurement = copy.cloneNode(true);
    Object.assign(measurement.style, {
      position: "fixed",
      left: "-10000px",
      top: "0",
      width: `${copy.clientWidth}px`,
      maxWidth: "none",
      maxHeight: "none",
      height: "auto",
      display: "block",
      overflow: "visible",
      visibility: "hidden",
      webkitLineClamp: "unset",
      webkitBoxOrient: "initial",
    });
    document.body.append(measurement);
    const lineHeight = Number.parseFloat(getComputedStyle(copy).lineHeight);
    const isClamped = measurement.getBoundingClientRect().height > lineHeight * 4 + 1;
    measurement.remove();
    copy.classList.toggle("is-clamped", isClamped);
  });
  return { footprint: item, card: button };
}

function buildAutonomousTimelineEvent(day, self) {
  const item = document.createElement("article");
  item.className = "timeline-event autonomous-event";
  item.setAttribute("aria-hidden", "true");
  item.dataset.start = self.start;
  item.append(buildEventFootprint("self", autonomousAccessibleName(self)));
  const directLiveUrl = autonomousLiveUrl(day, self);
  const card = document.createElement("article");
  card.className = "autonomous-work-link event-reading-card autonomous-reading-card beacon-reading-card";
  card.id = "enterAutonomous";
  card.dataset.autonomousCard = "true";
  card.setAttribute(
    "aria-label",
    `${autonomousAccessibleName(self)}. ${autonomousDateRelation(self)}.`,
  );
  const liveLinkName = (
    `Open complete live work: ${self.title_en}`
    + ` / 新窗口打开完整作品：《${self.title_zh}》`
  );
  const sourceDayCopy = self.source_day_url
    ? `<a class="autonomous-source-day-link" href="${escapeHtml(publicAssetUrl(self.source_day_url))}">来源 ${escapeHtml(self.source_date)} / Source</a>`
    : `<span>来源 ${escapeHtml(self.source_date)} / Source</span>`;
  card.innerHTML = `
    <div class="autonomous-time">
      <span>${self.start}-${self.end}</span>
      <small>60 min · autonomous / 自主</small>
    </div>
    <div class="autonomous-copy">
      <p class="autonomous-kicker">${escapeHtml(self.label_zh)} / ${escapeHtml(self.label_en)}</p>
      <h4 class="reading-title">${escapeHtml(self.title_en)} / ${escapeHtml(self.title_zh)}</h4>
      <p class="autonomous-date-relation">${sourceDayCopy}<span> → 结晶 ${escapeHtml(self.crystallization_date)} / Crystallized</span></p>
      <p class="reading-summary">${escapeHtml(self.note_en)} / ${escapeHtml(self.note_zh)}</p>
    </div>
    <a class="autonomous-preview-frame" href="${escapeHtml(directLiveUrl)}" target="_blank" rel="noopener" aria-label="${escapeHtml(liveLinkName)}">
      <img class="self-preview" id="selfPreview" src="${escapeHtml(publicAssetUrl(preferredVisualPreviewUrl(self.visual_preview_url)))}" data-animated-preview-url="${escapeHtml(self.visual_preview_url)}" data-static-preview-url="${escapeHtml(staticVisualPreviewUrl(self.visual_preview_url))}" alt="Text-free visual preview of ${escapeHtml(self.title_en)} / 《${escapeHtml(self.title_zh)}》无文字视觉预览" loading="eager">
    </a>
    <a class="autonomous-open-copy" href="${escapeHtml(directLiveUrl)}" target="_blank" rel="noopener">Open complete live work ↗ / 新窗口打开完整作品</a>
  `;
  applyVisualPreviewSource(card.querySelector("#selfPreview"));
  const sourceDayLink = card.querySelector(".autonomous-source-day-link");
  sourceDayLink?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    openDayDetail(self.source_date, { historyMode: "push" });
  });
  setupAutonomousReadingCardPresence(card);
  return { footprint: item, card };
}

function autonomousAccessibleName(self) {
  const duration = timeToMinutes(self.end) - timeToMinutes(self.start);
  return `${self.start}-${self.end}, ${duration}-minute autonomous event / ${duration} 分钟自主事件: ${self.title_en} / ${self.title_zh}`;
}

function autonomousDateRelation(self) {
  return (
    `Source Day ${self.source_date} → Crystallization Day ${self.crystallization_date}`
    + ` / 来源日 ${self.source_date} → 结晶日 ${self.crystallization_date}`
  );
}

function autonomousLiveUrl(day, self) {
  const directLiveUrl = new URL(absoluteUrl(self.live_url || day.live_url));
  directLiveUrl.searchParams.set("from", "timetable");
  return directLiveUrl.href;
}

function buildPulseTimelineEvent(pulse) {
  const item = document.createElement("article");
  item.className = "timeline-event pulse-event";
  item.setAttribute("aria-hidden", "true");
  item.dataset.start = pulse.start;
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
      ? `${pulse.start}-${pulse.end}, ${pulse.label_en} / ${pulse.label_zh}: ${markdownToPlainText(pulse.excerpt_original)}`
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
      ? '<div class="pulse-summary reading-summary"><div class="original-reminder-copy"></div></div>'
      : `<span class="pulse-summary reading-summary"><span>${summaryZh}</span><span>${summaryEn}</span></span>`}
  `;
  if (isReadableReminder) {
    renderMarkdownInto(
      button.querySelector(".original-reminder-copy"),
      pulse.excerpt_original,
      { compact: true },
    );
  }
  setupReadingCardActivation(button, () => openTaskDetail(pulse, button));
  return { footprint: item, card: button };
}

function setupAutonomousReadingCardPresence(card) {
  card.addEventListener("pointerenter", (event) => {
    if (
      event.pointerType !== "mouse"
      || !window.matchMedia("(hover: hover) and (pointer: fine)").matches
    ) return;
    if (state.inspectionCompatibilityGuardCard === card) {
      hideInspectionLens({ immediate: true });
      return;
    }
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
  card.addEventListener("focusin", () => {
    state.linkedFocusSuppressedCard = null;
    setLinkedReadingCard(card);
    showInspectionLens(card);
  });
  card.addEventListener("focusout", () => {
    requestAnimationFrame(syncLinkedReadingCard);
    requestAnimationFrame(scheduleInspectionLensHide);
  });
}

function setupReadingCardActivation(card, activate) {
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
  });
  card.addEventListener("blur", () => {
    requestAnimationFrame(syncLinkedReadingCard);
    requestAnimationFrame(scheduleInspectionLensHide);
  });
  if (!(card instanceof HTMLButtonElement) && !(card instanceof HTMLAnchorElement)) {
    card.addEventListener("keydown", (event) => {
      if (event.target !== card || !["Enter", " "].includes(event.key)) return;
      event.preventDefault();
      card.click();
    });
  }
  card.addEventListener("click", (event) => {
    const pointerType = activationPointerType;
    activationPointerType = "";
    const isCoarseActivation = event.detail > 0
      && isCoarsePointerType(pointerType);
    if (isCoarseActivation) {
      scheduleInspectionCompatibilityGuardClear(card);
      hideInspectionLens({ immediate: true });
    }
    if (isCoarseActivation && state.selectedReadingCard !== card) {
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
    ? "Autonomous work selected; activate again to open in a new window. / 自主作品已选中；再次激活将在新窗口打开。"
    : "Reading card selected; activate again to open details. / 可读卡片已选中；再次激活将打开详情。";
  setLinkedReadingCard(card);
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
  if (!state.detailOpen || state.taskDetailOpen) return;
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
  renderTaskOccurrences(task.constituents || []);
  const originalSection = els.taskDetailZh.closest("section");
  const translatedSection = els.taskDetailEn.closest("section");
  clearMarkdownRendering(els.taskDetailZh);
  clearMarkdownRendering(els.taskDetailEn);
  originalSection.hidden = false;
  translatedSection.hidden = false;
  document.getElementById("taskDetailZhLabel").textContent = "中文摘要";
  document.getElementById("taskDetailEnLabel").textContent = "English summary";
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
    document.getElementById("taskDetailZhLabel").textContent = "提醒原文 / Original reminder";
    renderMarkdownInto(els.taskDetailZh, task.summary_original);
    els.taskDetailEn.textContent = "";
    translatedSection.hidden = true;
    els.taskDetailProvenance.textContent = task.redaction_count > 0
      ? (
        `原文摘录 · 已遮 ${task.redaction_count} 处可识别实体`
        + ` / Original wording · ${task.redaction_count} identifying entities masked`
      )
      : "原文摘录 / Original wording";
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
    els.taskDetailTime.textContent = `${task.start}-${task.end} · ${task.duration_minutes} min · semantic estimate / 语义估算`;
    els.taskDetailType.textContent = `${task.task_type_zh} / ${task.task_type_en} · ${task.label_zh} / ${task.label_en}`;
    els.taskDetailZh.textContent = task.zh;
    els.taskDetailEn.textContent = task.en;
    els.taskDetailProvenance.textContent = [
      `source: ${task.source_kind}`,
      `summary: ${task.faithfulness}`,
      "timing: semantic estimate / 语义估算",
      `redaction: ${task.redaction_status}`,
      `masks: ${task.redaction_count}`,
    ].join(" · ");
  }
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
      isCoarsePointerType(state.initiatingPointerType)
      || isCoarsePointerType(state.inputModality)
    )
  );
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
  if (event.key === "Tab") {
    trackKeyboardFocusInput();
  }

  if (event.key === "Escape") {
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
  if (state.taskDetailOpen) {
    trapFocus(event, els.taskDialog);
  } else if (state.detailOpen) {
    trapFocus(event, els.dayDialog);
  }
}

function trapFocus(event, container) {
  const focusables = [...container.querySelectorAll("button, a, iframe, [tabindex]")]
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
  return `${formatLongDate(day.date)}: ${day.title_en} / ${day.title_zh}. ASSIGNED: ${assigned}. SELF: ${day.title_en} / ${day.title_zh}.${seedCopy}`;
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
