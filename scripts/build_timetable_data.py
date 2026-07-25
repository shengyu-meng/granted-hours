#!/usr/bin/env python3
"""Build public data for the Granted Hours living month calendar."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_DAYS = ROOT / "metadata" / "days.json"
DEFAULT_CONFIG = ROOT / "metadata" / "timetable-calendar.json"
DEFAULT_HISTORY = ROOT / "metadata" / "timetable-history.json"
DEFAULT_LEGACY_OVERRIDES = ROOT / "metadata" / "timetable-v1.json"
DEFAULT_OUTPUT = ROOT / "src" / "timetable" / "timetable-data.js"

MINUTES_PER_DAY = 24 * 60
REQUIRED_PUBLIC_FIELDS = (
    "date",
    "title_en",
    "title_zh",
    "variable_en",
    "variable_zh",
    "gif",
    "preview",
    "archive_url",
    "live_url",
)
REQUIRED_TAXONOMY = {
    "social_media_organization",
    "document_processing",
    "code_development",
    "research_synthesis",
    "system_maintenance",
    "visual_production",
}
ALLOWED_PROVENANCE = {"record_based", "archive_based", "inferred"}


def minutes(value: str) -> int:
    if value == "24:00":
        return MINUTES_PER_DAY
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def parse_date(value: str) -> date:
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_url(base_url: str, path_or_url: str) -> str:
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return urljoin(base_url, path_or_url.lstrip("/"))


def stable_index(seed: str, size: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:16], 16) % size


def format_minutes(value: int) -> str:
    if value == MINUTES_PER_DAY:
        return "24:00"
    return f"{value // 60:02d}:{value % 60:02d}"


def allocated_lengths(total: int, count: int, seed: str, minimum: int) -> list[int]:
    """Split a continuous range into deterministic, credible, non-uniform spans."""
    require(count > 0, "Cannot allocate a range across zero tasks")
    require(total >= count * minimum, "Task range is too short for the requested minimum")
    weights = [37 + stable_index(f"{seed}|weight|{index}", 83) for index in range(count)]
    distributable = total - count * minimum
    weight_total = sum(weights)
    extras = [(distributable * weight) // weight_total for weight in weights]
    lengths = [minimum + extra for extra in extras]
    remainder = total - sum(lengths)
    fractions = [
        ((distributable * weight) % weight_total, stable_index(f"{seed}|tie|{index}", 10_000), index)
        for index, weight in enumerate(weights)
    ]
    for _, _, index in sorted(fractions, reverse=True)[:remainder]:
        lengths[index] += 1
    require(sum(lengths) == total, "Internal time allocation did not preserve the range")
    return lengths


def task_ranges(day_date: str, count: int, autonomous: dict) -> list[tuple[str, str]]:
    autonomous_start = minutes(autonomous["start"])
    autonomous_end = minutes(autonomous["end"])
    use_two_before = count >= 7 and stable_index(f"{day_date}|pre-autonomous-count", 2) == 1
    before_count = 2 if use_two_before else 1
    after_count = count - before_count
    before_lengths = allocated_lengths(
        autonomous_start,
        before_count,
        f"{day_date}|before",
        62 if before_count == 2 else autonomous_start,
    )
    after_lengths = allocated_lengths(
        MINUTES_PER_DAY - autonomous_end,
        after_count,
        f"{day_date}|after",
        82,
    )

    ranges = []
    cursor = 0
    for length in before_lengths:
        ranges.append((format_minutes(cursor), format_minutes(cursor + length)))
        cursor += length
    require(cursor == autonomous_start, f"{day_date} pre-autonomous allocation mismatch")

    cursor = autonomous_end
    for length in after_lengths:
        ranges.append((format_minutes(cursor), format_minutes(cursor + length)))
        cursor += length
    require(cursor == MINUTES_PER_DAY, f"{day_date} post-autonomous allocation mismatch")
    return ranges


def validate_public_days(public_days: list[dict]) -> list[str]:
    require(isinstance(public_days, list), "metadata/days.json must be a list")
    dates = [item.get("date") for item in public_days]
    require(all(isinstance(value, str) for value in dates), "Every public day needs a date")
    require(dates == sorted(dates), "Public day dates must be sorted ascending")
    require(len(dates) == len(set(dates)), "Public day dates must be unique")

    for item in public_days:
        day_date = item["date"]
        parse_date(day_date)
        missing = set(REQUIRED_PUBLIC_FIELDS).difference(item)
        require(not missing, f"{day_date} is missing public fields: {sorted(missing)}")
        for field in REQUIRED_PUBLIC_FIELDS:
            require(str(item[field]).strip(), f"{day_date} has an empty public field: {field}")
    return dates


def validate_config(config: dict) -> None:
    require(config.get("schema") == "granted-hours-timetable-calendar-v2", "Config schema must be v2")
    require(config.get("timezone") == "Asia/Shanghai", "Config timezone must be Asia/Shanghai")
    require(config.get("canonical_base_url", "").startswith("https://"), "Config needs canonical_base_url")

    autonomous = config.get("autonomous_hour", {})
    start = minutes(autonomous.get("start", ""))
    end = minutes(autonomous.get("end", ""))
    require(0 <= start < end <= MINUTES_PER_DAY, "autonomous_hour must be within one day")
    for field in ("label_en", "label_zh", "short_en", "short_zh", "note_en", "note_zh"):
        require(str(autonomous.get(field, "")).strip(), f"autonomous_hour missing {field}")

    note = config.get("public_data_note", {})
    require(str(note.get("en", "")).strip(), "public_data_note.en is required")
    require(str(note.get("zh", "")).strip(), "public_data_note.zh is required")

    taxonomy = config.get("taxonomy", {})
    require(REQUIRED_TAXONOMY.issubset(taxonomy), "Config taxonomy is missing required categories")
    for category, entry in taxonomy.items():
        for field in ("label_en", "label_zh", "short_en", "short_zh", "description_en", "description_zh"):
            require(str(entry.get(field, "")).strip(), f"Taxonomy {category} missing {field}")

    slots = config.get("default_work_slots", [])
    require(slots, "default_work_slots is required")
    cursor = 0
    for slot in slots:
        start_slot = minutes(slot["start"])
        end_slot = minutes(slot["end"])
        if cursor == start:
            cursor = end
        require(start_slot == cursor, f"default_work_slots gap or overlap at {slot['start']}")
        require(start_slot < end_slot, f"default_work_slots invalid range {slot['start']}-{slot['end']}")
        require(not (start_slot < end and end_slot > start), "default_work_slots overlap autonomous hour")
        require(slot["category"] in taxonomy, f"default_work_slots unknown category {slot['category']}")
        cursor = end_slot
    require(cursor == MINUTES_PER_DAY, "default_work_slots must cover all non-autonomous time")


def load_history(path: Path) -> dict[str, dict]:
    require(path.exists(), f"History source does not exist: {path}")
    source = read_json(path)
    require(
        source.get("schema") == "granted-hours-timetable-history-v2",
        "History schema must be granted-hours-timetable-history-v2",
    )
    days = source.get("days")
    require(isinstance(days, list), "History days must be a list")
    history_by_date = {}
    for entry in days:
        require(isinstance(entry, dict), "Every history entry must be an object")
        day_date = entry.get("date")
        require(isinstance(day_date, str), "Every history entry needs a date")
        parse_date(day_date)
        require(day_date not in history_by_date, f"Duplicate history entry: {day_date}")
        require(
            set(entry) == {"date", "provenance", "assigned_residues"},
            f"{day_date} history must contain only date/provenance/assigned_residues",
        )
        require(entry.get("provenance") in ALLOWED_PROVENANCE - {"inferred"}, f"{day_date} has invalid authored provenance")
        residues = entry.get("assigned_residues")
        require(isinstance(residues, list) and 5 <= len(residues) <= 8, f"{day_date} history needs 5-8 assigned residues")
        signatures = set()
        for index, residue in enumerate(residues):
            require(isinstance(residue, dict), f"{day_date} residue {index + 1} must be an object")
            require(
                set(residue) == {"category", "en", "zh"},
                f"{day_date} residue {index + 1} must contain only category/en/zh",
            )
            require(residue["category"] in REQUIRED_TAXONOMY, f"{day_date} residue {index + 1} has an unknown category")
            require(str(residue["en"]).strip(), f"{day_date} residue {index + 1} missing en")
            require(str(residue["zh"]).strip(), f"{day_date} residue {index + 1} missing zh")
            signature = (residue["category"], residue["en"], residue["zh"])
            require(signature not in signatures, f"{day_date} assigned residues must be unique")
            signatures.add(signature)
        history_by_date[day_date] = entry
    return history_by_date


def load_legacy(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    source = read_json(path)
    return {item["date"]: item for item in source.get("days", []) if item.get("date")}


def inferred_history(public_entry: dict) -> dict:
    """Deterministic public-safe fallback for a synthetic future public day."""
    return {
        "date": public_entry["date"],
        "provenance": "inferred",
        "assigned_residues": [
            {
                "category": "system_maintenance",
                "en": "Run the routine service-health pass and preserve actionable failure evidence",
                "zh": "执行例行服务健康检查并保留可操作的故障证据",
            },
            {
                "category": "research_synthesis",
                "en": "Verify public-source freshness and separate confirmed findings from open questions",
                "zh": "核验公开来源的新鲜度并区分已确认发现与待解问题",
            },
            {
                "category": "document_processing",
                "en": "Consolidate working notes into a concise bilingual review brief",
                "zh": "将工作笔记整理为简明的双语复核简报",
            },
            {
                "category": "code_development",
                "en": "Resolve a queued interface maintenance item and run focused regression checks",
                "zh": "处理一项排队中的界面维护任务并执行聚焦回归检查",
            },
            {
                "category": "social_media_organization",
                "en": "Organize the public-content queue and reconcile pending publication evidence",
                "zh": "整理公开内容队列并核对待处理的发布证据",
            },
            {
                "category": "visual_production",
                "en": "Prepare a reusable visual reference sheet and audit its composition",
                "zh": "准备可复用的视觉参考表并审查其构图",
            },
            {
                "category": "system_maintenance",
                "en": "Validate backup and recovery state before closing the maintenance cycle",
                "zh": "在结束维护周期前验证备份与恢复状态",
            },
        ],
    }


def build_tasks(public_entry: dict, config: dict, history_entry: dict | None) -> tuple[list[dict], str]:
    history = history_entry or inferred_history(public_entry)
    day_date = public_entry["date"]
    residues = history["assigned_residues"]
    ranges = task_ranges(day_date, len(residues), config["autonomous_hour"])
    tasks = []
    for residue, (start, end) in zip(residues, ranges):
        category = residue["category"]
        taxonomy_entry = config["taxonomy"][category]
        description_en = residue["en"]
        description_zh = residue["zh"]
        require(
            public_entry["title_en"].lower() not in description_en.lower()
            and public_entry["title_zh"] not in description_zh,
            f"{day_date} assigned residue must not mention the autonomous artwork title",
        )
        tasks.append(
            {
                "origin": "assigned",
                "category": category,
                "start": start,
                "end": end,
                "label_en": taxonomy_entry["label_en"],
                "label_zh": taxonomy_entry["label_zh"],
                "en": description_en,
                "zh": description_zh,
                "short_en": taxonomy_entry["short_en"],
                "short_zh": taxonomy_entry["short_zh"],
            }
        )
    return tasks, history["provenance"]


def build_cell_assigned(tasks: list[dict]) -> list[dict]:
    markers = []
    seen = set()
    for task in tasks:
        if task["category"] in seen:
            continue
        seen.add(task["category"])
        markers.append(
            {
                "origin": "assigned",
                "category": task["category"],
                "label_en": task["label_en"],
                "label_zh": task["label_zh"],
                "short_en": task["short_en"],
                "short_zh": task["short_zh"],
            }
        )
        if len(markers) == 2:
            break
    return markers


def default_jewel(public_entry: dict, config: dict) -> tuple[str, str]:
    return (
        (
            f"{public_entry['title_en']} is the autonomous public work for this date. "
            "The calendar can mark the entrance, but it cannot manage the dream inside it."
        ),
        (
            f"《{public_entry['title_zh']}》是这一天的自主公开作品。"
            "日历可以标出入口，但不能管理其中的梦。"
        ),
    )


def build_autonomous_work(public_entry: dict, config: dict, legacy_entry: dict | None) -> dict:
    autonomous = config["autonomous_hour"]
    if legacy_entry and legacy_entry.get("jewel_en") and legacy_entry.get("jewel_zh"):
        jewel_en = legacy_entry["jewel_en"]
        jewel_zh = legacy_entry["jewel_zh"]
    else:
        jewel_en, jewel_zh = default_jewel(public_entry, config)

    return {
        "origin": "self",
        "category": "autonomous_artwork",
        "start": autonomous["start"],
        "end": autonomous["end"],
        "label_en": autonomous["label_en"],
        "label_zh": autonomous["label_zh"],
        "short_en": autonomous["short_en"],
        "short_zh": autonomous["short_zh"],
        "title_en": public_entry["title_en"],
        "title_zh": public_entry["title_zh"],
        "variable_en": public_entry["variable_en"],
        "variable_zh": public_entry["variable_zh"],
        "en": f"Enter live artwork: {public_entry['title_en']}",
        "zh": f"进入实时作品：《{public_entry['title_zh']}》",
        "note_en": jewel_en,
        "note_zh": jewel_zh,
        "archive_url": public_entry["archive_url"],
        "live_url": public_entry["live_url"],
        "preview": public_entry["preview"],
    }


def relation_candidates(day_date: str, dates: list[str]) -> list[str]:
    others = [candidate for candidate in dates if candidate != day_date]
    nonconsecutive = [
        candidate
        for candidate in others
        if abs((parse_date(day_date) - parse_date(candidate)).days) > 1
    ]
    return nonconsecutive or others


def valid_relation(day_date: str, relation: dict, public_by_date: dict[str, dict], corpus_size: int) -> bool:
    target = relation.get("target")
    if target not in public_by_date:
        return False
    if corpus_size > 2 and abs((parse_date(day_date) - parse_date(target)).days) <= 1:
        return False
    return all(str(relation.get(field, "")).strip() for field in ("axis_en", "axis_zh", "sentence_en", "sentence_zh"))


def build_relations(day_date: str, public_entry: dict, dates: list[str], public_by_date: dict[str, dict], legacy_entry: dict | None) -> list[dict]:
    relations = []
    if legacy_entry:
        for relation in legacy_entry.get("relations", []):
            if valid_relation(day_date, relation, public_by_date, len(dates)):
                relations.append(
                    {
                        "origin": "curated",
                        "target": relation["target"],
                        "axis_en": relation["axis_en"],
                        "axis_zh": relation["axis_zh"],
                        "sentence_en": relation["sentence_en"],
                        "sentence_zh": relation["sentence_zh"],
                    }
                )

    if relations:
        return relations

    candidates = relation_candidates(day_date, dates)
    require(candidates, f"{day_date} needs at least one possible relation target")
    target_date = candidates[stable_index(f"{day_date}|{public_entry['title_en']}|relation", len(candidates))]
    target = public_by_date[target_date]
    return [
        {
            "origin": "generated",
            "target": target_date,
            "axis_en": f"another entrance through {target['variable_en']}",
            "axis_zh": f"经由「{target['variable_zh']}」的另一个入口",
            "sentence_en": f"The calendar skips sequence and reopens the same problem through {target['title_en']}.",
            "sentence_zh": f"日历跳过顺序，经由《{target['title_zh']}》重新打开同一个问题。",
        }
    ]


def validate_tasks(day_date: str, tasks: list[dict], autonomous: dict) -> None:
    start = minutes(autonomous["start"])
    end = minutes(autonomous["end"])
    require(tasks == sorted(tasks, key=lambda item: minutes(item["start"])), f"{day_date} tasks must be chronological")

    cursor = 0
    for task in tasks:
        for field in ("origin", "category", "start", "end", "en", "zh", "short_en", "short_zh", "label_en", "label_zh"):
            require(str(task.get(field, "")).strip(), f"{day_date} task missing {field}")
        require(task["origin"] == "assigned", f"{day_date} task origin must be assigned")
        task_start = minutes(task["start"])
        task_end = minutes(task["end"])
        if cursor == start:
            cursor = end
        require(task_start == cursor, f"{day_date} has a task coverage gap at {task['start']}")
        require(task_start < task_end, f"{day_date} has an invalid task range")
        require(not (task_start < end and task_end > start), f"{day_date} has task overlap with autonomous hour")
        cursor = task_end
    require(cursor == MINUTES_PER_DAY, f"{day_date} tasks must cover all non-autonomous time")


def validate_day(day: dict, dates: set[str], corpus_size: int, autonomous: dict) -> None:
    for field in ("date", "title_en", "title_zh", "variable_en", "variable_zh", "archive_url", "live_url", "preview"):
        require(str(day.get(field, "")).strip(), f"{day.get('date')} missing {field}")
    for field in ("archive_url", "live_url", "preview", "gif"):
        require(day[field].startswith("https://"), f"{day['date']} {field} must be an absolute URL")

    validate_tasks(day["date"], day["task_residues"], autonomous)

    self_work = day["autonomous_work"]
    require(self_work.get("origin") == "self", f"{day['date']} autonomous_work must have origin self")
    for field in ("start", "end", "title_en", "title_zh", "variable_en", "variable_zh", "en", "zh", "note_en", "note_zh", "live_url"):
        require(str(self_work.get(field, "")).strip(), f"{day['date']} autonomous_work missing {field}")
    require(minutes(self_work["start"]) == minutes(autonomous["start"]), f"{day['date']} autonomous start mismatch")
    require(minutes(self_work["end"]) == minutes(autonomous["end"]), f"{day['date']} autonomous end mismatch")

    require(day.get("relations"), f"{day['date']} needs at least one semantic relation")
    for relation in day["relations"]:
        target = relation["target"]
        require(target in dates, f"{day['date']} relation points outside public corpus: {target}")
        if corpus_size > 2:
            delta = abs((parse_date(day["date"]) - parse_date(target)).days)
            require(delta > 1, f"{day['date']} relation must be nonconsecutive: {target}")
        for field in ("axis_en", "axis_zh", "sentence_en", "sentence_zh"):
            require(str(relation.get(field, "")).strip(), f"{day['date']} relation missing {field}")


def build_data(
    public_days: list[dict],
    config: dict,
    legacy_by_date: dict[str, dict],
    history_by_date: dict[str, dict],
) -> dict:
    dates = validate_public_days(public_days)
    validate_config(config)
    public_by_date = {item["date"]: item for item in public_days}
    base_url = config["canonical_base_url"]
    output_days = []
    require(history_by_date, "At least one authored history entry is required")
    latest_authored_date = max(history_by_date)

    for public_entry in public_days:
        day_date = public_entry["date"]
        history_entry = history_by_date.get(day_date)
        require(
            history_entry is not None or day_date > latest_authored_date,
            f"{day_date} is missing authored history; inferred fallback is reserved for future dates",
        )
        public_absolute = {
            **public_entry,
            "archive_url": canonical_url(base_url, public_entry["archive_url"]),
            "live_url": canonical_url(base_url, public_entry["live_url"]),
            "preview": canonical_url(base_url, public_entry["preview"]),
            "gif": canonical_url(base_url, public_entry["gif"]),
        }
        legacy_entry = legacy_by_date.get(day_date)
        tasks, history_provenance = build_tasks(public_absolute, config, history_entry)
        autonomous_work = build_autonomous_work(public_absolute, config, legacy_entry)
        relations = build_relations(day_date, public_absolute, dates, public_by_date, legacy_entry)
        day = {
            **{field: public_absolute[field] for field in REQUIRED_PUBLIC_FIELDS},
            "jewel_en": autonomous_work["note_en"],
            "jewel_zh": autonomous_work["note_zh"],
            "history_provenance": history_provenance,
            "cell_assigned": build_cell_assigned(tasks),
            "cell_self": {
                "origin": "self",
                "short_en": config["autonomous_hour"]["short_en"],
                "short_zh": config["autonomous_hour"]["short_zh"],
                "title_en": public_entry["title_en"],
                "title_zh": public_entry["title_zh"],
            },
            "task_residues": tasks,
            "autonomous_work": autonomous_work,
            "relations": relations,
        }
        validate_day(day, set(dates), len(dates), config["autonomous_hour"])
        output_days.append(day)

    return {
        "schema": "granted-hours-timetable-v2",
        "timezone": config["timezone"],
        "canonical_base_url": config["canonical_base_url"],
        "autonomous_hour": config["autonomous_hour"],
        "public_data_note": config["public_data_note"],
        "note_en": config["public_data_note"]["en"],
        "note_zh": config["public_data_note"]["zh"],
        "taxonomy": config["taxonomy"],
        "days": output_days,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-days", type=Path, default=DEFAULT_PUBLIC_DAYS)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--legacy-overrides", type=Path, default=DEFAULT_LEGACY_OVERRIDES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    public_days = read_json(args.public_days)
    config = read_json(args.config)
    history_by_date = load_history(args.history)
    legacy_by_date = load_legacy(args.legacy_overrides)
    output_data = build_data(public_days, config, legacy_by_date, history_by_date)

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "export const timetableData = "
        + json.dumps(output_data, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    try:
        display_path = output_path.resolve().relative_to(ROOT)
    except ValueError:
        display_path = output_path
    print(f"Wrote {display_path} with {len(output_data['days'])} public days.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
