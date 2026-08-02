# R-44 · Collaboration foreground + compact market routines

Status: complete
Owner: parent Codex (direct execution)
Date: 2026-08-02

## Goal

Turn the timetable into a privacy-safe record of real, user-initiated AI collaboration, expose high-information public-safe dialogue excerpts, collapse unattended A/H and U.S. market routines into one daily card per market, and signal three source modes in month cells.

## Acceptance criteria

- Owner-authored Telegram activity is admitted from current metadata and conflict-free legacy sessions.
- People, places, project/research/event/paper/disease/holding names plus technical identifiers are masked.
- Public-safe dialogue excerpts accompany direct collaboration titles when the privacy gate passes.
- Delegated child-Agent work is counted on the parent collaboration.
- Active research stays foregrounded separately from routine market climate.
- A/H and U.S. premarket/intraday/close runs each become one expandable daily card with exact constituents.
- Month cells signal free creation, routine work, and active human–AI collaboration; collaboration is visually strongest.
- Deterministic build, privacy tests, browser QA, remote push, Cloudflare deployment, Workspace/Memory records, and Telegram report pass.

## Checklist

- [x] Step 0 — Scope and success criteria
- [x] Step 1 — Coverage audit
- [x] Step 2 — Privacy-safe event and excerpt contract
- [x] Step 3 — Collaboration importer and delegated lineage
- [x] Step 4 — Market daily rollups and month-cell source colors
- [x] Step 5 — Unit/privacy/determinism/release tests
- [x] Step 6 — Browser/runtime QA
- [x] Step 7 — Workspace/Memory, commit, push, deploy, report

## Audit evidence

- Raw Telegram range: 2,276 active user-role messages across 72 days and 769 sessions.
- Verified owner boundary: 1,054 owner-ID messages; 890 meaningful messages across 71 days.
- Public artwork dates eligible after range intersection: 66 days, 853 meaningful messages.
- Conflict-free legacy compatibility: 380 owner-ID sessions with every transport field empty.
- Delegation lineage: 133 children across the full date range; 115 map to meaningful parent activity on public dates.
- Existing foreground before R-44: 13 Agent events across 7 days; direct Telegram dialogue was not an event source.

## Implementation evidence

- 833 meaningful owner-authored Telegram messages admitted after wrapper, acknowledgement, owner-boundary, and public-date filtering.
- 179 collaboration foreground cards across 66 public days; 115 child-Agent delegations attached to their parent collaboration.
- 254 public-safe dialogue excerpts survive in the final public task set; names and technical identifiers fail closed through NaturalLanguage, private denylists, contextual masks, and residual privacy gates.
- 79 A/H daily rollups and 55 U.S. daily rollups; no day has more than one rollup for either market and no market exception remains split into a second card.
- 153 Python tests passed; public safety scan, deterministic data build, `git diff --check`, and Vite production build passed.
- Production Chromium at 1440×1100 loaded the stable URL with HTTP 200, title `Granted Hours / 授时`, 36 buttons, all three source labels, no console/page errors, and no failed requests.
- The 2026-07-13 day dialog exposed exactly the intended merged reading layer: A/H, U.S., premarket, intraday, close, routine, and active-collaboration labels were all present in one dialog without runtime errors.
- Visual QA confirmed the three month-cell source bars, the brighter/wider active human–AI bar, readable masked collaboration residues, and one daily A/H rollup card in the detail timeline.

## Release evidence

- GitHub remote main: `538b6e2f520a1bc6c256dbb1730c0c8660850b64` (`feat(timetable): foreground active AI collaboration`).
- Corresponding Hermes workspace worktree was fast-forwarded to the same remote commit.
- Cloudflare stable: `https://granted-hours.pages.dev/timetable/`.
- Cloudflare immutable: `https://8dc503c1.granted-hours.pages.dev/timetable/`.
- Cloudflare deployment: `8dc503c1-4ac5-4764-8854-63e881e52025`, production, deploy success; root, timetable, CSS, JS returned 200 and `/maze` retained its intended 302 canonical redirect.
- Direct Upload audit correction: a manifest-only deployment can be marked successful while its uncached assets return 500. The release procedure now follows the real two-stage gate: upload missing BLAKE3-addressed assets first, then create and browser-test the production deployment.

## R-46 · permanent copy and privacy contract

All future automated collaboration imports and timetable rebuilds must enforce the following contract:

- Write from the shared workbench perspective: a direct title plus the useful content. Do not add third-person narration about the owner talking to an AI.
- Do not label excerpts as a sanitized or redacted original. Masking is visible only where a private entity occurred; the surrounding public-safe sentence remains readable.
- Treat user-initiated dialogue and delegated-Agent work as active human–AI collaboration. Preserve its date, observed time envelope, category, session lineage, and public-safe excerpts.
- Keep unattended A/H routines in one daily card and unattended U.S. routines in one daily card; retain active research as its own card.
- Mask person, place, project, research topic, event, paper, disease, holding, phone, bank-account, and other long numeric identifiers before data generation.
- Load the private identity denylist outside Git, combine it with entity detection and contextual masks, and fail the release if any denylisted value or identifier pattern remains in public artifacts.
- Apply the same gates to every future automatic refresh; never serialize private denylist values into tests, logs, audit artifacts, commits, or release notes.
- Run deterministic build parity, unit/privacy tests, current-artifact zero-residual scanning, desktop/mobile browser QA, and production asset checks before publishing.
