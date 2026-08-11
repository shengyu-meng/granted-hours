#!/usr/bin/env python3
"""Private denylist loading and public-safe market fact projection.

The denylist values are process-local inputs. Callers may serialize only the
returned projection, never the private fixtures or their terms.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, Sequence


PRIVATE_DENYLIST_SCHEMA = "granted-hours-private-denylist-v1"
PUBLIC_IDENTITY_ALLOWLIST_SCHEMA = "granted-hours-public-identity-allowlist-v1"
FIXED_REDACTION_BLOCK = "████"

URL_RE = re.compile(
    r"(?ix)(?:\b(?:https?|ftp)://|\bwww\.)\S+"
    r"|\b(?:[A-Z0-9-]+\.)+(?:com|org|net|io|ai|cn|co|dev|app)\b(?:/\S*)?"
)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
HANDLE_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_.-]{2,}")
PHONE_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:\+?86[- ]?)?1[3-9]\d(?:\d{8}|[- ]\d{4}[- ]\d{4})(?![A-Za-z0-9.])"
)
LONG_NUMERIC_IDENTIFIER_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:\d{4}[- ]?){3}\d{4}(?:[- ]?\d{1,3})?(?![A-Za-z0-9.])"
)
SOURCE_LABEL_RE = re.compile(
    r"(?ix)^\s*(?:"
    r"来源|消息源|作者|发布者|创作者|公众号|博主|频道|账号|群聊|群|"
    r"文章标题|文章|帖子标题|帖子|链接|"
    r"source|author|publisher|creator|newsletter|blogger|channel|account|"
    r"group|article\s+title|article|post\s+title|post|link"
    r")\s*(?:[:：]\s*)?"
)
LEADING_ATTRIBUTION_RE = re.compile(
    r"(?ix)^\s*(?:据|根据|来自|转自|摘自)\s*"
    r"|^\s*(?:via|according\s+to|reported\s+by|published\s+by|from)\s+"
)
REPORTING_VERB_RE = re.compile(
    r"(?ix)(?:称|表示|报道|指出|认为|推荐|提到|写道|发布|转发)\s*[:：]?"
    r"|\b(?:says?|reports?|notes?|writes?|argues?|recommends?|mentions?|"
    r"publishes?|posts?)\b\s*[:：]?"
)
LEADING_REPORTING_RE = re.compile(
    r"(?ix)^\s*(?:(?:消息|报道|研报)\s*)?"
    r"(?:称|表示|报道|指出|认为|推荐|提到|写道|发布|转发)\s*[:：]?\s*"
    r"|^\s*(?:says?|reports?|notes?|writes?|argues?|recommends?|mentions?|"
    r"publishes?|posts?)\b\s*[:：]?\s*"
)
TRAILING_ATTRIBUTION_RE = re.compile(
    r"(?ix)\s*(?:据(?:消息|报道)?|来自|转自|摘自|via|according\s+to|"
    r"as\s+reported\s+by|reported\s+by|published\s+by)\s*[（(]?\s*[）)]?\s*$"
)
ATTRIBUTION_SEPARATOR_RE = re.compile(r"\s*(?:—|–|\||[,，:：])\s*")
PUBLIC_FACT_ANCHOR_RE = re.compile(
    r"(?ix)(?:\$[A-Z]{1,6}\b|\b[A-Z]{2,6}\b|"
    r"\b\d{4,6}\.(?:HK|SH|SZ|SS|US)\b|(?<!\d)\d{4,6}(?!\d)|"
    r"[+-]?\d+(?:\.\d+)?\s*%|\d+(?:\.\d+)?\s*(?:元|美元|港元|USD|HKD|CNY))"
)
ACCOUNT_POSITION_TRADE_RE = re.compile(
    r"(?ix)"
    r"\b(?:account|portfolio|holding|position|cost\s*basis|p\s*&?\s*l|"
    r"unrealized|realized|buy|sell|bought|sold|add(?:ed|ing)?|trim(?:med|ming)?|"
    r"entry|exit|stop[- ]?loss|take[- ]?profit|order|fill|allocation)\b"
    r"|账户|账号|组合|持仓|持有|仓位|成本|盈亏|浮盈|浮亏|买入|卖出|加仓|减仓|"
    r"建仓|清仓|止损|止盈|订单|委托|成交|调仓|配置比例"
)
PRIVATE_TECHNICAL_RE = re.compile(
    r"(?ix)"
    r"(?:/Users/|/(?:tmp|var/folders)/|file://|\.hermes|state\.db|"
    r"(?:[\w.-]+/)*[\w.-]+\.(?:py|jsonl?|db|sqlite)\b|"
    r"session[_ -]?id|chat[_ -]?id|message[_ -]?id|api[_ -]?key|"
    r"access[_ -]?token|authorization\s*:|"
    r"\[(?:silent|debug|trace)\]|"
    r"\b(?:ad[- ]?hoc|tempfile|temporary\s+script|verification\s+script|"
    r"profile\s+timeline|full[- ]loop\s+json|investment\s+os)\b|"
    r"(?:临时|专项|定向)?(?:验证|校验)?脚本|抓取方式|写入时间)"
)
MARKET_FACT_RE = re.compile(
    r"(?ix)"
    r"(?:\$[A-Z]{1,6}\b|\b[A-Z]{2,6}\b|\b\d{4,6}\.(?:HK|SH|SZ|SS|US)\b|"
    r"(?<!\d)\d{4,6}(?!\d)|[+-]?\d+(?:\.\d+)?\s*%|"
    r"\d+(?:\.\d+)?\s*(?:元|美元|港元|人民币|USD|HKD|CNY)|"
    r"AI\s*硬件|半导体|光互连|机器人|具身智能|能源|资源|利率|"
    r"AI\s*hardware|semiconductor|optical\s+interconnect|robotics|energy|rates|"
    r"市场|股价|涨幅|跌幅|上涨|下跌|突破|回撤|波动|估值|市盈率|"
    r"market|price|rose|fell|gain|decline|breakout|drawdown|volatility|valuation|"
    r"防守|进攻|中性|均衡|强势|弱势|defensive|offensive|neutral|balanced)"
)
MARKDOWN_PREFIX_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|#{1,6}\s*)")
SPACE_RE = re.compile(r"[ \t]+")
AMBIGUOUS_HOLDING_TERM_RE = re.compile(r"(?:[A-Za-z]{1,3}|\d{1,5})")
HOLDING_CONTEXT_PREFIX = (
    r"(?P<context>(?:\b(?:ticker|symbol|stock\s+code|security\s+code)\b|"
    r"(?:股票|证券|标的)(?:代码)?)\s*(?:[:：=#-]\s*)?)"
)
CONJUNCTION_SPLIT_RE = re.compile(
    r"(?ix)\s+(?:but|while|whereas|and|with|as\s+well\s+as)\s+"
    r"|\s*(?:但是|但|而且|并且|同时|且)\s*"
)
PUBLIC_RECOVERY_RE = re.compile(
    r"(?x)\b(?i:market|theme|outlook|judg(?:e)?ment|view|remains?|"
    r"strong|weak|defensive|offensive|neutral|balanced)\b"
    r"|\b[A-Z]{2,6}(?:[.-][A-Z])?\b"
    r"|市场|主题|判断|观点|仍然|依然|强势|弱势|防守|进攻|中性|均衡"
)


def _validate_private_path(path: Path) -> Path:
    resolved = path.resolve()
    if ".private" not in resolved.parts:
        raise ValueError(
            "Private denylist must live under an ignored .private directory"
        )
    return resolved


def load_private_denylist(path: Path, expected_kind: str) -> tuple[str, ...]:
    """Load validated exact terms without returning the source document."""
    resolved = _validate_private_path(path)
    try:
        source = json.loads(resolved.read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError("Could not read private denylist") from error
    except json.JSONDecodeError as error:
        raise ValueError("Private denylist is not valid JSON") from error
    if not isinstance(source, dict) or set(source) != {"schema", "kind", "terms"}:
        raise ValueError("Private denylist has invalid fields")
    if source.get("schema") != PRIVATE_DENYLIST_SCHEMA:
        raise ValueError("Private denylist has an invalid schema")
    if source.get("kind") != expected_kind:
        raise ValueError("Private denylist kind does not match its use")
    terms = source.get("terms")
    if not isinstance(terms, list) or not all(isinstance(term, str) for term in terms):
        raise ValueError("Private denylist terms must be a string list")
    normalized = {term.strip() for term in terms if term.strip()}
    if not normalized:
        raise ValueError("Private denylist must contain at least one term")
    if len(normalized) > 20_000 or any(len(term) > 180 for term in normalized):
        raise ValueError("Private denylist exceeds its bounded term budget")
    return tuple(sorted(normalized, key=lambda term: (-len(term), term.casefold())))


def load_public_identity_allowlist(path: Path) -> tuple[str, ...]:
    """Load the owner's explicit public-name authorization from tracked metadata."""
    try:
        source = json.loads(path.resolve().read_text(encoding="utf-8"))
    except OSError as error:
        raise ValueError("Public identity allowlist is unavailable") from error
    except json.JSONDecodeError as error:
        raise ValueError("Public identity allowlist is not valid JSON") from error
    if not isinstance(source, dict) or set(source) != {
        "schema",
        "authorization",
        "names",
    }:
        raise ValueError("Public identity allowlist has invalid fields")
    if source.get("schema") != PUBLIC_IDENTITY_ALLOWLIST_SCHEMA:
        raise ValueError("Public identity allowlist has an invalid schema")
    if source.get("authorization") != "explicit_owner_authorization_2026-08-11":
        raise ValueError("Public identity allowlist lacks explicit owner authorization")
    names = source.get("names")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        raise ValueError("Public identity allowlist names must be a string list")
    normalized = {name.strip() for name in names if name.strip()}
    if not normalized or len(normalized) > 40 or any(len(name) > 120 for name in normalized):
        raise ValueError("Public identity allowlist exceeds its bounded name budget")
    return tuple(sorted(normalized, key=lambda name: (-len(name), name.casefold())))


def exclude_public_identity_terms(
    private_terms: Sequence[str],
    public_names: Sequence[str],
) -> tuple[str, ...]:
    """Remove only exact, explicitly authorized names from a private denylist."""
    allowed = {name.casefold() for name in public_names}
    return tuple(term for term in private_terms if term.casefold() not in allowed)


def _term_pattern(
    term: str,
    *,
    contextual_ambiguous: bool = False,
) -> re.Pattern[str]:
    escaped = re.escape(term)
    flags = re.IGNORECASE if term.isascii() else 0
    if contextual_ambiguous and AMBIGUOUS_HOLDING_TERM_RE.fullmatch(term):
        return re.compile(
            rf"{HOLDING_CONTEXT_PREFIX}(?P<term>(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9]))",
            flags,
        )
    if term.isascii() and re.fullmatch(r"[A-Za-z0-9._$-]+", term):
        return re.compile(
            rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])",
            flags,
        )
    return re.compile(escaped, flags)


def replace_private_terms(
    value: str,
    terms: Sequence[str],
    replacement: str,
    *,
    contextual_ambiguous: bool = False,
) -> str:
    result = value
    for term in terms:
        pattern = _term_pattern(
            term,
            contextual_ambiguous=contextual_ambiguous,
        )
        result = pattern.sub(
            lambda match: (
                f"{match.groupdict().get('context', '')}{replacement}"
            ),
            result,
        )
    return result


def denied_terms_present(
    value: str,
    terms: Sequence[str],
    *,
    contextual_ambiguous: bool = False,
) -> bool:
    folded_value = value.casefold()
    return any(
        term.casefold() in folded_value
        and
        _term_pattern(
            term,
            contextual_ambiguous=contextual_ambiguous,
        ).search(value)
        for term in terms
    )


def _bounded_fact(value: str, limit: int = 180) -> str:
    value = SPACE_RE.sub(" ", value).strip(" \t\n,，;；:：-|—")
    if len(value) <= limit:
        return value
    candidate = value[: limit - 1].rstrip(" ,，;；:：-|—")
    return candidate + "…"


def _fragments(text: str) -> Iterable[str]:
    for line in text.splitlines():
        line = MARKDOWN_PREFIX_RE.sub("", line.strip())
        if not line or line.startswith("```"):
            continue
        for fragment in re.split(r"[;；。！？!?]\s*|(?<=\.)\s+", line):
            fragment = fragment.strip()
            if fragment:
                yield fragment


def _strip_labeled_attribution(value: str) -> str:
    """Remove an attribution lead while preserving the following market fact."""
    label = SOURCE_LABEL_RE.match(value)
    leading = LEADING_ATTRIBUTION_RE.match(value) if label is None else None
    match = label or leading
    if match is None:
        without_leading_verb = LEADING_REPORTING_RE.sub("", value)
        if without_leading_verb != value:
            return without_leading_verb
        reporting = REPORTING_VERB_RE.search(value)
        anchor = PUBLIC_FACT_ANCHOR_RE.search(value)
        if (
            reporting is not None
            and reporting.start() <= 100
            and (anchor is None or reporting.start() < anchor.start())
        ):
            return value[reporting.end() :].strip()
        return value
    remainder = value[match.end() :].strip()
    if not remainder:
        return ""
    reporting = REPORTING_VERB_RE.search(remainder)
    if reporting is not None and reporting.start() <= 100:
        return remainder[reporting.end() :].strip()
    separator = ATTRIBUTION_SEPARATOR_RE.search(remainder)
    if separator is not None and separator.start() <= 100:
        return remainder[separator.end() :].strip()
    anchor = PUBLIC_FACT_ANCHOR_RE.search(remainder)
    if anchor is None:
        return ""
    return remainder[anchor.start() :].strip()


def _sanitize_market_clause(
    clause: str,
    *,
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
) -> str:
    value = MARKDOWN_LINK_RE.sub(lambda match: match.group(1), clause)
    value = URL_RE.sub("", value)
    value = HANDLE_RE.sub("", value)
    value = PHONE_RE.sub(FIXED_REDACTION_BLOCK, value)
    value = LONG_NUMERIC_IDENTIFIER_RE.sub(FIXED_REDACTION_BLOCK, value)
    value = replace_private_terms(value, source_terms, "")
    value = _strip_labeled_attribution(value)
    value = TRAILING_ATTRIBUTION_RE.sub("", value)
    if PRIVATE_TECHNICAL_RE.search(value):
        return ""
    value = _remove_private_account_trade_spans(value)
    if not value:
        return ""
    value = replace_private_terms(
        value,
        holdings_terms,
        FIXED_REDACTION_BLOCK,
        contextual_ambiguous=True,
    )
    value = re.sub(r"[（(]\s*[）)]", "", value)
    return _bounded_fact(value)


def _remove_private_account_trade_spans(value: str) -> str:
    """Remove private spans while retaining separable public market language."""
    value = re.sub(
        r"[（(][^（）()]{0,220}[）)]",
        lambda match: (
            "" if ACCOUNT_POSITION_TRADE_RE.search(match.group(0)) else match.group(0)
        ),
        value,
    )
    retained: list[str] = []
    for piece in CONJUNCTION_SPLIT_RE.split(value):
        piece = piece.strip(" \t,，;；:：-|—")
        if not piece:
            continue
        private = ACCOUNT_POSITION_TRADE_RE.search(piece)
        if private is None:
            retained.append(piece)
            continue
        prefix = piece[: private.start()].strip(" \t,，;；:：-|—")
        suffix_source = piece[private.end() :]
        recovery = PUBLIC_RECOVERY_RE.search(suffix_source)
        suffix = (
            suffix_source[recovery.start() :].strip(" \t,，;；:：-|—")
            if recovery is not None
            else ""
        )
        for candidate in (prefix, suffix):
            if candidate and MARKET_FACT_RE.search(candidate):
                retained.append(candidate)
    return SPACE_RE.sub(" ", " ".join(retained)).strip()


def _sanitize_market_fragment(
    fragment: str,
    *,
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
) -> str:
    """Drop private clauses, not neighboring public clauses in one sentence."""
    safe_clauses = []
    for clause in re.split(r"[,，]", fragment):
        safe = _sanitize_market_clause(
            clause,
            holdings_terms=holdings_terms,
            source_terms=source_terms,
        )
        if safe:
            safe_clauses.append(safe)
    return _bounded_fact("，".join(safe_clauses))


def project_market_evidence(
    responses: Sequence[str],
    *,
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
    maximum_facts: int = 4,
) -> list[str]:
    """Extract bounded public facts while masking holdings and removing sources."""
    facts: list[str] = []
    signatures: set[str] = set()
    for response in responses:
        if not isinstance(response, str):
            continue
        for original in _fragments(response):
            fragment = _sanitize_market_fragment(
                original,
                holdings_terms=holdings_terms,
                source_terms=source_terms,
            )
            if not fragment or MARKET_FACT_RE.search(fragment) is None:
                continue
            if denied_terms_present(
                fragment,
                holdings_terms,
                contextual_ambiguous=True,
            ) or denied_terms_present(
                fragment,
                source_terms,
            ):
                raise ValueError("Private denylist term survived market projection")
            signature = fragment.casefold()
            if signature in signatures:
                continue
            signatures.add(signature)
            facts.append(fragment)
            if len(facts) >= maximum_facts:
                return facts
    return facts


def assert_private_terms_absent(
    value: str,
    *,
    holdings_terms: Sequence[str],
    source_terms: Sequence[str],
) -> None:
    if denied_terms_present(
        value,
        holdings_terms,
        contextual_ambiguous=True,
    ) or denied_terms_present(
        value,
        source_terms,
    ):
        raise ValueError("Private denylist term was about to be serialized")
