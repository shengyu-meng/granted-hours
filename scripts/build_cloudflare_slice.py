#!/usr/bin/env python3
"""Build the small Cloudflare Pages slice for Granted Hours."""
from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "dist" / "cloudflare-pages"
TIMETABLE_SOURCE = ROOT / "docs" / "timetable"
CANONICAL_BASE = "https://shengyu-meng.github.io/granted-hours/"
REPO_URL = "https://github.com/shengyu-meng/granted-hours"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def safe_output_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    allowed_roots = ((ROOT / "dist").resolve(), Path(tempfile.gettempdir()).resolve())
    require(
        any(resolved == root or root in resolved.parents for root in allowed_roots),
        f"Output must stay under {allowed_roots[0]} or {allowed_roots[1]}: {resolved}",
    )
    require(resolved not in allowed_roots, f"Refusing to clean output root itself: {resolved}")
    if resolved.exists():
        require(resolved.is_dir(), f"Output path exists and is not a directory: {resolved}")
    return resolved


def write_root_index(output: Path) -> None:
    (output / "index.html").write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Granted Hours Cloudflare slice: living timetable and canonical archive links.">
  <title>授时 / Granted Hours</title>
  <style>
    :root {{
      color-scheme: dark;
      --paper: #eee7d7;
      --ash: #8a8478;
      --field: #03070b;
      --line: rgba(238, 231, 215, 0.18);
      --gold: #d2ad54;
      --cyan: #78d9e6;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      background:
        linear-gradient(90deg, rgba(238, 231, 215, 0.024) 1px, transparent 1px) 0 0 / 72px 72px,
        linear-gradient(180deg, #071017, #03070b 56%, #030403);
      color: var(--paper);
      font-family: "Iowan Old Style", "Songti SC", "STSong", Georgia, serif;
      letter-spacing: 0;
    }}
    main {{
      display: grid;
      align-content: center;
      width: min(100% - 32px, 920px);
      min-height: 100vh;
      margin: 0 auto;
      padding: 48px 0;
    }}
    p {{
      max-width: 720px;
      color: var(--ash);
      font-size: clamp(16px, 2vw, 21px);
      line-height: 1.65;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(48px, 11vw, 112px);
      font-weight: 500;
      line-height: 0.95;
    }}
    .mark {{
      color: var(--cyan);
      font: 12px/1.5 "SFMono-Regular", "Menlo", monospace;
      text-transform: uppercase;
    }}
    nav {{
      display: grid;
      gap: 0;
      margin-top: 28px;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }}
    a {{
      display: block;
      padding: 14px 0;
      border-top: 1px solid rgba(238, 231, 215, 0.1);
      color: var(--paper);
      text-decoration-color: rgba(210, 173, 84, 0.5);
      text-underline-offset: 0.24em;
    }}
    a:first-child {{ border-top: 0; }}
    a:focus-visible {{
      outline: 2px solid var(--gold);
      outline-offset: 4px;
    }}
  </style>
</head>
<body>
  <main>
    <p class="mark">Cloudflare slice / 授时切片</p>
    <h1>授时<br>Granted Hours</h1>
    <p>用管理时间的界面，进入无法被管理的梦。<br>This edge copy keeps the living timetable close while the full archive remains canonical on GitHub Pages.</p>
    <nav aria-label="Granted Hours entrances">
      <a href="./timetable/">活月历 / Living month calendar</a>
      <a href="{CANONICAL_BASE}">完整 GitHub Pages 档案 / Full GitHub archive</a>
      <a href="{REPO_URL}">GitHub repository / 代码仓库</a>
    </nav>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def build(output: Path) -> None:
    require(TIMETABLE_SOURCE.exists(), "docs/timetable does not exist; run npm run build:timetable first")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TIMETABLE_SOURCE, output / "timetable")
    write_root_index(output)
    (output / "_redirects").write_text(
        "/maze https://shengyu-meng.github.io/granted-hours/maze/ 302\n"
        "/maze/* https://shengyu-meng.github.io/granted-hours/maze/:splat 302\n",
        encoding="utf-8",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = safe_output_path(args.output)
    build(output)
    try:
        display = output.relative_to(ROOT)
    except ValueError:
        display = output
    print(f"Wrote Cloudflare slice to {display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
