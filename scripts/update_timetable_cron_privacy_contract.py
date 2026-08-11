#!/usr/bin/env python3
"""Install the timetable v10 self-maintaining daily-closure contract in live jobs."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import secrets
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


FREE_ROAM_JOB_NAME = "白夜自由时段 · nightly autonomous roam"
DIALOGUE_JOB_NAME = "授时：前一日工作对话脱敏同步"
CLOSURE_JOB_NAME = "授时：每日自由创作与日历闭环"
TARGET_ROLES = {"free_roam", "dialogue", "closure"}
MARKER = "[授时每日公开闭环契约 v10]"
CONTRACT_BLOCK_RE = re.compile(
    r"(?:\n+)?\[(?:授时公开语义隐私契约|授时每日公开闭环契约) v\d+\]\n"
    r"(?:- [^\n]*(?:\n|$))+"
)
STALE_PUBLISH_SECTION_RE = re.compile(
    r"\n公开归档与日历闭环（有公开产物时必做）：\n"
    r".*?"
    r"13\. 若某步卡住/失败，立即停止该步并报告，不等到超时；GitHub 已成功而 Cloudflare 失败时不回滚 GitHub。\n?",
    re.DOTALL,
)
COMMON_CONTRACT = """

[授时每日公开闭环契约 v10]
- 公开文本的处理优先级固定为：先对识别实体打码（████）并保留句子本身的轮廓；整句打码后仍然敏感时，才把该句替换为有界的隐喻或抽象；只有连隐喻都会泄露私人事实时才整条删除。不得把“删除整条”当作默认方案，也不得用类别或主题模板句充当卡片正文。
- 家庭梦境、亲密关系、照护与父母子女角色，只能保留为“私人经验中的关系/责任/照护平衡”等抽象协作主题；不得公开具体人物、情节、冲突或家庭结构。
- 身体、药物、疾病、症状、低能量和情绪状态，只能保留为“个人恢复安排”等抽象主题；不得公开具体名称、表现或时间线。
- 未公开品牌、产品、媒体、采购、活动和合作 Brief，只能保留文案结构、协作流程、发布节奏等工作方法；不得公开主体、产品、活动、身份、账户或合作语境。
- 密钥、Token、部署平台、量化终端、数据链路和账户状态，只能保留为“核对外部服务权限、部署与数据链路可用性”；不得公开平台名、凭据、故障细节或运行状态。
- 人名、地名、项目名、事件名、论文名、研究课题名、疾病名、实际持仓名、手机号、银行账号、路径、URL、凭据及技术标识必须先经过私有 denylist、实体识别与格式规则处理；私有 denylist 保持 Git 外 0600，任何值不得进入日志。
- `metadata/public-identity-allowlist.json` 是所有者明确授权的公开姓名豁免，只允许精确名称 `Simon`、`Simon的白日梦`、`Simon Meng` 绕过人名遮罩；豁免姓名不得让同句中的路径、凭据、账户、私有项目或其他身份绕过扫描。提醒、主动协作、语义清洗和最终安全扫描必须读取同一文件。
- 从 AI 回复补充公开结果时，必须先做独立二次审核；只允许已完成的发现、设计取舍、方法或可验证公开成果。家庭/健康、未公开商业、个人投资与交易、发布运营、教育身份、账户与基础设施、进度闲聊一律不作为新增结果；未知私人语境直接拒绝，不得为了补足卡片编造。
- 主动协作卡的要求与完成必须由 Agent 基于打码后的真实证据撰写为可读轮廓，写入 `metadata/timetable-collaboration-contours.json`（按证据签名 key）；`import_collaboration_events.py` 报 Missing contours 时先补齐注册表再重跑，禁止回退到“要求澄清一个工作判断”“完成了视觉结构调整与结果核验”等模板句式。英文与中文对齐且掩码数量一致。
- 用户主动交谈、主动交办，以及主会话有证据委派给 Codex/GPT/Claude/子 Agent 并返回完成结果的工作，都是“人机主动协作”；发布前必须运行 `python3 scripts/import_collaboration_events.py`，不得只运行旧的单日摘要 upsert。
- A/H 与美股例行扫描只提交聚合卡片：保留运行次数、宽泛主题、有限状态和通用新鲜度提示；不得提交标的、持仓、价格、动作建议、终端名、源状态、Workspace 标识或维护路径。
- 运行 `import_timetable_pulses.py` 时必须传入 `--private-redaction-terms .private/identity-denylist.json`，并使用其默认 `--public-identity-allowlist metadata/public-identity-allowlist.json`，使提醒文本与主动协作使用同一套 denylist 与精确公开姓名豁免；不得只依赖通用实体识别。
- 提醒导入必须同时传入 `--authorize-self-reminders --authorize-authentic-reminder-disclosure`；缺少双语翻译时，先对该日期运行 `prepare_reminder_translation_candidates.py`，让 `--jobs` 与 `--output-dir` 指向运行时配置中的真实调度目录（路径保持私有且不得写入日志），并传入 `--date YYYY-MM-DD --private-redaction-terms .private/identity-denylist.json --output .private/reminder-translation-candidates.json`。只从该 0600 文件中的实体打码与语义抽象后候选补齐 `metadata/timetable-reminder-translations.json`，核对中英掩码数量和完整句边界，再重跑同一日期。不得用无授权导入把真实提醒改写为“提醒未公开”，不得把部分历史 receipt 缺失解释为删除旧提醒的证据，也不得把候选文件提交到公开仓库。
- 日历提醒与主动协作均使用 `granted-hours-first-person-v2`：提醒正文以“我提醒 Simon / 我告诉 Simon / 我给 Simon 一个小小的提示”等稳定自然变体开头；协作要求以“Simon 让我 / Simon 交给我一项任务 / Simon 和我说”等稳定自然变体转述。变体只能改变引语框架，不能改变证据、语气强度、完成状态或隐私边界。
- 面向读者只显示直接标题和完整内容，不显示“已整理/已核对……具体内容不公开”“结果｜”“脱敏原话”、遮罩计数、source kind、faithfulness 或上下文压缩/交接提示。长对话只能在完整句边界收束；无法形成完整句的片段不展示。措辞整理必须位于语义抽象与实体打码之后，不能借补全文意恢复被遮蔽的细节。
- 生成或导入日历后，必须先运行 `python3 scripts/apply_semantic_public_policy.py --write`，再运行 `python3 scripts/test_semantic_public_policy.py` 与 `python3 scripts/check_public_safety.py`。任一门禁失败时停止构建、提交、推送和部署，且日志不得回显命中的原文。
- `npm run build:timetable` 已内置同一语义清洗步骤；不得绕开它直接发布旧的 timetable 数据或静态产物。
- 每次运行都必须审计积压而不只看昨天或今天：完整自由创作产物存在但尚未进入 `metadata/days.json` 的日期、`waiting_for_public_day`、`blocked` 和 `partial` 日期都进入持久待办，后续按日期从旧到新重试；失败不得吞掉日期或伪报成功。
- 新作品不再依赖人工编辑硬编码日期表：06:35 闭环对每个明确 `--date` 的未知日期，必须让 `import_free_roam_artifacts.py` 从唯一、已安全扫描的标准双语 `*-note.md` 自动建立 `metadata/autonomous-artwork-entries.json` 声明；说明、日期、授时时段或六项必要媒体任一不完整即 fail closed。不得使用无 `--date` 的发现模式，也不得猜测缺失字段。
- 发布状态必须区分 `ok/partial/blocked/waiting_for_public_day/no_change`，记录公开 SHA、最新日期、待办日期与失败阶段；状态和日志只写计数、日期、哈希与错误类别，不写私有原文或命中的敏感值。
""".rstrip()

FREE_ROAM_CONTRACT = COMMON_CONTRACT + """
- 05:00 任务从 v6 起只负责自由创作、私有日志、本地安全验证和原子 ready receipt；不得写 canonical public worktree，不得 commit、push 或 deploy。公开归档统一交给 06:35 闭环任务，避免创作与发布在同一长任务中互相拖死。
- 本任务禁止执行任何公开归档、commit、push 或 deploy；即使 prompt 其他段落残留旧发布步骤，也一律以本契约为准并忽略，公开归档统一由 06:35 闭环任务执行。
- ready receipt 写入 workspace `tmp/granted-hours-free-roam-ready/YYYY-MM-DD.json`，权限 0600，只含 schema、日期、作品文件基名、所需资产是否齐全、验证状态与更新时间，不含作品正文、私有日志、会话或身份信息。
- 标准双语 `*-note.md` 必须逐项包含标题、自由变量、发心、交互、余像、Source Day、Crystallization Day、03:17–04:17 Asia/Shanghai 授时时段和开放体验时长；它是后续自动声明的唯一公共元数据源。ready receipt 只在完整资产检查后写入；OCR/运行时检查若暂时不可用可标 `verification_pending`，但必须由 06:35 闭环复跑验证，不能因此永久漏发。
- 完整资产生成后必须从 workspace 根目录运行 `python3 art-projects/granted-hours-daily-sync/scripts/write_free_roam_ready_receipt.py --date YYYY-MM-DD --artifacts artifacts/free-roam --receipts tmp/granted-hours-free-roam-ready`；禁止手写 receipt JSON。该命令核验文件、尺寸与 GIF 帧数，原子写入 v2/0600 收据。
""".rstrip()

DIALOGUE_CONTRACT = COMMON_CONTRACT + """
- 00:20 任务只处理刚结束的前一自然日：收集严格 owner-route 私有证据、完成私有审计，并把该日期原子加入 mode-0600 closure state 的 `event_backlog_dates`。它不得写 canonical public worktree，不得运行公开 importer，不得 commit、push 或 deploy。
- 前一日事件必须等到次日 06:35 闭环，与次日自由创作作品在同一个公开提交中发布。若前一日作品尚未公开，仍保留该事件日期，待作品 oldest-first 入历后再导入，不能永久漏收。
- 00:20 只写日期、计数、状态和错误类别；不把私有证据正文复制进 closure state。重复运行同一日期必须幂等，不得重复追加。
""".rstrip()

CLOSURE_CONTRACT = COMMON_CONTRACT + """
- 这是 06:35 主运行、08:35 与 10:35 有界重试的每日自由创作与日历闭环。每次都先检查状态；无新作品、无事件积压且上一轮已成功时立即写 `no_change` 退出。发现 05:00 创作仍在运行时只记录 `blocked_upstream_running`，交给下一次重试，不并发修改公开仓库。
- 预检第一步固定运行 `python3 scripts/plan_daily_closure.py --current-date YYYY-MM-DD`，并严格按其 `artwork_dates`、`event_dates`、`waiting_event_dates` 执行；不得自行猜测日期。该计划器会确定性排除当天事件，同时让新作品日暂时没有事件脉冲。
- 先从 ready receipt 与 `artifacts/free-roam` 交叉验证完整产物，再把所有“已有完整产物但未进入日历”的日期按从旧到新处理；一次可连续补齐多日，不得只处理今天。缺少声明、预览或翻译时修复该日期，不能跳过后清空待办。
- 日期导入只能使用显式 `--date YYYY-MM-DD`。未知日期由 importer 严格读取该日期唯一的安全双语 note 并自动写入公开声明注册表；禁止人工每日改脚本、退回无 `--date` 的全语料导入，或把一个日期的错误扩大为全仓库改写。
- 发布顺序固定为两条日期轨：先导入当天及历史积压的作品；再只对“早于当前自然日”的 `event_backlog_dates` 逐日运行 `python3 scripts/import_collaboration_events.py --date YYYY-MM-DD`，以及带 `--private-redaction-terms .private/identity-denylist.json --authorize-self-reminders --authorize-authentic-reminder-disclosure` 的 `import_timetable_pulses.py --date YYYY-MM-DD`。绝不在当天早晨提前导入当天后续协作/例行事件；当天事件由次日 00:20 收集，并随次日作品闭环发布。
- ready receipt 的验证状态为 pending/partial 时，闭环必须对该日期重新运行 `qa_visual_previews.mjs --date YYYY-MM-DD` 及必要的本地安全检查；通过后原子升级 receipt 为 passed 再继续，失败则保留 oldest-first backlog，不能把暂时运行时问题变成永久缺席。
- 构建公开数据后必须从 canonical public worktree 运行 `python3 scripts/test_first_person_public_contract.py`；它是第一人称协作、例行汇总、审核判断、满意度证据和浏览器运行时一致性的硬门控，失败即停止提交、推送和部署。
- 预览必须同时存在 PNG、GIF 与 WebP；三者都要表现作品本身，禁止目录、错误页、加载壳或可被 OCR 读出的界面/路径文字。GIF/WebP 必须有可见运动、固定帧数和有界时长，archive 与 docs 镜像哈希必须一致。
- 动态捕获只允许一次有界尝试，90 秒仍未完成就终止整棵捕获进程，改用已验证 PNG 的无文字视觉区域生成确定性固定帧动画并同步导出 GIF/WebP；不得把无限等待、静态单帧、缺任一格式或旧 WebP 继续沿用当作成功。
- 只允许 canonical worktree；开始和发布后均验证 `HEAD == origin/main == git ls-remote origin refs/heads/main`。无事务清单时，工作树不干净或三方失配必须 fail closed、保留积压，不 merge/rebase/reset，也不吸收无关改动。
- 第一次写 canonical worktree **之前**，必须把恢复事务原子写入 public state：`transaction_schema=granted-hours-closure-transaction-v1`、`status=in_progress`、`base_head`、`dates`、`stage`、`allowed_path_roots` 与空的 `owned_paths`。每个会改文件的命令前先扩充有界 `allowed_path_roots`，命令后立刻用 `git status --porcelain -z` 更新精确 `owned_paths`；出现门禁失败时先写 `status=blocked`、失败阶段与当前精确路径集，再退出。
- 后续运行遇到 dirty worktree 时，只有同时满足以下条件才允许恢复：事务清单存在且状态为 `in_progress/blocked`；`HEAD == base_head == origin/main == remote main`；积压仍含事务日期；当前 dirty 路径集合与 `owned_paths` **完全相等**；每个路径都位于记录的 `allowed_path_roots`。任一条件不满足都视为无关改动并 fail closed。恢复只能从记录阶段继续，不能把新路径静默并入旧事务。
- 唯一可自动替换旧事务的安全例外：状态为 `blocked`、阶段仍是 `preflight`、`owned_paths` 与 `allowed_path_roots` 都为空，且当前 worktree clean、`HEAD == origin/main == remote main`。此时说明旧闭环从未写公共文件；保留全部作品/事件积压，以当前 HEAD 重建事务后继续。其他 stale base 一律不能自动吸收。
- 提交、推送、部署及公网验收全部成功且工作树恢复干净后，事务状态改为 `completed` 并清空 `owned_paths`；GitHub 已成功但 Cloudflare 失败时保留同一事务为 `partial`，后续只补部署，不能因 dirty 状态重复导入或重做提交。
- 只有测试与公开安全门禁全部通过才能显式暂存、提交、推送和 Cloudflare 部署；GitHub 成功而 Cloudflare 失败时状态为 `partial` 且后续继续补部署，不回滚已发布提交。
- 事务已 `completed/partial` 且 `origin/main` 已包含该事务提交后，若 canonical 仍落后于 `origin/main`，只允许在 dirty 路径集合为空、或与事务 `allowed_path_roots` 内的残留路径完全一致时先对齐：`git fetch origin && git checkout -B main origin/main`，随后必须 `git status` 干净才能开始当日任务；对齐不产生新提交，也不把残留改动并入任何提交。
""".rstrip()

CONTRACT_BY_ROLE = {
    "free_roam": FREE_ROAM_CONTRACT,
    "dialogue": DIALOGUE_CONTRACT,
    "closure": CLOSURE_CONTRACT,
}


def job_role(job: dict) -> str | None:
    name = job.get("name")
    if name == FREE_ROAM_JOB_NAME:
        return "free_roam"
    if name == DIALOGUE_JOB_NAME:
        return "dialogue"
    if name == CLOSURE_JOB_NAME:
        return "closure"
    return None


def make_closure_job(free_roam_job: dict) -> dict:
    workspace_value = free_roam_job.get("workdir")
    if not isinstance(workspace_value, str) or not workspace_value.strip():
        raise SystemExit("The free-roam job has no workspace")
    workspace = Path(workspace_value).resolve()
    artifacts = workspace / "artifacts" / "free-roam"
    receipts = workspace / "tmp" / "granted-hours-free-roam-ready"
    public_worktree = (
        workspace / "art-projects" / "granted-hours-daily-sync"
    )
    public_state = workspace / "tmp" / "granted-hours-daily-closure-state.json"
    prompt = f"""你在执行《授时 / Granted Hours》每日自由创作与日历闭环。任务每天 06:35 主运行，08:35 与 10:35 Asia/Shanghai 有界重试，承接 05:00 自由创作，并自动追赶历史积压。不得递归创建或修改 Cron。

固定路径：
- workspace: `{workspace}`
- private artifacts: `{artifacts}`
- private ready receipts: `{receipts}`
- canonical public worktree: `{public_worktree}`
- public state: `{public_state}`

只在 canonical public worktree 完成导入、测试、提交、推送、部署和公网验收。最终只报告日期、计数、公开 SHA、远程仓库/公网部署状态、积压日期和错误类别；不得回显私有对话、私有日志或敏感命中值。
"""
    timezone = ZoneInfo("Asia/Shanghai")
    now = datetime.now(timezone)
    next_run = now.replace(hour=6, minute=35, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return {
        "id": secrets.token_hex(6),
        "name": CLOSURE_JOB_NAME,
        "prompt": prompt,
        "skills": copy.deepcopy(free_roam_job.get("skills", [])),
        "skill": free_roam_job.get("skill"),
        "model": None,
        "provider": None,
        "base_url": None,
        "script": None,
        "context_from": None,
        "schedule": {
            "kind": "cron",
            "expr": "35 6,8,10 * * *",
            "display": "35 6,8,10 * * *",
        },
        "schedule_display": "35 6,8,10 * * *",
        "repeat": {"times": None, "completed": 0},
        "enabled": True,
        "state": "scheduled",
        "paused_at": None,
        "paused_reason": None,
        "created_at": now.isoformat(),
        "next_run_at": next_run.isoformat(),
        "last_run_at": None,
        "last_status": None,
        "last_error": None,
        "last_delivery_error": None,
        "deliver": free_roam_job.get("deliver", "origin"),
        "origin": copy.deepcopy(free_roam_job.get("origin")),
        "enabled_toolsets": [
            "terminal",
            "file",
            "web",
            "session_search",
            "memory",
            "skills",
            "vision",
        ],
        "workdir": str(workspace),
        "fire_claim": None,
    }



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jobs", type=Path)
    parser.add_argument("--write", action="store_true")
    parser.add_argument(
        "--backup",
        type=Path,
        help="Copy the pre-write catalog to this new rollback path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = json.loads(args.jobs.read_text(encoding="utf-8"))
    jobs = source.get("jobs")
    if not isinstance(jobs, list):
        raise SystemExit("Cron job catalog has no jobs array")
    jobs_by_role: dict[str, dict] = {}
    for job in jobs:
        if not isinstance(job, dict):
            continue
        role = job_role(job)
        if role is None:
            continue
        if role in jobs_by_role:
            raise SystemExit(f"More than one timetable job matched role {role}")
        jobs_by_role[role] = job
    changed = 0
    if "free_roam" not in jobs_by_role or "dialogue" not in jobs_by_role:
        raise SystemExit("Required timetable source jobs were not found")
    if "closure" not in jobs_by_role:
        closure_job = make_closure_job(jobs_by_role["free_roam"])
        jobs.append(closure_job)
        jobs_by_role["closure"] = closure_job
    for role, job in jobs_by_role.items():
        prompt = job.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise SystemExit(f"Target cron role {role} has no prompt")
        contract = CONTRACT_BY_ROLE[role]
        role_changed = False
        if not (prompt.count(MARKER) == 1 and prompt.rstrip().endswith(contract)):
            base = CONTRACT_BLOCK_RE.sub("", prompt).rstrip()
            if "[授时每日公开闭环契约" in base or "[授时公开语义隐私契约" in base:
                raise SystemExit(f"Target cron role {role} has a malformed privacy contract")
            if role == "free_roam":
                base = STALE_PUBLISH_SECTION_RE.sub("", base).rstrip()
            job["prompt"] = f"{base}\n{contract}\n"
            role_changed = True
        if role == "closure":
            expected_schedule = {
                "kind": "cron",
                "expr": "35 6,8,10 * * *",
                "display": "35 6,8,10 * * *",
            }
            if job.get("schedule") != expected_schedule:
                job["schedule"] = expected_schedule
                role_changed = True
            if job.get("schedule_display") != "35 6,8,10 * * *":
                job["schedule_display"] = "35 6,8,10 * * *"
                role_changed = True
        changed += int(role_changed)
    missing = TARGET_ROLES - set(jobs_by_role)
    if missing:
        raise SystemExit("Required timetable cron roles were not found")
    if args.write and changed:
        mode = args.jobs.stat().st_mode & 0o777
        if args.backup is not None:
            if args.backup.exists():
                raise SystemExit("Cron rollback backup path already exists")
            args.backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(args.jobs, args.backup)
            os.chmod(args.backup, mode)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=args.jobs.parent,
            prefix=f".{args.jobs.name}.",
            suffix=".tmp",
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                json.dump(source, output, ensure_ascii=False, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, mode)
            os.replace(temporary, args.jobs)
        finally:
            temporary.unlink(missing_ok=True)
    print(
        f"Timetable cron privacy contract mode={'write' if args.write else 'audit'}; "
        f"targets={len(jobs_by_role)}; changed={changed}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
