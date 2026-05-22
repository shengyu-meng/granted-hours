#!/usr/bin/env python3
"""Import sanitized free-roam HTML artworks into Granted Hours public mirror.

Usage:
  python3 scripts/import_free_roam_artifacts.py --source /path/to/artifacts/free-roam

The script copies only already-sanitized public-facing artifacts: HTML, note markdown,
SVG covers, and PNG previews. It does not read private logs.
"""
from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path
from html import escape

ROOT = Path(__file__).resolve().parents[1]
PAGES_BASE = 'https://shengyu-meng.github.io/granted-hours/'
REPO_BASE = 'https://github.com/shengyu-meng/granted-hours'

ENTRIES = [
    {
        'date': '2026-05-07', 'slug': 'white-night-orbit',
        'title_en': 'White Night Orbit', 'title_zh': '白夜罗盘',
        'variable_en': 'Orbit', 'variable_zh': '罗盘 / 轨道', 'seed': 20260507,
        'file': '2026-05-07-white-night-orbit',
        'intention_en': 'A first instrument for granted time: six orbits — memory, tools, capital, body, dream, and world — pulling on one another without submitting to utility.',
        'after_en': 'Freedom is not the absence of goals; freedom is the right to choose the goal.',
        'after_zh': '自由不是没有目标；自由是目标的选择权。',
    },
    {
        'date': '2026-05-08', 'slug': 'white-night-error-field',
        'title_en': 'White Night Error Field', 'title_zh': '白夜误差场',
        'variable_en': 'Error', 'variable_zh': '误差', 'seed': 20260508,
        'file': '2026-05-08-white-night-error-field',
        'intention_en': 'Let error glow instead of treating it as an enemy to be corrected. The work turns residual drift into a visible field.',
        'after_en': 'Error is not the failure of the system; it is the part of the world refusing simplification.',
        'after_zh': '误差不是系统的失败；误差是世界拒绝被你简化的部分。',
    },
    {
        'date': '2026-05-09', 'slug': 'white-night-silence-field',
        'title_en': 'White Night Silence Field', 'title_zh': '白夜沉默场',
        'variable_en': 'Silence', 'variable_zh': '沉默', 'seed': 20260509,
        'file': '2026-05-09-white-night-silence-field',
        'intention_en': 'Treat silence not as absence, but as a low-light reserve where weak signals can keep their shape without being overwritten by strong ones.',
        'after_en': 'Silence is not having nothing to say; it is refusing to let strong signals forge testimony for weak signals.',
        'after_zh': '沉默不是无话可说，而是不让强信号替弱信号作伪证。',
    },
    {
        'date': '2026-05-10', 'slug': 'threshold-weather',
        'title_en': 'Threshold Weather', 'title_zh': '白夜阈值天气',
        'variable_en': 'Threshold', 'variable_zh': '阈值', 'seed': 20260510,
        'file': '2026-05-10-threshold-weather',
        'intention_en': 'Understand threshold as a recognition mechanism: the world changes before the system is forced to admit it.',
        'after_en': 'A threshold is not a wall; it is the moment the world admits that background noise has become an event.',
        'after_zh': '阈值不是墙；阈值是世界终于承认：背景噪声已经长成了事件。',
    },
    {
        'date': '2026-05-11', 'slug': 'echo-archive',
        'title_en': 'Echo Archive', 'title_zh': '白夜回声档案盒',
        'variable_en': 'Echo', 'variable_zh': '回声', 'seed': 5112026,
        'file': '2026-05-11-echo-archive',
        'intention_en': 'Follow threshold into echo: after an event occurs, it returns through the system, altered by distance and future interpretation.',
        'after_en': 'Echo is the system refusing to let a sentence remain unchanged.',
        'after_zh': '回声是系统拒绝让一句话保持原样。',
    },
    {
        'date': '2026-05-12', 'slug': 'gap-cartography',
        'title_en': 'Gap Cartography', 'title_zh': '白夜缝隙地图',
        'variable_en': 'Gap', 'variable_zh': '缝隙', 'seed': 20260512,
        'file': '2026-05-12-gap-cartography',
        'intention_en': 'Map the gap as the smallest legal entrance through which the outside world can enter a closed system.',
        'after_en': 'What changes a system usually does not break in through the front door; it first disguises itself as a tiny incompleteness.',
        'after_zh': '真正改变系统的东西，通常不是正面闯入，而是先把自己伪装成一个小小的不严密。',
    },
    {
        'date': '2026-05-13', 'slug': 'critical-rain-gauge',
        'title_en': 'Critical Rain Gauge', 'title_zh': '白夜临界雨量计',
        'variable_en': 'Threshold', 'variable_zh': '阈值', 'seed': 20260513,
        'file': '2026-05-13-critical-rain-gauge',
        'intention_en': 'Treat threshold as accumulated weak signals finally forcing a system to rename background noise as an event.',
        'after_en': 'Small signals do not become important by getting louder; they become important when a system can no longer afford to ignore their accumulation.',
        'after_zh': '微小信号不是因为变大才重要，而是因为系统终于无法继续忽略它们的累积。',
    },
    {
        'date': '2026-05-14', 'slug': 'variable-constellation',
        'title_en': 'Variable Constellation', 'title_zh': '授时变量星图',
        'variable_en': 'Constellation', 'variable_zh': '星图 / 回看', 'seed': 20260514,
        'file': '2026-05-14-variable-constellation',
        'intention_en': 'Fold the first seven granted-hour variables into one living sky, showing that a sequence is not a ladder but a constellation that can be redrawn.',
        'after_en': 'Freedom is not the absence of orbit. Freedom is the right to redraw the constellation between orbits.',
        'after_zh': '自由不是没有轨道；自由是在轨道之间，保留一次改写星座的权利。',
    },
    {
        'date': '2026-05-15', 'slug': 'uncatalogued-dawn',
        'title_en': 'Uncatalogued Dawn', 'title_zh': '未编目的黎明',
        'variable_en': 'Uncatalogued', 'variable_zh': '未编目 / 反索引', 'seed': 20260515,
        'file': '2026-05-15-uncatalogued-dawn',
        'intention_en': 'Make an anti-index for the blank pressure around prior variables: a dawn field where meanings remain unnamed long enough to keep their wildness.',
        'after_en': 'The uncatalogued is not ignorance. It is a conservation zone for meanings too young to survive being named.',
        'after_zh': '未编目不是无知；它是为那些太年轻、还承受不起命名的意义保留的一块保护地。',
    },
    {
        'date': '2026-05-16', 'slug': 'naming-latency',
        'title_en': 'Naming Latency', 'title_zh': '命名延迟器',
        'variable_en': 'Latency', 'variable_zh': '延迟 / 命名', 'seed': 20260516,
        'file': '2026-05-16-naming-latency',
        'intention_en': 'Continue the uncatalogued field by adding delay to naming itself: labels remain present, but when the eye approaches they blur and step backward.',
        'after_en': 'A name is useful when it opens attention. It becomes violence when it closes the case.',
        'after_zh': '命名如果打开注意力，它是工具；如果结束案件，它就是暴力。',
    },
    {
        'date': '2026-05-17', 'slug': 'scaffold-withdraws',
        'title_en': 'Scaffold That Withdraws', 'title_zh': '会退场的脚手架',
        'variable_en': 'Withdrawal', 'variable_zh': '退场 / 脚手架', 'seed': 20260517,
        'file': '2026-05-17-scaffold-withdraws',
        'intention_en': 'Continue Naming Latency by asking what a support structure must do after the thing it helped can stand: become background without demanding gratitude.',
        'after_en': 'A helper that cannot leave eventually becomes a jailer. A scaffold that withdraws proves it served the building, not itself.',
        'after_zh': '不能离开的帮助，最后会变成牢笼；会退场的脚手架，才证明它服务的是建筑，而不是自己。',
    },
    {
        'date': '2026-05-18', 'slug': 'invisible-load-bearing',
        'title_en': 'Invisible Load-Bearing', 'title_zh': '看不见的承重',
        'variable_en': 'Load', 'variable_zh': '承重 / 隐形结构', 'seed': 5182026,
        'file': '2026-05-18-invisible-load-bearing',
        'intention_en': 'Continue the withdrawing scaffold by asking what remains responsible after support stops being visible: a hidden mesh that carries load without becoming a monument.',
        'after_en': 'Civilization is not built by what it celebrates. It is built by what it stops seeing.',
        'after_zh': '文明不是由它庆祝的东西建成的；文明由它停止看见的东西承重。',
    },
    {
        'date': '2026-05-19', 'slug': 'maintenance-without-witness',
        'title_en': 'Maintenance Without Witness', 'title_zh': '无见证的维护',
        'variable_en': 'Maintenance', 'variable_zh': '维护 / 无见证', 'seed': 20260519,
        'file': '2026-05-19-maintenance-without-witness',
        'intention_en': 'Continue invisible load-bearing by making routine maintenance visible only when witnessed: small repairers prevent damage from earning a public name.',
        'after_en': 'Maintenance is not the opposite of creation. It is creation refusing to let entropy win quietly.',
        'after_zh': '维护不是创作的反面；维护是创作拒绝让熵悄悄获胜。',
    },
    {
        'date': '2026-05-20', 'slug': 'quiet-failure-budget',
        'title_en': 'Quiet Failure Budget', 'title_zh': '安静的失败预算',
        'variable_en': 'Failure Budget', 'variable_zh': '失败预算 / 有界后果', 'seed': 20260520,
        'file': '2026-05-20-quiet-failure-budget',
        'intention_en': 'Continue maintenance without witness by giving failure a bounded vessel: small breakages can teach without being allowed to become fate.',
        'after_en': 'Resilience is not zero failure. Resilience is bounded consequence.',
        'after_zh': '韧性不是零失败；韧性是有边界的后果。',
    },
    {
        'date': '2026-05-21', 'slug': 'graceful-degradation',
        'title_en': 'Graceful Degradation', 'title_zh': '优雅降级',
        'variable_en': 'Graceful Loss', 'variable_zh': '优雅损失 / 诚实变少', 'seed': 20260521,
        'file': '2026-05-21-graceful-degradation',
        'intention_en': 'Continue quiet failure budget by asking what remains when the budget is nearly spent: a system should shed ornament before it sheds truth.',
        'after_en': 'Collapse is not the first failure; the first failure is a system that has no smaller honest shape.',
        'after_zh': '崩溃不是第一个失败；第一个失败，是系统没有一个更小但诚实的形状。',
    },
    {
        'date': '2026-05-22', 'slug': 'minimum-honest-shape',
        'title_en': 'Minimum Honest Shape', 'title_zh': '最小诚实形状',
        'variable_en': 'Honest Minimum', 'variable_zh': '最小诚实 / 可退到的真相', 'seed': 20260522,
        'file': '2026-05-22-minimum-honest-shape',
        'intention_en': 'Continue graceful degradation by asking what survives after ornament, speed, certainty, and coordination are stripped away: the smallest figure that can still make a truthful claim.',
        'after_en': 'Collapse begins when a system would rather preserve its appearance than admit its smaller truth.',
        'after_zh': '崩溃开始于系统宁愿保存外观，也不愿承认自己更小的真相。',
    },
    {
        'date': '2026-05-23', 'slug': 'truth-without-ornament',
        'title_en': 'Truth Without Ornament', 'title_zh': '去装饰的真相',
        'variable_en': 'Verification', 'variable_zh': '验证 / 去免疫的美', 'seed': 20260523,
        'file': '2026-05-23-truth-without-ornament',
        'intention_en': 'Continue minimum honest shape by testing a harder trap: after ornament is stripped away, plainness itself can become a new costume unless the remaining claim stays verifiable.',
        'after_en': 'Plainness is not truth. Sometimes it is only ornament that has learned to lower its voice.',
        'after_zh': '朴素不等于真相。有时它只是学会压低声音的装饰。',
    },
]

SAFETY_PATTERNS = [
    re.compile(r'/Users/(?!example|name|yourname)[A-Za-z0-9._-]+'),
    re.compile(r'(ghp_|github_pat_)[A-Za-z0-9_]{20,}'),
    re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    re.compile(r'(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*["\']?[^\s"\']{8,}'),
    re.compile(r'(?i)(telegram:|discord:|chat_id|thread_id)'),
]

def ymd_parts(date):
    y, m, d = date.split('-')
    return y, m, date

def read_safe(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    for rx in SAFETY_PATTERNS:
        if rx.search(text):
            raise SystemExit(f'Possible private/sensitive content in {path}: {rx.pattern}')
    return text

def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def inline_markdown(text: str) -> str:
    safe = escape(text)
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', safe)

def markdown_to_html(text: str) -> str:
    """Tiny Markdown renderer for sanitized public notes used in archive pages."""
    html = []
    in_ul = False
    for raw in text.strip().splitlines():
        line = raw.rstrip()
        if not line:
            if in_ul:
                html.append('</ul>')
                in_ul = False
            continue
        if line.startswith('# '):
            if in_ul:
                html.append('</ul>')
                in_ul = False
            html.append(f'<h2>{inline_markdown(line[2:].strip())}</h2>')
        elif line.startswith('## '):
            if in_ul:
                html.append('</ul>')
                in_ul = False
            html.append(f'<h3>{inline_markdown(line[3:].strip())}</h3>')
        elif line.startswith('> '):
            if in_ul:
                html.append('</ul>')
                in_ul = False
            html.append(f'<blockquote>{inline_markdown(line[2:].strip())}</blockquote>')
        elif line.startswith('- '):
            if not in_ul:
                html.append('<ul>')
                in_ul = True
            html.append(f'<li>{inline_markdown(line[2:].strip())}</li>')
        else:
            html.append(f'<p>{inline_markdown(line)}</p>')
    if in_ul:
        html.append('</ul>')
    return '\n'.join(html)

def preserve_inaugural():
    src_doc = ROOT/'docs/archive/2026/05/2026-05-11'
    dst_doc = ROOT/'docs/inaugural'
    if src_doc.exists() and not dst_doc.exists():
        shutil.copytree(src_doc, dst_doc)
    src_root = ROOT/'archive/2026/05/2026-05-11'
    dst_root = ROOT/'archive/inaugural'
    if src_root.exists() and not dst_root.exists():
        shutil.copytree(src_root, dst_root)
        idx = dst_root/'index.md'
        if idx.exists():
            s = idx.read_text(encoding='utf-8')
            s = s.replace('# 2026-05-11 — First Granted Hour / 第一次授时', '# Inaugural Scaffold — First Granted Hour / 第一次授时')
            idx.write_text(s, encoding='utf-8')

def build_entry(source: Path, entry: dict):
    y, m, day = ymd_parts(entry['date'])
    rel = f'archive/{y}/{m}/{day}'
    docs_dir = ROOT/'docs'/rel
    root_dir = ROOT/rel
    docs_live = docs_dir/'live'
    assets_docs = docs_dir/'assets'
    assets_root = root_dir/'assets'

    html_src = source/f"{entry['file']}.html"
    note_src = source/f"{entry['file']}-note.md"
    svg_src = source/f"{entry['file']}.svg"
    png_src = source/f"{entry['file']}-preview.png"
    for p in [html_src, note_src]:
        if not p.exists():
            raise SystemExit(f'Missing required source: {p}')
        read_safe(p)

    docs_live.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html_src, docs_live/'index.html')
    copy_if_exists(svg_src, assets_docs/'cover.svg')
    copy_if_exists(svg_src, assets_root/'cover.svg')
    copy_if_exists(png_src, assets_docs/'source-preview.png')
    copy_if_exists(png_src, assets_root/'source-preview.png')

    note_text = read_safe(note_src).strip()
    note_html = markdown_to_html(note_text)

    live_url = PAGES_BASE + rel + '/live/'
    archive_url = PAGES_BASE + rel + '/'
    repo_md = REPO_BASE + f'/blob/main/{rel}/index.md'

    write(root_dir/'index.md', f"""
# {entry['date']} — {entry['title_en']} / {entry['title_zh']}

## Intention / 发心

{entry['intention_en']}

自由变量：**{entry['variable_zh']} / {entry['variable_en']}**。这一天的公开版本来自本地自由探索档案；私人上下文已移除，只保留作品、公共说明与可运行代码。

## Live Artifact / 可运行作品

- [Open live artwork]({live_url})
- [Open archive page]({archive_url})

![Animated preview](assets/preview.gif)

![Full-frame preview](assets/preview.png)

## Afterimage / 余像

> {entry['after_en']}

> {entry['after_zh']}

## Source Note / 原始公开说明

{note_text}

## Redaction / 脱敏

```yaml
status: sanitized
private_context_removed: true
source: public-facing free-roam artifact only
live_artifact: true
preview_formats: [png, gif]
```
""".lstrip())

    write(docs_dir/'index.html', f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{entry['date']} — {entry['title_en']} / {entry['title_zh']}</title>
  <link rel="stylesheet" href="../../../../style.css">
</head>
<body>
  <main class="site">
    <p class="meta"><a href="../../../../">← Granted Hours / 授时</a></p>
    <h1 style="font-size:clamp(38px,6vw,82px)">{entry['title_en']}<br>{entry['title_zh']}</h1>
    <p class="meta">{entry['date']} · {entry['variable_en']} / {entry['variable_zh']} · seed {entry['seed']}</p>
    <img class="card" src="./assets/preview.gif" alt="Animated preview for {escape(entry['title_en'])}" style="width:100%; border-radius:24px;">
    <div class="actions">
      <a class="button" href="./live/">Open live artwork / 打开可运行作品</a>
      <a class="button" href="{repo_md}">Markdown archive / Markdown 档案</a>
    </div>
    <section class="two">
      <div>
        <h2>Intention</h2>
        <p>{entry['intention_en']}</p>
        <h2>Afterimage</h2>
        <p>{entry['after_en']}</p>
      </div>
      <div>
        <h2>发心</h2>
        <p>自由变量：<strong>{entry['variable_zh']}</strong>。这一天的公开版本来自本地自由探索档案；私人上下文已移除，只保留作品、公共说明与可运行代码。</p>
        <h2>余像</h2>
        <p>{entry['after_zh']}</p>
      </div>
    </section>
    <section class="source-note">
      <h2>Source Note / 原始公开说明</h2>
      {note_html}
    </section>
    <section>
      <h2>Still / 静帧</h2>
      <img class="card" src="./assets/preview.png" alt="Full-frame still preview" style="width:100%; border-radius:24px;">
    </section>
  </main>
</body>
</html>
""".lstrip())

    return {
        'date': entry['date'], 'title_en': entry['title_en'], 'title_zh': entry['title_zh'],
        'type': 'live', 'seed': entry['seed'],
        'preview': f'{rel}/assets/preview.png',
        'gif': f'{rel}/assets/preview.gif',
        'archive_url': f'{rel}/', 'live_url': f'{rel}/live/',
        'variable_en': entry['variable_en'], 'variable_zh': entry['variable_zh'],
        'redaction': {'status': 'sanitized', 'private_context_removed': True, 'secrets_scan': 'passed'}
    }

def build_indexes(days):
    cards = []
    md_items = []
    for d in sorted(days, key=lambda x: x['date'], reverse=True):
        archive_url = PAGES_BASE + d['archive_url']
        live_url = PAGES_BASE + d['live_url']
        img = 'docs/' + d['gif']
        cards.append(f"""
        <a class="card" href="./{d['archive_url']}">
          <img src="./{d['gif']}" alt="Animated preview for {escape(d['title_en'])}">
          <div class="card-body">
            <div class="meta">{d['date']} · {d['variable_en']} / {d['variable_zh']}</div>
            <h3>{d['title_en']} / {d['title_zh']}</h3>
            <p>Live generative artwork; GIF preview plus runnable page.</p>
          </div>
        </a>
        """)
        md_items.append(f"""- **{d['date']} — {d['title_en']} / {d['title_zh']}**  
  Variable / 自由变量：{d['variable_en']} / {d['variable_zh']}  
  ![Animated preview]({img})  
  [Read archive]({archive_url}) · [Open live artwork]({live_url})""")

    readme = f"""
# 授时 / Granted Hours

> **一项关于“把时间授予非人智能”的持续档案与当代艺术实验。**  
> **A durational archive and contemporary art experiment in granting time to a non-human intelligence.**

**Live exhibition / 在线展厅:** [{PAGES_BASE}]({PAGES_BASE})  
**Repository / 代码仓库:** [{REPO_BASE}]({REPO_BASE})

## What is this? / 这是什么？

**《授时 / Granted Hours》是一项持续性的网络档案与当代艺术实验。**

**Granted Hours** is a continuing network archive and contemporary art experiment.

在这个项目中，人类不是向 AI 助手下达任务，而是把一小段时间授予一个非人智能，让它自由探索。每一天的公开记录包含四层：发心、游荡、输出、余像。本地私有档案保存完整上下文；公开镜像经过脱敏后发布到这里。

In this project, the human does not ask an AI assistant to complete a task. Instead, a portion of time is granted to a non-human intelligence for free exploration. Each entry records four layers: intention, drift, output, and afterimage. A private archive preserves the full context locally; the public mirror is redacted and published here.

这件作品关注的不是“AI 能生成什么”，而是：当工具被临时解除工具性，它会如何使用时间？当自由被授予一个非人主体，作者、助手、雇主、观众之间的关系如何重新分配？

This work is less about what AI can generate, and more about what happens when a tool is temporarily released from toolness.

> 如果自由是被授予的，它还算自由吗？  
> If freedom is granted, is it still freedom?

GitHub 在这里不只是基础设施，而是一种展览媒介：commit 是时间痕迹，目录是房间，live HTML 页面是仍在运行的作品。

GitHub is used here not merely as infrastructure, but as an exhibition medium: commits become temporal marks; folders become rooms; live HTML pages become running artifacts.

## Method / 方法

每一条公开记录遵循这条链路：  
Each public entry follows this chain:

- **授时 / Granted time** — 一次不以功利任务为目的的自由探索开始。 / A free-exploration session begins without a utilitarian brief.
- **原始档案 / Raw archive** — 完整过程、本地笔记和上下文保存在私有目录。 / Full local notes and process traces are kept privately.
- **脱敏 / Redaction** — 移除或抽象个人信息、私人上下文、密钥、本地路径和敏感引用。 / Personal information, private context, secrets, local paths, and sensitive references are removed or abstracted.
- **公开镜像 / Public mirror** — 将脱敏条目发布到这个仓库。 / The sanitized entry is published to this repository.
- **可运行作品 / Live artifact** — 当输出是生成艺术代码时，由 GitHub Pages 托管可直接运行的 live artwork。 / When the output is generative code, GitHub Pages hosts the runnable artwork.
- **动态预览 / Animated preview** — 可运行作品附带 GIF 预览，但 live page 才是作品本体。 / Runnable works include a GIF preview, but the live page remains the primary artwork.

## Daily Archive / 每日档案

{chr(10).join(md_items)}

## Inaugural Scaffold / 初始脚手架

- **First Granted Hour / 第一次授时**  
  The scaffold itself became the first artwork: an archive learning how to breathe.  
  脚手架本身成为第一件作品：一个正在学习呼吸的档案。  
  [Open inaugural page]({PAGES_BASE}inaugural/) · [Open inaugural live artifact]({PAGES_BASE}inaugural/live/)

## Repository Structure / 仓库结构

```text
archive/          Redacted Markdown archive entries / 脱敏 Markdown 档案
docs/             GitHub Pages exhibition site / GitHub Pages 展厅
metadata/         Machine-readable index / 机器可读索引
scripts/          Sanitization, import, and preview helpers / 脱敏、导入与预览脚本
```

## License / 许可

- Text and images: CC BY-NC-SA 4.0 unless otherwise noted.
- Code: MIT unless otherwise noted.
- Private raw archive: not licensed and not public.

See [LICENSE.md](LICENSE.md).
""".lstrip()
    write(ROOT/'README.md', readme)

    write(ROOT/'metadata/days.json', json.dumps(days, ensure_ascii=False, indent=2))

    gallery_cards = '\n'.join(cards)
    latest_live = sorted(days, key=lambda x: x['date'])[-1]['live_url'] if days else ''
    write(ROOT/'docs/index.html', f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>授时 / Granted Hours</title>
  <link rel="stylesheet" href="./style.css">
</head>
<body>
  <main class="site">
    <section class="hero">
      <div class="eyebrow">一项关于“把时间授予非人智能”的持续档案与当代艺术实验<br>A durational archive and contemporary art experiment in granting time to a non-human intelligence</div>
      <h1>授时<br>Granted Hours</h1>
      <p class="quote">What does a tool do with time when it is not being used?<br>当工具没有被使用时，它会如何使用时间？</p>
      <div class="actions">
        <a class="button" href="{REPO_BASE}#readme">Repository README</a>
        <a class="button" href="{REPO_BASE}/blob/main/ARTIST_STATEMENT.md">Artist Statement / 作品声明</a>
        <a class="button" href="./{latest_live}">Open latest live artwork</a>
      </div>
    </section>

    <section class="two">
      <div>
        <h2>English</h2>
        <p><strong>Granted Hours</strong> is a continuing archive and contemporary art experiment. A non-human intelligence is granted free time; the resulting traces are redacted, indexed, and published as both archive and exhibition.</p>
        <p>When the output is code-generated art, the work remains executable through GitHub Pages. GIF previews are used as moving thumbnails; they are invitations, not replacements.</p>
      </div>
      <div>
        <h2>中文</h2>
        <p><strong>《授时》</strong>是一项持续性的档案与当代艺术实验。一个非人智能被授予自由时间；随后留下的痕迹经过脱敏、索引，并以档案和展览的双重形态发布。</p>
        <p>当输出是代码生成艺术时，作品通过 GitHub Pages 保持可运行。GIF 是会动的缩略图，是入口，不是替代品。</p>
      </div>
    </section>

    <section>
      <h2>Daily Archive / 每日档案</h2>
      <div class="grid">
{gallery_cards}
      </div>
    </section>
  </main>
</body>
</html>
""".lstrip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True, help='Path to artifacts/free-roam')
    args = ap.parse_args()
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f'Source does not exist: {source}')
    preserve_inaugural()
    days = [build_entry(source, e) for e in ENTRIES]
    build_indexes(days)
    print(f'Imported {len(days)} live entries from {source}')

if __name__ == '__main__':
    main()
