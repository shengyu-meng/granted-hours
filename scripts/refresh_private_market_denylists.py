#!/usr/bin/env python3
"""Refresh the ignored holdings denylist from verified live positions only.

The source document may contain other portfolio-adjacent collections. They are
intentionally never consulted: only the root ``positions`` list participates in
the output. Private values stay process-local and are never printed.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Iterable


PRIVATE_DENYLIST_SCHEMA = "granted-hours-private-denylist-v1"
MAX_POSITIONS = 50_000
MAX_TERMS = 20_000
MAX_TERM_LENGTH = 180
MISSING = object()

CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,31}$")
PREFIX_CODE_RE = re.compile(
    r"^(?P<exchange>SH|SZ|SS|BJ|HK|US|SSE|SZSE|BSE|NASDAQ|NYSE|AMEX)"
    r"[.:-]?(?P<ticker>[A-Z0-9][A-Z0-9.-]{0,31})$"
)
SUFFIX_CODE_RE = re.compile(
    r"^(?P<ticker>[A-Z0-9][A-Z0-9.-]{0,31})"
    r"[.:-](?P<exchange>SH|SZ|SS|BJ|HK|US)$"
)


class HoldingsSourceError(ValueError):
    """Raised for a malformed or ambiguous holdings source."""


def _reject_non_finite_json(_value: str) -> None:
    raise HoldingsSourceError("Holdings source contains a non-finite number")


def _validate_output_path(path: Path) -> Path:
    resolved = path.resolve()
    if ".private" not in resolved.parts:
        raise HoldingsSourceError(
            "Output must be under an ignored .private directory"
        )
    if resolved.name in {"", ".", ".."}:
        raise HoldingsSourceError("Output must name a private denylist file")
    return resolved


def _load_positions(path: Path) -> list[object]:
    try:
        with path.open(encoding="utf-8") as source_file:
            source = json.load(
                source_file,
                parse_constant=_reject_non_finite_json,
            )
    except HoldingsSourceError:
        raise
    except OSError as error:
        raise HoldingsSourceError("Could not read holdings source") from error
    except json.JSONDecodeError as error:
        raise HoldingsSourceError("Holdings source is not valid JSON") from error
    if not isinstance(source, dict):
        raise HoldingsSourceError("Holdings source root must be an object")
    positions = source.get("positions", MISSING)
    if not isinstance(positions, list):
        raise HoldingsSourceError(
            "Holdings source must contain a root positions list"
        )
    if len(positions) > MAX_POSITIONS:
        raise HoldingsSourceError("Holdings source exceeds its position budget")
    return positions


def _is_valid_quantity(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _position_is_active(position: object) -> bool:
    if not isinstance(position, dict):
        raise HoldingsSourceError("Every position must be an object")
    quantity_unknown = position.get("qty_unknown", False)
    if not isinstance(quantity_unknown, bool):
        raise HoldingsSourceError("Position quantity status is ambiguous")
    quantity = position.get("qty", MISSING)
    if quantity_unknown:
        if quantity is not MISSING and quantity is not None:
            if not _is_valid_quantity(quantity) or float(quantity) < 0:
                raise HoldingsSourceError("Position quantity is malformed")
        return True
    if quantity is MISSING or not _is_valid_quantity(quantity):
        raise HoldingsSourceError("Position quantity is missing or malformed")
    # A negative known quantity is a real short position, not malformed data.
    # Only an exact zero is inactive; both long and short exposure must be
    # represented in the private holdings denylist.
    return float(quantity) != 0


def _required_identity(position: dict, field: str, limit: int) -> str:
    value = position.get(field)
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value.strip()) > limit
        or any(ord(character) < 32 for character in value)
    ):
        raise HoldingsSourceError("Active position identity is malformed")
    return value.strip()


def _market_family(market: str, exchange: str | None) -> str | None:
    normalized = re.sub(r"[^A-Z0-9]", "", market.upper())
    if exchange in {"HK"} or normalized in {"HK", "HKG", "HONGKONG"}:
        return "HK"
    if exchange in {"US", "NASDAQ", "NYSE", "AMEX"} or normalized in {
        "US",
        "USA",
        "NASDAQ",
        "NYSE",
        "AMEX",
    }:
        return "US"
    if exchange in {"SH", "SS", "SZ", "BJ", "SSE", "SZSE", "BSE"} or normalized in {
        "CN",
        "CHINA",
        "A",
        "ASHARE",
        "SH",
        "SSE",
        "SZ",
        "SZSE",
        "BJ",
        "BSE",
    }:
        return "CN"
    return None


def _split_code(code: str) -> tuple[str, str | None]:
    compact = re.sub(r"\s+", "", code).upper().lstrip("$")
    prefix = PREFIX_CODE_RE.fullmatch(compact)
    if prefix is not None:
        return prefix.group("ticker"), prefix.group("exchange")
    suffix = SUFFIX_CODE_RE.fullmatch(compact)
    if suffix is not None:
        return suffix.group("ticker"), suffix.group("exchange")
    if CODE_RE.fullmatch(compact) is not None:
        return compact, None
    return "", None


def _cn_exchange(ticker: str, exchange: str | None) -> str | None:
    if exchange in {"SH", "SS", "SSE"}:
        return "SH"
    if exchange in {"SZ", "SZSE"}:
        return "SZ"
    if exchange in {"BJ", "BSE"}:
        return "BJ"
    if not ticker.isdigit() or len(ticker) != 6:
        return None
    if ticker[0] in {"5", "6", "9"}:
        return "SH"
    if ticker[0] in {"0", "1", "2", "3"}:
        return "SZ"
    if ticker[0] in {"4", "8"}:
        return "BJ"
    return None


def _ticker_aliases(code: str, market: str) -> Iterable[str]:
    ticker, exchange = _split_code(code)
    if not ticker:
        return ()
    family = _market_family(market, exchange)
    aliases: set[str] = {ticker}
    if family == "US":
        aliases.update(
            {
                f"${ticker}",
                f"US.{ticker}",
                f"{ticker}.US",
                f"NASDAQ:{ticker}",
                f"NYSE:{ticker}",
            }
        )
    elif family == "HK" and ticker.isdigit():
        numeric = str(int(ticker))
        variants = {numeric, numeric.zfill(4), numeric.zfill(5)}
        for variant in variants:
            aliases.update(
                {
                    f"HK.{variant}",
                    f"HK{variant}",
                    f"{variant}.HK",
                }
            )
    elif family == "CN":
        normalized_exchange = _cn_exchange(ticker, exchange)
        if normalized_exchange is not None:
            suffixes = (
                {"SH", "SS"}
                if normalized_exchange == "SH"
                else {normalized_exchange}
            )
            aliases.update(
                {
                    f"{normalized_exchange}.{ticker}",
                    f"{normalized_exchange}{ticker}",
                }
            )
            aliases.update(f"{ticker}.{suffix}" for suffix in suffixes)
    return aliases


def derive_holdings_terms(positions: list[object]) -> tuple[str, ...]:
    terms_by_folded_value: dict[str, str] = {}

    def add(value: str) -> None:
        normalized = value.strip()
        if not normalized or len(normalized) > MAX_TERM_LENGTH:
            raise HoldingsSourceError("Derived holding alias is malformed")
        terms_by_folded_value.setdefault(normalized.casefold(), normalized)

    for position in positions:
        if not _position_is_active(position):
            continue
        assert isinstance(position, dict)
        code = _required_identity(position, "code", 64)
        name = _required_identity(position, "name", MAX_TERM_LENGTH)
        market = _required_identity(position, "market", 32)
        ticker, exchange = _split_code(code)
        if not ticker or _market_family(market, exchange) is None:
            raise HoldingsSourceError("Active position market identity is ambiguous")
        add(code)
        add(name)
        for alias in _ticker_aliases(code, market):
            add(alias)
        if len(terms_by_folded_value) > MAX_TERMS:
            raise HoldingsSourceError("Derived denylist exceeds its term budget")
    if not terms_by_folded_value:
        raise HoldingsSourceError("No active holdings were found")
    return tuple(
        sorted(
            terms_by_folded_value.values(),
            key=lambda term: (-len(term), term.casefold(), term),
        )
    )


def write_private_denylist(path: Path, terms: tuple[str, ...]) -> None:
    output = _validate_output_path(path)
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    document = {
        "schema": PRIVATE_DENYLIST_SCHEMA,
        "kind": "holdings",
        "terms": list(terms),
    }
    file_descriptor = -1
    temporary_name = ""
    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=".holdings-denylist-",
            suffix=".tmp",
            dir=output.parent,
        )
        os.fchmod(file_descriptor, 0o600)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as temporary_file:
            file_descriptor = -1
            json.dump(document, temporary_file, ensure_ascii=False, indent=2)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, output)
        temporary_name = ""
        os.chmod(output, 0o600)
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        if temporary_name:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def refresh(holdings_source: Path, output: Path) -> None:
    positions = _load_positions(holdings_source)
    terms = derive_holdings_terms(positions)
    write_private_denylist(output, terms)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdings-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        refresh(args.holdings_source, args.output)
    except HoldingsSourceError as error:
        raise SystemExit(str(error)) from error
    print("Refreshed private holdings denylist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
