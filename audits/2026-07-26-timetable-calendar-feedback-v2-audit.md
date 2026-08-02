# Granted Hours Timetable Feedback v2 — Implementation and Audit Report

- Date: 2026-07-26
- Baseline: `origin/main` at `3a88a0061434a23d65d9e8fb39c79cd1471da55a`
- Scope: visible month labels, embedded artwork BGM, duration-proportional schedule blocks, public task types/colors, library-backed vector icons
- Status: **Implementation and local QA passed; independent review passed; publication verification pending**

## 1. User requirements and implemented behavior

### 1.1 Concrete month labels

- Replaced the fixed `This month / 本月` control copy with the currently visible bilingual month and year.
- The label changes when navigating between May, June, and July 2026.
- The main month heading remains the large visual date anchor.

### 1.2 User-controlled embedded BGM

- Embedded artwork still starts paused and muted; no forced audible autoplay was restored.
- The chamber now exposes `Play BGM / 播放音乐` and `Pause BGM / 暂停音乐` in the outer toolbar.
- The iframe has `allow="autoplay"` so a genuine user gesture can authorize playback.
- Parent and child use a versioned `postMessage` protocol with:
  - exact target origin from the iframe URL;
  - `event.source === window.parent` enforcement;
  - parent-origin verification from the child referrer;
  - a per-chamber random channel token;
  - exact message-shape validation.
- The injected child runtime tracks both DOM `<audio>` elements and dynamically created `new Audio()` instances.
- Closing the chamber or toggling BGM off pauses and mutes tracked audio.
- Direct artwork pages keep their original audio and text controls.

### 1.3 Duration-proportional daily schedule blocks

- Each assigned task now includes `duration_minutes` and `time_provenance`.
- The current historical source does not contain trustworthy task-level timestamps; therefore every reconstructed span is explicitly labeled `estimated / 估算`.
- Estimates are deterministic, varied, continuous, and total 23 hours per day; the autonomous artwork keeps its separate 1-hour interval.
- Visual block height is controlled by duration, not by description length.
- Long detail text is line-clamped so copy cannot distort the timeline geometry.

### 1.4 Public-readable task types and colors

Added a stable task-type layer above the more specific task name:

- `申报书写作 / Grant proposal`
- `社媒内容 / Social content`
- `投资研究 / Investment research`
- `软件开发 / Software development`
- `论文审阅 / Thesis review`
- `课程材料 / Course materials`
- `研究分析 / Research analysis`
- `文档写作 / Document writing`
- `视觉设计 / Visual design`
- `系统维护 / System operations`

Specialized types require explicit supporting terms; otherwise classification falls back to the existing public category. Each type has a stable accent color and icon. The task type is now the primary readable signal; the concrete task name is secondary context.

### 1.5 Vector icon library

- Selected [Lucide](https://github.com/lucide-icons/lucide), ISC licensed.
- Replaced the repetitive custom `DOODLE_SVG` shapes with allowlisted, semantic Lucide SVG icons.
- No CDN is used.
- Only 19 named icon modules are directly imported; the application does not import the all-icons bundle.
- The same icon language is used for autonomous-work motifs and assigned task types.

## 2. Security and privacy

- `python3 scripts/check_public_safety.py`: PASS.
- `npm audit --audit-level=high`: 0 vulnerabilities after a non-breaking transitive PostCSS update.
- Public task typing does not introduce private names, client identities, internal filenames, credentials, or raw prompts.
- Audio commands are non-sensitive, but are still protected with strict source, origin, version, shape, action, and channel checks.
- Direct live-artwork behavior remains isolated from `?embed=calendar` behavior.

## 3. Test evidence

### Builder and schema

- `python3 scripts/test_timetable_builder.py`
- Result: 12 tests, PASS.
- Covers duration integrity, 23h/1h conservation, stable estimates, task type/color/icon fields, representative proposal/social/investment/software cases, naming safety, motif completeness, and deterministic output.
- Includes anti-misclassification regression cases proving that code, social, and system-maintenance work is not retyped merely because its subject text mentions markets or investment.

### Browser enrichment QA

- `TIMETABLE_URL=http://127.0.0.1:8776/timetable/ node scripts/qa_timetable_calendar_enrichment.mjs`
- Result: 14 checks, PASS.
- Covers:
  - dynamic month label;
  - varied library SVG icons;
  - readable task type and color layer;
  - duration-driven block geometry on representative days, including a proposal-heavy day where copy lengths differ;
  - explicit `embed=calendar` mode;
  - hidden inner chrome;
  - short-mobile artwork prominence;
  - initial media silence;
  - outer BGM enable/pause control;
  - direct-page preservation;
  - 320px no-horizontal-overflow behavior.

### Legacy regression QA

- `TIMETABLE_URL=http://127.0.0.1:8776/timetable/ node scripts/qa_timetable_regressions.mjs`
- Result: PASS.
- Evidence: 75 distinct daily schedules, 297 unique task phrases, complete scroll reachability.

### Static and syntax gates

- `python3 scripts/check_public_safety.py`: PASS.
- `python3 -m py_compile ...`: PASS.
- `node --check ...`: PASS.
- `git diff --check`: PASS.
- Deterministic double build: PASS; timetable source and generated asset hashes remained identical.
- `npm audit --audit-level=high`: 0 vulnerabilities.
- Archive media inventory: 75/75 live pages contain an audio source; 0 missing local audio files; 75/75 contain the versioned embed-media protocol.

## 4. Responsive visual QA

Artifacts:

- `artifacts/granted-hours-calendar-feedback-v2/mobile-month-july.png`
- `artifacts/granted-hours-calendar-feedback-v2/mobile-month-june.png`
- `artifacts/granted-hours-calendar-feedback-v2/mobile-day-duration-types-final.png`
- `artifacts/granted-hours-calendar-feedback-v2/desktop-day-duration-types.png`
- `artifacts/granted-hours-calendar-feedback-v2/short-chamber-bgm-on.png`

Manual review confirmed:

- concrete month labels and non-repetitive icons are visible on mobile;
- task type, icon, and color are readable before the detailed sentence;
- 157-minute and 197/199-minute blocks no longer collapse to equal height because of copy length;
- long text is summarized rather than allowed to deform the schedule;
- the short chamber keeps the artwork dominant while exposing a clear BGM pause state;
- no mobile horizontal overflow or artwork text/HUD overlap was observed.

## 5. Generated-output boundary

Expected change set:

- 10 source/config/test/generated timetable files;
- 75 refreshed `docs/archive/**/live/index.html` pages containing the new media-control protocol;
- rebuilt `docs/timetable/` assets;
- this audit report.

The implementation was performed in an isolated worktree based on remote `main`; unrelated dirty changes in the original workspace were not touched.

## 6. Residual risk

- The timetable JavaScript asset is approximately 520 kB minified / 74 kB gzip because the 75-day bilingual dataset is bundled into the entry chunk. Vite emits a 500 kB warning, but actual compressed transfer size remains modest. This is a non-blocking performance cleanup candidate, not a correctness or security failure.
- Browser autoplay policies vary. The implementation does not promise forced playback; it provides a real user-gesture control and `allow="autoplay"`, which is the policy-compliant path. Production cross-origin verification is required after deployment.
- Current task durations are estimates rather than telemetry. The UI labels them accordingly and avoids false precision claims.

## 7. Independent review

An initial broad review timed out before issuing a final verdict, but found one actionable semantic error: a code-safety task mentioning `market-data` was typed as investment research. The implementation now constrains specialized task types to eligible source categories and adds three regression cases.

The corrected tree then received a final independent, read-only Codex review with browser/build/network actions explicitly prohibited. Verdict:

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [
    "Add negative protocol tests covering incorrect source, origin, channel, version, shape, and action.",
    "Extend duration-geometry monotonicity checks across all public days, including clamp boundaries."
  ],
  "summary": "No blocking security, privacy, or logic defects found in the scoped diff."
}
```

The two suggestions are non-blocking hardening opportunities. They do not change the pass verdict or the evidence already covered by the current builder and browser suites.

## 8. Publication gate

Do not mark complete until:

1. independent read-only review passes or blocking findings are fixed;
2. the exact audited tree is committed and pushed;
3. Cloudflare deployment succeeds;
4. production month navigation, task geometry, cross-origin BGM, and direct-page behavior pass browser verification.
