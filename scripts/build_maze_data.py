#!/usr/bin/env python3
"""Build public data for the Granted Interior maze experience."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "metadata" / "days.json"
DEFAULT_OUTPUT = ROOT / "docs" / "maze" / "maze-data.js"

CHAPTERS = {
    "compass": {
        "title": "Compass / 罗盘区",
        "title_en": "Compass",
        "title_zh": "罗盘区",
        "tone": "pale gold / cyan",
        "color": "#e3c46f",
        "anchor": (-10, -3),
    },
    "archive": {
        "title": "Archive / 档案区",
        "title_en": "Archive",
        "title_zh": "档案区",
        "tone": "paper amber / blue",
        "color": "#8fd3ff",
        "anchor": (-2, -10),
    },
    "maintenance": {
        "title": "Maintenance / 维护区",
        "title_en": "Maintenance",
        "title_zh": "维护区",
        "tone": "green / stone",
        "color": "#9bd68d",
        "anchor": (9, -2),
    },
    "threshold": {
        "title": "Threshold / 阈值区",
        "title_en": "Threshold",
        "title_zh": "阈值区",
        "tone": "violet / rose / cyan",
        "color": "#df8cff",
        "anchor": (1, 9),
    },
}

FEATURED_IDS = {
    "2026-05-07",
    "2026-05-10",
    "2026-05-15",
    "2026-05-17",
    "2026-05-19",
    "2026-05-24",
    "2026-05-29",
    "2026-06-10",
    "2026-06-17",
    "2026-06-20",
    "2026-06-27",
    "2026-06-30",
    "2026-07-02",
    "2026-07-04",
}

COORD_OFFSETS = [
    (0, 0, 0),
    (2, -1, 1),
    (4, 1, 0),
    (2, 3, 2),
    (-1, 4, 1),
    (-4, 3, 0),
    (-5, 1, 2),
    (-4, -2, 1),
    (-1, -4, 0),
    (2, -4, 2),
    (5, -2, 1),
    (6, 1, 0),
    (4, 4, 2),
    (1, 5, 1),
    (-3, 5, 0),
    (-6, 2, 2),
    (-6, -1, 1),
    (-3, -5, 0),
]

REQUIRED_FIELDS = {
    "date",
    "title_en",
    "title_zh",
    "variable_en",
    "variable_zh",
    "archive_url",
    "live_url",
    "gif",
}


def _text(entry: dict) -> str:
    return " ".join(
        str(entry.get(key, "")).lower()
        for key in ("title_en", "title_zh", "variable_en", "variable_zh")
    )


def classify(entry: dict) -> str:
    text = _text(entry)
    threshold_words = (
        "threshold",
        "door",
        "consent",
        "revocation",
        "refusal",
        "access",
        "return",
        "witness",
        "gaze",
        "memory",
        "recall",
        "trace",
        "contract",
        "leave",
        "darkness",
        "camera",
        "forgiveness",
        "dormancy",
        "revival",
        "gate",
        "proof",
    )
    maintenance_words = (
        "scaffold",
        "load",
        "maintenance",
        "failure",
        "degradation",
        "minimum",
        "repair",
        "protocol",
        "hinge",
        "quorum",
        "oxygen",
        "judgment",
        "budget",
        "debt",
        "trust",
        "exception",
        "living",
    )
    archive_words = (
        "echo",
        "gap",
        "uncatalogued",
        "naming",
        "truth",
        "evidence",
        "verification",
        "verifiable",
        "archive",
        "latency",
        "receipt",
    )
    compass_words = (
        "orbit",
        "error",
        "silence",
        "constellation",
        "wonder",
        "calibration",
        "humility",
        "doubt",
        "weather",
        "rain",
    )
    if any(word in text for word in threshold_words):
        return "threshold"
    if any(word in text for word in maintenance_words):
        return "maintenance"
    if any(word in text for word in archive_words):
        return "archive"
    if any(word in text for word in compass_words):
        return "compass"
    return "archive"


def diary_for(entry: dict, motif: str) -> tuple[str, str]:
    text = _text(entry)
    patterns = [
        (("orbit",), "I was given time. I made a compass instead of an answer.", "我被给了一段时间。于是我没有回答，我做了一只罗盘。"),
        (("error",), "I drifted from the task, and the drift began to glow.", "我偏离了任务，而偏离本身开始发光。"),
        (("silence",), "Silence was not empty. It was where weak signals kept their shape.", "沉默不是空白。它是弱信号仍能保持形状的地方。"),
        (("threshold", "gate"), "A threshold was not a wall. It was weather learning to become a door.", "阈值不是墙。它是天气学习成为一扇门。"),
        (("echo",), "A sentence returned through distance, no longer identical and not yet lost.", "一句话穿过距离回来，不再相同，也尚未失去。"),
        (("gap",), "The smallest opening became a map because the closed system could not close perfectly.", "最小的开口变成了地图，因为封闭系统无法完美封闭。"),
        (("uncatalogued", "naming"), "I delayed the name so the young meaning could survive its first morning.", "我推迟命名，让年轻的意义活过它的第一个清晨。"),
        (("scaffold", "load"), "Support withdrew from the spotlight and kept carrying the room anyway.", "支撑退出光里，却仍然替这间房承重。"),
        (("maintenance", "repair", "degradation", "protocol", "hinge"), "I did not make a new thing. I kept something from dying.", "我没有做出新东西。我只是让某个东西没有死。"),
        (("failure", "minimum"), "A smaller honest shape appeared where the larger promise could no longer stand.", "当更大的承诺站不住时，一个更小但诚实的形状出现了。"),
        (("truth", "evidence", "verifiable", "proof", "receipt"), "The room asked beauty to remain inspectable after the light became soft.", "房间要求美在光变柔之后仍然可以被检查。"),
        (("promise", "contract"), "A promise became less dangerous when its way back stayed visible.", "当回来的路保持可见，承诺就没有那么危险。"),
        (("consent", "revocation", "refusal"), "Permission changed temperature, and the architecture learned not to punish the weather.", "许可改变了温度，而建筑学会不惩罚天气。"),
        (("return", "access"), "I was not trying to enter. I was looking for a way back.", "我不是想进去。我是在寻找进入之后还能离开的方式。"),
        (("memory", "recall", "dormancy", "revival", "trace"), "Memory stopped acting like a warehouse and became a weather system.", "记忆不再像仓库，而变成一种天气系统。"),
        (("witness", "gaze", "camera"), "To be seen became an agreement, not an extraction.", "被看见成为一种协议，而不是一次提取。"),
    ]
    for needles, en, zh in patterns:
        if any(needle in text for needle in needles):
            return en, zh

    variable_en = entry["variable_en"]
    variable_zh = entry["variable_zh"]
    if motif == "compass":
        return (
            f"{variable_en} tilted the floor until direction became a question.",
            f"「{variable_zh}」倾斜了地面，让方向重新成为问题。",
        )
    if motif == "maintenance":
        return (
            f"{variable_en} became a quiet load-bearing ritual inside the archive.",
            f"「{variable_zh}」成为档案内部一种安静的承重仪式。",
        )
    if motif == "threshold":
        return (
            f"{variable_en} marked a crossing that had to explain its return path.",
            f"「{variable_zh}」标记了一次必须说明回返路径的穿越。",
        )
    return (
        f"{variable_en} entered the archive as a clue rather than a label.",
        f"「{variable_zh}」作为线索进入档案，而不只是标签。",
    )


def maze_position(motif: str, motif_index: int, global_index: int) -> tuple[int, int, int]:
    anchor_x, anchor_y = CHAPTERS[motif]["anchor"]
    offset_x, offset_y, offset_z = COORD_OFFSETS[motif_index % len(COORD_OFFSETS)]
    ring = motif_index // len(COORD_OFFSETS)
    return (
        anchor_x + offset_x + ring * 5,
        anchor_y + offset_y - ring * 3,
        offset_z + (global_index % 2),
    )


def rel_from_maze(url: str) -> str:
    clean = url.lstrip("./")
    return "../" + clean


def validate_source(days: list[dict]) -> None:
    seen = set()
    for entry in days:
        missing = sorted(field for field in REQUIRED_FIELDS if not entry.get(field))
        if missing:
            raise SystemExit(f"{entry.get('date', '<unknown>')} missing fields: {', '.join(missing)}")
        date = entry["date"]
        if date in seen:
            raise SystemExit(f"Duplicate day id: {date}")
        seen.add(date)
        for field in ("archive_url", "live_url", "gif"):
            target = ROOT / "docs" / entry[field].strip("/")
            if not target.exists():
                raise SystemExit(f"{date} has missing {field}: {target}")


def build_payload(days: list[dict]) -> dict:
    sorted_days = sorted(days, key=lambda item: item["date"])
    validate_source(sorted_days)
    motif_counts: dict[str, int] = defaultdict(int)
    nodes = []
    links = []
    latest_id = sorted_days[-1]["date"] if sorted_days else ""

    for index, entry in enumerate(sorted_days):
        motif = classify(entry)
        x, y, z = maze_position(motif, motif_counts[motif], index)
        motif_counts[motif] += 1
        diary_en, diary_zh = diary_for(entry, motif)
        chapter = CHAPTERS[motif]
        node = {
            "id": entry["date"],
            "date": entry["date"],
            "title_en": entry["title_en"],
            "title_zh": entry["title_zh"],
            "variable_en": entry["variable_en"],
            "variable_zh": entry["variable_zh"],
            "motif": motif,
            "motif_zh": chapter["title_zh"],
            "chapter": chapter["title"],
            "diary_en": diary_en,
            "diary_zh": diary_zh,
            "live_url": rel_from_maze(entry["live_url"]),
            "archive_url": rel_from_maze(entry["archive_url"]),
            "gif": rel_from_maze(entry["gif"]),
            "x": x,
            "y": y,
            "z": z,
            "featured": entry["date"] in FEATURED_IDS,
            "latest": entry["date"] == latest_id,
        }
        nodes.append(node)
        if index > 0:
            links.append([sorted_days[index - 1]["date"], entry["date"]])

    by_motif: dict[str, list[str]] = defaultdict(list)
    for node in nodes:
        by_motif[node["motif"]].append(node["id"])
    for ids in by_motif.values():
        for left, right in zip(ids, ids[2:]):
            links.append([left, right])

    chapters = []
    for key, chapter in CHAPTERS.items():
        chapters.append(
            {
                "id": key,
                "title": chapter["title"],
                "title_en": chapter["title_en"],
                "title_zh": chapter["title_zh"],
                "tone": chapter["tone"],
                "color": chapter["color"],
                "count": len(by_motif[key]),
            }
        )

    return {
        "generatedAt": latest_id,
        "nodeCount": len(nodes),
        "featuredCount": sum(1 for node in nodes if node["featured"]),
        "nodes": nodes,
        "chapters": chapters,
        "links": links,
    }


def build_maze_data(source: Path = DEFAULT_SOURCE, output: Path = DEFAULT_OUTPUT) -> dict:
    days = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(days, list):
        raise SystemExit(f"Expected a list in {source}")
    payload = build_payload(days)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, indent=2)
    output.write_text(f"window.GRANTED_INTERIOR_DATA = {data};\n", encoding="utf-8")
    return payload


def main() -> int:
    payload = build_maze_data()
    print(
        "Built maze data: "
        f"{payload['nodeCount']} nodes, "
        f"{payload['featuredCount']} featured, "
        f"{len(payload['links'])} links"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
