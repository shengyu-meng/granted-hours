#!/usr/bin/env python3
"""Build public data for the Granted Hours living month calendar."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from reminder_disclosure import (
    DISCLOSURE_AUTHORIZATION,
    DISCLOSURE_POLICY,
    FIXED_REDACTION_BLOCK,
    PROJECTION_PROVENANCE as REMINDER_PROJECTION_PROVENANCE,
    REDACTION_POLICY as REMINDER_REDACTION_POLICY,
    project_private_reminder,
)
from semantic_public_policy import polish_public_excerpt
from import_free_roam_artifacts import ENTRIES as AUTONOMOUS_ARTWORK_ENTRIES

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_DAYS = ROOT / "metadata" / "days.json"
DEFAULT_CONFIG = ROOT / "metadata" / "timetable-calendar.json"
DEFAULT_HISTORY = ROOT / "metadata" / "timetable-history.json"
DEFAULT_PULSES = ROOT / "metadata" / "timetable-pulses.json"
DEFAULT_LEGACY_OVERRIDES = ROOT / "metadata" / "timetable-v1.json"
DEFAULT_OUTPUT = ROOT / "src" / "timetable" / "timetable-data.js"

MINUTES_PER_DAY = 24 * 60
PULSE_SNAPSHOT_SCHEMA = "granted-hours-timetable-pulses-v6"
LEGACY_PULSE_SNAPSHOT_SCHEMAS = {
    "granted-hours-timetable-pulses-v3",
    "granted-hours-timetable-pulses-v4",
}
REMINDER_TRANSLATION_PROVENANCE = (
    "public_mask_preserving_translation_v1"
)
CJK_RE = re.compile(
    r"[\u3040-\u30ff\u3100-\u312f\u31a0-\u31bf\u31f0-\u31ff"
    r"\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\uf900-\ufaff]"
)
LATIN_RE = re.compile(r"[A-Za-z]")
REQUIRED_PUBLIC_FIELDS = (
    "date",
    "source_date",
    "crystallization_date",
    "title_en",
    "title_zh",
    "variable_en",
    "variable_zh",
    "gif",
    "preview",
    "visual_preview",
    "archive_url",
    "live_url",
    "bgm",
)
REQUIRED_TAXONOMY = {
    "social_media_organization",
    "document_processing",
    "code_development",
    "research_synthesis",
    "system_maintenance",
    "visual_production",
    "redacted_private",
}
ALLOWED_HISTORY_PROVENANCE = {"record_based", "withheld", "dialogue_based"}
SESSION_SOURCE_KINDS = {"agent_session", "collaboration_session"}
ACTIVE_COLLABORATION_SOURCE_KINDS = {
    "collaboration_session",
    "agent_session",
    "daily_record",
    "task_card",
    "public_post_archive",
    "withheld",
}
URL_RE = re.compile(r"(?i)(?:\b(?:https?|ftp)://|\bwww\.)\S+")
VOICE_POLICY_VERSION = "granted-hours-first-person-v2"

COLLABORATION_REQUEST_VOICES = (
    ("Simon 让我来做这件事：", "Simon asked me: "),
    ("Simon 交给我一项任务：", "Simon gave me this task: "),
    ("Simon 和我说：", "Simon said to me: "),
    ("Simon 请我来处理：", "Simon came to me with a request: "),
    ("Simon 希望我帮忙：", "Simon asked for my help: "),
    ("Simon 把这件事交给我：", "Simon handed this work to me: "),
)
REMINDER_VOICES = (
    ("我提醒 Simon：", "I reminded Simon:"),
    ("我告诉 Simon：", "I told Simon:"),
    ("我给 Simon 一个小小的提示：", "I gave Simon a small nudge:"),
    ("我把这句话留给 Simon：", "I left this note for Simon:"),
    ("我轻轻提醒 Simon：", "I gently reminded Simon:"),
    ("我对 Simon 说：", "I said to Simon:"),
)

SENSITIVE_ASSIGNED_WORK_RE = re.compile(
    r"(?i)\bholdings\b|持仓|仓位|试仓|\blive\s+futu\b|\breal\s+account\b|真实账户|账户敞口|账户权限"
    r"|\b(?:broker\s+positions?|positions)\b|头寸|券商头寸|\baccount\s+exposure\b|\bportfolio\s+(?:allocation|holdings|exposure)\b|组合(?:持仓|配置)"
    r"|\bbelow-band\s+allocation\b|低于目标区间的配置|\bpositions\b.{0,24}\b(?:sizing|cap|limit)\b"
)
PRIVATE_OPERATIONAL_CONTEXT_RE = re.compile(
    r"(?i)(?:openclaw|hermes)(?:\s+(?:agent|skills?|workflow|watchdog|host-health))"
    r"|(?:wechat|微信).{0,64}(?:local\s+history|本地历史|incremental\s+messages|增量消息|private\s+chats|私聊)"
)
SPOUSE_ACTIVITY_RE = re.compile(
    r"(?i)(?:广西民族大学|人才小高地|会计学|管理学|工商管理硕士|数智财会|财会人才)"
    r"|\bMBA\b|\bGuangxi\s+Minzu\s+University\b|\btalent[- ]highland\b"
    r"|\bmanagement\s+(?:studies|science|degree|discipline)\b"
    r"|\baccounting\b.{0,40}\b(?:thes(?:is|es)|course|teaching|teacher|student|talent|degree|undergraduate|proposal|training)\b"
    r"|\b(?:thes(?:is|es)|course|teaching|teacher|student|talent|degree|undergraduate|proposal|training)\b.{0,40}\baccounting\b"
)
EDUCATION_IDENTITY_RE = re.compile(
    r"(?i)\b(?:school|university|college|faculty|department|institute|academy|"
    r"accounting|digital[- ]accounting|mba|degree|undergraduate|graduate|"
    r"bachelor(?:'s)?|master(?:'s)?|doctoral|education|teaching|teacher|instructor|"
    r"course(?:work|s|[- ]materials?|[- ]program)?|syllabus|curriculum|"
    r"dissertation|talent[- ](?:training|development))\b"
    r"|\b(?:academic\s+major|major\s+(?:identity|program|subject|field))\b"
    r"|(?:学校|大学|学院|学部|院系|系部|研究院|研究所|书院|教师|导师|"
    r"专业(?:名称|身份|方向|课程|建设|设置|申报|培养)|"
    r"财会|会计|工商管理硕士|数智人才|人才培养|本科|硕士|博士|学位|课程|课件|"
    r"教学|教案|毕业设计)"
    r"|(?:本科|硕士|博士|学位|毕业|会计).{0,8}论文"
    r"|论文.{0,8}(?:评阅|外审|导师|学生|学位)"
)
PROPOSAL_TITLE_CONTEXT_RE = re.compile(
    r"(?i)\b(?:school|university|college|faculty|department|institute|academy|"
    r"accounting|digital[- ]accounting|mba|education|course|curriculum|"
    r"talent[- ](?:training|development))(?:[a-z0-9&/()'’-]*[ -]+){0,5}"
    r"(?:proposal|application)\b"
    r"|(?:学校|大学|学院|学部|院系|研究院|研究所|书院|专业|财会|会计|人才培养|"
    r"本科|硕士|博士|学位|课程|教学)[^，。；;]{0,24}(?:申报书|申请书)"
    r"|《[^》]{2,40}》(?:申报书|申请书)"
)
FINANCE_DOMAIN_KEYWORDS = (
    "finance",
    "financial",
    "market",
    "market-data",
    "premarket",
    "stock",
    "stocks",
    "a-share",
    "hong kong",
    "investment",
    "equity",
    "securities",
    "option",
    "put",
    "covered-call",
    "portfolio",
    "trading",
    "trades",
    "broker",
    "futures",
    "fund",
    "capital flow",
    "财经",
    "金融",
    "市场",
    "股票",
    "A股",
    "港股",
    "美股",
    "证券",
    "期权",
    "投资",
    "行情",
    "基金",
    "资本流",
)
THEME_MOTIFS = {"window", "seam", "bridge", "echo", "weather", "time", "room", "light", "void"}
THEME_MOTIF_RULES = (
    ("window", ("window", "aperture", "threshold", "door", "gate", "opening", "窗", "门", "阈", "开口", "出口")),
    ("seam", ("repair", "seam", "wound", "scar", "graft", "fracture", "修复", "接缝", "裂", "伤")),
    ("bridge", ("bridge", "orbit", "route", "path", "crossing", "link", "桥", "轨道", "路径", "渡")),
    ("echo", ("echo", "memory", "archive", "recall", "witness", "回声", "记忆", "档案", "回忆", "见证")),
    ("weather", ("weather", "rain", "garden", "flow", "tide", "field", "天气", "下雨", "雨水", "花园", "流动", "流域", "潮汐", "场域")),
    ("time", ("time", "latency", "interval", "clock", "wait", "continuity", "时间", "延迟", "间隙", "时钟", "等待", "连续")),
    ("room", ("room", "scaffold", "wall", "structure", "architecture", "房间", "脚手架", "墙", "结构", "建筑")),
    ("light", ("light", "dawn", "glow", "sun", "crystal", "光", "黎明", "晶")),
    ("void", ("silence", "quiet", "gap", "absence", "void", "invisible", "沉默", "安静", "空隙", "缺席", "虚", "不可见")),
)
TASK_TYPE_DEFINITIONS = {
    "grant_proposal": {
        "zh": "申报书写作",
        "en": "Grant proposal",
        "color": "amber",
        "icon": "file-pen-line",
    },
    "social_content": {
        "zh": "社媒内容",
        "en": "Social content",
        "color": "cyan",
        "icon": "megaphone",
    },
    "investment_research": {
        "zh": "投资研究",
        "en": "Investment research",
        "color": "green",
        "icon": "chart-no-axes-combined",
    },
    "software_development": {
        "zh": "软件开发",
        "en": "Software development",
        "color": "blue",
        "icon": "code-xml",
    },
    "thesis_review": {
        "zh": "论文审阅",
        "en": "Thesis review",
        "color": "violet",
        "icon": "book-open-check",
    },
    "course_materials": {
        "zh": "课程材料",
        "en": "Course materials",
        "color": "coral",
        "icon": "presentation",
    },
    "research_analysis": {
        "zh": "研究分析",
        "en": "Research analysis",
        "color": "lime",
        "icon": "search",
    },
    "document_writing": {
        "zh": "文档写作",
        "en": "Document writing",
        "color": "sand",
        "icon": "file-text",
    },
    "visual_design": {
        "zh": "视觉设计",
        "en": "Visual design",
        "color": "pink",
        "icon": "palette",
    },
    "system_operations": {
        "zh": "系统维护",
        "en": "System operations",
        "color": "slate",
        "icon": "settings",
    },
    "redacted_record": {
        "zh": "私密记录",
        "en": "Private record",
        "color": "slate",
        "icon": "lock-keyhole",
    },
    "active_collaboration": {
        "zh": "人机主动协作",
        "en": "Active human–AI collaboration",
        "color": "blue",
        "icon": "messages-square",
    },
}
TASK_TYPE_FALLBACKS = {
    "social_media_organization": "social_content",
    "document_processing": "document_writing",
    "code_development": "software_development",
    "research_synthesis": "research_analysis",
    "system_maintenance": "system_operations",
    "visual_production": "visual_design",
    "redacted_private": "redacted_record",
}
SPECIAL_TASK_TYPE_RULES = (
    (
        "grant_proposal",
        {"document_processing", "research_synthesis"},
        (
            "grant proposal",
            "project proposal",
            "funding application",
            "application requirement",
            "proposal submission",
            "proposal claim",
            "项目申报",
            "申报书",
            "申报提交",
            "申报政策",
            "申报主张",
        ),
    ),
    (
        "thesis_review",
        {"document_processing", "research_synthesis"},
        (
            "thesis",
            "dissertation",
            "anonymized thesis",
            "thesis-review rubric",
            "论文审阅",
            "论文评阅",
            "学位论文",
            "匿名论文",
        ),
    ),
    (
        "course_materials",
        {"document_processing", "research_synthesis"},
        (
            "course material",
            "coursework",
            "teaching material",
            "lecture material",
            "syllabus",
            "课程材料",
            "教学材料",
            "课程讲义",
        ),
    ),
)
PULSE_DEFINITIONS = {
    "ah_market_scan": {
        "label_en": "A/H market scan",
        "label_zh": "A/H 市场扫描",
        "color": "green",
    },
    "us_market_scan": {
        "label_en": "U.S. market scan",
        "label_zh": "美股市场扫描",
        "color": "green",
    },
    "ai_daily_brief": {
        "label_en": "AI daily brief",
        "label_zh": "AI 日报",
        "color": "cyan",
    },
    "daily_reminder": {
        "label_en": "Daily reminder",
        "label_zh": "每日提醒",
        "color": "amber",
    },
    "system_routine": {
        "label_en": "System routine",
        "label_zh": "系统例行任务",
        "color": "blue",
    },
    "background_routine": {
        "label_en": "Other background run record",
        "label_zh": "其他后台运行记录",
        "color": "slate",
    },
}

REMINDER_OWNERSHIP_FIELDS = {
    "owner_scope",
    "ownership_provenance",
}
AUTHENTIC_REMINDER_FIELDS = {
    "disclosure_policy",
    "disclosure_authorization",
    "public_label_zh",
    "public_label_en",
    "summary_original",
    "excerpt_original",
    "original_language",
    "projection_kind",
    "redaction_policy",
    "redaction_count",
    "semantic_abstraction_count",
    "projection_provenance",
    "summary_en",
    "excerpt_en",
    "translation_provenance",
}
LEGACY_REMINDER_PROVENANCE_FIELDS = {
    *REMINDER_OWNERSHIP_FIELDS,
    "action_provenance",
}
LEGACY_LIMITED_REMINDER_FIELDS = {
    "disclosure_policy",
    "disclosure_authorization",
    "public_label_zh",
    "public_label_en",
    "motif",
    "action_structure",
    "projection_kind",
    "redaction_policy",
    "redaction_count",
    "projection_provenance",
}
REMINDER_OWNER_SCOPES = {
    "self",
    "self_scheduler_residue",
    "other_person",
    "unknown",
}
REMINDER_OWNERSHIP_PROVENANCE = {
    "explicit_user_authorization",
    "explicit_import_authorization",
    "unverified",
}
AUTHORIZED_REMINDER_OWNERSHIP_PROVENANCE = {
    "explicit_user_authorization",
    "explicit_import_authorization",
}
PUBLIC_READING_LAYERS = {"climate", "event", "absence", "beacon"}
PUBLIC_NARRATIVE_OUTCOMES = {
    "foreground_event",
    "climate_aggregate",
    "readable_reminder",
    "hidden_individual_reading_item",
    "promoted_routine_exception",
    "beacon",
    "absence",
    "settings_change",
}

CONFIG_CHANGE_RE = re.compile(
    r"静默|不用再报|不用汇报|不播报|暂停|命名|缩写|改到|移除|不再|自动识别公共节假日|发布指令改为"
)
VAGUE_INTERNAL_TITLES = {
    "后台例行任务",
    "系统例行任务",
    "静默检查",
    "Background routine",
    "System routine",
    "Silent check",
}
MARKET_STATES = (
    (
        ("defensive / risk-contraction", "防守 / 风险收缩"),
        "防守 / 风险收缩",
        "defensive / risk-contraction",
    ),
    (
        ("offensive / risk-expansion", "进攻 / 风险扩张"),
        "进攻 / 风险扩张",
        "offensive / risk-expansion",
    ),
    (
        ("balanced / neutral", "均衡 / 中性"),
        "均衡 / 中性",
        "balanced / neutral",
    ),
)
MARKET_THEMES = (
    (
        ("AI hardware and semiconductors", "AI 硬件与半导体"),
        "AI 硬件与半导体",
        "AI hardware and semiconductors",
    ),
    (
        ("optical interconnects", "光互连"),
        "光互连",
        "optical interconnects",
    ),
    (
        ("embodied AI", "具身智能"),
        "具身智能",
        "embodied AI",
    ),
    (
        ("resources and rates", "资源与利率"),
        "资源与利率",
        "resources and rates",
    ),
    (
        ("market regime and volatility", "市场状态与波动"),
        "市场状态与波动",
        "market regime and volatility",
    ),
)
PUBLIC_ALERT_PATTERNS = (
    re.compile(r"(?i)\bwarnings?\s+were\s+present\b"),
    re.compile(r"(?i)\b[1-9]\d*\s+(?:exposed|contained)\s+(?:a\s+)?public-level\b"),
    re.compile(r"(?i)\bdid\s+not\s+pass\s+its\s+publication\s+gate\b"),
    re.compile(r"(?:存在数据或链路新鲜度警告|[1-9]\d*\s*次出现公开级别(?:异常|采集)|未达发布闸门)"),
)
MARKET_EXCEPTION_PATTERNS = (
    re.compile(r"(?i)\b[1-9]\d*\s+(?:exposed|contained)\s+(?:a\s+)?public-level\b"),
    re.compile(r"(?i)\bdid\s+not\s+pass\s+its\s+publication\s+gate\b"),
    re.compile(r"(?:[1-9]\d*\s*次出现公开级别(?:异常|采集)|未达发布闸门)"),
)


def minutes(value: str) -> int:
    if value == "24:00":
        return MINUTES_PER_DAY
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def pulse_has_public_alert(category: str, public_copy: str) -> bool:
    """Keep routine market freshness warnings in climate, not the foreground."""
    patterns = (
        MARKET_EXCEPTION_PATTERNS
        if category in {"ah_market_scan", "us_market_scan"}
        else PUBLIC_ALERT_PATTERNS
    )
    return any(pattern.search(public_copy) for pattern in patterns)


def parse_date(value: str) -> date:
    year, month, day = (int(part) for part in value.split("-"))
    return date(year, month, day)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def mask_token_count(value: str, context: str) -> int:
    """Count intact fixed masks and reject split or altered block runs."""
    runs = re.findall(r"█+", value)
    require(
        all(len(run) % len(FIXED_REDACTION_BLOCK) == 0 for run in runs),
        f"{context} contains a split or altered ████ token",
    )
    return sum(len(run) // len(FIXED_REDACTION_BLOCK) for run in runs)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_url(base_url: str, path_or_url: str) -> str:
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    return urljoin(base_url, path_or_url.lstrip("/"))


def public_timetable_day_url(base_url: str, day_date: str) -> str:
    return f"{base_url.rstrip('/')}/timetable/?date={day_date}"


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


TASK_NAME_RULES = {
    "social_media_organization": [
        ({"keywords": ["排期", "schedule", "timing", "timed", "接收顺序", "intake sequence", "队列", "queue"], "task_name_zh": "发布队列整理", "task_name_en": "Publishing queue curation"}),
        ({"keywords": ["发布结果", "delivery evidence", "归档证据", "archive evidence", "evidence ledger"], "task_name_zh": "发布结果归档", "task_name_en": "Publication result archiving"}),
        ({"keywords": ["素材", "asset", "image", "video", "media", "缺失媒体", "required media"], "task_name_zh": "发帖素材核验", "task_name_en": "Post material verification"}),
        ({"keywords": ["平台限制", "platform limit", "platform restriction", "发布模式", "publication mode", "发布状态", "publication state"], "task_name_zh": "平台发布规则", "task_name_en": "Platform publishing rules"}),
        ({"keywords": ["作者开场", "author opening", "开场语境", "opening context", "语气", "tone"], "task_name_zh": "文案语气整理", "task_name_en": "Editorial voice curation"}),
        ({"keywords": ["双语公开", "bilingual public", "公开摘要", "public summary", "微博", "weibo", "post", "tweet", "publish", "copy", "caption"], "task_name_zh": "微博/社媒文案", "task_name_en": "Weibo/social media copy"}),
        ({"keywords": ["链接", "link", "来源", "source"], "task_name_zh": "图文链接整理", "task_name_en": "Content link organization"}),
    ],
    "document_processing": [
        ({"keywords": ["项目申报", "申报书", "proposal", "application requirement", "funding application", "提交要求", "submission requirement"], "task_name_zh": "项目申报书", "task_name_en": "Project proposal"}),
        ({"keywords": ["课程", "course", "教学", "teaching", "lecture"], "task_name_zh": "课程材料", "task_name_en": "Course materials"}),
        ({"keywords": ["论文", "匿名化", "thesis", "paper", "manuscript", "审阅量规", "review rubric"], "task_name_zh": "论文审阅", "task_name_en": "Thesis review"}),
        ({"keywords": ["学位", "人才培养", "教育要求", "degree", "talent development", "education requirement"], "task_name_zh": "教育项目材料", "task_name_en": "Education project materials"}),
        ({"keywords": ["交接", "handoff", "交付", "delivery", "提交检查", "submission checklist", "打包", "package"], "task_name_zh": "交付与提交文档", "task_name_en": "Delivery and submission documents"}),
        ({"keywords": ["机器状态", "machine state", "系统状态", "system state", "运行说明", "operations note", "维护运行", "maintenance run"], "task_name_zh": "系统运行说明", "task_name_en": "System operations note"}),
        ({"keywords": ["风险", "risk", "情景假设", "scenario assumption", "失效条件", "invalidation"], "task_name_zh": "风险情景简报", "task_name_en": "Risk scenario brief"}),
        ({"keywords": ["复核说明", "review note", "复核摘要", "review summary", "简报", "brief"], "task_name_zh": "研究复核简报", "task_name_en": "Research review brief"}),
        ({"keywords": ["双语", "bilingual", "translation", "translating", "翻译"], "task_name_zh": "双语文稿", "task_name_en": "Bilingual manuscript"}),
        ({"keywords": ["归档条目", "archive entry", "主题索引", "thematic index", "证据台账", "evidence ledger"], "task_name_zh": "知识索引与归档", "task_name_en": "Knowledge indexing and archiving"}),
        ({"keywords": ["标题", "表格", "图注", "参考资料", "格式", "format", "caption", "table", "可正常打开", "open correctly"], "task_name_zh": "文档格式核对", "task_name_en": "Document format verification"}),
        ({"keywords": ["笔记", "notes", "压缩", "compress", "重复", "duplicate"], "task_name_zh": "工作笔记整理", "task_name_en": "Working note curation"}),
        ({"keywords": ["修改", "revision", "revise", "edit", "编辑"], "task_name_zh": "报告与文稿修订", "task_name_en": "Report and manuscript revision"}),
        ({"keywords": ["撰写", "drafting", "compose", "写", "说明", "guide"], "task_name_zh": "文档撰写", "task_name_en": "Document drafting"}),
    ],
    "research_synthesis": [
        ({"keywords": ["财经", "financial", "finance", "market", "economy", "价格", "price", "股票", "stock", "交易", "trade", "投资", "investment", "监测候选", "monitoring candidate", "下行情景", "downside scenario"], "task_name_zh": "每日财经建议", "task_name_en": "Daily financial guidance"}),
        ({"keywords": ["政策", "policy", "regulation", "教育要求", "education requirement", "官方要求", "official requirement", "official rules", "teaching practice", "教学实践", "会计ai项目"], "task_name_zh": "政策与教育核验", "task_name_en": "Policy and education verification"}),
        ({"keywords": ["来源新鲜度", "source freshness", "source-freshness", "公开来源的新鲜度", "public-source freshness"], "task_name_zh": "来源时效核验", "task_name_en": "Source freshness verification"}),
        ({"keywords": ["一手来源", "first-party source", "溯源", "provenance", "引文", "citation"], "task_name_zh": "来源溯源核验", "task_name_en": "Source provenance verification"}),
        ({"keywords": ["复用权利", "reuse rights", "许可", "license", "licensing"], "task_name_zh": "版权与许可核验", "task_name_en": "Rights and licensing review"}),
        ({"keywords": ["文献", "literature"], "task_name_zh": "文献综述", "task_name_en": "Literature review"}),
        ({"keywords": ["艺术", "art", "visual case", "aesthetic"], "task_name_zh": "艺术案例调研", "task_name_en": "Art case research"}),
        ({"keywords": ["capability claims", "supported capabilities", "verified capability", "能力主张", "有支撑的能力", "已验证能力"], "task_name_zh": "能力声明核验", "task_name_en": "Capability claim verification"}),
        ({"keywords": ["AI", "AI 工具", "creative-tool", "创作工具"], "task_name_zh": "AI 工具调研", "task_name_en": "AI tool research"}),
        ({"keywords": ["情景", "scenario", "预测", "prediction", "保护", "protection"], "task_name_zh": "情景推演", "task_name_en": "Scenario analysis"}),
        ({"keywords": ["集成方案", "integration approach", "技术方案", "technical approach", "选项", "option"], "task_name_zh": "技术方案对比", "task_name_en": "Technical approach comparison"}),
        ({"keywords": ["证据", "evidence", "主张", "claim", "缺口", "gap", "矛盾", "contradiction", "反方", "counterargument", "置信度", "confidence"], "task_name_zh": "证据链复核", "task_name_en": "Evidence-chain review"}),
        ({"keywords": ["资料核验", "material verification", "公开资料", "public material", "审计", "audit"], "task_name_zh": "政策/资料核验", "task_name_en": "Policy/material verification"}),
    ],
    "code_development": [
        ({"keywords": ["移动", "mobile", "responsive", "phone"], "task_name_zh": "移动端修复", "task_name_en": "Mobile fix"}),
        ({"keywords": ["embed=calendar", "cross-origin iframe", "cross-origin embed", "跨域 iframe", "网页嵌入"], "task_name_zh": "网页嵌入开发", "task_name_en": "Web embed development"}),
        ({"keywords": ["私人源", "private source", "脱敏", "sanitized", "redaction", "public mirror"], "task_name_zh": "数据脱敏开发", "task_name_en": "Data sanitization development"}),
        ({"keywords": ["解析器", "parser", "schema", "模式校验", "畸形输入", "malformed input", "error handling", "错误处理"], "task_name_zh": "数据解析与校验", "task_name_en": "Data parsing and validation"}),
        ({"keywords": ["公开路由", "public route", "URL", "archive output", "归档输出"], "task_name_zh": "网站路由校验", "task_name_en": "Website route verification"}),
        ({"keywords": ["API", "接口", "connector", "连接器", "endpoint", "数据连接"], "task_name_zh": "数据接口开发", "task_name_en": "Data API development"}),
        ({"keywords": ["慢", "slow", "瓶颈", "bottleneck", "超时", "timeout", "profile", "可观测", "observability"], "task_name_zh": "性能与可观测性", "task_name_en": "Performance and observability"}),
        ({"keywords": ["缺陷", "defect", "bug", "修复", "fix"], "task_name_zh": "缺陷修复", "task_name_en": "Defect repair"}),
        ({"keywords": ["重构", "refactor", "重复转换", "duplicate transformation", "移除重复", "remove duplicate"], "task_name_zh": "代码重构", "task_name_en": "Code refactoring"}),
        ({"keywords": ["恢复路径", "recovery path", "备用行为", "fallback behavior"], "task_name_zh": "恢复路径演练", "task_name_en": "Recovery-path rehearsal"}),
        ({"keywords": ["自动化", "automation", "script", "脚本", "定时工作流", "scheduled workflow"], "task_name_zh": "自动化脚本", "task_name_en": "Automation script"}),
        ({"keywords": ["只读", "read-only", "不执行", "nonexecution", "建议型输出", "advisory output", "闸门", "gate"], "task_name_zh": "安全闸门开发", "task_name_en": "Safety-gate development"}),
        ({"keywords": ["测试", "test", "回归", "regression"], "task_name_zh": "回归测试", "task_name_en": "Regression testing"}),
        ({"keywords": ["界面", "UI", "interface", "网页", "web", "前端", "frontend"], "task_name_zh": "网页界面开发", "task_name_en": "Web interface development"}),
    ],
    "system_maintenance": [
        ({"keywords": ["operating-contract alignment", "运行契约对齐"], "task_name_zh": "运行契约核对", "task_name_en": "Operating-contract review"}),
        ({"keywords": ["maintenance queue", "维护队列"], "task_name_zh": "维护队列处理", "task_name_en": "Maintenance queue processing"}),
        ({"keywords": ["slow maintenance", "缓慢的维护阶段"], "task_name_zh": "系统性能排查", "task_name_en": "System performance diagnosis"}),
        ({"keywords": ["preweek maintenance", "周前维护检查"], "task_name_zh": "周前系统检查", "task_name_en": "Preweek system check"}),
        ({"keywords": ["maintenance confidence", "维护置信度"], "task_name_zh": "系统置信度校验", "task_name_en": "System confidence calibration"}),
        ({"keywords": ["备份", "backup", "恢复", "recovery", "restore"], "task_name_zh": "备份恢复检查", "task_name_en": "Backup recovery check"}),
        ({"keywords": ["私人残留", "private residue", "脱敏", "sanitization", "归档完整性", "archive integrity", "媒体溯源", "media provenance"], "task_name_zh": "公开归档安全检查", "task_name_en": "Public archive safety check"}),
        ({"keywords": ["过期", "stale", "新鲜", "freshness", "时间戳", "timestamp", "来源可用", "source availability"], "task_name_zh": "数据时效校验", "task_name_en": "Data freshness verification"}),
        ({"keywords": ["只读", "read-only", "防护", "guardrail", "人工复核", "human review", "不执行", "nonexecution", "观察工具", "observation tool"], "task_name_zh": "权限与安全闸门", "task_name_en": "Permission and safety gates"}),
        ({"keywords": ["交付证据", "delivery evidence", "交付", "delivery", "产物", "artifact", "交接", "handoff", "对账", "reconcile"], "task_name_zh": "交付证据核对", "task_name_en": "Delivery evidence reconciliation"}),
        ({"keywords": ["定时", "scheduled", "例行刷新", "routine refresh", "每日集成", "daily integration", "cron"], "task_name_zh": "定时任务维护", "task_name_en": "Scheduled task maintenance"}),
        ({"keywords": ["告警", "alert", "噪声", "noise"], "task_name_zh": "告警治理", "task_name_en": "Alert governance"}),
        ({"keywords": ["备用", "fallback", "离线", "offline", "部分退出", "partial exit"], "task_name_zh": "备用链路检查", "task_name_en": "Fallback-path verification"}),
        ({"keywords": ["健康", "health", "service"], "task_name_zh": "服务健康检查", "task_name_en": "Service health check"}),
        ({"keywords": ["监控", "monitor", "observe", "日志", "log"], "task_name_zh": "监控系统校验", "task_name_en": "Monitoring system check"}),
        ({"keywords": ["Agent", "workflow", "工作流"], "task_name_zh": "Agent 工作流维护", "task_name_en": "Agent workflow maintenance"}),
    ],
    "visual_production": [
        ({"keywords": ["裁切", "crop", "署名", "attribution"], "task_name_zh": "图片裁切与署名", "task_name_en": "Image crop and attribution"}),
        ({"keywords": ["复用权利", "reuse rights", "来源语境", "source context", "provenance"], "task_name_zh": "视觉版权核验", "task_name_en": "Visual rights verification"}),
        ({"keywords": ["媒体卡片", "media card", "配图", "social image"], "task_name_zh": "社媒配图制作", "task_name_en": "Social media image production"}),
        ({"keywords": ["联络表", "contact sheet"], "task_name_zh": "视觉联络表", "task_name_en": "Visual contact sheet"}),
        ({"keywords": ["文档渲染", "document rendering", "层级", "hierarchy", "可读性", "readability"], "task_name_zh": "文档视觉排版", "task_name_en": "Document visual layout"}),
        ({"keywords": ["版式", "layout", "composition", "构图", "structure"], "task_name_zh": "版式与构图", "task_name_en": "Layout and composition"}),
        ({"keywords": ["参考", "reference", "visual", "素材", "asset"], "task_name_zh": "视觉参考整理", "task_name_en": "Visual reference organization"}),
        ({"keywords": ["图像", "image", "picture", "视觉", "visual", "graphic", "svg"], "task_name_zh": "图像制作", "task_name_en": "Image production"}),
    ],
}


# Exact public-safe phrases are authored evidence, not fuzzy inference. They cover
# recurring historical work templates whose concise names cannot be derived
# honestly from a single keyword.
TASK_NAME_EXACT = {
    ("document_processing", "Compare document variants and reconcile unsupported differences"): ("文档版本核对", "Document version reconciliation"),
    ("document_processing", "Restructure a long report around claims, support, and verification gaps"): ("长报告重构", "Long-report restructuring"),
    ("document_processing", "Prepare a compact weekend review ledger"): ("周末复核台账", "Weekend review ledger"),
    ("document_processing", "Document the public-data boundary and reconstruction caveats"): ("公开数据说明", "Public-data boundary note"),
    ("document_processing", "Compare two independent review variants and reconcile their strongest corrections"): ("独立审校核对", "Independent review reconciliation"),
    ("document_processing", "Run build, syntax, regression, safety, and enrichment verification checks"): ("发布前质检", "Pre-release verification"),
    ("code_development", "Check that market-data gaps cannot silently become action signals"): ("行动信号安全校验", "Action-signal safety check"),
    ("code_development", "Validate task packaging, context boundaries, and deterministic output"): ("Agent 任务封装验证", "Agent task-package validation"),
    ("code_development", "Validate maintenance schemas and deterministic state updates"): ("状态模式校验", "State-schema validation"),
    ("code_development", "Inspect the failing integration step and verify its bounded fallback"): ("集成故障排查", "Integration failure diagnosis"),
    ("code_development", "Verify serialization preserves provenance and review-only flags"): ("序列化溯源校验", "Serialization provenance check"),
    ("code_development", "Verify a scheduled pipeline remains deterministic across repeated runs"): ("定时流水线校验", "Scheduled pipeline verification"),
    ("code_development", "Reconcile generated state with the source-of-truth contract"): ("生成状态对账", "Generated-state reconciliation"),
    ("code_development", "Preserve local behavior while upgrading a reusable system component"): ("组件升级兼容", "Component upgrade compatibility"),
    ("code_development", "Verify bottom reachability, focus behavior, and true touch scrolling"): ("交互滚动回归", "Interaction-scroll regression"),
    ("code_development", "Reconstruct assigned history from non-autonomous records with explicit provenance"): ("指派历史重建", "Assigned-history reconstruction"),
    ("social_media_organization", "Close the content batch with per-item delivery verification"): ("发布批次验收", "Publication batch acceptance"),
    ("social_media_organization", "Organize public-content candidates without advancing their status"): ("内容候选整理", "Public-content candidate curation"),
    ("research_synthesis", "Summarize what is known, uncertain, and explicitly out of scope"): ("研究边界摘要", "Research-boundary summary"),
    ("research_synthesis", "Evaluate public references for relevance before expanding the research queue"): ("参考资料筛选", "Reference relevance screening"),
    ("research_synthesis", "Compare independent sources and downgrade unsupported convergence"): ("交叉来源核验", "Cross-source verification"),
    ("research_synthesis", "Review unresolved research items and retire those with no viable source path"): ("研究待办清理", "Research backlog pruning"),
    ("research_synthesis", "Reconcile source status across the research ledger and review brief"): ("来源状态对账", "Source-status reconciliation"),
    ("research_synthesis", "Separate structural context from short-lived noise in the daily review"): ("结构与噪声研判", "Structure-versus-noise review"),
    ("research_synthesis", "Build a verified reading corpus around a bounded research question"): ("研究语料构建", "Verified research corpus"),
    ("research_synthesis", "Trace visual references to their public context and stated method"): ("视觉方法溯源", "Visual-method provenance"),
    ("research_synthesis", "Compare the week's research threads and select bounded Monday follow-ups"): ("周研究复盘", "Weekly research review"),
    ("research_synthesis", "Distinguish adjacent aesthetics through source-backed criteria"): ("美学分类研究", "Aesthetic classification research"),
    ("research_synthesis", "Compare publication venues against actual scope and selection history"): ("投稿渠道调研", "Publication venue research"),
    ("research_synthesis", "Build a sociological classification from real public visual samples"): ("视觉社会学分类", "Visual sociology classification"),
    ("research_synthesis", "Review historical records without converting autonomous self-time into assigned labor"): ("自主时间档案复核", "Autonomous-time archive review"),
    ("research_synthesis", "Locate primary texts and distinguish originals, translations, and commentary"): ("一手文本核验", "Primary-text verification"),
    ("research_synthesis", "Review public source candidates for the next day's content batch"): ("内容来源筛选", "Content-source screening"),
    ("research_synthesis", "Verify the source set for the next large public-content queue"): ("批量来源核验", "Batch source verification"),
    ("system_maintenance", "Preserve deferred publication state without silently sending it"): ("待发状态保护", "Deferred-publication state protection"),
    ("system_maintenance", "Validate provenance levels after the source graph refresh"): ("溯源层级校验", "Provenance-level verification"),
    ("system_maintenance", "Audit the operating contract for drift across linked components"): ("运行契约审计", "Operating-contract audit"),
    ("system_maintenance", "Inspect queue state for duplicated or orphaned work items"): ("队列完整性检查", "Queue integrity check"),
    ("system_maintenance", "Audit generated reports for unsupported certainty"): ("报告置信度审计", "Report-confidence audit"),
    ("system_maintenance", "Run structural checks on the final document package"): ("交付包结构检查", "Delivery-package structure check"),
    ("system_maintenance", "Define a public-safe archive boundary that excludes raw private records"): ("公开归档边界", "Public archive boundary"),
    ("system_maintenance", "Run public-safety and generated-asset checks after the interface rebuild"): ("发布前安全检查", "Pre-release safety check"),
    ("system_maintenance", "Review interface and publication warnings left from the weekend run"): ("周末运行警告复核", "Weekend warning review"),
    ("system_maintenance", "Diagnose outbound source failures and preserve retry evidence"): ("出站来源故障排查", "Outbound-source failure diagnosis"),
    ("system_maintenance", "Run deterministic build, public-safety, syntax, and regression checks"): ("构建与安全质检", "Build and safety verification"),
    ("system_maintenance", "Refresh live artwork fold snippets and test calendar integration on multiple viewports"): ("作品嵌入更新", "Artwork embed refresh"),
}

TASK_NAME_EXACT.update({
    ("code_development", "Implement explicit embed=calendar mode for cross-origin iframe operation"): ("网页嵌入开发", "Web embed development"),
    ("research_synthesis", "Review capability claims against observed system behavior"): ("能力声明核验", "Capability claim verification"),
    ("research_synthesis", "Separate structural themes from price-proxy noise in the review"): ("市场结构与噪声复核", "Market structure and noise review"),
    ("research_synthesis", "Review decision-useful deltas without promoting advisory material"): ("决策变化复核", "Decision-useful change review"),
    ("research_synthesis", "Review public market evidence without exposing instruments, positions, or account data"): ("市场公开证据复核", "Public market evidence review"),
    ("research_synthesis", "Assess a monitoring candidate through primary sources and counterevidence"): ("监测候选评估", "Monitoring candidate assessment"),
    ("research_synthesis", "Extract decision-useful changes while leaving weak signals unpromoted"): ("决策变化提取", "Decision-useful change extraction"),
    ("research_synthesis", "Review evidence freshness before retaining any monitoring candidate"): ("监测证据时效复核", "Monitoring evidence freshness review"),
    ("research_synthesis", "Model bounded downside scenarios without exposing instruments or account data"): ("下行情景推演", "Bounded downside scenario analysis"),
    ("document_processing", "Edit bilingual public summaries while preserving the original opening context"): ("双语公开摘要", "Bilingual public summary"),
    ("document_processing", "Normalize bilingual terminology across the review materials"): ("双语术语统一", "Bilingual terminology alignment"),
    ("document_processing", "Normalize bilingual captions across the weekend batch"): ("双语图注整理", "Bilingual caption alignment"),
    ("document_processing", "Produce a bilingual synthesis that labels every source status"): ("双语研究综述", "Bilingual research synthesis"),
    ("document_processing", "Edit bilingual summaries while retaining their opening context"): ("双语摘要整理", "Bilingual summary editing"),
    ("document_processing", "Derive concrete bilingual task names from category and description keywords"): ("任务命名规则", "Task naming rules"),
    ("research_synthesis", "Review public technical claims for licensing and evidence limits"): ("技术许可核验", "Technical licensing review"),
    ("research_synthesis", "Trace primary sources for the highest-priority review items"): ("一手来源追溯", "Primary-source tracing"),
    ("research_synthesis", "Review source freshness and separate confirmed findings from open questions"): ("来源时效复核", "Source freshness review"),
    ("research_synthesis", "Audit provenance, reuse rights, and evidence status for archive materials"): ("归档版权核验", "Archive rights review"),
    ("research_synthesis", "Record unresolved source questions for later primary-source review"): ("来源问题登记", "Source-question register"),
    ("research_synthesis", "Compare fallback observations with the primary-source requirement"): ("来源要求核对", "Source-requirement review"),
    ("research_synthesis", "Audit historical schedule diversity and provenance across public dates"): ("日程溯源审计", "Schedule provenance audit"),
    ("research_synthesis", "Check source freshness before carrying public claims forward"): ("来源时效检查", "Source freshness check"),
    ("research_synthesis", "Verify public-source freshness and register unresolved evidence gaps"): ("公开来源时效核验", "Public-source freshness verification"),
    ("document_processing", "Completed the main ████ proposal, research framework, and technical route for ████, retaining explicit gaps for missing facts."): ("████申报书编制", "████ proposal drafting"),
    ("document_processing", "Revised the ████ proposal against nine comments, verified references, reduced scope, and redrew the figures."): ("████申报书修订", "████ proposal revision"),
    ("document_processing", "Used existing ████ materials to complete the ████ plan and related templates for ████."): ("████模板填报", "████ template completion"),
    ("document_processing", "Applied ████ standards to complete anchored comments, issue summaries, and DOCX validation for the first batch of ████ manuscripts."): ("████文稿批注", "████ manuscript annotation"),
    ("document_processing", "Completed a pre-external-review audit of a ████ manuscript for ████, inserted anchored comments, and verified text, anchors, authorship, and file integrity."): ("████文稿复核", "████ manuscript review"),
    ("code_development", "Fix mobile artwork text overlap and refine detail layout responsiveness"): ("移动作品重叠修复", "Mobile artwork overlap repair"),
    ("code_development", "Converted cash-secured put, assignment, and covered-call rules into a ████ account-aware scanner and verified it with live-data dry runs."): ("期权策略扫描器验证", "Options-strategy scanner verification"),
    ("visual_production", "Design and integrate deterministic theme-derived planner doodles as SVG motifs"): ("主题图案设计", "Theme doodle design"),
})


def derive_authored_task_name(category: str, description_en: str, description_zh: str) -> tuple[str, str]:
    """Name authored history from evidence; never infer a stronger specialty."""
    if category == "redacted_private":
        return "████", "████"
    exact = TASK_NAME_EXACT.get((category, description_en.strip()))
    if exact:
        return exact
    clean_en = re.sub(r"\s+", " ", description_en).strip().rstrip(".")
    words = clean_en.split(" ")
    name_en = " ".join(words[:6]) + ("…" if len(words) > 6 else "")
    clean_zh = re.sub(r"\s+", "", description_zh).strip().rstrip("。")
    name_zh = clean_zh[:16] + ("…" if len(clean_zh) > 16 else "")
    return name_zh, name_en


def derive_task_name(category: str, description_en: str, description_zh: str) -> tuple[str, str]:
    """Derive a concrete public task name from authored phrases or bounded keywords."""
    exact = TASK_NAME_EXACT.get((category, description_en.strip()))
    if exact:
        return exact
    rules = TASK_NAME_RULES.get(category, [])
    for rule in rules:
        for kw in rule["keywords"]:
            if keyword_matches(kw, description_en, description_zh):
                return rule["task_name_zh"], rule["task_name_en"]
    fallback_names = {
        "social_media_organization": ("公开内容编排", "Public content curation"),
        "document_processing": ("文稿整理与修订", "Manuscript editing"),
        "code_development": ("功能开发与验证", "Feature development and verification"),
        "research_synthesis": ("专题研究与综合", "Topic research and synthesis"),
        "system_maintenance": ("系统维护工作", "System maintenance work"),
        "visual_production": ("视觉内容制作", "Visual content production"),
        "redacted_private": ("████", "████"),
    }
    return fallback_names.get(category, ("工作整理", "Work organization"))


COLLABORATION_TASK_NAMES = {
    "research_synthesis": ("研究与题材判断", "Research and thematic inquiry"),
    "visual_production": ("视觉创作与修改", "Visual creation and revision"),
    "document_processing": ("写作与文档打磨", "Writing and document refinement"),
    "code_development": ("开发与验证", "Development and validation"),
    "social_media_organization": ("内容组织与发布", "Content organization and publishing"),
    "system_maintenance": ("系统维护与部署", "System maintenance and deployment"),
    "redacted_private": ("讨论与任务推进", "Discussion and task advancement"),
}


def keyword_matches(keyword: str, description_en: str, description_zh: str) -> bool:
    """Match English tokens on boundaries and CJK phrases as substrings."""
    folded = keyword.casefold()
    if re.fullmatch(r"[a-z0-9][a-z0-9 /_-]*", folded):
        haystack = f"{description_en} {description_zh}".casefold()
        return re.search(rf"(?<![a-z0-9]){re.escape(folded)}(?![a-z0-9])", haystack) is not None
    return keyword in description_zh or folded in description_en.casefold()


def derive_task_type(category: str, description_en: str, description_zh: str) -> dict:
    """Expose a stable public work type, using specialties only when the text supports them."""
    if category != "redacted_private" and is_finance_domain(description_en, description_zh):
        definition = TASK_TYPE_DEFINITIONS["investment_research"]
        return {
            "task_type": "investment_research",
            "task_type_zh": definition["zh"],
            "task_type_en": definition["en"],
            "task_color": definition["color"],
            "task_icon": definition["icon"],
        }

    for task_type, eligible_categories, keywords in SPECIAL_TASK_TYPE_RULES:
        if category in eligible_categories and any(
            keyword_matches(keyword, description_en, description_zh) for keyword in keywords
        ):
            definition = TASK_TYPE_DEFINITIONS[task_type]
            return {
                "task_type": task_type,
                "task_type_zh": definition["zh"],
                "task_type_en": definition["en"],
                "task_color": definition["color"],
                "task_icon": definition["icon"],
            }

    task_type = TASK_TYPE_FALLBACKS[category]
    definition = TASK_TYPE_DEFINITIONS[task_type]
    return {
        "task_type": task_type,
        "task_type_zh": definition["zh"],
        "task_type_en": definition["en"],
        "task_color": definition["color"],
        "task_icon": definition["icon"],
    }


def is_finance_domain(description_en: str, description_zh: str) -> bool:
    """Classify the domain after removing explicit non-finance negations."""
    cleaned_en = re.sub(
        r"(?i)\b(?:non[- ]?financial|non[- ]?finance|not\s+(?:a\s+)?financial)\b",
        "",
        description_en,
    )
    cleaned_zh = re.sub(r"(?:非金融|非投资)", "", description_zh)
    return any(
        keyword_matches(keyword, cleaned_en, cleaned_zh)
        for keyword in FINANCE_DOMAIN_KEYWORDS
    )


def derive_theme_motif(public_entry: dict, config: dict) -> str:
    day_date = public_entry["date"]
    override = config.get("theme_motif_overrides", {}).get(day_date)
    if override:
        return override
    subject_en = f"{public_entry['title_en']} {public_entry['variable_en']}"
    subject_zh = f"{public_entry['title_zh']} {public_entry['variable_zh']}"
    for motif, keywords in THEME_MOTIF_RULES:
        if any(keyword_matches(keyword, subject_en, subject_zh) for keyword in keywords):
            return motif
    raise SystemExit(f"{day_date} needs an authored theme_motif_overrides entry")


def task_ranges(day_date: str, residues: list[dict], autonomous: dict) -> list[tuple[str, str]]:
    autonomous_start = minutes(autonomous["start"])
    autonomous_end = minutes(autonomous["end"])
    default_slots = [8 * 60, 10 * 60 + 30, 13 * 60 + 30, 16 * 60, 19 * 60, 21 * 60 + 30]
    duration_ranges = {
        "code_development": (75, 180),
        "document_processing": (60, 150),
        "research_synthesis": (45, 135),
        "social_media_organization": (20, 60),
        "visual_production": (45, 120),
        "redacted_private": (30, 90),
        "system_maintenance": (20, 75),
    }
    semantic_starts = (
        (re.compile(r"(?i)(?:premarket|pre-open|盘前)"), 7 * 60 + 30),
        (re.compile(r"(?i)(?:morning|晨间|上午)"), 9 * 60),
        (re.compile(r"(?i)(?:midday|午间|中午)"), 11 * 60 + 30),
        (re.compile(r"(?i)(?:close|收盘|盘后|复盘)"), 15 * 60 + 30),
        (re.compile(r"(?i)(?:overnight|night|晚间|夜间)"), 21 * 60),
    )
    ranges = []
    for index, residue in enumerate(residues):
        if residue.get("source_kind") in SESSION_SOURCE_KINDS:
            expected_provenance = (
                {"observed_message_envelope"}
                if residue.get("source_kind") == "collaboration_session"
                else {"observed_session_window", "observed_message_fallback"}
            )
            require(
                residue.get("time_provenance") in expected_provenance
                and isinstance(residue.get("start"), str)
                and isinstance(residue.get("end"), str),
                f"{day_date} session residue is missing observed timing",
            )
            ranges.append((residue["start"], residue["end"]))
            continue
        text = f"{residue.get('en', '')} {residue.get('zh', '')}"
        start = next(
            (candidate for pattern, candidate in semantic_starts if pattern.search(text)),
            default_slots[index % len(default_slots)],
        )
        start += stable_index(f"{day_date}|{index}|task-start", 4) * 5
        minimum, maximum = duration_ranges.get(str(residue.get("category", "")), (45, 120))
        steps = max(1, (maximum - minimum) // 15 + 1)
        duration = minimum + stable_index(f"{day_date}|{index}|task-duration", steps) * 15
        if start < autonomous_end and start + duration > autonomous_start:
            start = autonomous_end + 10
        if start + duration > MINUTES_PER_DAY:
            start = MINUTES_PER_DAY - duration
        ranges.append((format_minutes(start), format_minutes(start + duration)))
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
            if item.get("type") == "calendar" and field in {
                "gif", "preview", "visual_preview", "archive_url", "live_url", "bgm",
            }:
                continue
            require(str(item[field]).strip(), f"{day_date} has an empty public field: {field}")
        require(
            item["crystallization_date"] == day_date,
            f"{day_date} crystallization_date must equal the archive date",
        )
        require(
            item["source_date"]
            == (parse_date(day_date) - timedelta(days=1)).isoformat(),
            f"{day_date} source_date must be the previous calendar day",
        )
    return dates


def validate_config(config: dict) -> None:
    require(config.get("schema") == "granted-hours-timetable-calendar-v2", "Config schema must be v2")
    require(config.get("timezone") == "Asia/Shanghai", "Config timezone must be Asia/Shanghai")
    require(config.get("canonical_base_url", "").startswith("https://"), "Config needs canonical_base_url")

    autonomous = config.get("autonomous_hour", {})
    start = minutes(autonomous.get("start", ""))
    end = minutes(autonomous.get("end", ""))
    require(0 <= start < end <= MINUTES_PER_DAY, "autonomous_hour must be within one day")
    for field in (
        "label_en",
        "label_zh",
        "short_en",
        "short_zh",
        "experience_duration_en",
        "experience_duration_zh",
        "note_en",
        "note_zh",
    ):
        require(str(autonomous.get(field, "")).strip(), f"autonomous_hour missing {field}")

    note = config.get("public_data_note", {})
    require(isinstance(note, dict) and {"en", "zh"}.issubset(note), "public_data_note must be an en/zh pair")
    require(all(isinstance(note.get(field), str) for field in ("en", "zh")), "public_data_note fields must be strings")

    taxonomy = config.get("taxonomy", {})
    require(REQUIRED_TAXONOMY.issubset(taxonomy), "Config taxonomy is missing required categories")
    for category, entry in taxonomy.items():
        for field in ("label_en", "label_zh", "short_en", "short_zh", "description_en", "description_zh"):
            require(str(entry.get(field, "")).strip(), f"Taxonomy {category} missing {field}")

    motif_overrides = config.get("theme_motif_overrides", {})
    require(isinstance(motif_overrides, dict), "theme_motif_overrides must be an object")
    for day_date, motif in motif_overrides.items():
        parse_date(day_date)
        require(motif in THEME_MOTIFS, f"{day_date} has unknown theme motif: {motif}")

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
        source.get("schema") == "granted-hours-timetable-history-v4",
        "History schema must be granted-hours-timetable-history-v4",
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
        require(entry.get("provenance") in ALLOWED_HISTORY_PROVENANCE, f"{day_date} has invalid authored provenance")
        raw_residues = entry.get("assigned_residues")
        require(isinstance(raw_residues, list), f"{day_date} assigned_residues must be a list")
        require(
            all(isinstance(residue, dict) for residue in raw_residues),
            f"{day_date} assigned residues must all be objects",
        )
        residues = [
            residue
            for residue in raw_residues
            if not SPOUSE_ACTIVITY_RE.search(f"{residue.get('en', '')} {residue.get('zh', '')}")
        ]
        require(len(residues) <= 10, f"{day_date} history needs 0-10 owner-assigned residues")
        signatures = set()
        for index, residue in enumerate(residues):
            require(isinstance(residue, dict), f"{day_date} residue {index + 1} must be an object")
            faithful_fields = {
                "category",
                "en",
                "zh",
                "redaction_status",
                "redaction_count",
                "source_kind",
                "faithfulness",
            }
            agent_fields = {
                "evidence_count",
                "agent_labels",
                "start",
                "end",
                "time_provenance",
            }
            collaboration_fields = {
                "session_count",
                "delegated_agent_count",
                "returned_agent_count",
                "request_zh",
                "request_en",
                "outcome_zh",
                "outcome_en",
                "completion_status",
                "pair_provenance",
            }
            assessment_fields = {
                "assessment_zh",
                "assessment_en",
                "assessment_provenance",
            }
            owner_response_fields = {
                "owner_response_zh",
                "owner_response_en",
                "owner_response_provenance",
                "owner_response_evidence_count",
            }
            optional_collaboration_fields = set()
            if any(field in residue for field in assessment_fields):
                optional_collaboration_fields |= assessment_fields
            if any(field in residue for field in owner_response_fields):
                optional_collaboration_fields |= owner_response_fields
            expected_fields = (
                faithful_fields
                | agent_fields
                | (
                    collaboration_fields | optional_collaboration_fields
                    if residue.get("source_kind") == "collaboration_session"
                    else set()
                )
                if residue.get("source_kind") in SESSION_SOURCE_KINDS
                else faithful_fields
            )
            require(
                set(residue) == expected_fields,
                f"{day_date} residue {index + 1} has an invalid faithful-summary schema",
            )
            require(residue["category"] in REQUIRED_TAXONOMY, f"{day_date} residue {index + 1} has an unknown category")
            require(str(residue["en"]).strip(), f"{day_date} residue {index + 1} missing en")
            require(str(residue["zh"]).strip(), f"{day_date} residue {index + 1} missing zh")
            require(len(residue["en"]) <= 300, f"{day_date} residue {index + 1} English summary is too long")
            require(len(residue["zh"]) <= 90, f"{day_date} residue {index + 1} Chinese summary is too long")
            public_copy = f"{residue['en']} {residue['zh']}"
            require(not SENSITIVE_ASSIGNED_WORK_RE.search(public_copy), f"{day_date} residue {index + 1} exposes holdings or position activity")
            require(not PRIVATE_OPERATIONAL_CONTEXT_RE.search(public_copy), f"{day_date} residue {index + 1} exposes private operational context")
            require(not EDUCATION_IDENTITY_RE.search(public_copy), f"{day_date} residue {index + 1} exposes education or profession identity")
            require(not PROPOSAL_TITLE_CONTEXT_RE.search(public_copy), f"{day_date} residue {index + 1} exposes a proposal title or topic")
            require(residue["redaction_status"] in {"none", "partial", "withheld"}, f"{day_date} residue {index + 1} has invalid redaction status")
            require(isinstance(residue["redaction_count"], int) and residue["redaction_count"] >= 0, f"{day_date} residue {index + 1} has invalid redaction count")
            require(residue["source_kind"] in {"daily_record", "maintenance_record", "task_card", "public_post_archive", "withheld", *SESSION_SOURCE_KINDS}, f"{day_date} residue {index + 1} has invalid source kind")
            require(residue["faithfulness"] == "faithful_summary", f"{day_date} residue {index + 1} must be a faithful summary")
            if residue["source_kind"] in SESSION_SOURCE_KINDS:
                require(
                    isinstance(residue["evidence_count"], int)
                    and not isinstance(residue["evidence_count"], bool)
                    and 1 <= residue["evidence_count"] <= 1000,
                    f"{day_date} residue {index + 1} has an invalid evidence count",
                )
                labels = residue["agent_labels"]
                require(
                    isinstance(labels, list)
                    and bool(labels)
                    and len(labels) == len(set(labels))
                    and all(
                        label in {"Hermes", "Codex", "GPT", "Claude", "subagent"}
                        for label in labels
                    ),
                    f"{day_date} residue {index + 1} has invalid agent labels",
                )
                expected_time_provenance = (
                    {"observed_message_envelope"}
                    if residue["source_kind"] == "collaboration_session"
                    else {"observed_session_window", "observed_message_fallback"}
                )
                require(
                    residue["time_provenance"] in expected_time_provenance,
                    f"{day_date} residue {index + 1} must use observed session timing",
                )
                require(
                    isinstance(residue["start"], str)
                    and isinstance(residue["end"], str)
                    and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", residue["start"])
                    is not None
                    and re.fullmatch(
                        r"(?:(?:[01]\d|2[0-3]):[0-5]\d|24:00)",
                        residue["end"],
                    )
                    is not None,
                    f"{day_date} residue {index + 1} has invalid observed Agent clocks",
                )
                observed_duration = minutes(residue["end"]) - minutes(residue["start"])
                maximum_duration = (
                    24 * 60
                    if residue["source_kind"] == "collaboration_session"
                    else 6 * 60
                )
                require(
                    1 <= observed_duration <= maximum_duration,
                    f"{day_date} residue {index + 1} has an unsafe observed session window",
                )
                if residue["source_kind"] == "collaboration_session":
                    for count_field in (
                        "session_count",
                        "delegated_agent_count",
                        "returned_agent_count",
                    ):
                        require(
                            isinstance(residue[count_field], int)
                            and not isinstance(residue[count_field], bool)
                            and residue[count_field] >= 0,
                            f"{day_date} residue {index + 1} has invalid {count_field}",
                        )
                    require(
                        1 <= residue["session_count"] <= residue["evidence_count"],
                        f"{day_date} residue {index + 1} has inconsistent session evidence",
                    )
                    require(
                        residue["returned_agent_count"]
                        <= residue["delegated_agent_count"],
                        f"{day_date} residue {index + 1} has inconsistent Agent returns",
                    )
                    for pair_field, maximum_length in (
                        ("request_zh", 360),
                        ("request_en", 520),
                        ("outcome_zh", 360),
                        ("outcome_en", 520),
                    ):
                        pair_copy = residue[pair_field]
                        require(
                            isinstance(pair_copy, str)
                            and bool(pair_copy.strip())
                            and len(pair_copy) <= maximum_length
                            and polish_public_excerpt(pair_copy, maximum_length) == pair_copy
                            and not URL_RE.search(pair_copy)
                            and "/Users/" not in pair_copy
                            and ".hermes" not in pair_copy
                            and "state.db" not in pair_copy
                            and not SENSITIVE_ASSIGNED_WORK_RE.search(pair_copy)
                            and not PRIVATE_OPERATIONAL_CONTEXT_RE.search(pair_copy)
                            and not EDUCATION_IDENTITY_RE.search(pair_copy)
                            and not PROPOSAL_TITLE_CONTEXT_RE.search(pair_copy),
                            f"{day_date} residue {index + 1} has unsafe {pair_field}",
                        )
                    if assessment_fields.issubset(residue):
                        require(
                            residue["assessment_provenance"]
                            == "owner_approved_ai_assessment",
                            f"{day_date} residue {index + 1} assessment lacks owner approval",
                        )
                        for field, maximum_length in (
                            ("assessment_zh", 240),
                            ("assessment_en", 360),
                        ):
                            value = residue[field]
                            require(
                                isinstance(value, str)
                                and bool(value.strip())
                                and len(value) <= maximum_length
                                and polish_public_excerpt(value, maximum_length) == value
                                and not URL_RE.search(value)
                                and not SENSITIVE_ASSIGNED_WORK_RE.search(value)
                                and not PRIVATE_OPERATIONAL_CONTEXT_RE.search(value),
                                f"{day_date} residue {index + 1} has unsafe {field}",
                            )
                        require(
                            residue["assessment_zh"].count("████")
                            == residue["assessment_en"].count("████"),
                            f"{day_date} residue {index + 1} assessment mask mismatch",
                        )
                    if owner_response_fields.issubset(residue):
                        require(
                            residue["owner_response_provenance"]
                            == "explicit_owner_feedback"
                            and isinstance(residue["owner_response_evidence_count"], int)
                            and not isinstance(residue["owner_response_evidence_count"], bool)
                            and residue["owner_response_evidence_count"] > 0,
                            f"{day_date} residue {index + 1} owner response lacks explicit evidence",
                        )
                        for field, maximum_length in (
                            ("owner_response_zh", 240),
                            ("owner_response_en", 360),
                        ):
                            value = residue[field]
                            require(
                                isinstance(value, str)
                                and bool(value.strip())
                                and len(value) <= maximum_length
                                and polish_public_excerpt(value, maximum_length) == value
                                and not URL_RE.search(value)
                                and not SENSITIVE_ASSIGNED_WORK_RE.search(value)
                                and not PRIVATE_OPERATIONAL_CONTEXT_RE.search(value),
                                f"{day_date} residue {index + 1} has unsafe {field}",
                            )
                        require(
                            residue["owner_response_zh"].count("████")
                            == residue["owner_response_en"].count("████"),
                            f"{day_date} residue {index + 1} owner response mask mismatch",
                        )
                    require(
                        residue["completion_status"] in {"completed", "unverified"},
                        f"{day_date} residue {index + 1} has invalid completion status",
                    )
                    allowed_pair_provenance = {
                        "matched_public_result_record",
                        "assistant_result_summary",
                        "no_public_result_evidence",
                    }
                    require(
                        residue["pair_provenance"] in allowed_pair_provenance,
                        f"{day_date} residue {index + 1} has invalid pair provenance",
                    )
                    require(
                        (
                            residue["completion_status"] == "completed"
                            and residue["pair_provenance"]
                            in {
                                "matched_public_result_record",
                                "assistant_result_summary",
                            }
                        )
                        or (
                            residue["completion_status"] == "unverified"
                            and residue["pair_provenance"]
                            == "no_public_result_evidence"
                        ),
                        f"{day_date} residue {index + 1} completion evidence mismatch",
                    )
                    request_zh_masks = residue["request_zh"].count("████")
                    request_en_masks = residue["request_en"].count("████")
                    outcome_zh_masks = residue["outcome_zh"].count("████")
                    outcome_en_masks = residue["outcome_en"].count("████")
                    require(
                        request_zh_masks == request_en_masks
                        and outcome_zh_masks == outcome_en_masks,
                        f"{day_date} residue {index + 1} collaboration pair mask mismatch",
                    )
            if residue["source_kind"] == "collaboration_session":
                require(
                    residue["redaction_count"]
                    == residue["request_zh"].count("████")
                    + residue["outcome_zh"].count("████"),
                    f"{day_date} residue {index + 1} collaboration redaction total mismatch",
                )
                require(
                    (residue["redaction_status"] == "none" and residue["redaction_count"] == 0)
                    or (residue["redaction_status"] == "partial" and residue["redaction_count"] > 0),
                    f"{day_date} residue {index + 1} collaboration redaction status mismatch",
                )
            elif residue["redaction_status"] == "none":
                require(residue["redaction_count"] == 0, f"{day_date} unredacted residue cannot report redactions")
            else:
                require(residue["redaction_count"] > 0, f"{day_date} redacted residue needs a positive redaction count")
                require(residue["en"].count("████") == residue["redaction_count"], f"{day_date} residue {index + 1} English mask count mismatch")
                require(residue["zh"].count("████") == residue["redaction_count"], f"{day_date} residue {index + 1} Chinese mask count mismatch")
            require("/Users/" not in residue["en"] and "/Users/" not in residue["zh"], f"{day_date} residue {index + 1} leaks a local path")
            signature = (
                (
                    residue["category"], residue["en"], residue["zh"],
                    residue["request_zh"], residue["request_en"],
                    residue["outcome_zh"], residue["outcome_en"],
                    residue["completion_status"],
                )
                if residue.get("source_kind") == "collaboration_session"
                else (residue["category"], residue["en"], residue["zh"])
            )
            require(signature not in signatures, f"{day_date} assigned residues must be unique")
            signatures.add(signature)
        history_by_date[day_date] = {**entry, "assigned_residues": residues}
    return history_by_date


def load_legacy(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    source = read_json(path)
    return {item["date"]: item for item in source.get("days", []) if item.get("date")}


def load_pulses(path: Path) -> dict[str, list[dict]]:
    require(path.exists(), f"Pulse snapshot does not exist: {path}")
    source = read_json(path)
    snapshot_schema = source.get("schema")
    require(
        snapshot_schema == PULSE_SNAPSHOT_SCHEMA
        or snapshot_schema in LEGACY_PULSE_SNAPSHOT_SCHEMAS,
        (
            f"Pulse snapshot schema must be {PULSE_SNAPSHOT_SCHEMA} "
            f"or a supported legacy schema"
        ),
    )
    require(source.get("timezone") == "Asia/Shanghai", "Pulse snapshot timezone must be Asia/Shanghai")
    days = source.get("days")
    require(isinstance(days, list), "Pulse snapshot days must be a list")
    result: dict[str, list[dict]] = {}
    for entry in days:
        require(isinstance(entry, dict) and set(entry) == {"date", "pulses"}, "Pulse day has invalid fields")
        day_date = entry["date"]
        parse_date(day_date)
        require(day_date not in result, f"Duplicate pulse date: {day_date}")
        pulses = entry["pulses"]
        require(isinstance(pulses, list), f"{day_date} pulses must be a list")
        clean_pulses = []
        for pulse in pulses:
            common_fields = {
                "start",
                "end",
                "duration_minutes",
                "execution_minutes",
                "time_bucket",
                "category",
                "count",
                "time_provenance",
                "summary_provenance",
            }
            is_reminder = (
                isinstance(pulse, dict)
                and pulse.get("category") == "daily_reminder"
            )
            is_authentic_reminder = (
                is_reminder
                and pulse.get("disclosure_policy") == DISCLOSURE_POLICY
            )
            has_legacy_policy = (
                is_reminder
                and "disclosure_policy" in pulse
                and not is_authentic_reminder
            )
            if is_authentic_reminder:
                expected_fields = (
                    common_fields
                    | REMINDER_OWNERSHIP_FIELDS
                    | AUTHENTIC_REMINDER_FIELDS
                )
            else:
                expected_fields = common_fields | {"summary_zh", "summary_en"}
                if is_reminder:
                    expected_fields |= (
                        LEGACY_REMINDER_PROVENANCE_FIELDS
                        if snapshot_schema in LEGACY_PULSE_SNAPSHOT_SCHEMAS
                        else REMINDER_OWNERSHIP_FIELDS
                    )
                if has_legacy_policy:
                    expected_fields |= LEGACY_LIMITED_REMINDER_FIELDS
            require(
                isinstance(pulse, dict)
                and set(pulse) == expected_fields,
                f"{day_date} pulse has invalid fields",
            )
            require(pulse["category"] in PULSE_DEFINITIONS, f"{day_date} pulse has unknown category")
            if pulse["category"] == "daily_reminder":
                require(
                    pulse["owner_scope"] in REMINDER_OWNER_SCOPES,
                    f"{day_date} reminder has invalid owner scope",
                )
                require(
                    pulse["ownership_provenance"] in REMINDER_OWNERSHIP_PROVENANCE,
                    f"{day_date} reminder has invalid ownership provenance",
                )
                if is_authentic_reminder:
                    require(
                        snapshot_schema == PULSE_SNAPSHOT_SCHEMA,
                        f"{day_date} authentic reminder requires the current pulse schema",
                    )
                    require(
                        pulse["disclosure_policy"] == DISCLOSURE_POLICY,
                        f"{day_date} reminder has invalid disclosure policy",
                    )
                    require(
                        pulse["disclosure_authorization"]
                        == DISCLOSURE_AUTHORIZATION,
                        f"{day_date} reminder has invalid disclosure authorization",
                    )
                    require(
                        pulse["projection_kind"]
                        in {
                            "verbatim",
                            "verbatim_redacted",
                            "semantic_abstracted",
                            "semantic_abstracted_redacted",
                        },
                        f"{day_date} reminder has invalid projection kind",
                    )
                    require(
                        pulse["redaction_policy"] == REMINDER_REDACTION_POLICY,
                        f"{day_date} reminder has invalid redaction policy",
                    )
                    require(
                        pulse["projection_provenance"]
                        == REMINDER_PROJECTION_PROVENANCE,
                        f"{day_date} reminder has invalid projection provenance",
                    )
                    require(
                        pulse["original_language"] in {"zh", "en", "mixed"},
                        f"{day_date} reminder has invalid original language",
                    )
                    summary_original = pulse["summary_original"]
                    excerpt_original = pulse["excerpt_original"]
                    require(
                        isinstance(summary_original, str)
                        and bool(summary_original.strip())
                        and len(summary_original) <= 50_000,
                        f"{day_date} reminder has invalid summary_original",
                    )
                    require(
                        isinstance(excerpt_original, str)
                        and bool(excerpt_original.strip())
                        and len(excerpt_original) <= 260,
                        f"{day_date} reminder has invalid excerpt_original",
                    )
                    if len(summary_original) <= 260:
                        require(
                            excerpt_original == summary_original,
                            f"{day_date} short reminder excerpt must equal its original",
                        )
                    else:
                        require(
                            excerpt_original.endswith("…")
                            and summary_original.startswith(excerpt_original[:-1]),
                            f"{day_date} reminder excerpt must be an extractive prefix",
                        )
                    require(
                        isinstance(pulse["redaction_count"], int)
                        and pulse["redaction_count"] >= 0,
                        f"{day_date} reminder has invalid redaction count",
                    )
                    source_mask_count = mask_token_count(
                        summary_original,
                        f"{day_date} reminder summary_original",
                    )
                    require(
                        source_mask_count == pulse["redaction_count"],
                        f"{day_date} reminder source mask count mismatch",
                    )
                    abstraction_count = pulse["semantic_abstraction_count"]
                    require(
                        isinstance(abstraction_count, int)
                        and not isinstance(abstraction_count, bool)
                        and abstraction_count >= 0,
                        f"{day_date} reminder has invalid semantic abstraction count",
                    )
                    expected_kind = (
                        "semantic_abstracted_redacted"
                        if abstraction_count and pulse["redaction_count"]
                        else "semantic_abstracted"
                        if abstraction_count
                        else "verbatim_redacted"
                        if pulse["redaction_count"]
                        else "verbatim"
                    )
                    require(
                        pulse["projection_kind"] == expected_kind,
                        f"{day_date} reminder projection kind disagrees with redaction count",
                    )
                    require(
                        bool(str(pulse["public_label_zh"]).strip())
                        and bool(str(pulse["public_label_en"]).strip()),
                        f"{day_date} reminder labels are empty",
                    )
                    require(
                        pulse["summary_provenance"]
                        == REMINDER_PROJECTION_PROVENANCE,
                        f"{day_date} reminder summary provenance mismatch",
                    )
                    summary_en = pulse["summary_en"]
                    excerpt_en = pulse["excerpt_en"]
                    require(
                        isinstance(summary_en, str)
                        and bool(summary_en.strip())
                        and len(summary_en) <= 100_000,
                        f"{day_date} reminder has invalid summary_en",
                    )
                    require(
                        isinstance(excerpt_en, str)
                        and bool(excerpt_en.strip())
                        and len(excerpt_en) <= 260,
                        f"{day_date} reminder has invalid excerpt_en",
                    )
                    for field, value in (
                        ("summary_en", summary_en),
                        ("excerpt_en", excerpt_en),
                    ):
                        require(
                            CJK_RE.search(value) is None,
                            f"{day_date} reminder {field} contains CJK characters",
                        )
                        require(
                            LATIN_RE.search(value) is not None,
                            f"{day_date} reminder {field} must contain Latin letters",
                        )
                        mask_token_count(
                            value,
                            f"{day_date} reminder {field}",
                        )
                    require(
                        mask_token_count(
                            summary_en,
                            f"{day_date} reminder summary_en",
                        )
                        == source_mask_count,
                        f"{day_date} reminder translation mask count mismatch",
                    )
                    if len(summary_en) <= 260:
                        require(
                            excerpt_en == summary_en,
                            f"{day_date} short reminder English excerpt must equal its translation",
                        )
                    else:
                        require(
                            excerpt_en.endswith("…")
                            and summary_en.startswith(excerpt_en[:-1]),
                            f"{day_date} reminder English excerpt must be an extractive prefix",
                        )
                    require(
                        pulse["translation_provenance"]
                        == REMINDER_TRANSLATION_PROVENANCE,
                        f"{day_date} reminder translation provenance mismatch",
                    )
                else:
                    require(
                        snapshot_schema in LEGACY_PULSE_SNAPSHOT_SCHEMAS
                        or not has_legacy_policy,
                        f"{day_date} legacy reminder policy is not allowed in v5",
                    )
            require(re.fullmatch(r"\d{2}:\d{2}", pulse["start"]) is not None, f"{day_date} pulse has invalid start")
            require(re.fullmatch(r"\d{2}:\d{2}", pulse["end"]) is not None, f"{day_date} pulse has invalid end")
            pulse_start = minutes(pulse["start"])
            pulse_end = minutes(pulse["end"])
            require(0 <= pulse_start < MINUTES_PER_DAY, f"{day_date} pulse start is outside the day")
            require(pulse_start < pulse_end <= MINUTES_PER_DAY, f"{day_date} pulse end is outside the day")
            require(pulse["duration_minutes"] == pulse_end - pulse_start, f"{day_date} pulse duration mismatch")
            require(isinstance(pulse["execution_minutes"], int) and pulse["execution_minutes"] > 0, f"{day_date} pulse execution duration must be positive")
            require(
                pulse["time_bucket"] in {"overnight", "dawn", "morning", "midday", "afternoon", "evening"},
                f"{day_date} pulse has invalid time bucket",
            )
            require(isinstance(pulse["count"], int) and pulse["count"] > 0, f"{day_date} pulse count must be positive")
            require(
                pulse["time_provenance"]
                in {"observed_session_window", "mixed_observed_and_receipt", "receipt_timestamp_estimate"},
                f"{day_date} pulse has invalid time provenance",
            )
            if not is_authentic_reminder:
                require(
                    pulse["summary_provenance"]
                    in {"derived_public_safe", "withheld_unverified"},
                    f"{day_date} pulse summary provenance mismatch",
                )
                require(
                    bool(
                        str(pulse["summary_zh"]).strip()
                        and str(pulse["summary_en"]).strip()
                    ),
                    f"{day_date} pulse summary is empty",
                )
                require(
                    len(pulse["summary_zh"]) <= 360
                    and len(pulse["summary_en"]) <= 520,
                    f"{day_date} pulse summary is too long",
                )
            clean_pulses.append(dict(pulse))
        require(
            clean_pulses == sorted(clean_pulses, key=lambda item: (minutes(item["start"]), item["category"])),
            f"{day_date} pulses must be chronological",
        )
        result[day_date] = clean_pulses
    return result


def inferred_history(public_entry: dict) -> dict:
    """Represent a newly published artwork day awaiting real event evidence."""
    return {
        "date": public_entry["date"],
        "provenance": "inferred",
        # Do not invent work for the current civil day.  The next closure will
        # replace this waiting state with evidence-backed prior-day events.
        "assigned_residues": [],
    }


def first_person_residue_copy(source_kind: str, en: str, zh: str) -> tuple[str, str]:
    """Project authored evidence in Black Day's voice without changing its claim."""
    if source_kind == "withheld":
        return en, zh
    prefixes = {
        "maintenance_record": ("During the routine window, I recorded: ", "我在例行时段记录："),
        "task_card": ("I recorded this evidenced work as: ", "我把这项有证据的工作记为："),
        "daily_record": ("I recorded: ", "我记录下："),
        "public_post_archive": ("I added this already-public work to the calendar: ", "我把这项已经公开的工作记入日历："),
        "agent_session": ("Through Codex, GPT, or a delegated Agent, I recorded: ", "我通过 Codex、GPT 或子 Agent 记录："),
    }
    prefix_en, prefix_zh = prefixes.get(source_kind, ("I recorded: ", "我记录："))
    return f"{prefix_en}{en}", f"{prefix_zh}{zh}"


def authored_residue_copy(source_kind: str, en: str, zh: str) -> tuple[str, str]:
    """Recover the evidence contour beneath the deterministic display voice."""
    if source_kind == "withheld":
        return en, zh
    prefixes = {
        "maintenance_record": ("During the routine window, I recorded: ", "我在例行时段记录："),
        "task_card": ("I recorded this evidenced work as: ", "我把这项有证据的工作记为："),
        "daily_record": ("I recorded: ", "我记录下："),
        "public_post_archive": ("I added this already-public work to the calendar: ", "我把这项已经公开的工作记入日历："),
        "agent_session": ("Through Codex, GPT, or a delegated Agent, I recorded: ", "我通过 Codex、GPT 或子 Agent 记录："),
    }
    prefix_en, prefix_zh = prefixes.get(source_kind, ("I recorded: ", "我记录："))
    require(en.startswith(prefix_en) and zh.startswith(prefix_zh), "First-person residue prefix mismatch")
    return en[len(prefix_en):], zh[len(prefix_zh):]


def stable_voice_variant(key: str, variants: tuple) -> tuple:
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    return variants[int.from_bytes(digest[:4], "big") % len(variants)]


def first_person_collaboration_pair(day_date: str, residue: dict) -> dict:
    request_zh = str(residue["request_zh"])
    request_en = str(residue["request_en"])
    outcome_zh = str(residue["outcome_zh"])
    outcome_en = str(residue["outcome_en"])
    request_zh = request_zh.lstrip("要求").lstrip("：:").strip()
    request_en = re.sub(r"(?i)^request\s*[:：]\s*", "", request_en).strip()
    prefix_zh, prefix_en = stable_voice_variant(
        f"collaboration:{day_date}:{request_zh}:{request_en}",
        COLLABORATION_REQUEST_VOICES,
    )
    request_zh = f"{prefix_zh}{request_zh}"
    request_en = f"{prefix_en}{request_en}"
    if residue.get("completion_status") == "completed":
        if not outcome_zh.startswith("我"):
            outcome_zh = f"我{outcome_zh.lstrip('已').strip()}"
        if not outcome_en.lower().startswith("i "):
            outcome_en = f"I {outcome_en[0].lower() + outcome_en[1:] if outcome_en else outcome_en}"
    return {
        "request_zh": request_zh,
        "request_en": request_en,
        "outcome_zh": outcome_zh,
        "outcome_en": outcome_en,
    }


def build_tasks(public_entry: dict, config: dict, history_entry: dict | None) -> tuple[list[dict], str]:
    history = history_entry or inferred_history(public_entry)
    day_date = public_entry["date"]
    residues = [
        residue
        for residue in history["assigned_residues"]
        if history_entry is None or residue.get("source_kind") != "maintenance_record"
    ]
    ranges = task_ranges(day_date, residues, config["autonomous_hour"])
    tasks = []
    for residue, (start, end) in zip(residues, ranges):
        category = residue["category"]
        taxonomy_entry = config["taxonomy"][category]
        source_kind = residue.get("source_kind", "inferred")
        description_en, description_zh = first_person_residue_copy(
            source_kind, residue["en"], residue["zh"]
        )
        require(
            public_entry["title_en"].lower() not in description_en.lower()
            and public_entry["title_zh"] not in description_zh,
            f"{day_date} assigned residue must not mention the autonomous artwork title",
        )
        if residue.get("source_kind") == "collaboration_session":
            task_name_zh, task_name_en = COLLABORATION_TASK_NAMES[category]
        elif history_entry is not None:
            # Voice is display copy. Task-name classification stays grounded in
            # the original evidence contour so first-person prefixes do not
            # collapse recognizable work types into generic labels.
            task_name_zh, task_name_en = derive_authored_task_name(
                category, residue["en"], residue["zh"]
            )
        else:
            task_name_zh, task_name_en = derive_task_name(category, description_en, description_zh)
        if residue.get("source_kind") == "collaboration_session":
            definition = TASK_TYPE_DEFINITIONS["active_collaboration"]
            task_type = {
                "task_type": "active_collaboration",
                "task_type_zh": definition["zh"],
                "task_type_en": definition["en"],
                "task_color": definition["color"],
                "task_icon": definition["icon"],
            }
        else:
            task_type = derive_task_type(category, description_en, description_zh)
        require(
            not EDUCATION_IDENTITY_RE.search(f"{task_name_en} {task_name_zh}")
            and not PROPOSAL_TITLE_CONTEXT_RE.search(f"{task_name_en} {task_name_zh}"),
            f"{day_date} generated task name exposes education or proposal identity",
        )
        duration_minutes = minutes(end) - minutes(start)
        redaction_status = residue.get("redaction_status", "none")
        redaction_count = residue.get("redaction_count", 0)
        faithfulness = residue.get("faithfulness", "inferred")
        collaboration_pair = (
            first_person_collaboration_pair(day_date, residue)
            if source_kind == "collaboration_session"
            else {}
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
                "task_name_zh": task_name_zh,
                "task_name_en": task_name_en,
                "duration_minutes": duration_minutes,
                "time_provenance": residue.get(
                    "time_provenance",
                    "estimated_semantic_window",
                ),
                "redaction_status": redaction_status,
                "redaction_count": redaction_count,
                "source_kind": source_kind,
                "faithfulness": faithfulness,
                "voice_policy_version": VOICE_POLICY_VERSION,
                **(
                    {
                        "evidence_count": residue["evidence_count"],
                        "agent_labels": residue["agent_labels"],
                    }
                    if source_kind in SESSION_SOURCE_KINDS
                    else {}
                ),
                **(
                    {
                        "session_count": residue["session_count"],
                        "delegated_agent_count": residue[
                            "delegated_agent_count"
                        ],
                        "returned_agent_count": residue[
                            "returned_agent_count"
                        ],
                        **collaboration_pair,
                        "completion_status": residue["completion_status"],
                        "pair_provenance": residue["pair_provenance"],
                        **(
                            {
                                field: residue[field]
                                for field in (
                                    "assessment_zh",
                                    "assessment_en",
                                    "assessment_provenance",
                                )
                            }
                            if "assessment_zh" in residue
                            else {}
                        ),
                        **(
                            {
                                field: residue[field]
                                for field in (
                                    "owner_response_zh",
                                    "owner_response_en",
                                    "owner_response_provenance",
                                    "owner_response_evidence_count",
                                )
                            }
                            if "owner_response_zh" in residue
                            else {}
                        ),
                    }
                    if source_kind == "collaboration_session"
                    else {}
                ),
                **task_type,
            }
        )
    tasks.sort(key=lambda task: (minutes(task["start"]), minutes(task["end"]), task["category"]))
    for index, task in enumerate(tasks):
        task["footprint_id"] = f"assigned-{index + 1:03d}"
    return tasks, history["provenance"]


def build_cell_assigned(tasks: list[dict]) -> list[dict]:
    markers = []
    for task in tasks:
        markers.append(
            {
                "origin": "assigned",
                "category": task["category"],
                "label_en": task["label_en"],
                "label_zh": task["label_zh"],
                "short_en": task["short_en"],
                "short_zh": task["short_zh"],
                "task_name_en": task.get("task_name_en", task["label_en"]),
                "task_name_zh": task.get("task_name_zh", task["label_zh"]),
            }
        )
    return markers


def build_cell_sources(tasks: list[dict], pulses: list[dict]) -> dict[str, dict]:
    active_count = sum(
        task.get("source_kind") in ACTIVE_COLLABORATION_SOURCE_KINDS
        for task in tasks
    )
    routine_count = sum(pulse.get("count", 0) for pulse in pulses) + sum(
        task.get("source_kind") == "maintenance_record" for task in tasks
    )
    return {
        "free_creation": {
            "present": True,
            "count": 1,
            "label_zh": "自由创作",
            "label_en": "Free creation",
        },
        "routine": {
            "present": routine_count > 0,
            "count": routine_count,
            "label_zh": "例行任务",
            "label_en": "Routine",
        },
        "active_collaboration": {
            "present": active_count > 0,
            "count": active_count,
            "label_zh": "人机主动协作",
            "label_en": "Active human–AI collaboration",
        },
    }


def first_person_reminder_copy(
    day_date: str,
    start: str,
    summary_original: str,
    summary_en: str,
    excerpt_original: str,
    excerpt_en: str,
    original_language: str,
) -> tuple[str, str, str, str]:
    """Add a stable, varied Black Day lead without changing reminder content."""
    lead_zh, lead_en = stable_voice_variant(
        f"reminder:{day_date}:{start}",
        REMINDER_VOICES,
    )
    lead_original = lead_en if original_language == "en" else lead_zh
    return (
        f"{lead_original}\n\n{summary_original}",
        f"{lead_en}\n\n{summary_en}",
        f"{lead_original}\n\n{excerpt_original}",
        f"{lead_en}\n\n{excerpt_en}",
    )


def build_background_pulses(day_date: str, pulses: list[dict]) -> list[dict]:
    events = []
    for index, pulse in enumerate(pulses):
        definition = PULSE_DEFINITIONS[pulse["category"]]
        label_zh = definition["label_zh"]
        label_en = definition["label_en"]
        redaction_policy = "not_applicable"
        if pulse["category"] == "daily_reminder":
            authentic_fields = {
                field: pulse.get(field)
                for field in AUTHENTIC_REMINDER_FIELDS
                if field in pulse
            }
            reminder = project_private_reminder(
                {
                    "owner_scope": pulse.get("owner_scope"),
                    "ownership_provenance": pulse.get("ownership_provenance"),
                    **authentic_fields,
                }
            )
            if reminder is None:
                continue
            label_zh = reminder["public_label_zh"]
            label_en = reminder["public_label_en"]
            redaction_policy = reminder["redaction_policy"]
        else:
            summary_zh = pulse["summary_zh"]
            summary_en = pulse["summary_en"]
        event = {
            "origin": "background",
            "footprint_id": f"background-{index + 1:03d}",
            "category": pulse["category"],
            "start": pulse["start"],
            "end": pulse["end"],
            "duration_minutes": pulse["duration_minutes"],
            "execution_minutes": pulse["execution_minutes"],
            "time_bucket": pulse["time_bucket"],
            "count": pulse["count"],
            "time_provenance": pulse["time_provenance"],
            "summary_provenance": pulse["summary_provenance"],
            "label_en": label_en,
            "label_zh": label_zh,
            "pulse_color": definition["color"],
            "redaction_policy": redaction_policy,
        }
        if pulse["category"] == "daily_reminder":
            (
                display_summary_original,
                display_summary_en,
                display_excerpt_original,
                display_excerpt_en,
            ) = first_person_reminder_copy(
                day_date,
                pulse["start"],
                reminder["summary_original"],
                pulse["summary_en"],
                reminder["excerpt_original"],
                pulse["excerpt_en"],
                reminder["original_language"],
            )
            event.update(
                {
                    "owner_scope": pulse["owner_scope"],
                    "ownership_provenance": pulse["ownership_provenance"],
                    "projection_kind": reminder["projection_kind"],
                    "redaction_count": reminder["redaction_count"],
                    "semantic_abstraction_count": reminder[
                        "semantic_abstraction_count"
                    ],
                    "summary_original": display_summary_original,
                    "excerpt_original": display_excerpt_original,
                    "original_language": reminder["original_language"],
                    "disclosure_policy": reminder["disclosure_policy"],
                    "disclosure_authorization": reminder[
                        "disclosure_authorization"
                    ],
                    "projection_provenance": reminder[
                        "projection_provenance"
                    ],
                    "summary_en": display_summary_en,
                    "excerpt_en": display_excerpt_en,
                    "translation_provenance": pulse[
                        "translation_provenance"
                    ],
                    "voice_policy_version": VOICE_POLICY_VERSION,
                }
            )
        else:
            event["summary_zh"] = summary_zh
            event["summary_en"] = summary_en
            public_copy = f"{summary_en} {summary_zh}"
            has_public_alert = pulse_has_public_alert(
                pulse["category"],
                public_copy,
            )
            if has_public_alert:
                event["public_alert"] = True
            event["label_zh"], event["label_en"] = public_occurrence_label(event)
            event["summary_zh"], event["summary_en"] = public_occurrence_summary(
                event,
                alert=has_public_alert,
            )
        events.append(event)
    return events


def classify_public_pulse(pulse: dict) -> dict:
    """Classify a public-safe scheduler footprint into its reading outcome."""
    if pulse["category"] == "daily_reminder":
        return {
            "outcome": "readable_reminder",
            "layer": "event",
            "evidence": [pulse.get("projection_kind", "verbatim")],
        }
    if pulse["category"] in {"system_routine", "background_routine"}:
        return {
            "outcome": "climate_aggregate",
            "layer": "climate",
            "evidence": ["daily_support_rollup"],
        }
    public_copy = f"{pulse.get('summary_en', '')} {pulse.get('summary_zh', '')}"
    if pulse.get("public_alert") is True or pulse_has_public_alert(
        pulse["category"],
        public_copy,
    ):
        return {
            "outcome": "promoted_routine_exception",
            "layer": "event",
            "evidence": ["public_alert"],
        }
    return {
        "outcome": "climate_aggregate",
        "layer": "climate",
        "evidence": ["repeated_public_routine"],
    }


def market_session_window(pulse: dict) -> str:
    start = minutes(pulse["start"])
    if pulse["category"] == "ah_market_scan":
        return (
            "premarket"
            if start < 9 * 60 + 30
            else "intraday"
            if start < 15 * 60
            else "close"
        )
    if pulse["category"] == "us_market_scan":
        return (
            "close"
            if start < 8 * 60
            else "premarket"
            if start < 21 * 60 + 30
            else "intraday"
        )
    raise ValueError("market_session_window requires a market pulse")


def climate_family_and_window(pulse: dict) -> tuple[str, str]:
    category = pulse["category"]
    if category == "ah_market_scan":
        return "ah_market", "daily"
    if category == "us_market_scan":
        return "us_market", "daily"
    if category == "ai_daily_brief":
        return "support_checks", "daily"
    return "support_checks", "daily"


def climate_group_label(family: str, window: str) -> tuple[str, str]:
    families = {
        "ah_market": ("A/H 市场例行任务", "A/H market routine"),
        "us_market": ("美股市场例行任务", "U.S. market routine"),
        "ai_brief": ("AI 日报采集", "AI brief collection"),
        "support_checks": ("后台例行运行", "Background routine activity"),
    }
    windows = {
        "premarket": ("盘前", "premarket"),
        "intraday": ("盘中", "intraday"),
        "close": ("收盘复核", "close review"),
        "daily": ("当日合并", "daily rollup"),
        "early": ("清晨与上午", "dawn & morning"),
        "daytime": ("日间", "daytime"),
        "evening": ("晚间", "evening"),
    }
    family_zh, family_en = families[family]
    window_zh, window_en = windows[window]
    return f"{family_zh} · {window_zh}", f"{family_en} · {window_en}"


def public_occurrence_label(pulse: dict) -> tuple[str, str]:
    if pulse["category"] == "daily_reminder":
        return (
            pulse.get("label_zh", "私人提醒"),
            pulse.get("label_en", "Private reminder"),
        )
    if pulse["category"] in {"ah_market_scan", "us_market_scan"}:
        market_zh, market_en = (
            ("A/H", "A/H")
            if pulse["category"] == "ah_market_scan"
            else ("美股", "U.S.")
        )
        window_zh, window_en = {
            "premarket": ("盘前扫描", "premarket scan"),
            "intraday": ("盘中报告", "intraday report"),
            "close": ("盘后复核", "close review"),
        }[market_session_window(pulse)]
        return f"{market_zh} {window_zh}", f"{market_en} {window_en}"
    labels = {
        "ai_daily_brief": ("AI 日报采集", "AI brief collection"),
        "system_routine": ("服务健康与时效检查", "Service health & freshness check"),
        "background_routine": ("其他后台运行记录", "Other background run record"),
    }
    return labels[pulse["category"]]


def market_public_outcomes(pulses: list[dict]) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    public_copy = " ".join(
        f"{pulse.get('summary_en', '')} {pulse.get('summary_zh', '')}"
        for pulse in pulses
    )
    states = [
        (label_zh, label_en)
        for tokens, label_zh, label_en in MARKET_STATES
        if any(token in public_copy for token in tokens)
    ]
    themes = [
        (label_zh, label_en)
        for tokens, label_zh, label_en in MARKET_THEMES
        if any(token in public_copy for token in tokens)
    ]
    return states, themes


def market_public_evidence(pulses: list[dict], language: str) -> list[str]:
    """Return distinct importer-projected facts without reconstructing private data."""
    field = f"summary_{language}"
    labels = (
        ("公开事实：", "Retained public evidence:")
        if language == "zh"
        else ("Retained public evidence:", "公开事实：")
    )
    facts = []
    signatures = set()
    for pulse in pulses:
        summary = str(pulse.get(field, "")).strip()
        evidence = ""
        for label in labels:
            if label in summary:
                evidence = summary.split(label, 1)[1].strip()
                break
        if not evidence:
            continue
        if language == "zh":
            evidence = re.split(
                r"。(?=(?:\d+\s*次|存在|未检测|本窗口))",
                evidence,
                maxsplit=1,
            )[0]
        else:
            evidence = re.split(
                r"\.\s+(?=(?:\d+\s+run|public report|data or|no public))",
                evidence,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0]
        evidence = evidence.strip(" .。;；")
        signature = evidence.casefold()
        if evidence and signature not in signatures:
            signatures.add(signature)
            facts.append(evidence)
    return facts


def public_occurrence_summary(pulse: dict, *, alert: bool = False) -> tuple[str, str]:
    category = pulse["category"]
    if category in {"ah_market_scan", "us_market_scan"}:
        return (
            f"我完成了这次例行扫描；我观察到：{pulse['summary_zh']}",
            f"I completed this routine scan; I observed: {pulse['summary_en']}",
        )
    if category == "ai_daily_brief":
        return (
            (
                f"我完成 {pulse['count']} 次 AI 日报采集；"
                + ("出现公开提示。" if alert else "未保留公开提示。")
            ),
            (
                f"I completed {pulse['count']} AI-brief collection run(s); "
                + ("a public notice was retained." if alert else "no public notice was retained.")
            ),
        )
    if category == "system_routine":
        return (
            (
                f"我完成 {pulse['count']} 次服务健康与时效检查；"
                + ("出现公开提示。" if alert else "未保留公开提示。")
            ),
            (
                f"I completed {pulse['count']} service-health and freshness check(s); "
                + ("a public notice was retained." if alert else "no public notice was retained.")
            ),
        )
    if category == "background_routine":
        return (
            (
                f"我完成 {pulse['count']} 次其他后台运行；"
                + ("出现公开提示。" if alert else "未保留公开提示。")
            ),
            (
                f"I completed {pulse['count']} other background run(s); "
                + ("a public notice was retained." if alert else "no public notice was retained.")
            ),
        )
    return pulse["summary_zh"], pulse["summary_en"]


def climate_group_summary(pulses: list[dict]) -> tuple[str, str]:
    run_count = sum(pulse["count"] for pulse in pulses)
    window_count = len(pulses)
    category = pulses[0]["category"]
    if category in {"ah_market_scan", "us_market_scan"}:
        windows = Counter(market_session_window(pulse) for pulse in pulses)
        window_zh = "、".join(
            f"{label} {windows[key]} 窗"
            for key, label in (
                ("premarket", "盘前"),
                ("intraday", "盘中"),
                ("close", "盘后复核"),
            )
            if windows[key]
        )
        window_en = ", ".join(
            f"{windows[key]} {label} window(s)"
            for key, label in (
                ("premarket", "premarket"),
                ("intraday", "intraday"),
                ("close", "close-review"),
            )
            if windows[key]
        )
        states, themes = market_public_outcomes(pulses)
        state_zh = "、".join(state[0] for state in states) if states else "多源扫描未收敛为单一状态标签"
        state_en = ", ".join(state[1] for state in states) if states else "multi-source scans did not converge on one regime label"
        theme_zh = "、".join(theme[0] for theme in themes) if themes else ""
        theme_en = ", ".join(theme[1] for theme in themes) if themes else ""
        facts_zh = "；".join(market_public_evidence(pulses, "zh"))[:260].rstrip("；; ")
        facts_en = "; ".join(market_public_evidence(pulses, "en"))[:340].rstrip("；; ")
        if not facts_zh:
            facts_zh = "未保留公开事实"
        if not facts_en:
            facts_en = "no public facts were retained"
        theme_clause_zh = f"；主题：{theme_zh}" if theme_zh else ""
        theme_clause_en = f"; themes: {theme_en}" if theme_en else ""
        return (
            f"我在 {window_count} 个精确窗口（{window_zh}）共完成 {run_count} 次扫描；我观察到：{state_zh}{theme_clause_zh}；公开事实：{facts_zh}。",
            f"I completed {run_count} scans across {window_count} exact windows ({window_en}); I observed: {state_en}{theme_clause_en}; retained public evidence: {facts_en}.",
        )
    if category == "ai_daily_brief":
        return (
            f"我在 {window_count} 个精确窗口共完成 {run_count} 次 AI 日报采集；未保留公开提示。",
            f"I completed {run_count} AI-brief collection run(s) across {window_count} exact window(s); no public notice was retained.",
        )
    alert_window_count = sum(pulse.get("public_alert") is True for pulse in pulses)
    quiet_window_count = window_count - alert_window_count
    if alert_window_count:
        status_zh = (
            f"{alert_window_count} 个窗口记录到通用状态变化，"
            f"{quiet_window_count} 个窗口无须单独提示"
        )
        status_en = (
            f"{alert_window_count} window(s) recorded a general status change; "
            f"{quiet_window_count} required no separate notice"
        )
    else:
        status_zh = f"{window_count} 个窗口均无须单独提示"
        status_en = f"all {window_count} windows required no separate notice"
    return (
        f"我在全天 {window_count} 个精确窗口共完成 {run_count} 次后台例行运行；我发现：{status_zh}。",
        f"I completed {run_count} background routine run(s) across {window_count} exact windows during the day; I found that {status_en}.",
    )


def build_public_reading_items(
    tasks: list[dict],
    autonomous_work: dict,
    pulses: list[dict],
) -> list[dict]:
    """Build a smaller public reading plane over the complete footprint audit."""
    reading_items = []
    climate_groups: dict[tuple[str, str], list[dict]] = {}

    for pulse in pulses:
        classification = classify_public_pulse(pulse)
        if classification["outcome"] == "climate_aggregate":
            key = climate_family_and_window(pulse)
            climate_groups.setdefault(key, []).append(pulse)
            continue

        reading_items.append(
            {
                "reading_id": f"{classification['layer']}-{pulse['footprint_id']}",
                "source": "pulses",
                "source_refs": [pulse["footprint_id"]],
                "layer": classification["layer"],
                "classification": classification["outcome"],
            }
        )

    for group_index, ((family, window), group) in enumerate(climate_groups.items(), 1):
        group.sort(key=lambda pulse: (minutes(pulse["start"]), pulse["footprint_id"]))
        reading_items.append(
            {
                "reading_id": f"climate-{group_index:02d}",
                "source": "pulses",
                "source_refs": [pulse["footprint_id"] for pulse in group],
                "layer": "climate",
                "classification": "climate_aggregate",
                "family": family,
                "window": window,
            }
        )

    config_tasks = [
        task
        for task in tasks
        if CONFIG_CHANGE_RE.search(f"{task.get('request_zh', '')} {task.get('request_en', '')} {task.get('zh', '')} {task.get('en', '')}")
    ]
    foreground_tasks = [task for task in tasks if task not in config_tasks]

    for task in foreground_tasks:
        reading_items.append(
            {
                "reading_id": f"event-{task['footprint_id']}",
                "source": "tasks",
                "source_refs": [task["footprint_id"]],
                "layer": "event",
                "classification": "foreground_event",
            }
        )

    if config_tasks:
        reading_items.append(
            {
                "reading_id": "settings-change-001",
                "source": "tasks",
                "source_refs": [task["footprint_id"] for task in config_tasks],
                "layer": "event",
                "classification": "settings_change",
            }
        )

    reading_items.append(
        {
            "reading_id": f"beacon-{autonomous_work['footprint_id']}",
            "source": "autonomous",
            "source_refs": [autonomous_work["footprint_id"]],
            "layer": (
                "absence"
                if autonomous_work.get("origin") == "absence"
                else "beacon"
            ),
            "classification": (
                "absence"
                if autonomous_work.get("origin") == "absence"
                else "beacon"
            ),
        }
    )

    layer_priority = {"beacon": 0, "event": 1, "absence": 2, "climate": 3}
    reading_items.sort(
        key=lambda item: (
            minutes(
                next(
                    event["start"]
                    for event in [*tasks, autonomous_work, *pulses]
                    if event["footprint_id"] == item["source_refs"][0]
                )
            ),
            layer_priority[item["layer"]],
            item["reading_id"],
        )
    )
    return reading_items


def timeline_event_priority(event: dict) -> int:
    return {"self": 0, "assigned": 1, "background": 2}.get(event.get("origin"), 9)


def build_timeline_events(tasks: list[dict], autonomous_work: dict, pulses: list[dict]) -> list[dict]:
    return sorted(
        [*tasks, autonomous_work, *pulses],
        key=lambda event: (minutes(event["start"]), timeline_event_priority(event)),
    )


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


def autonomous_briefs_by_date() -> dict[str, dict[str, str]]:
    briefs: dict[str, dict[str, str]] = {}
    for entry in AUTONOMOUS_ARTWORK_ENTRIES:
        day_date = entry.get("date")
        require(isinstance(day_date, str), "Autonomous artwork entry is missing a date")
        require(day_date not in briefs, f"Duplicate autonomous artwork brief: {day_date}")
        brief = {
            "title_en": str(entry.get("title_en", "")).strip(),
            "title_zh": str(entry.get("title_zh", "")).strip(),
            "brief_en": str(entry.get("intention_en", "")).strip(),
            "brief_zh": str(entry.get("intention_zh", "")).strip(),
        }
        for field, value in brief.items():
            require(value, f"{day_date} autonomous artwork brief is missing {field}")
        briefs[day_date] = brief
    return briefs


def build_autonomous_work(
    public_entry: dict,
    config: dict,
    legacy_entry: dict | None,
    brief_entry: dict[str, str] | None,
) -> dict:
    autonomous = config["autonomous_hour"]
    duration_minutes = minutes(autonomous["end"]) - minutes(autonomous["start"])
    if public_entry.get("type") == "calendar":
        return {
            "origin": "absence",
            "footprint_id": "beacon-001",
            "category": "autonomous_artwork",
            "start": autonomous["start"],
            "end": autonomous["end"],
            "duration_minutes": duration_minutes,
            "experience_duration_en": "No autonomous work this day",
            "experience_duration_zh": "当日无自由作品",
            "source_date": public_entry["source_date"],
            "crystallization_date": public_entry["crystallization_date"],
            "source_day_url": public_entry.get("source_day_url"),
            "crystallization_day_url": public_entry.get("crystallization_day_url"),
            "label_en": autonomous["label_en"],
            "label_zh": autonomous["label_zh"],
            "short_en": "ABSENT",
            "short_zh": "缺席",
            "title_en": public_entry["title_en"],
            "title_zh": public_entry["title_zh"],
            "variable_en": public_entry["variable_en"],
            "variable_zh": public_entry["variable_zh"],
            "en": "No autonomous work was created this day; the window is marked absent.",
            "zh": "当日未生成自由作品；自主窗口标记为缺席。",
            "note_en": "Absent creation window; collaboration and routine records remain public.",
            "note_zh": "缺席的创作窗口；当日协作与例行记录仍公开。",
            "brief_en": "",
            "brief_zh": "",
            "archive_url": "",
            "live_url": "",
            "preview": "",
            "preview_url": "",
            "visual_preview_url": "",
            "gif_url": "",
            "bgm_url": "",
        }
    if legacy_entry and legacy_entry.get("jewel_en") and legacy_entry.get("jewel_zh"):
        jewel_en = legacy_entry["jewel_en"]
        jewel_zh = legacy_entry["jewel_zh"]
    else:
        jewel_en, jewel_zh = default_jewel(public_entry, config)

    require(brief_entry is not None, f"{public_entry['date']} is missing its bilingual artwork brief")
    require(
        brief_entry["title_en"] == public_entry["title_en"]
        and brief_entry["title_zh"] == public_entry["title_zh"],
        f"{public_entry['date']} artwork brief title mismatch",
    )

    return {
        "origin": "self",
        "footprint_id": "beacon-001",
        "category": "autonomous_artwork",
        "start": autonomous["start"],
        "end": autonomous["end"],
        "duration_minutes": duration_minutes,
        "experience_duration_en": autonomous["experience_duration_en"],
        "experience_duration_zh": autonomous["experience_duration_zh"],
        "source_date": public_entry["source_date"],
        "crystallization_date": public_entry["crystallization_date"],
        "source_day_url": public_entry["source_day_url"],
        "crystallization_day_url": public_entry["crystallization_day_url"],
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
        "brief_en": brief_entry["brief_en"],
        "brief_zh": brief_entry["brief_zh"],
        "archive_url": public_entry["archive_url"],
        "live_url": public_entry["live_url"],
        "preview": public_entry["preview"],
        "preview_url": public_entry["preview"],
        "visual_preview_url": public_entry["visual_preview"],
        "gif_url": public_entry["gif"],
        "bgm_url": public_entry["bgm"],
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
    for task in tasks:
        for field in (
            "origin",
            "footprint_id",
            "category",
            "start",
            "end",
            "en",
            "zh",
            "short_en",
            "short_zh",
            "label_en",
            "label_zh",
            "task_name_en",
            "task_name_zh",
            "task_type",
            "task_type_en",
            "task_type_zh",
            "task_color",
            "task_icon",
            "time_provenance",
            "redaction_status",
            "redaction_count",
            "source_kind",
            "faithfulness",
            "voice_policy_version",
        ):
            require(str(task.get(field, "")).strip(), f"{day_date} task missing {field}")
        require(task["origin"] == "assigned", f"{day_date} task origin must be assigned")
        task_start = minutes(task["start"])
        task_end = minutes(task["end"])
        task_type = task["task_type"]
        require(task_type in TASK_TYPE_DEFINITIONS, f"{day_date} has unknown task type {task_type}")
        type_definition = TASK_TYPE_DEFINITIONS[task_type]
        require(task["task_type_en"] == type_definition["en"], f"{day_date} task type English label mismatch")
        require(task["task_type_zh"] == type_definition["zh"], f"{day_date} task type Chinese label mismatch")
        require(task["task_color"] == type_definition["color"], f"{day_date} task type color mismatch")
        require(task["task_icon"] == type_definition["icon"], f"{day_date} task type icon mismatch")
        expected_time_provenance = (
            {"observed_message_envelope"}
            if task["source_kind"] == "collaboration_session"
            else {"observed_session_window", "observed_message_fallback"}
            if task["source_kind"] == "agent_session"
            else {"estimated_semantic_window"}
        )
        require(
            task["time_provenance"] in expected_time_provenance,
            f"{day_date} task has invalid time provenance",
        )
        require(task["redaction_status"] in {"none", "partial", "withheld"}, f"{day_date} task has invalid redaction status")
        require(isinstance(task["redaction_count"], int) and task["redaction_count"] >= 0, f"{day_date} task has invalid redaction count")
        require(task["faithfulness"] in {"faithful_summary", "inferred"}, f"{day_date} task has invalid faithfulness state")
        require(task["voice_policy_version"] == VOICE_POLICY_VERSION, f"{day_date} task has stale voice policy")
        require(task_start < task_end, f"{day_date} has an invalid task range")
        require(
            task.get("duration_minutes") == task_end - task_start,
            f"{day_date} task duration must match its estimated range",
        )
        if task["source_kind"] not in SESSION_SOURCE_KINDS:
            require(not (task_start < end and task_end > start), f"{day_date} has task overlap with autonomous hour")


def validate_day(day: dict, dates: set[str], corpus_size: int, autonomous: dict) -> None:
    for field in ("date", "title_en", "title_zh", "variable_en", "variable_zh", "archive_url", "live_url", "preview", "visual_preview"):
        require(str(day.get(field, "")).strip(), f"{day.get('date')} missing {field}")
    for field in ("archive_url", "live_url", "preview", "visual_preview", "gif", "bgm"):
        require(day[field].startswith("https://"), f"{day['date']} {field} must be an absolute URL")
    require(day.get("theme_motif") in THEME_MOTIFS, f"{day['date']} needs a semantic theme_motif")
    require(
        day.get("crystallization_date") == day["date"],
        f"{day['date']} crystallization date mismatch",
    )
    require(
        day.get("source_date")
        == (parse_date(day["date"]) - timedelta(days=1)).isoformat(),
        f"{day['date']} source date mismatch",
    )
    require(
        day.get("crystallization_window")
        == {
            "start": autonomous["start"],
            "end": autonomous["end"],
            "timezone": "Asia/Shanghai",
        },
        f"{day['date']} crystallization window mismatch",
    )
    if day["source_date"] in dates:
        require(
            str(day.get("source_day_url", "")).endswith(
                f"/timetable/?date={day['source_date']}"
            ),
            f"{day['date']} source day needs a public timetable link",
        )
    else:
        require(
            day.get("source_day_url") is None,
            f"{day['date']} source day link must be absent outside the public corpus",
        )
    seeds = day.get("forward_artwork_seeds")
    require(isinstance(seeds, list), f"{day['date']} forward_artwork_seeds must be a list")
    require(len(seeds) <= 1, f"{day['date']} has duplicate forward artwork seeds")
    for seed in seeds:
        require(
            set(seed)
            == {
                "source_date",
                "crystallization_date",
                "title_en",
                "title_zh",
                "day_url",
            },
            f"{day['date']} forward artwork seed has invalid fields",
        )
        require(
            seed["source_date"] == day["date"]
            and seed["crystallization_date"] in dates
            and parse_date(seed["crystallization_date"])
            == parse_date(seed["source_date"]) + timedelta(days=1),
            f"{day['date']} forward artwork seed has invalid dates",
        )

    validate_tasks(day["date"], day["task_residues"], autonomous)

    self_work = day["autonomous_work"]
    if self_work.get("origin") == "absence":
        require(
            str(self_work.get("title_en", "")).strip()
            and str(self_work.get("title_zh", "")).strip()
            and str(self_work.get("note_en", "")).strip()
            and str(self_work.get("note_zh", "")).strip(),
            f"{day['date']} absence autonomous_work missing readable fields",
        )
        require(minutes(self_work["start"]) == minutes(autonomous["start"]), f"{day['date']} autonomous start mismatch")
        require(minutes(self_work["end"]) == minutes(autonomous["end"]), f"{day['date']} autonomous end mismatch")
        require(
            self_work.get("duration_minutes")
            == minutes(self_work["end"]) - minutes(self_work["start"]),
            f"{day['date']} autonomous duration mismatch",
        )
        require(
            self_work["source_date"] == day["source_date"]
            and self_work["crystallization_date"] == day["crystallization_date"],
            f"{day['date']} autonomous dual-date metadata mismatch",
        )
        if self_work.get("source_day_url") is not None:
            require(
                str(self_work["source_day_url"]).endswith(
                    f"/timetable/?date={day['source_date']}"
                ),
                f"{day['date']} absence source day link mismatch",
            )
    else:
        require(self_work.get("origin") == "self", f"{day['date']} autonomous_work must have origin self")
        for field in ("footprint_id", "start", "end", "experience_duration_en", "experience_duration_zh", "title_en", "title_zh", "variable_en", "variable_zh", "en", "zh", "note_en", "note_zh", "brief_en", "brief_zh", "live_url", "preview_url", "visual_preview_url", "gif_url", "bgm_url"):
            require(str(self_work.get(field, "")).strip(), f"{day['date']} autonomous_work missing {field}")
        for field in ("preview_url", "visual_preview_url", "gif_url", "bgm_url"):
            require(self_work[field].startswith("https://"), f"{day['date']} autonomous {field} must be an absolute URL")
        require(minutes(self_work["start"]) == minutes(autonomous["start"]), f"{day['date']} autonomous start mismatch")
        require(minutes(self_work["end"]) == minutes(autonomous["end"]), f"{day['date']} autonomous end mismatch")
        require(
            self_work.get("duration_minutes")
            == minutes(self_work["end"]) - minutes(self_work["start"]),
            f"{day['date']} autonomous duration mismatch",
        )
        require(
            self_work["source_date"] == day["source_date"]
            and self_work["crystallization_date"] == day["crystallization_date"],
            f"{day['date']} autonomous dual-date metadata mismatch",
        )

    pulses = day.get("background_pulses")
    require(isinstance(pulses, list), f"{day['date']} background_pulses must be a list")
    for pulse in pulses:
        require(pulse.get("origin") == "background", f"{day['date']} pulse origin must be background")
        require(pulse.get("category") in PULSE_DEFINITIONS, f"{day['date']} pulse category is invalid")
        require(isinstance(pulse.get("count"), int) and pulse["count"] > 0, f"{day['date']} pulse count is invalid")
        require(str(pulse.get("footprint_id", "")).strip(), f"{day['date']} pulse needs a footprint id")
        if pulse["category"] == "daily_reminder":
            require(
                pulse.get("disclosure_policy") == DISCLOSURE_POLICY,
                f"{day['date']} public reminder must use the authentic v2 policy",
            )
            require(
                bool(str(pulse.get("summary_original", "")).strip())
                and bool(str(pulse.get("excerpt_original", "")).strip())
                and bool(str(pulse.get("summary_en", "")).strip())
                and bool(str(pulse.get("excerpt_en", "")).strip()),
                f"{day['date']} public reminder needs readable original and English fields",
            )
            require(
                "summary_zh" not in pulse,
                f"{day['date']} public reminder must not synthesize Chinese wording",
            )
    require(
        day.get("cell_sources") == build_cell_sources(day["task_residues"], pulses),
        f"{day['date']} month-cell source bars are not derived from exact sources",
    )
    timeline = day.get("timeline_events")
    require(
        timeline == build_timeline_events(day["task_residues"], self_work, pulses),
        f"{day['date']} unified timeline is not chronological",
    )
    footprint_ids = [event.get("footprint_id") for event in timeline]
    require(
        all(isinstance(footprint_id, str) and footprint_id for footprint_id in footprint_ids),
        f"{day['date']} timeline needs stable day-local footprint ids",
    )
    require(
        len(footprint_ids) == len(set(footprint_ids)),
        f"{day['date']} timeline footprint ids must be unique",
    )

    reading_items = day.get("reading_items")
    require(isinstance(reading_items, list) and reading_items, f"{day['date']} needs a public reading projection")
    sources_by_collection = {
        "tasks": {
            source["footprint_id"]: source
            for source in day["task_residues"]
        },
        "pulses": {
            source["footprint_id"]: source
            for source in pulses
        },
        "autonomous": {
            self_work["footprint_id"]: self_work,
        },
    }
    projected_ids = []
    reading_ids = set()
    for item in reading_items:
        compact_fields = {
            "reading_id",
            "source",
            "source_refs",
            "layer",
            "classification",
        }
        expected_fields = (
            compact_fields | {"family", "window"}
            if item.get("classification") == "climate_aggregate"
            else compact_fields
        )
        require(
            set(item) == expected_fields,
            f"{day['date']} reading item is not a compact source-reference projection",
        )
        require(item.get("layer") in PUBLIC_READING_LAYERS, f"{day['date']} reading item has invalid layer")
        require(
            item.get("classification") in PUBLIC_NARRATIVE_OUTCOMES,
            f"{day['date']} reading item has invalid classification",
        )
        require(str(item.get("reading_id", "")).strip(), f"{day['date']} reading item missing reading_id")
        require(item["reading_id"] not in reading_ids, f"{day['date']} reading ids must be unique")
        reading_ids.add(item["reading_id"])
        source_collection = item.get("source")
        require(
            source_collection in sources_by_collection,
            f"{day['date']} reading item has an invalid source collection",
        )
        members = item.get("source_refs")
        require(isinstance(members, list) and members, f"{day['date']} reading item needs footprint members")
        require(
            all(member in sources_by_collection[source_collection] for member in members),
            f"{day['date']} reading item has a dangling source reference",
        )
        sources = [sources_by_collection[source_collection][member] for member in members]
        projected_ids.extend(members)
        if item["classification"] == "climate_aggregate":
            require(item["layer"] == "climate", f"{day['date']} climate aggregate is on the wrong layer")
            require(
                source_collection == "pulses",
                f"{day['date']} climate group must reference background pulses",
            )
            label_zh, label_en = climate_group_label(item["family"], item["window"])
            summary_zh, summary_en = climate_group_summary(sources)
        elif item["classification"] == "foreground_event":
            require(
                source_collection == "tasks" and len(sources) == 1,
                f"{day['date']} foreground event needs one assigned source",
            )
            label_en, label_zh = sources[0]["task_name_en"], sources[0]["task_name_zh"]
            summary_en, summary_zh = sources[0]["en"], sources[0]["zh"]
        elif item["classification"] == "beacon":
            require(
                source_collection == "autonomous" and len(sources) == 1,
                f"{day['date']} beacon needs one autonomous source",
            )
            label_en, label_zh = sources[0]["title_en"], sources[0]["title_zh"]
            summary_en, summary_zh = sources[0]["note_en"], sources[0]["note_zh"]
        elif item["classification"] == "absence":
            require(
                source_collection == "autonomous" and len(sources) == 1,
                f"{day['date']} absence beacon needs one autonomous source",
            )
            require(item["layer"] == "absence", f"{day['date']} absence is on the wrong layer")
            label_en, label_zh = sources[0]["title_en"], sources[0]["title_zh"]
            summary_en, summary_zh = sources[0]["note_en"], sources[0]["note_zh"]
        elif item["classification"] == "settings_change":
            require(
                source_collection == "tasks" and sources,
                f"{day['date']} settings change needs assigned task sources",
            )
            require(item["layer"] == "event", f"{day['date']} settings change is on the wrong layer")
            label_zh, label_en = "当日设置变更", "Day's settings changes"
            summary_zh = "；".join(
                str(source.get("zh", "")).strip()
                for source in sources
                if str(source.get("zh", "")).strip()
            )
            summary_en = "; ".join(
                str(source.get("en", "")).strip()
                for source in sources
                if str(source.get("en", "")).strip()
            )
        elif item["classification"] == "readable_reminder":
            require(
                source_collection == "pulses"
                and len(sources) == 1
                and sources[0].get("category") == "daily_reminder",
                f"{day['date']} readable reminder needs one v2 reminder source",
            )
            label_zh, label_en = public_occurrence_label(sources[0])
            summary_original = sources[0]["summary_original"]
            excerpt_original = sources[0]["excerpt_original"]
        else:
            require(
                source_collection == "pulses" and len(sources) == 1,
                f"{day['date']} routine projection needs one background source",
            )
            label_zh, label_en = public_occurrence_label(sources[0])
            if item["classification"] == "promoted_routine_exception":
                label_zh = f"{label_zh}提示"
                label_en = f"{label_en} alert"
            summary_en, summary_zh = sources[0]["summary_en"], sources[0]["summary_zh"]
        required_hydrated_values = [
            (label_en, "label_en"),
            (label_zh, "label_zh"),
        ]
        if item["classification"] == "readable_reminder":
            required_hydrated_values.extend(
                [
                    (summary_original, "summary_original"),
                    (excerpt_original, "excerpt_original"),
                    (sources[0]["summary_en"], "summary_en"),
                    (sources[0]["excerpt_en"], "excerpt_en"),
                ]
            )
        else:
            required_hydrated_values.extend(
                [
                    (summary_en, "summary_en"),
                    (summary_zh, "summary_zh"),
                ]
            )
        for value, field in required_hydrated_values:
            require(str(value).strip(), f"{day['date']} reading item missing hydrated {field}")
        require(label_en not in VAGUE_INTERNAL_TITLES, f"{day['date']} exposes a vague English title")
        require(label_zh not in VAGUE_INTERNAL_TITLES, f"{day['date']} exposes a vague Chinese title")
        if item["classification"] == "readable_reminder":
            require(
                item["layer"] == "event",
                f"{day['date']} readable reminder is on the wrong layer",
            )
            source = sources[0]
            if source.get("projection_kind") in {
                "verbatim_redacted",
                "semantic_abstracted_redacted",
            }:
                require(
                    source.get("redaction_count", 0) > 0,
                    f"{day['date']} redacted reminder needs a positive redaction count",
                )
    require(
        len(projected_ids) == len(set(projected_ids)),
        f"{day['date']} one footprint must not appear in multiple reading items",
    )
    require(
        sorted(projected_ids) == sorted(footprint_ids),
        f"{day['date']} reading projection must account for every exact footprint",
    )

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
    pulses_by_date: dict[str, list[dict]] | None = None,
) -> dict:
    dates = validate_public_days(public_days)
    validate_config(config)
    public_by_date = {item["date"]: item for item in public_days}
    base_url = config["canonical_base_url"]
    output_days = []
    require(history_by_date, "At least one authored history entry is required")
    latest_authored_date = max(history_by_date)
    pulses_by_date = pulses_by_date or {}
    latest_pulse_date = max(pulses_by_date) if pulses_by_date else ""
    artwork_briefs = autonomous_briefs_by_date()

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
            "visual_preview": canonical_url(base_url, public_entry["visual_preview"]),
            "gif": canonical_url(base_url, public_entry["gif"]),
            "bgm": canonical_url(base_url, public_entry["bgm"]),
        }
        public_absolute["source_day_url"] = (
            public_timetable_day_url(base_url, public_entry["source_date"])
            if public_entry["source_date"] in public_by_date
            else None
        )
        public_absolute["crystallization_day_url"] = public_timetable_day_url(
            base_url,
            public_entry["crystallization_date"],
        )
        canonical_root = f"{base_url.rstrip('/')}/"
        archive_root = f"{canonical_root}archive/{public_entry['date'][:4]}/{public_entry['date'][5:7]}/{public_entry['date']}/"
        is_calendar_only = public_entry.get("type") == "calendar"
        if not is_calendar_only:
            require(public_absolute["archive_url"] == archive_root, f"{public_entry['date']} archive_url must stay on the canonical day path")
            require(public_absolute["live_url"] == f"{archive_root}live/", f"{public_entry['date']} live_url must stay on the canonical live path")
            require(public_absolute["preview"] == f"{archive_root}assets/preview.png", f"{public_entry['date']} preview must stay on the canonical asset path")
            require(public_absolute["visual_preview"] == f"{archive_root}assets/visual-preview.gif", f"{public_entry['date']} visual preview must stay on the canonical text-free GIF path")
            require(public_absolute["gif"] == f"{archive_root}assets/visual-preview.gif", f"{public_entry['date']} gif must stay on the canonical text-free GIF path")
            bgm_parts = urlsplit(public_absolute["bgm"])
            live_parts = urlsplit(f"{archive_root}live/")
            decoded_bgm_path = unquote(bgm_parts.path)
            decoded_live_path = unquote(live_parts.path)
            relative_bgm_path = decoded_bgm_path[len(decoded_live_path):] if decoded_bgm_path.startswith(decoded_live_path) else ""
            require(
                bgm_parts.scheme == live_parts.scheme
                and bgm_parts.netloc == live_parts.netloc
                and not bgm_parts.query
                and not bgm_parts.fragment
                and "\\" not in decoded_bgm_path
                and all(segment not in {".", ".."} for segment in decoded_bgm_path.split("/"))
                and bool(relative_bgm_path)
                and "/" not in relative_bgm_path
                and relative_bgm_path.endswith(".mp3"),
                f"{public_entry['date']} bgm must stay on the canonical live path",
            )
        legacy_entry = legacy_by_date.get(day_date)
        tasks, history_provenance = build_tasks(public_absolute, config, history_entry)
        brief_entry = artwork_briefs.get(day_date)
        if brief_entry is None and public_entry.get("brief_en") and public_entry.get("brief_zh"):
            brief_entry = {
                "title_en": public_entry["title_en"],
                "title_zh": public_entry["title_zh"],
                "brief_en": str(public_entry["brief_en"]).strip(),
                "brief_zh": str(public_entry["brief_zh"]).strip(),
            }
        autonomous_work = build_autonomous_work(
            public_absolute,
            config,
            legacy_entry,
            brief_entry,
        )
        pulse_source = pulses_by_date.get(day_date, [])
        require(
            pulse_source or is_calendar_only or not latest_pulse_date or day_date > latest_pulse_date,
            f"{day_date} is missing real scheduler run evidence",
        )
        background_pulses = build_background_pulses(day_date, pulse_source)
        reading_items = build_public_reading_items(tasks, autonomous_work, background_pulses)
        relations = build_relations(day_date, public_absolute, dates, public_by_date, legacy_entry)
        forward_artwork_seeds = [
            {
                "source_date": day_date,
                "crystallization_date": target["crystallization_date"],
                "title_en": target["title_en"],
                "title_zh": target["title_zh"],
                "day_url": public_timetable_day_url(
                    base_url,
                    target["crystallization_date"],
                ),
            }
            for target in public_days
            if target["source_date"] == day_date
        ]
        day = {
            **{field: public_absolute[field] for field in REQUIRED_PUBLIC_FIELDS},
            "type": public_entry.get("type", "live"),
            "source_day_url": public_absolute["source_day_url"],
            "crystallization_day_url": public_absolute[
                "crystallization_day_url"
            ],
            "crystallization_window": {
                "start": config["autonomous_hour"]["start"],
                "end": config["autonomous_hour"]["end"],
                "timezone": config["timezone"],
            },
            "theme_motif": derive_theme_motif(public_entry, config),
            "jewel_en": autonomous_work["note_en"],
            "jewel_zh": autonomous_work["note_zh"],
            "history_provenance": history_provenance,
            "cell_assigned": build_cell_assigned(tasks),
            "cell_sources": build_cell_sources(tasks, background_pulses),
            "cell_self": {
                "origin": "self",
                "short_en": (
                    "ABSENT"
                    if is_calendar_only
                    else config["autonomous_hour"]["short_en"]
                ),
                "short_zh": (
                    "缺席"
                    if is_calendar_only
                    else config["autonomous_hour"]["short_zh"]
                ),
                "title_en": public_entry["title_en"],
                "title_zh": public_entry["title_zh"],
            },
            "forward_artwork_seeds": forward_artwork_seeds,
            "task_residues": tasks,
            "autonomous_work": autonomous_work,
            "background_pulses": background_pulses,
            "timeline_events": build_timeline_events(tasks, autonomous_work, background_pulses),
            "reading_items": reading_items,
            "relations": relations,
        }
        validate_day(day, set(dates), len(dates), config["autonomous_hour"])
        output_days.append(day)

    bgm_playlist = [
        {
            "date": day["date"],
            "title_en": day["title_en"],
            "title_zh": day["title_zh"],
            "bgm_url": day["autonomous_work"]["bgm_url"],
        }
        for day in sorted(output_days, key=lambda item: item["date"], reverse=True)
        if day["autonomous_work"].get("bgm_url")
    ]

    return {
        "schema": "granted-hours-timetable-v2",
        "timezone": config["timezone"],
        "canonical_base_url": config["canonical_base_url"],
        "autonomous_hour": config["autonomous_hour"],
        "dual_date_model": {
            "source_day_offset_days": -1,
            "crystallization_window": {
                "start": config["autonomous_hour"]["start"],
                "end": config["autonomous_hour"]["end"],
                "timezone": config["timezone"],
            },
        },
        "public_data_note": config["public_data_note"],
        "note_en": config["public_data_note"]["en"],
        "note_zh": config["public_data_note"]["zh"],
        "taxonomy": config["taxonomy"],
        "pulse_taxonomy": PULSE_DEFINITIONS,
        "bgm_playlist": bgm_playlist,
        "days": output_days,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-days", type=Path, default=DEFAULT_PUBLIC_DAYS)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--history", type=Path, default=DEFAULT_HISTORY)
    parser.add_argument("--pulses", type=Path, default=DEFAULT_PULSES)
    parser.add_argument("--legacy-overrides", type=Path, default=DEFAULT_LEGACY_OVERRIDES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def render_javascript(output_data: dict) -> str:
    """Serialize canonical data once and rehydrate exact timeline references."""
    serialized_data = {
        **output_data,
        "days": [
            {
                key: value
                for key, value in day.items()
                if key != "timeline_events"
            }
            for day in output_data["days"]
        ],
    }
    return (
        "const timetableDataSource = "
        + json.dumps(serialized_data, ensure_ascii=False, indent=2)
        + ";\n"
        + """
const timelineMinutes = (value) => {
  if (value === "24:00") return 24 * 60;
  const [hour, minute] = value.split(":").map(Number);
  return hour * 60 + minute;
};
const timelinePriority = (event) => (
  { self: 0, assigned: 1, background: 2 }[event.origin] ?? 9
);
for (const day of timetableDataSource.days) {
  day.timeline_events = [
    ...day.task_residues,
    day.autonomous_work,
    ...day.background_pulses,
  ].sort((left, right) => (
    timelineMinutes(left.start) - timelineMinutes(right.start)
    || timelinePriority(left) - timelinePriority(right)
  ));
}
export const timetableData = timetableDataSource;
""".lstrip()
    )


def main() -> int:
    args = parse_args()
    public_days = read_json(args.public_days)
    config = read_json(args.config)
    history_by_date = load_history(args.history)
    pulses_by_date = load_pulses(args.pulses)
    legacy_by_date = load_legacy(args.legacy_overrides)
    output_data = build_data(public_days, config, legacy_by_date, history_by_date, pulses_by_date)

    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_javascript(output_data),
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
