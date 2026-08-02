# Granted Hours UI brief — 时间构成 / Temporal Composition

## Intent
把日详情从“卡片塞进日历”重构成一张可浏览的平面构成：真实时间是骨架，可读浮签是观看装置。借鉴蒙德里安的分割、非对称平衡、矩形张力与留白，但不复制其红黄蓝配色或画面。

## Core contract
1. **Footprint layer / 时间足迹层**
   - `top = startMinute × minuteHeight`
   - `height = durationMinutes × minuteHeight`
   - overlap lanes remain exact and deterministic
   - one-minute events remain one-minute visual marks; no fake visual duration
2. **Reading layer / 阅读构成层**
   - every event gets a readable rectangular label/card independent of the exact footprint height
   - routine cards always expose bilingual title + concise date-specific summary; never hide all copy into a hairline
   - assigned cards retain title/type + summary
   - autonomous card may be taller than its exact 60-minute footprint and includes the audited animated/static visual preview
   - a visible connector/registration mark ties each reading card back to the exact footprint
3. **Activation / 激活**
   - mouse hover and keyboard focus bring a card forward and slightly enlarge it
   - first coarse-pointer tap selects/enlarges the card; second tap opens the existing event detail (or live artwork for autonomous work)
   - tapping elsewhere clears selection
   - selected state uses `aria-expanded`/accessible copy and must not require hover
4. **Composition / 平面构成**
   - sharp rectangular planes, firm structural rules, deliberate asymmetry, and meaningful negative space
   - duration/density remain visible underneath the labels; the reading layer must not turn the day back into a vertical list
   - dark palette: graphite/black-blue field, bone typography, mineral cyan, oxidized gold, ash green, restrained rust/violet accents
   - light palette: warm mineral paper/stone with charcoal, deep teal, ochre and oxidized rust
   - avoid generic glass pills, rounded SaaS cards, rainbow gradients, and direct Mondrian imitation
5. **Motion**
   - one restrained transition: selected card comes forward, preview gently scales/pans
   - `prefers-reduced-motion` removes transform/animation and selects static WebP

## Implementation preference
- Keep `.timeline-event` as the exact geometry box measured by existing tests.
- Add explicit descendants/classes for `event-footprint` and `event-reading-card` (or an equivalent semantically clear split).
- Use collision-aware label placement or a deterministic editorial layout so minimum-readable cards do not hide each other. Preserve chronological orientation and keep labels inside the 24-hour canvas.
- Do not alter public data extraction/privacy logic.

## Acceptance
- At 1440×900, 1024×768, 768×700, 390×844, and 421×386 touch:
  - exact event top/height and horizontal overlap lanes still pass;
  - every background event has a visible title and non-empty summary in its reading card;
  - minimum readable routine card height is at least 48 CSS px (target 54–64 px) without changing `.timeline-event` height;
  - reading cards do not overlap each other where their horizontal ranges intersect;
  - autonomous preview card is at least 112 CSS px tall and image decodes;
  - first touch selects/enlarges; second touch opens detail/live target; keyboard focus works;
  - no horizontal overflow, page errors, inaccessible bottom content, or reduced-motion regression.
