# Soft palette + responsive typography evidence

## Outcome

Category color now behaves as reflected light in the existing glass system: theme-aware semantic hue is mixed at 6–10% into mineral surfaces, 24–38% into resting edges (with a stronger mineral/private-reminder edge), and 56% only for hover, focus, or selection. Whole-card opacity is fixed at `1`; neutral theme ink carries titles and narrative copy; category color is reserved for restrained icons, time/meta, rules, and edges. Focus rings, redaction bars, accessibility semantics, and privacy projection were not weakened.

A shared `clamp()` scale now covers the home display, day dialog, task detail, inspection lens, bilingual card titles, summaries, time/category/meta, and supporting copy. The narrow mobile climate title uses a compact 9.5px/1.15 treatment while its summary/body grows to 10px and meta to 9px, so the longest bilingual label and at least four summary lines remain readable without changing exact footprints.

## Before / after metrics

All measurements are actual Chromium computed styles or rendered composite pixels from `scripts/qa_timetable_visual_balance.mjs`.

| Metric | Baseline | After | Change |
| --- | ---: | ---: | ---: |
| Home display heading | 57px | 44px | −22.8% |
| Day-dialog heading | 42px | 33.984px | −19.1% |
| Task-detail heading | 34px | 28.8px | −15.3% |
| Inspection-plate heading | 29px | 23px | −20.7% |
| Desktop supporting-copy mean | 11.6px | 13.103px | +13.0% |
| Desktop card-title mean | 11px | 13.71px | +24.6% |
| Desktop card-body mean | 8.5px | 11.232px | +32.1% |
| Desktop card-meta mean | 7.333px | 9.833px | +34.1% |
| Mobile home/day supporting mean | 9.4px | 11.6px | +23.4% |
| Mobile card-title mean | 10px | 11.063px | +10.6% |
| Mobile card-body mean | 8.5px | 10px | +17.6% |
| Mobile card-meta mean | 7.333px | 8.833px | +20.5% |
| Task supporting-copy mean | — | — | +16.7% |
| Lens supporting-copy mean | — | — | +17.1% |
| Dark surface-to-panel distance | 33.356 | 18.073 | −45.8% |
| Light surface-to-panel distance | 27.376 | 12.419 | −54.6% |

Small-text contrast remains WCAG AA: minimum 8.433:1 in dark and 5.493:1 in light in the balance audit. Minimum semantic accent separation is 55.000 (dark) / 57.801 (light), and rendered edge separation is 21.956 / 25.140. Every representative category surface moved at least 24.5% closer to its panel. In dark, the loudest climate sample scores 77.853 while every active sample is at least 80.289; in light those values are 64.719 and 71.880. The complete per-category rendered RGB, border, contrast, font-size/line-height, overflow, and footprint geometry records are in:

- `audits/soft-palette-typography/baseline/metrics.json`
- `audits/soft-palette-typography/after/metrics.json`

Exact footprint count, start/end, duration, lane/lane-count, top, height, left, and width are unchanged within 0.26px. No horizontal/text-fit failure was found at desktop, 390×844, or 421×386 across card titles/summaries/meta, task-detail copy, or inspection-lens copy. Vertically scrollable task panels are distinguished from clipped text in the recorded fit samples.

## Screenshots

Baseline and after evidence are intentionally separate. Each `metrics.json` contains the exact repository-relative screenshot list and asserts a closed, empty inspection-lens state before every resting capture.

- `audits/soft-palette-typography/baseline/`: 11 calendar, day, task, and intentional-lens captures at desktop dark/light, 390×844, and 421×386.
- `audits/soft-palette-typography/after/`: the same 11 final-state captures.
- `audits/soft-palette-typography/hover-regression/evidence-manifest.json`: exact intentional assigned, autonomous GIF, light support lens, two timed GIF frames, and coarse-pointer resting captures.

The hover manifest proves two different rendered GIF-frame hashes, same-origin decoded GIF priority, static fallback under reduced motion, typographic fallback after media failure, viewport containment, closed resting lenses, hybrid mouse/touch/pen synchronization, and first-tap-select/second-tap-open at 390×844 and 421×386.

## QA results

Passed:

- `python3 scripts/test_timetable_builder.py` — 25 tests.
- `python3 scripts/test_timetable_pulse_importer.py` — 5 tests.
- `node scripts/test_timeline_layout.mjs` — 5 cases.
- `node scripts/qa_timetable_unified_timeline.mjs` — 75 days.
- `node scripts/qa_timetable_privacy_fixture.mjs` — isolated fixture, canonical output untouched, DOM/attributes/accessibility/log/OCR surfaces scanned.
- `node scripts/qa_timetable_public_hierarchy.mjs` — 2026-07-21 and 2026-07-22 across 1440×900, 1024×768, 768×700, 390×844, and 421×386.
- `node scripts/qa_timetable_hover_preview.mjs` — dark/light lens, real GIF progression, load/decode fallbacks, reduced motion, keyboard, hybrid pointer, touch, pen, and focus return.
- `node scripts/qa_timetable_true_calendar.mjs`.
- `node scripts/qa_timetable_temporal_composition.mjs` — five viewports, 2,698 routine records; the canonical popup request is fulfilled inside Playwright so the exact `from=timetable` URL assertion has no remote GET dependency.
- `node scripts/qa_timetable_themes.mjs`.
- `node scripts/qa_timetable_calendar_enrichment.mjs`.
- `node scripts/qa_timetable_dialog_full_artwork.mjs`.
- `node scripts/qa_timetable_regressions.mjs`.
- `node scripts/qa_timetable_visual_balance.mjs` in baseline and after modes.
- `node scripts/qa_timetable_release_evidence.mjs` — two byte-identical isolated builds and exact canonical parity.
- `python3 scripts/check_public_safety.py --root .`.
- `npm audit --omit=dev --audit-level=high` — 0 vulnerabilities.
- `git diff --check`.

The privacy and public-hierarchy screenshot suites ran in isolated temporary mirrors so their prior audit directories were not overwritten. No remote, Git-history, deployment, or external write occurred.

## Canonical build

| Asset | Baseline bytes / gzip | After bytes / gzip | Change |
| --- | ---: | ---: | ---: |
| JavaScript | 4,346,752 / 273,657 | 4,346,752 / 273,657 | unchanged |
| CSS | 79,920 / 15,147 | 92,594 / 16,424 | +12,674 / +1,277 |
| `index.html` | 7,927 | 7,927 | unchanged |

The JavaScript SHA-256 is unchanged. The generated canonical filenames and current deterministic evidence are recorded in `audits/public-readable-hierarchy/release-evidence.json`.

## Changed-file inventory

Authored:

- `src/timetable/styles.css`
- `scripts/qa_timetable_visual_balance.mjs`
- `scripts/qa_timetable_temporal_composition.mjs`
- `audits/soft-palette-typography/README.md`
- every exact screenshot/JSON path enumerated by `baseline/metrics.json`, `after/metrics.json`, and `hover-regression/evidence-manifest.json`

Regenerated:

- `docs/timetable/index.html`
- removed `docs/timetable/assets/index-BLIC1OwA.css`
- removed `docs/timetable/assets/index-Bsn4nEYs.js`
- added `docs/timetable/assets/index-DPn2lVXW.css`
- added `docs/timetable/assets/index-OfJxPr3M.js`
- `audits/public-readable-hierarchy/release-evidence.json`

## Blockers and residual risk

No blocker. Vite still reports the existing large-chunk warning, but JavaScript bytes and hash are unchanged and remain below both release budgets. The CSS adds 1,277 gzip bytes for the theme-aware color and responsive type systems. The baseline evidence predates a served-asset hash field; its phase/configuration, separate screenshots, computed metrics, and pre-edit capture remain intact.
