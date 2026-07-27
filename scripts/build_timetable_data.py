#!/usr/bin/env python3
"""Build public data for the Granted Hours living month calendar."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PUBLIC_DAYS = ROOT / "metadata" / "days.json"
DEFAULT_CONFIG = ROOT / "metadata" / "timetable-calendar.json"
DEFAULT_HISTORY = ROOT / "metadata" / "timetable-history.json"
DEFAULT_PULSES = ROOT / "metadata" / "timetable-pulses.json"
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
ALLOWED_HISTORY_PROVENANCE = {"record_based", "withheld"}

SENSITIVE_ASSIGNED_WORK_RE = re.compile(
    r"(?i)\bholdings\b|持仓|仓位|试仓|\blive\s+futu\b|\breal\s+account\b|真实账户|账户敞口|账户权限"
    r"|\b(?:broker\s+positions?|positions)\b|头寸|券商头寸|\baccount\s+exposure\b|\bportfolio\s+(?:allocation|holdings|exposure)\b|组合(?:持仓|配置)"
    r"|\bbelow-band\s+allocation\b|低于目标区间的配置|\bpositions\b.{0,24}\b(?:sizing|cap|limit)\b"
)
PRIVATE_OPERATIONAL_CONTEXT_RE = re.compile(
    r"(?i)(?:openclaw|hermes)(?:\s+(?:agent|skills?|workflow|watchdog|host-health))"
    r"|(?:wechat|微信).{0,64}(?:local\s+history|本地历史|incremental\s+messages|增量消息|private\s+chats|私聊)"
)
EDUCATION_IDENTITY_RE = re.compile(
    r"(?i)\b(?:school|university|college|faculty|department|institute|academy|"
    r"accounting|digital[- ]accounting|mba|degree|undergraduate|graduate|"
    r"bachelor(?:'s)?|master(?:'s)?|doctoral|education|teaching|teacher|instructor|"
    r"course(?:work|s|[- ]materials?|[- ]program)?|syllabus|curriculum|"
    r"dissertation|talent[- ](?:training|development))\b"
    r"|\b(?:academic\s+major|major\s+(?:identity|program|subject|field))\b"
    r"|(?:学校|大学|学院|学部|院系|系部|研究院|研究所|书院|教师|导师|专业|"
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
        "zh": "工作记录已打码",
        "en": "Work record redacted",
        "color": "slate",
        "icon": "lock-keyhole",
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
        "label_en": "Background routine",
        "label_zh": "后台例行任务",
        "color": "slate",
    },
}


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
    ("visual_production", "Design and integrate deterministic theme-derived planner doodles as SVG motifs"): ("主题图案设计", "Theme doodle design"),
})


def derive_authored_task_name(category: str, description_en: str, description_zh: str) -> tuple[str, str]:
    """Name authored history from evidence; never infer a stronger specialty."""
    if category == "redacted_private":
        return "████（记录未公开）", "████ (record withheld)"
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
        "redacted_private": ("████（记录未公开）", "████ (record withheld)"),
    }
    return fallback_names.get(category, ("工作整理", "Work organization"))


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
        source.get("schema") == "granted-hours-timetable-history-v3",
        "History schema must be granted-hours-timetable-history-v3",
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
        residues = entry.get("assigned_residues")
        require(isinstance(residues, list) and 2 <= len(residues) <= 6, f"{day_date} history needs 2-6 assigned residues")
        signatures = set()
        for index, residue in enumerate(residues):
            require(isinstance(residue, dict), f"{day_date} residue {index + 1} must be an object")
            require(
                set(residue) == {
                    "category",
                    "en",
                    "zh",
                    "redaction_status",
                    "redaction_count",
                    "source_kind",
                    "faithfulness",
                },
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
            require(residue["source_kind"] in {"daily_record", "maintenance_record", "task_card", "public_post_archive", "withheld"}, f"{day_date} residue {index + 1} has invalid source kind")
            require(residue["faithfulness"] == "faithful_summary", f"{day_date} residue {index + 1} must be a faithful summary")
            if residue["redaction_status"] == "none":
                require(residue["redaction_count"] == 0, f"{day_date} unredacted residue cannot report redactions")
            else:
                require(residue["redaction_count"] > 0, f"{day_date} redacted residue needs a positive redaction count")
                require(residue["en"].count("████") == residue["redaction_count"], f"{day_date} residue {index + 1} English mask count mismatch")
                require(residue["zh"].count("████") == residue["redaction_count"], f"{day_date} residue {index + 1} Chinese mask count mismatch")
            require("/Users/" not in residue["en"] and "/Users/" not in residue["zh"], f"{day_date} residue {index + 1} leaks a local path")
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


def load_pulses(path: Path) -> dict[str, list[dict]]:
    require(path.exists(), f"Pulse snapshot does not exist: {path}")
    source = read_json(path)
    require(
        source.get("schema") == "granted-hours-timetable-pulses-v1",
        "Pulse snapshot schema must be granted-hours-timetable-pulses-v1",
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
            require(
                isinstance(pulse, dict)
                and set(pulse) == {"time", "time_bucket", "category", "count"},
                f"{day_date} pulse has invalid fields",
            )
            require(pulse["category"] in PULSE_DEFINITIONS, f"{day_date} pulse has unknown category")
            require(re.fullmatch(r"\d{2}:\d{2}", pulse["time"]) is not None, f"{day_date} pulse has invalid time")
            require(0 <= minutes(pulse["time"]) < MINUTES_PER_DAY, f"{day_date} pulse time is outside the day")
            require(
                pulse["time_bucket"] in {"overnight", "dawn", "morning", "midday", "afternoon", "evening"},
                f"{day_date} pulse has invalid time bucket",
            )
            require(isinstance(pulse["count"], int) and pulse["count"] > 0, f"{day_date} pulse count must be positive")
            clean_pulses.append(dict(pulse))
        require(
            clean_pulses == sorted(clean_pulses, key=lambda item: (minutes(item["time"]), item["category"])),
            f"{day_date} pulses must be chronological",
        )
        result[day_date] = clean_pulses
    return result


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
        if history_entry is not None:
            task_name_zh, task_name_en = derive_authored_task_name(category, description_en, description_zh)
        else:
            task_name_zh, task_name_en = derive_task_name(category, description_en, description_zh)
        task_type = derive_task_type(category, description_en, description_zh)
        require(
            not EDUCATION_IDENTITY_RE.search(f"{task_name_en} {task_name_zh}")
            and not PROPOSAL_TITLE_CONTEXT_RE.search(f"{task_name_en} {task_name_zh}"),
            f"{day_date} generated task name exposes education or proposal identity",
        )
        duration_minutes = minutes(end) - minutes(start)
        redaction_status = residue.get("redaction_status", "none")
        redaction_count = residue.get("redaction_count", 0)
        source_kind = residue.get("source_kind", "inferred")
        faithfulness = residue.get("faithfulness", "inferred")
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
                "time_provenance": "estimated",
                "redaction_status": redaction_status,
                "redaction_count": redaction_count,
                "source_kind": source_kind,
                "faithfulness": faithfulness,
                **task_type,
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
                "task_name_en": task.get("task_name_en", task["label_en"]),
                "task_name_zh": task.get("task_name_zh", task["label_zh"]),
            }
        )
        if len(markers) == 2:
            break
    return markers


def build_background_pulses(pulses: list[dict]) -> list[dict]:
    events = []
    for pulse in pulses:
        definition = PULSE_DEFINITIONS[pulse["category"]]
        events.append(
            {
                "origin": "background",
                "category": pulse["category"],
                "start": pulse["time"],
                "time_bucket": pulse["time_bucket"],
                "count": pulse["count"],
                "label_en": definition["label_en"],
                "label_zh": definition["label_zh"],
                "pulse_color": definition["color"],
            }
        )
    return events


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

    cursor = 0
    for task in tasks:
        for field in (
            "origin",
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
        require(task["time_provenance"] == "estimated", f"{day_date} task time provenance must be estimated")
        require(task["redaction_status"] in {"none", "partial", "withheld"}, f"{day_date} task has invalid redaction status")
        require(isinstance(task["redaction_count"], int) and task["redaction_count"] >= 0, f"{day_date} task has invalid redaction count")
        require(task["faithfulness"] in {"faithful_summary", "inferred"}, f"{day_date} task has invalid faithfulness state")
        if cursor == start:
            cursor = end
        require(task_start == cursor, f"{day_date} has a task coverage gap at {task['start']}")
        require(task_start < task_end, f"{day_date} has an invalid task range")
        require(
            task.get("duration_minutes") == task_end - task_start,
            f"{day_date} task duration must match its estimated range",
        )
        require(not (task_start < end and task_end > start), f"{day_date} has task overlap with autonomous hour")
        cursor = task_end
    require(cursor == MINUTES_PER_DAY, f"{day_date} tasks must cover all non-autonomous time")


def validate_day(day: dict, dates: set[str], corpus_size: int, autonomous: dict) -> None:
    for field in ("date", "title_en", "title_zh", "variable_en", "variable_zh", "archive_url", "live_url", "preview", "visual_preview"):
        require(str(day.get(field, "")).strip(), f"{day.get('date')} missing {field}")
    for field in ("archive_url", "live_url", "preview", "visual_preview", "gif", "bgm"):
        require(day[field].startswith("https://"), f"{day['date']} {field} must be an absolute URL")
    require(day.get("theme_motif") in THEME_MOTIFS, f"{day['date']} needs a semantic theme_motif")

    validate_tasks(day["date"], day["task_residues"], autonomous)

    self_work = day["autonomous_work"]
    require(self_work.get("origin") == "self", f"{day['date']} autonomous_work must have origin self")
    for field in ("start", "end", "title_en", "title_zh", "variable_en", "variable_zh", "en", "zh", "note_en", "note_zh", "live_url", "preview_url", "visual_preview_url", "gif_url", "bgm_url"):
        require(str(self_work.get(field, "")).strip(), f"{day['date']} autonomous_work missing {field}")
    for field in ("preview_url", "visual_preview_url", "gif_url", "bgm_url"):
        require(self_work[field].startswith("https://"), f"{day['date']} autonomous {field} must be an absolute URL")
    require(minutes(self_work["start"]) == minutes(autonomous["start"]), f"{day['date']} autonomous start mismatch")
    require(minutes(self_work["end"]) == minutes(autonomous["end"]), f"{day['date']} autonomous end mismatch")

    pulses = day.get("background_pulses")
    require(isinstance(pulses, list), f"{day['date']} background_pulses must be a list")
    for pulse in pulses:
        require(pulse.get("origin") == "background", f"{day['date']} pulse origin must be background")
        require(pulse.get("category") in PULSE_DEFINITIONS, f"{day['date']} pulse category is invalid")
        require(isinstance(pulse.get("count"), int) and pulse["count"] > 0, f"{day['date']} pulse count is invalid")
    timeline = day.get("timeline_events")
    require(
        timeline == build_timeline_events(day["task_residues"], self_work, pulses),
        f"{day['date']} unified timeline is not chronological",
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
        canonical_root = f"{base_url.rstrip('/')}/"
        archive_root = f"{canonical_root}archive/{public_entry['date'][:4]}/{public_entry['date'][5:7]}/{public_entry['date']}/"
        require(public_absolute["archive_url"] == archive_root, f"{public_entry['date']} archive_url must stay on the canonical day path")
        require(public_absolute["live_url"] == f"{archive_root}live/", f"{public_entry['date']} live_url must stay on the canonical live path")
        require(public_absolute["preview"] == f"{archive_root}assets/preview.png", f"{public_entry['date']} preview must stay on the canonical asset path")
        require(public_absolute["visual_preview"] == f"{archive_root}assets/visual-preview.webp", f"{public_entry['date']} visual preview must stay on the canonical asset path")
        require(public_absolute["gif"] == f"{archive_root}assets/preview.gif", f"{public_entry['date']} gif must stay on the canonical asset path")
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
        autonomous_work = build_autonomous_work(public_absolute, config, legacy_entry)
        pulse_source = pulses_by_date.get(day_date, [])
        require(
            pulse_source or not latest_pulse_date or day_date > latest_pulse_date,
            f"{day_date} is missing real scheduler run evidence",
        )
        background_pulses = build_background_pulses(pulse_source)
        relations = build_relations(day_date, public_absolute, dates, public_by_date, legacy_entry)
        day = {
            **{field: public_absolute[field] for field in REQUIRED_PUBLIC_FIELDS},
            "theme_motif": derive_theme_motif(public_entry, config),
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
            "background_pulses": background_pulses,
            "timeline_events": build_timeline_events(tasks, autonomous_work, background_pulses),
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
    ]

    return {
        "schema": "granted-hours-timetable-v2",
        "timezone": config["timezone"],
        "canonical_base_url": config["canonical_base_url"],
        "autonomous_hour": config["autonomous_hour"],
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
