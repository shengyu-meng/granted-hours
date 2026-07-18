#!/usr/bin/env python3
"""Build public data for the Granted Hours non-human timetable."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DAYS = ROOT / "metadata" / "days.json"
TIMETABLE_SOURCE = ROOT / "metadata" / "timetable-v1.json"
OUTPUT = ROOT / "src" / "timetable" / "timetable-data.js"

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


def minutes(value: str) -> int:
    if value == "24:00":
        return 24 * 60
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def parse_date(value: str) -> date:
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> int:
    public_days = json.loads(PUBLIC_DAYS.read_text(encoding="utf-8"))
    source = json.loads(TIMETABLE_SOURCE.read_text(encoding="utf-8"))

    latest = sorted(public_days, key=lambda item: item["date"])[-7:]
    latest_dates = [item["date"] for item in latest]
    configured_dates = [item["date"] for item in source["days"]]
    require(
        configured_dates == latest_dates,
        f"metadata/timetable-v1.json must describe latest seven public dates: {latest_dates}",
    )

    public_by_date = {item["date"]: item for item in public_days}
    source_by_date = {item["date"]: item for item in source["days"]}

    start = minutes(source["autonomous_hour"]["start"])
    end = minutes(source["autonomous_hour"]["end"])
    require(0 <= start < end <= 24 * 60, "autonomous_hour must be within one day")

    merged_days = []
    for day_date in latest_dates:
        public_entry = public_by_date[day_date]
        source_entry = source_by_date[day_date]
        missing = set(REQUIRED_PUBLIC_FIELDS).difference(public_entry)
        require(not missing, f"{day_date} is missing public fields: {sorted(missing)}")
        residues = source_entry["task_residues"]
        require(5 <= len(residues) <= 8, f"{day_date} must have 5-8 task residues")
        for residue in residues:
            residue_start = minutes(residue["start"])
            residue_end = minutes(residue["end"])
            require(residue_start < residue_end, f"{day_date} has an invalid residue range")
            overlaps_jewel = residue_start < end and residue_end > start
            require(not overlaps_jewel, f"{day_date} has task residue overlapping autonomous hour")

        relations = source_entry["relations"]
        require(relations, f"{day_date} needs at least one semantic relation")
        for relation in relations:
            target = relation["target"]
            require(target in source_by_date, f"{day_date} relation points outside the timetable slice: {target}")
            delta = abs((parse_date(day_date) - parse_date(target)).days)
            require(delta > 1, f"{day_date} relation must be nonconsecutive: {target}")

        merged_days.append(
            {
                **{field: public_entry[field] for field in REQUIRED_PUBLIC_FIELDS},
                "jewel_en": source_entry["jewel_en"],
                "jewel_zh": source_entry["jewel_zh"],
                "task_residues": residues,
                "relations": relations,
            }
        )

    output_data = {
        "schema": source["schema"],
        "timezone": source["timezone"],
        "autonomous_hour": source["autonomous_hour"],
        "note_en": source["note_en"],
        "note_zh": source["note_zh"],
        "days": merged_days,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "export const timetableData = "
        + json.dumps(output_data, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT.relative_to(ROOT)} with {len(merged_days)} public days.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
