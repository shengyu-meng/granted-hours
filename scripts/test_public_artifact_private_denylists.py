#!/usr/bin/env python3
"""Count-only regression gate for private terms in generated public artifacts."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import public_projection_privacy as privacy


ROOT = Path(__file__).resolve().parents[1]
HOLDINGS_PATH = ROOT / ".private" / "holdings-denylist.json"
SOURCES_PATH = ROOT / ".private" / "self-media-denylist.json"
IDENTITIES_PATH = ROOT / ".private" / "identity-denylist.json"


def public_artifact_paths() -> list[Path]:
    paths = [*sorted((ROOT / "metadata").glob("*.json"))]
    paths.append(ROOT / "src" / "timetable" / "timetable-data.js")
    paths.extend(
        path
        for path in sorted((ROOT / "docs" / "timetable").rglob("*"))
        if path.is_file()
    )
    return paths


class PublicArtifactPrivateDenylistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.holdings_terms = privacy.load_private_denylist(
            HOLDINGS_PATH,
            "holdings",
        )
        cls.source_terms = privacy.load_private_denylist(
            SOURCES_PATH,
            "self_media_sources",
        )
        cls.identity_terms = privacy.load_private_denylist(
            IDENTITIES_PATH,
            "identities",
        )

    def test_generated_public_artifacts_have_zero_private_term_matches(self) -> None:
        counts: dict[str, int] = {}
        for path in public_artifact_paths():
            public_text = path.read_text(encoding="utf-8", errors="ignore")
            counts[str(path.relative_to(ROOT))] = (
                int(
                    privacy.denied_terms_present(
                        public_text,
                        self.holdings_terms,
                        contextual_ambiguous=True,
                    )
                )
                + int(
                    privacy.denied_terms_present(
                        public_text,
                        self.source_terms,
                    )
                )
                + int(
                    privacy.denied_terms_present(
                        public_text,
                        self.identity_terms,
                    )
                )
            )
        self.assertEqual(
            sum(counts.values()),
            0,
            msg=f"private-term match counts by public artifact: {counts}",
        )

    def test_collaboration_copy_has_no_third_party_or_redacted_original_labels(self) -> None:
        forbidden = (
            "你主动与 Hermes",
            "脱敏原话",
            "Sanitized original dialogue",
            "工作记录已打码",
            "Work record redacted",
        )
        findings = {
            str(path.relative_to(ROOT)): [term for term in forbidden if term in path.read_text(encoding="utf-8", errors="ignore")]
            for path in public_artifact_paths()
        }
        self.assertFalse(
            any(findings.values()),
            msg=f"legacy collaboration framing remains: {findings}",
        )

    def test_public_agent_artifacts_have_no_private_binding_field(self) -> None:
        forbidden_public_field = "evidence" + "_hashes"
        counts = {
            str(path.relative_to(ROOT)): path.read_text(
                encoding="utf-8",
                errors="ignore",
            ).count(forbidden_public_field)
            for path in public_artifact_paths()
        }
        self.assertEqual(
            sum(counts.values()),
            0,
            msg=f"forbidden Agent hash-field counts by public artifact: {counts}",
        )

    def test_live_holdings_denylist_is_owner_read_write_only(self) -> None:
        self.assertEqual(HOLDINGS_PATH.stat().st_mode & 0o777, 0o600)

    def test_market_public_summaries_have_no_local_technical_traces(self) -> None:
        snapshot = json.loads(
            (ROOT / "metadata" / "timetable-pulses.json").read_text(
                encoding="utf-8"
            )
        )
        findings: list[str] = []
        for day in snapshot["days"]:
            for pulse in day["pulses"]:
                if pulse.get("category") not in {
                    "ah_market_scan",
                    "us_market_scan",
                }:
                    continue
                public_copy = " ".join(
                    str(pulse.get(field, ""))
                    for field in ("summary_zh", "summary_en")
                )
                if privacy.PRIVATE_TECHNICAL_RE.search(public_copy):
                    findings.append(
                        f"{day['date']} {pulse['category']}"
                    )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
