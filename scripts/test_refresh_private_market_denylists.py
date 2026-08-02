#!/usr/bin/env python3
"""Safety tests for the live-position-only holdings denylist refresh."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import public_projection_privacy as privacy
import refresh_private_market_denylists as refresh


class RefreshPrivateMarketDenylistsTests(unittest.TestCase):
    def write_source(self, root: Path, source: object) -> Path:
        path = root / "portfolio.json"
        path.write_text(
            json.dumps(source, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def test_only_active_positions_contribute_bounded_market_aliases(self) -> None:
        positions = [
            {
                "code": "600123.SH",
                "name": "合成持有甲",
                "market": "CN",
                "qty": 12,
                "qty_unknown": False,
                "account": "must-not-be-an-alias",
            },
            {
                "code": "0700.HK",
                "name": "合成持有乙",
                "market": "HK",
                "qty": None,
                "qty_unknown": True,
            },
            {
                "code": "SKIP",
                "name": "合成零仓",
                "market": "US",
                "qty": 0,
                "qty_unknown": False,
            },
        ]
        terms = set(refresh.derive_holdings_terms(positions))
        for expected in (
            "合成持有甲",
            "600123.SH",
            "600123",
            "SH.600123",
            "SH600123",
            "合成持有乙",
            "0700.HK",
            "00700.HK",
            "HK.00700",
        ):
            self.assertIn(expected, terms)
        for forbidden in (
            "SKIP",
            "合成零仓",
            "must-not-be-an-alias",
            "CN",
            "HK",
        ):
            self.assertNotIn(forbidden, terms)
        self.assertNotIn("700", terms)
        self.assertNotIn("00700", terms)

    def test_watchlist_and_recommendation_siblings_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_path = self.write_source(
                root,
                {
                    "positions": [
                        {
                            "code": "HELDX",
                            "name": "合成实仓",
                            "market": "US",
                            "qty": 3,
                            "qty_unknown": False,
                        }
                    ],
                    "symbols": ["PUBLICX"],
                    "watchlist": [{"code": "PUBLICX"}],
                    "recommendations": [{"code": "PUBLICX"}],
                    "portfolio_guard_focus": ["PUBLICX"],
                    "funds": [{"code": "PUBLICX"}],
                    "accounts": [{"code": "PUBLICX"}],
                    "summary": {"featured": "PUBLICX"},
                },
            )
            output_path = root / ".private" / "holdings-denylist.json"
            refresh.refresh(source_path, output_path)
            document = json.loads(output_path.read_text(encoding="utf-8"))
            terms = tuple(document["terms"])
            facts = privacy.project_market_evidence(
                ["PUBLICX 报 31.20 美元，涨幅 +3.1%，市场判断偏强势。"],
                holdings_terms=terms,
                source_terms=(),
            )
            output_mode = os.stat(output_path).st_mode & 0o777

        self.assertEqual(
            set(document),
            {"schema", "kind", "terms"},
        )
        self.assertEqual(document["schema"], privacy.PRIVATE_DENYLIST_SCHEMA)
        self.assertEqual(document["kind"], "holdings")
        self.assertNotIn("PUBLICX", terms)
        self.assertIn("PUBLICX", " ".join(facts))
        self.assertEqual(output_mode, 0o600)

    def test_malformed_or_ambiguous_quantities_fail_closed(self) -> None:
        base = {"code": "SAFE", "name": "合成标的", "market": "US"}
        invalid_positions = (
            {**base, "qty": "3", "qty_unknown": False},
            {**base, "qty_unknown": False},
            {**base, "qty": True, "qty_unknown": False},
            {**base, "qty": -1, "qty_unknown": True},
            {**base, "qty": 3, "qty_unknown": "false"},
            {**base, "market": "unknown", "qty": 3, "qty_unknown": False},
        )
        for position in invalid_positions:
            with self.subTest(fields=sorted(position)):
                with self.assertRaises(refresh.HoldingsSourceError):
                    refresh.derive_holdings_terms([position])

    def test_negative_known_quantity_is_an_active_short_position(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_path = self.write_source(
                root,
                {
                    "positions": [
                        {
                            "code": "VALIDX",
                            "name": "合成有效仓位",
                            "market": "US",
                            "qty": 2,
                            "qty_unknown": False,
                        },
                        {
                            "code": "SHORTX",
                            "name": "合成空头仓位",
                            "market": "US",
                            "qty": -1,
                            "qty_unknown": False,
                        },
                    ]
                },
            )
            output = root / ".private" / "holdings-denylist.json"
            refresh.refresh(source_path, output)
            document = json.loads(output.read_text(encoding="utf-8"))
            terms = tuple(document["terms"])
            self.assertIn("VALIDX", terms)
            self.assertIn("SHORTX", terms)
            self.assertIn("合成空头仓位", terms)

    def test_ambiguous_tickers_are_contextual_and_qualified_aliases_are_exact(self) -> None:
        positions = [
            {
                "code": "F",
                "name": "Synthetic Motor Company",
                "market": "US",
                "qty": 1,
                "qty_unknown": False,
            },
            {
                "code": "ON",
                "name": "Synthetic Semiconductor Company",
                "market": "US",
                "qty": 1,
                "qty_unknown": False,
            },
            {
                "code": "0700.HK",
                "name": "合成港股公司",
                "market": "HK",
                "qty": 1,
                "qty_unknown": False,
            },
            {
                "code": "600123.SH",
                "name": "合成沪市公司",
                "market": "CN",
                "qty": 1,
                "qty_unknown": False,
            },
            {
                "code": "BRK.B",
                "name": "Synthetic Class Share Company",
                "market": "US",
                "qty": 1,
                "qty_unknown": False,
            },
        ]
        terms = refresh.derive_holdings_terms(positions)
        ordinary = privacy.project_market_evidence(
            [
                "AI theme stays ON; F is a grade; the public numeric price is 700 USD.",
            ],
            holdings_terms=terms,
            source_terms=(),
            maximum_facts=10,
        )
        qualified = privacy.project_market_evidence(
            [
                "ticker F rose 3.1%; stock code ON gained 2.0%; "
                "HK.700 rose 1.2%; 600123.SH gained 1.1%; BRK.B rose 0.8%.",
            ],
            holdings_terms=terms,
            source_terms=(),
            maximum_facts=10,
        )
        ordinary_copy = " ".join(ordinary)
        qualified_copy = " ".join(qualified)
        for public_value in ("AI", "ON", "F", "700"):
            self.assertIn(public_value, ordinary_copy)
        for private_form in (
            "ticker F",
            "stock code ON",
            "HK.700",
            "600123.SH",
            "BRK.B",
        ):
            self.assertNotIn(private_form, qualified_copy)
        self.assertIn(privacy.FIXED_REDACTION_BLOCK, qualified_copy)

    def test_root_positions_list_and_private_output_are_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            missing_positions = self.write_source(
                root,
                {"symbols": ["IGNORED"]},
            )
            with self.assertRaises(refresh.HoldingsSourceError):
                refresh.refresh(
                    missing_positions,
                    root / ".private" / "holdings-denylist.json",
                )
            with self.assertRaisesRegex(
                refresh.HoldingsSourceError,
                "ignored .private",
            ):
                refresh.write_private_denylist(
                    root / "public.json",
                    ("SYNTHETIC",),
                )


if __name__ == "__main__":
    unittest.main()
