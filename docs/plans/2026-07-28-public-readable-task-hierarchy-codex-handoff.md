# Codex handoff — public-readable task hierarchy

## Objective
Refine Granted Hours day-detail so repeated routines become a subdued readable climate layer, active conversations/work stay foreground, vague internal labels are renamed/aggregated/omitted, and private reminders can appear as truthful redacted residues without exposing raw private content.

## Required runtime
- Implement with Codex `gpt-5.6-sol`, reasoning `xhigh` (Simon calls this GPT-5.6-SOL Ultra).
- Work only in this isolated worktree.
- Do not commit, push, deploy, or edit other worktrees/profile memory.

## User intent
1. Dates such as 2026-07-21 and 2026-07-22 contain many A/H or U.S. market scans. The frequency is truthful, but those cards visually bury active dialogue/work.
2. Repeated routines should behave as **climate**, not headline events.
3. Completely incomprehensible tasks have no public reason to appear as individual cards. Translate them into truthful functional public language, aggregate them, or omit the individual reading card.
4. Daily/private reminders may be shown as redacted sentences: preserve action, syntax, time/relationship structure when safe; replace identifying nouns with fixed-length blocks. The result should attract attention without revealing the concrete person/project/place/amount/private matter.
5. Exact 24-hour event geometry remains truthful and all source routine occurrences remain auditable in the footprint layer.

## Conceptual hierarchy
- **Climate layer / 气候层**: repeated routine activity, translucent and visually subordinate.
- **Event layer / 事件层**: active dialogue, judgment, creation, research and actions, opaque and foreground.
- **Absence layer / 缺席层**: public-safe redacted private reminders; medium prominence, visible sentence skeleton.
- **Beacon layer / 灯塔层**: autonomous AI self-time/artwork, highest distinctness.
- Routine exceptions that changed the day (anomaly, upgrade, alert, generated follow-up/action) should be promoted from climate to event.

## Non-negotiable truth/privacy contracts
1. Keep exact footprint `top`, `height`, concurrency lanes, date, start/end and count. Do not use min-height on truthful footprint geometry.
2. Group/merge only the **reading layer**, never erase source occurrences from the footprint/data audit layer.
3. Prefer semantic-window groups over one all-day blob: e.g. A/H premarket/intraday/close; U.S. premarket/intraday/close. Derive windows deterministically from existing task labels/times.
4. Never fabricate a public meaning. A vague job may be renamed only when its existing source/evidence identifies a truthful function; otherwise aggregate as a low-prominence infrastructure group or omit its individual reading card.
5. Redact before public serialization. Raw private text must never enter generated timetable data, DOM, `aria-*`, `title`, data attributes, source maps, built JS, logs, screenshots or committed fixtures.
6. Fixed redaction blocks must not reveal original token length or stable cross-day identity. Do not implement CSS blur, hover reveal, click-to-unmask, reversible encoding or pseudonymous linkage.
7. Ownership gate comes before redaction: activity belonging to another person remains excluded, not converted into an intriguing masked item.
8. Inspect only project-relevant timetable generation inputs and routine/reminder evidence. Do not trawl unrelated chats, credentials or personal files. If no authorized reminder source exists, implement the safe redaction pipeline with synthetic fixtures and improve only existing public reminder records—do not invent or import private material.

## Required implementation behavior
### Climate aggregation
- On 2026-07-21 and 2026-07-22, reduce repeated market/routine reading-card dominance materially while retaining every exact footprint.
- Render one readable group per deterministic semantic family/window where useful, including bilingual title, time span, occurrence count and concise date-specific outcome summary.
- Default climate cards/fields to low contrast and translucency; active/event/absence/beacon cards remain clearly above them.
- Provide accessible expand/collapse or drill-down to inspect individual routine occurrences without reflowing/falsifying exact footprints.
- Highlight matching footprints as a group on focus/touch/mouse; preserve keyboard focus precedence, hybrid pointer behavior and reduced motion.

### Readability gate
Each independent visible reading item must answer: what happened, when, and why it matters. Ban foreground titles whose only meaning is `后台例行任务`, `系统例行任务`, `静默检查` or equivalent internal exhaust unless followed by a truthful readable function.

Implement a deterministic public narrative classifier/projection with outcomes:
- foreground event;
- climate aggregate;
- redacted reminder residue;
- hidden individual reading item (footprint retained);
- promoted routine exception.

### Redacted reminders
Use a stable public-safe format such as:
- `私人提醒 / Private reminder`
- `下午联系 ███，确认 ███ 的下一步。`
Preserve verbs and relational structure only when source evidence makes them safe. Use a small explicit sanitization vocabulary/policy and synthetic positive/negative fixtures. The exact example is not mandated.

## Visual direction
- Maintain the sharp mineral `Temporal Composition` system; no return to generic rounded dashboard cards.
- Climate layer should consume roughly 20–30% visual attention regardless of event count; active work should dominate.
- Use opacity, z-depth, border strength, typography and spacing—not deletion of time evidence—to establish hierarchy.
- Redaction bars are compositional negative space, not glitch effects or sensational secrecy.

## Required tests
1. Preserve existing timeline-layout, true-calendar, temporal-composition, theme, reduced-motion, touch, hybrid pointer, accessibility and public-safety tests.
2. Add focused tests for 2026-07-21 and 2026-07-22:
   - every raw occurrence retains an exact footprint;
   - climate reading groups are fewer than their constituent repeated routines;
   - no reading-card collision or horizontal overflow across `1440×900`, `1024×768`, `768×700`, `390×844`, `421×386`;
   - active/assigned event contrast and stacking outrank climate groups;
   - group expansion reveals readable constituent occurrences and closes/restores focus correctly;
   - exception promotion works from explicit evidence;
   - vague internal labels do not survive as standalone foreground titles;
   - synthetic private reminder names/projects/amounts are absent from all generated/build outputs, DOM and accessible names, while a fixed redacted sentence remains visible;
   - fixed bars do not encode secret length.
3. Run deterministic build twice and compare output hashes.
4. Generate QA screenshots for 2026-07-21 and 2026-07-22 at desktop, mobile and short-touch. Inspect for information hierarchy, not only geometry.
5. Run public-safety scan and `npm audit --omit=dev --audit-level=high`.

## Expected files
Likely areas (inspect before deciding):
- `src/timetable/main.js`
- `src/timetable/styles.css`
- `src/timetable/timeline-layout.js`
- timetable builder/importer/public-safe projection scripts
- focused QA/unit scripts
- generated `docs/timetable/**`
Do not change raw archive art/media unless required for this UI.

## Completion report
Return:
- exact files changed;
- classification/redaction/aggregation rules implemented;
- real counts on 2026-07-21 and 2026-07-22 before vs after reading-layer aggregation;
- tests and real command outputs;
- screenshot paths;
- privacy proof (which synthetic secrets were verified absent);
- remaining risks.
Do not commit, push or deploy.
