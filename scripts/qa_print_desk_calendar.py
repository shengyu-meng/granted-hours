#!/usr/bin/env python3
"""Validate and render a Granted Hours 210 x 140 mm desk-calendar PDF."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import pdfplumber
    from PIL import Image, ImageStat
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - environment diagnostic
    raise SystemExit(
        "Missing PDF QA dependency. Run with the Codex bundled Python. "
        f"Original error: {exc}"
    ) from exc


PAGE_W_MM = 210.0
PAGE_H_MM = 140.0
MM_PER_POINT = 25.4 / 72.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--render-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument("--require-qr-decode", action="store_true")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(failures: list[str], condition: bool, message: str) -> None:
    if not condition:
        failures.append(message)


def page_uris(page: Any) -> list[str]:
    uris: list[str] = []
    for ref in page.get("/Annots", []) or []:
        annotation = ref.get_object()
        action = annotation.get("/A")
        if action and action.get("/URI"):
            uris.append(str(action.get("/URI")))
    return uris


def render_pdf(pdf: Path, render_dir: Path, dpi: int) -> list[Path]:
    executable = shutil.which("pdftoppm")
    if not executable:
        raise RuntimeError("pdftoppm is unavailable")
    render_dir.mkdir(parents=True, exist_ok=True)
    for stale in render_dir.glob("page-*.jpg"):
        stale.unlink()
    prefix = render_dir / "page"
    subprocess.run(
        [executable, "-jpeg", "-jpegopt", "quality=88", "-r", str(dpi), str(pdf), str(prefix)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    pages = sorted(
        render_dir.glob("page-*.jpg"),
        key=lambda path: int(path.stem.rsplit("-", 1)[-1]),
    )
    return pages


def expected_pixels(dpi: int) -> tuple[int, int]:
    return round(PAGE_W_MM / 25.4 * dpi), round(PAGE_H_MM / 25.4 * dpi)


def inspect_rendered_pages(
    rendered: list[Path], expected_count: int, dpi: int, failures: list[str]
) -> list[dict[str, Any]]:
    fail(failures, len(rendered) == expected_count, f"Rendered {len(rendered)} pages, expected {expected_count}")
    expected_w, expected_h = expected_pixels(dpi)
    metrics: list[dict[str, Any]] = []
    for index, path in enumerate(rendered, start=1):
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            stat = ImageStat.Stat(rgb)
            mean = sum(stat.mean) / 3
            variance = sum(stat.var) / 3
            fail(
                failures,
                abs(rgb.width - expected_w) <= 2 and abs(rgb.height - expected_h) <= 2,
                f"Rendered page {index} has unexpected pixels {rgb.size}",
            )
            fail(failures, 8 < mean < 248, f"Rendered page {index} has suspicious mean {mean:.2f}")
            fail(failures, variance > 35, f"Rendered page {index} appears blank (variance {variance:.2f})")
            metrics.append(
                {
                    "page": index,
                    "pixels": [rgb.width, rgb.height],
                    "mean": round(mean, 2),
                    "variance": round(variance, 2),
                }
            )
    return metrics


def decode_day_qrs(
    rendered: list[Path], manifest: dict[str, Any], dpi: int, failures: list[str]
) -> dict[str, Any]:
    try:
        import zxingcpp  # type: ignore
    except ImportError:
        failures.append("zxingcpp is required for QR decode validation")
        return {"available": False, "decoded": 0}
    cover_offset = int(manifest.get("cover_pages", 0))
    scale = dpi / 25.4
    left = int((181.0 - 3.0) * scale)
    right = int((202.0 + 3.0) * scale)
    top = int((140.0 - (29.5 + 3.0)) * scale)
    bottom = int((140.0 - (11.0 - 3.0)) * scale)
    decoded = 0
    for record in manifest["pages"]:
        pdf_page_number = cover_offset + int(record["page"])
        image_path = rendered[pdf_page_number - 1]
        with Image.open(image_path) as image:
            crop = image.convert("RGB").crop((left, top, right, bottom))
            results = zxingcpp.read_barcodes(crop)
        texts = [item.text for item in results]
        expected = record["qr_url"]
        fail(
            failures,
            expected in texts,
            f"QR page for {record['date']} did not decode to its exact URL; decoded={texts}",
        )
        if expected in texts:
            decoded += 1
    return {"available": True, "decoded": decoded, "expected": len(manifest["pages"])}


def build_contact_sheet(
    rendered: list[Path], manifest: dict[str, Any], output: Path
) -> list[int]:
    cover_offset = int(manifest.get("cover_pages", 0))
    records = manifest["pages"]
    densest = max(records, key=lambda item: int(item.get("timeline_events", 0)))
    absence = next((item for item in records if item.get("type") != "live"), records[0])
    most_collaboration = max(records, key=lambda item: int(item.get("collaboration_items", 0)))
    long_header = next((item for item in records if item.get("header_truncated")), records[len(records) // 2])
    middle = records[len(records) // 2]
    numbers = [1] if cover_offset else []
    numbers.extend(
        [
            cover_offset + int(records[0]["page"]),
            cover_offset + int(absence["page"]),
            cover_offset + int(densest["page"]),
            cover_offset + int(most_collaboration["page"]),
            cover_offset + int(long_header["page"]),
            cover_offset + int(middle["page"]),
            cover_offset + int(records[-1]["page"]),
        ]
    )
    numbers = list(dict.fromkeys(numbers))
    thumb_w = 840
    thumb_h = round(thumb_w * PAGE_H_MM / PAGE_W_MM)
    gap = 24
    cols = 2
    rows = (len(numbers) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * thumb_w + (cols + 1) * gap, rows * thumb_h + (rows + 1) * gap), "#D8D2C7")
    for index, number in enumerate(numbers):
        with Image.open(rendered[number - 1]) as opened:
            thumb = opened.convert("RGB")
            thumb.thumbnail((thumb_w, thumb_h), Image.Resampling.LANCZOS)
            x = gap + (index % cols) * (thumb_w + gap)
            y = gap + (index // cols) * (thumb_h + gap)
            sheet.paste(thumb, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, "JPEG", quality=90, optimize=True)
    return numbers


def main() -> int:
    args = parse_args()
    pdf = args.pdf.expanduser().resolve()
    manifest_path = (args.manifest or pdf.with_suffix(".manifest.json")).expanduser().resolve()
    report_path = (args.report or pdf.with_suffix(".qa.json")).expanduser().resolve()
    render_dir = args.render_dir.expanduser().resolve()
    failures: list[str] = []

    fail(failures, pdf.exists(), f"PDF missing: {pdf}")
    fail(failures, manifest_path.exists(), f"Manifest missing: {manifest_path}")
    if failures:
        print(json.dumps({"passed": False, "failures": failures}, indent=2))
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    reader = PdfReader(str(pdf))
    expected_pages = int(manifest["pdf_pages"])
    fail(failures, len(reader.pages) == expected_pages, f"PDF has {len(reader.pages)} pages, expected {expected_pages}")
    fail(failures, sha256_file(pdf) == manifest["output_sha256"], "PDF SHA-256 differs from manifest")

    dimensions: list[list[float]] = []
    for index, page in enumerate(reader.pages, start=1):
        width_mm = float(page.mediabox.width) * MM_PER_POINT
        height_mm = float(page.mediabox.height) * MM_PER_POINT
        dimensions.append([round(width_mm, 3), round(height_mm, 3)])
        fail(failures, abs(width_mm - PAGE_W_MM) <= 0.02, f"Page {index} width is {width_mm:.3f} mm")
        fail(failures, abs(height_mm - PAGE_H_MM) <= 0.02, f"Page {index} height is {height_mm:.3f} mm")

    cover_offset = int(manifest.get("cover_pages", 0))
    with pdfplumber.open(str(pdf)) as opened:
        if cover_offset:
            cover_text = opened.pages[0].extract_text() or ""
            fail(failures, "GRANTED HOURS" in cover_text and "授时" in cover_text, "Cover title is incomplete")
        for record in manifest["pages"]:
            pdf_page_number = cover_offset + int(record["page"])
            text = opened.pages[pdf_page_number - 1].extract_text() or ""
            fail(
                failures,
                f"CRYSTALLIZATION {record['date']}" in text,
                f"Date text missing on page for {record['date']}",
            )
            fail(failures, "OPEN THIS CIVIL DAY" in text, f"QR caption missing for {record['date']}")
            fail(
                failures,
                record["qr_url"] in page_uris(reader.pages[pdf_page_number - 1]),
                f"Exact QR hyperlink annotation missing for {record['date']}",
            )
            fail(
                failures,
                not any(char in text for char in "‐‑‒–—―"),
                f"Non-ASCII dash remains on page for {record['date']}",
            )

    rendered = render_pdf(pdf, render_dir, args.dpi)
    render_metrics = inspect_rendered_pages(rendered, expected_pages, args.dpi, failures)
    qr_result = {"available": False, "decoded": 0}
    if args.require_qr_decode:
        qr_result = decode_day_qrs(rendered, manifest, args.dpi, failures)
    contact_sheet = render_dir / "contact-sheet.jpg"
    contact_pages = build_contact_sheet(rendered, manifest, contact_sheet)

    report = {
        "schema": "granted-hours-print-desk-calendar-qa-v1",
        "passed": not failures,
        "pdf": str(pdf),
        "pdf_sha256": sha256_file(pdf),
        "page_count": len(reader.pages),
        "page_size_mm": dimensions[0] if dimensions else None,
        "date_range": manifest["date_range"],
        "live_artwork_days": manifest["live_artwork_days"],
        "absence_days": manifest["absence_days"],
        "rendered_pages": len(rendered),
        "render_metrics": render_metrics,
        "qr_decode": qr_result,
        "contact_sheet": str(contact_sheet),
        "contact_sheet_pages": contact_pages,
        "failures": failures,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
