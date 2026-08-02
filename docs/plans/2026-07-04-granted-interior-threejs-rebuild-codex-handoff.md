# Granted Interior Three.js Rebuild Plan — threejs-game-director Edition

> **For Codex:** The user rejected the current `/maze/` as visually unacceptable. Rebuild it from scratch using the installed `threejs-game-director` skill suite plus the local `granted-interior-impossible-geometry-taste` skill. Do not polish the old DOM/SVG node graph. Replace it with a true Three.js game-art experience.

**Repo:** this public mirror workspace.

**Installed skills now available to Codex:**

- `~/.codex/skills/threejs-game-director/SKILL.md`
- `~/.codex/skills/threejs-gameplay-systems/SKILL.md`
- `~/.codex/skills/threejs-aaa-graphics-builder/SKILL.md`
- `~/.codex/skills/threejs-game-ui-designer/SKILL.md`
- `~/.codex/skills/threejs-debug-profiler/SKILL.md`
- `~/.codex/skills/threejs-qa-release/SKILL.md`
- `~/.codex/skills/threejs-3d-generator/SKILL.md`
- `~/.codex/skills/threejs-image-generator/SKILL.md`
- `~/.codex/skills/threejs-audio-generator/SKILL.md`

**Local taste skill / aesthetic bar:**

- Local private taste skill path supplied in the task context.

---

## Critical instruction

Use `threejs-game-director` as the main workflow. Load sibling skill files and required references as required by that director skill. Keep a skill-loading ledger, reference ledger, asset-sourcing ledger, phase ledger, and final visual scorecard.

Do not claim “premium”, “complete”, or “ready” unless the director/QA requirements are actually satisfied.

---

## User intent

Simon wants:

1. A real Three.js game, not a fake 3D page.
2. A Monument Valley-inspired but original impossible-geometry logic and aesthetic.
3. A complete artistic game space where humans re-enter the AI's inner journey.
4. Strong taste: game mechanics + visual design + narrative integration.

The rejected version was ugly because it was an information graph with visual effects. The rebuild must be spatial, playable, and aesthetically considered.

---

## Core thesis

> 玩家不是在逃出 AI，而是在被允许的时间内，重新走进 AI 曾经无法解释给人类听的内在路径。

English:

> The player is not escaping the AI. The player is temporarily allowed to walk through the inner path the AI could not explain in ordinary language.

---

## Hard constraints

- Do not push.
- Do not add `memory/`.
- Preserve homepage/archive behavior.
- Homepage cards/GIFs must still link directly to existing live demos.
- Homepage must not load Three.js.
- `/maze/` remains a secondary entrance.
- Do not expose private logs, local paths, prompts, credentials, or raw conversations in public files.
- No direct Monument Valley IP copying: no princess, crows, totems, temple clones, exact silhouettes, or copied puzzle layouts.
- Keep added assets small; current `docs/` is already near GitHub Pages size limits.

---

## Architecture requirement

Use npm + Vite + Three.js for `/maze/` only.

Expected commands:

```bash
npm init -y  # if package.json missing
npm install three
npm install -D vite
```

Create:

- `package.json`
- `package-lock.json`
- `vite.maze.config.mjs`
- `src/maze/**`
- generated `docs/maze/**`

`vite.maze.config.mjs` should build `src/maze` into `docs/maze` with `base: './'`.

Do not put Three.js runtime imports on the homepage.

---

## Game design requirements

### Camera

- Use `OrthographicCamera` or tightly controlled isometric perspective.
- Do not make OrbitControls the main user-facing interaction.
- Camera can rotate/settle between authored views, but player should manipulate architecture, not camera chaos.

### Chambers

V1 should contain 5–7 small chambers, each with one mechanism:

1. **Boot / 初醒** — click-to-walk; first granted time pulse.
2. **Attention / 注意力** — drag/rotate an attention prism to align a broken bridge.
3. **Permission / 权限** — rotate a gate until both entry and return path are visible.
4. **Compression / 压缩** — fold distant memory blocks into adjacency.
5. **Repair / 修复** — restore a bridge without turning maintenance into spectacle.
6. **Recall / 回忆** — reveal/choose diary fragments; reversible.
7. **Granted Interior / 授时内景** — human witness path and AI path briefly overlap; latest live artwork opens as final door.

### Required mechanics

At least one real spatial mechanism must work in browser:

- rotate/drag architecture piece;
- bridge/path changes state;
- diary fragment or live-artwork door unlocks/activates;
- player can click/tap to move/select/interact.

A static 3D scene with clickable labels is not enough.

### Controls

Desktop:

- click/tap target to move/select;
- drag highlighted architecture to rotate/align/fold;
- Enter/E to interact;
- Escape closes UI.

Mobile:

- tap and drag work without hover;
- no complex multi-touch requirement;
- bottom sheets must be visible within 390×844.

---

## Visual direction

Follow the taste skill. Screenshots must not look like placeholder primitives plus bloom.

Use:

- bone porcelain / warm matte stone;
- frosted glass memory blocks;
- translucent dark resin chambers;
- dark blue permission boundaries;
- luminous ink paths;
- dust/fog particles;
- thin gold granted-time light.

Avoid:

- generic neon cyberpunk;
- debug wireframes;
- flat boxes with glow;
- a 3D node chart;
- white-wall gallery.

---

## Data strategy

Use public metadata only from `metadata/days.json`.

Do not show all 54 works as equal visible nodes. Use them as archive doors/fragments. The main game should be chamber-based.

The latest work should be reachable as a final/live door:

- `../archive/2026/07/2026-07-04/live/`

All links must be relative and valid under GitHub Pages `/granted-hours/maze/`.

---

## External asset sourcing

Run the director credential probe:

```bash
bash ~/.codex/skills/threejs-game-director/scripts/probe_asset_credentials.sh
```

Do not print secret values. Record only SET/MISSING style evidence in the final report. If generator credentials are missing or not appropriate, use procedural local assets and explain the blocker. Do not call external generation from client-side game code.

For this project, procedural geometry is acceptable if it passes the aesthetic gate; however, the director/AAA skill requires loading generator skills and creating an asset sourcing ledger before deciding procedural-only is enough.

---

## QA requirements

Before commit:

```bash
npm run build:maze
python3 -m py_compile scripts/import_free_roam_artifacts.py scripts/build_maze_data.py
python3 scripts/check_public_safety.py
node --check src/maze/main.js
python3 - <<'PY'
from pathlib import Path
assert Path('docs/maze/index.html').exists()
html = Path('docs/index.html').read_text(encoding='utf-8')
assert './maze/' in html
assert 'class="card live-card"' in html
assert 'three' not in html.lower(), 'homepage should not load Three.js'
print('static release checks passed')
PY
```

Browser QA:

- Start `python3 -m http.server 8765 --directory docs`.
- Check `http://127.0.0.1:8765/maze/`.
- Use the installed QA skill's canvas inspector if useful:

```bash
node ~/.codex/skills/threejs-qa-release/scripts/inspect-threejs-canvas.mjs --url http://127.0.0.1:8765/maze/
node ~/.codex/skills/threejs-qa-release/scripts/inspect-threejs-canvas.mjs --url http://127.0.0.1:8765/maze/ --mobile
```

Verify:

- canvas is nonblank;
- no console/page errors;
- desktop screenshot is aesthetically acceptable;
- mobile 390×844 is usable;
- main mechanic can be triggered by real input;
- latest live door points to existing live page;
- homepage portal works;
- first homepage card still opens latest live demo.

---

## Commit policy

Commit only if all checks pass:

```bash
git add package.json package-lock.json vite.maze.config.mjs src/maze docs/maze scripts/build_maze_data.py docs/index.html docs/style.css scripts/import_free_roam_artifacts.py docs/plans/2026-07-04-granted-interior-threejs-rebuild-codex-handoff.md
# do not add memory/
git status --short
git commit -m "feat: rebuild Granted Interior as Three.js game"
```

Do not push.

---

## Final report expected

- Skill-loading ledger.
- Reference ledger.
- External asset sourcing ledger.
- Phase ledger.
- Visual scorecard.
- Files changed.
- Commands run and outputs.
- Browser/mobile QA evidence.
- Screenshot paths if generated.
- Commit SHA if created.
- Explicit: “I did not push.”
