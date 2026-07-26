# Granted Hours 移动端作品与混合日历审计报告

- 审计日期：2026-07-26
- 审计对象：`timetable` 月历、每日详情、嵌入式 live artwork、历史任务公开数据
- 结论：**通过**
- 发布目标：仓库 `shengyu-meng/granted-hours` 的 `main` 分支；本报告随同修复提交触发站点部署

## 1. 问题与根因

移动端从月历进入每日作品后，作品页内部的标题、说明、状态和控制按钮以绝对定位覆盖画面。月历外层与作品 iframe 跨域，外层 CSS 无法可靠控制 iframe 内部布局，因此只修改 timetable 外壳不能解决根因。

## 2. 修复控制

1. 月历打开 live artwork 时追加精确查询参数 `embed=calendar`。
2. 75 个 live 页面在 `<head>` 前置注入统一隔离脚本和样式：
   - iframe 内部自行识别 calendar embed；
   - 隐藏标题、HUD、状态、说明和内部按钮；
   - 暂停并静音音频，静音视频；
   - 保留外层 Return / Escape path；
   - 独立访问作品页时保留原文字、声音、折叠按钮和作品控制。
3. 生成器 `scripts/import_free_roam_artifacts.py` 负责刷新全部 live 页面，避免只修生成产物导致下次构建回归。
4. 短视口 chamber 将主要高度留给作品画面；作品正文进入画面下方正常文档流，不再覆盖画面。

## 3. 日历与数据语义审计

- 月份控制改为 `This month / 本月`，不再误写为 Today。
- 明确同一个 Agent 的两种时间制度：23h 人机协作劳动与 1h AI 自主创作。
- 当前公开历史包含 481 条任务、297 种任务描述/短标题。
- 已有历史只使用：
  1. 完整公开短语的人工映射；或
  2. 从原公开描述提取的短标题。
- 模糊关键词推断只用于未来尚无 authored history 的日期，禁止用弱关键词改写既有历史。
- 当前历史通用 fallback：0。
- 来源时效、来源溯源、版权许可被拆分为不同语义，不再互相冒充。
- 每日主题图案使用语义规则或明确的日期覆盖；没有随机/hash motif 兜底。

## 4. 自动化验证证据

### Builder 单元测试

- 命令：`python3 scripts/test_timetable_builder.py`
- 结果：**10/10 PASS**
- 覆盖：历史完整性、时间连续性、确定性、authored/inferred 双路径命名、负例语义、motif 缺失和非法值拒绝。

### 响应式与嵌入回归

- 命令：`TIMETABLE_URL=http://127.0.0.1:8772/timetable/ node scripts/qa_timetable_calendar_enrichment.mjs`
- 结果：**11/11 PASS**
- 覆盖：75 个 live 页面、3 类历史作品运行时变体、跨域 embed 参数、音视频状态、独立访问不退化、短视口、320px 七列无横向溢出。

### 原有 timetable 回归

- 命令：`TIMETABLE_URL=http://127.0.0.1:8772/timetable/ node scripts/qa_timetable_regressions.mjs`
- 结果：**PASS**
- 数据：75 天、297 个独特任务短语、75 份不同日程、详情滚动到底可达。

### 安全与语法

- `python3 scripts/check_public_safety.py`：**PASS**
- Python `py_compile`：**PASS**
- Node `--check`：**PASS**
- `git diff --check`：**PASS**

### 确定性构建

- 两次完整构建 tree SHA-256：
  `f8104c0a0a3721f5f2def2f465a98097ce0153c6f07faa62f7b7cb473f3b652d`
- 结果：**一致**

## 5. 独立代码审查

最终 Codex 只读审查：

```json
{
  "passed": true,
  "security_concerns": [],
  "logic_errors": [],
  "suggestions": [],
  "summary": "Both exact mappings resolve correctly; future inference separates source freshness, provenance, and licensing; table-driven dual-path coverage is present; all 481 historical tasks remain on the authored path; semantic motifs and all 75 embed guards remain intact."
}
```

## 6. 视觉验收

已检查：

- 390 × 844 移动月历；
- 390 × 844 每日详情；
- 421 × 386 短视口 chamber；
- 320px 窄屏回归；
- 代表性历史作品 2026-05-07、2026-07-06、2026-07-17；
- 最新作品 2026-07-26。

结论：没有文字与作品画面重叠，没有横向溢出，Return / Escape 可达，独立作品页不退化。

## 7. 风险与边界

- 仓库原工作区包含大量与本修复无关的 staged / unstaged 修改；发布必须使用严格白名单或干净临时 worktree，禁止 `git add -A`。
- 本审计通过不等于公网部署完成。远程 ref、干净 fresh clone 与部署后的真实 URL 必须在推送后另行核验。
