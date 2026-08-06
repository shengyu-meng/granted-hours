# Codex Handoff — Granted Hours 市场可读性 + Agent 事件补全

## 上下文
- 主线：`feat/daily-dialogue-calendar-sync` @ `6ee6d94aec692e78ebefcfedab110b586b700c77`（已在 origin/main）。
- 用户 2026-08-01 在 Telegram `🎨 自由创作` 提出两点新需求：
  1. 市场详情过保守——常态显示「未形成公开级别状态结论」太不可读。
  2. 整个日历被股票扫描占据；Codex/GPT/子Agent 的代码、PPT、写稿、调研、审校类工作未补为前景事件。
- 后续被红圈指出的额外 UI 修复：主题按钮的 "Theme / 主题" 多余文字去除；主题按钮与月历音乐按钮增加小矢量图标（太阳/月亮、播放/暂停音乐播放器）。

## 任务定义
1. 隐私口径放宽：
   - 允许公开：非当前持仓的公开公司/标的、公开代码、市场事件、主题、价格/涨跌/估值/百分比、判断；
   - 必须隐藏：当前持仓、私密账户状态、自媒体来源归属（媒体/公众号/博主/频道/文章名/链接）、凭据/路径/聊天ID/会话ID；
   - 允许保留 Codex/GPT/Claude/子Agent 名称（公开代理框架名称），但具体执行人/学校/课程/作品/公司/学校/MBA/民大/配偶等实体必须 `████`。
   - 来源归属一律不可出现：作者/公众号/自媒体/频道/URL 等。
2. 市场投影更新：
   - `scripts/build_timetable_data.py` 中市场提取不应常态返回 "未形成公开级别状态结论 / 无额外公开主题"，改为提取公开安全的非持仓标的、主题、事件作为默认；
   - 持仓/来源隐私闸门增加私有持仓 denylist 与来源归属 denylist 的细粒度 scan/正则；
   - 在 `tests/` 增加 RED 测试覆盖（公开非持仓标的可显示；持仓/来源被遮蔽或拒绝）。
3. Agent 事件采集 + 历史回填：
   - 实现一个聚合器：从 会话状态库 中按日期聚合 `codex|gpt|claude|subagent|子Agent|子代理|智能体` 命中的对话会话；
   - 按分类（`code_development / document_processing / visual_production / research_synthesis / social_media_organization / system_maintenance`）回填到 `timetable-history.json`，每事件 1-2 句公开安全结果；
   - 敏感实体（学校、课程、配偶、民大、MBA、作品名等）按 span 打码；
   - 历史回填需可追溯到日期与对话 hash，不编造；
   - 增加 RED 测试：覆盖率、跨日期分布、隐私闸门。
4. UI 修复：
   - 删除主题按钮的冗余 "Theme / 主题" 文字（仅保留图标 + aria-label）；
   - 主题按钮与月历音乐按钮加 SVG 图标（暗时月亮→亮时太阳；播放/暂停音乐图标），保持现有暗/亮主题与可访问性；
   - 不增加外链，不改变 Bundle 体积超过 5KB gzip。

## 边界
- 必须在 worktree `/Users/████/HermesWorkspaces/Heizhou/art-projects/granted-hours-market-agent-events-20260801` 内操作；分支 `fix/granted-hours-market-agent-events-20260801`。
- 必须修改生成器而非只改生成产物，确保未来 cron 不会覆盖修复。
- 必须独立隐私/逻辑审查（clean-context Codex 第二轮），所有阻塞问题修复后再进入父级 QA。

## 验证门
- 单元/集成测试：现有 73 Python 测试 + 新增 RED 测试全 PASS。
- `python scripts/test_*.py` 全 PASS。
- `node --input-type=module <public_hierarchy>` 风格公开安全扫描 PASS：bundle/DOM/aria 无持仓标的无来源归属。
- 视觉 QA：1440×900 / 1024×768 / 768×700 / 390×844 / 421×386 五个视口双向（暗/亮）都通过，无遮挡、无控制层重叠。
- Bundle gzip 增量 ≤ 5KB。

## 运行命令
```bash
cd /Users/████/HermesWorkspaces/Heizhou/art-projects/granted-hours-market-agent-events-20260801
codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox \
  -m gpt-5.5 -c model_reasoning_effort="xhigh" \
  "Read TODO-2026-08-01-granted-hours-market-readability-agent-events.md and this plan, then implement+test+verify the change set. Keep diff scoped. Return the SHA, full test names, privacy review verdict, and visual evidence path."
```

## 不要做的事
- 不要推送、不要部署、不要 `rm -rf` 任何保护路径。
- 不要暴露凭证或私有凭据。
- 不要试图复活旧历史中的敏感对象。
- 不要把 `████` 替换回具体名词。

## 交付清单
- 完整测试报告（行号、断言、命令）。
- 隐私审查 PASS / BLOCK 与修复记录。
- 5 视口 × 2 主题的视觉证据。
- Bundle gzip 增量。
- 最终 commit SHA 与本地/远程/远程 stable/immutable URL 的验证。