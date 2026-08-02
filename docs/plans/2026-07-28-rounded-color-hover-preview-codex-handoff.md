# Codex handoff — rounded semantic color + hover inspection lens

## Objective
Polish Granted Hours timetable day detail with rounded time blocks, an Apple-UI-inspired moderately saturated semantic palette, and a desktop hover/focus inspection lens that enlarges each event’s visual—especially autonomous AI artwork with GIF/video motion—without changing exact calendar truth or the approved public-readable hierarchy.

## Execution contract
- Work only in this isolated worktree.
- Implement with TDD; inspect actual code/data/assets before deciding media behavior.
- Do not commit, push, deploy, or edit other worktrees/Hermes memory/config.
- Preserve the public-readable hierarchy, ownership-before-redaction, privacy fixture, deterministic build evidence, and exact 24-hour footprint geometry from commit `9fadbdb`.
- Do not stop at an engineering demo: the result must be visually polished and production-grade.

## User intent
1. Every visible time/event block should have rounded corners.
2. Different content types should use distinct colors. Raise saturation slightly but keep it refined; use Apple UI as a palette reference, not a literal copy or a neon rainbow.
3. Hovering an event with a fine pointer should automatically reveal a larger visual preview.
4. Autonomous AI creation events with video/GIF motion are the priority: motion should actually play in the inspection lens when public-safe media exists.

## Visual direction
### Rounded geometry
- Reading cards: refined 10–14px radius.
- Exact metric footprints: subtle 3–6px radius so they remain metric traces, not pills.
- Inspection lens: 16–20px radius, deep material surface, restrained shadow and hairline.
- Keep the timeline’s constructivist/temporal composition; do not turn it into a generic dashboard.

### Semantic Apple-adjacent palette
Create theme-aware CSS tokens and deterministic category/classification mapping. Suggested roles:
- active assigned/dialogue/work: blue;
- A/H scan: green/mint;
- U.S. scan: cyan/blue;
- AI brief: orange;
- service/support climate: indigo;
- private reminder absence: purple/pink;
- promoted warning/exception: coral/red;
- autonomous beacon/artwork: gold/cyan depending current motif.

Dark reference hues may start near `#0A84FF`, `#30D158`, `#64D2FF`, `#FF9F0A`, `#5E5CE6`, `#BF5AF2`, `#FF453A`; light reference hues may start near `#007AFF`, `#34C759`, `#32ADE6`, `#FF9500`, `#5856D6`, `#AF52DE`, `#FF3B30`. Mix into the project’s mineral surfaces rather than filling cards with pure system color. Accent/border can be more saturated; backgrounds should stay around a restrained tint. Maintain useful contrast in both themes and keep climate visually behind event/absence/beacon.

Colors must encode content, not lane position or random index. Add a stable `data-category`/role hook where needed.

## Hover/focus inspection lens
Use a fixed/viewport-collision-aware inspection lens, not a giant cursor-following tooltip. It must feel connected to the hovered event and avoid covering its trigger where feasible.

### Behavior
- Fine pointer: `pointerenter`/hover shows automatically; moving to another card updates the lens; pointerleave hides after a short non-jitter delay.
- Keyboard focus may show the same visual enhancement, but essential semantics already remain on the card/detail dialog, so avoid duplicate screen-reader narration.
- Coarse pointer/mobile: no hover lens and no interference with the existing first-tap-select/second-tap-open contract.
- Day dialog scroll/close/Escape and page navigation hide the lens.
- Lens is visual enhancement, not the only way to reach content; keep cards clickable/focusable.
- Prefer `pointer-events:none` unless product behavior truly requires lens controls.

### Media resolution order
Audit the actual corpus and implement a public-safe resolver:
1. direct public same-origin video URL if already present in canonical metadata and safe → `<video muted autoplay loop playsinline>`;
2. text-free animated GIF/webp preview if available → animated `<img>`;
3. decoded static preview/poster;
4. if an event has no public visual asset, show a larger semantic typographic plate with color, title, time and concise summary—do not fabricate imagery.

Autonomous AI creation must preferentially use its motion asset. Do not embed the full live page/iframe in a hover lens.

### Motion, fallback, performance
- Lazy-load lens media only on hover/focus; do not preload every GIF/video.
- Under `prefers-reduced-motion: reduce`, use an audited static poster and disable lens transitions/autoplay.
- On video/GIF/image decode/load failure, fall back to the static preview, then typographic plate; never leave a broken icon.
- Reset/stop video when hidden or switching events.
- No layout shift; lens stays inside viewport and above the dialog while not clipping under its scroll root.

## Data/public safety
- Do not expose raw reminder source text in preview labels, alt text, `aria-*`, data attributes, title attributes, logs or media URLs.
- Other-person activity remains excluded before redaction.
- No image generation is required. Use only existing audited public assets and semantic typographic fallback.
- If existing media metadata is insufficient for direct video, do not invent a URL; prioritize existing GIF/static previews.

## Required TDD/QA
Create or extend focused Playwright QA covering:
1. Computed border radius for every reading card and exact footprint at desktop/light/dark/mobile.
2. Representative categories have distinct deterministic computed accent colors; climate remains lower salience than foreground; contrast remains readable.
3. Fine-pointer hover shows lens, updates when moving between cards, hides on leave/scroll/close/Escape, remains in viewport, does not cover trigger where feasible, and creates no horizontal overflow.
4. AI autonomous event loads a decoded/enabled motion preview when a GIF/video exists; prove GIF/video URL/type and successful media readiness. Static fallback works after forced media failure.
5. `prefers-reduced-motion` uses static preview and no autoplay/animated asset.
6. Coarse pointer `390×844` and `421×386` does not show hover lens and preserves first-tap-select/second-tap-open.
7. Keyboard focus and detail-dialog focus-return behavior remain correct.
8. Exact footprint top/height/lane equations and public-readable 7/21–7/22 counts are unchanged.
9. No console/page/request failures, no private fixture string in source/bundle/DOM/accessibility/logs, public safety and npm audit pass.
10. Build twice and prove canonical `docs/timetable` parity and size budgets.

Capture intentional screenshots (outside commit unless documenting release evidence):
- 7/21 desktop dark with assigned hover lens;
- 7/21 desktop with autonomous GIF/video lens visible;
- 7/22 desktop light with a market/support event lens;
- 390×844 and 421×386 no-hover resting states.

## Existing commands to preserve
- `python3 scripts/test_timetable_builder.py`
- `python3 scripts/test_timetable_pulse_importer.py`
- `node scripts/test_timeline_layout.mjs`
- `node scripts/qa_timetable_privacy_fixture.mjs`
- `node scripts/qa_timetable_release_evidence.mjs`
- `node scripts/qa_timetable_public_hierarchy.mjs`
- all existing timetable QA scripts
- `python3 scripts/check_public_safety.py`
- `npm audit --omit=dev --audit-level=high`
- `git diff --check`

## Completion output
Return:
- files changed and design mapping;
- hover resolver/media behavior and actual audited examples;
- exact before/after bundle size evidence;
- all test commands/results;
- screenshots and viewport evidence;
- any residual risk.
