# 授时七日电路板日程试验审计

日期：2026-08-13（Asia/Shanghai）

试验范围：2026-08-06 至 2026-08-12（含首尾）

状态：试验已结束；2026-08-13 已按 Simon 的决定撤下 PCB 运行时与切换按钮，当前生产界面仅保留普通日程表

后续审计：[普通日程表恢复、移动压缩与自动链路审计](./AUDIT-2026-08-13-standard-timetable-mobile-compaction-release.md)

功能发布提交：`30c8c02`（`Prototype seven-day PCB timetable view`）

不可变部署：<https://bc1efbd8.granted-hours.pages.dev/timetable/>

## 1. 目标与边界

这次改动只触及“非人日程表”的选中日期详情层。月历未改；普通日程表仍是每次新打开日期时的默认视图；PCB 模式只在上述七个日期显示切换按钮。2026-08-05 及更早日期、2026-08-13 及后续日期均不会自动进入试验。

PCB 不是七套手工页面。它是一套共享模板：可读事件根据内容量、累计时长、语义层和成员足迹数自动获得 compact、medium、large 或 main 封装；AI 自由创作是唯一的 `AI–CORE` 主芯片。

## 2. 实现核对

- 右上角新增 `PCB / 电路板` 切换按钮，置于声音控制与 `Close / 关闭` 之间；切换后按钮变为 `NORMAL / 普通`。
- 普通版与 PCB 版复用同一份 `reading_items`、`timeline_events`、布局投影和反向联动逻辑。
- 事件块被包装为不透明芯片，带四边针脚、芯片参考号和索引点。
- 真实时间足迹改绘为铜线/焊盘；卡片到锚点的连接线改绘为可点亮的走线。
- AI 自由创作保持方形预览，在桌面、移动、短屏和 4K 下均为面积最大的芯片。
- 芯片仍只从左或右边缘切入；没有恢复居中覆盖时间条的旧行为。
- 空白小时折叠、25 个小时刻度、精确并行关系、触控分组、任务详情和作品详情入口均保留。
- PCB 模式显示“可回滚试验”范围说明；普通模式不显示 PCB 装饰。

## 3. 七日数据完整性

| 日期 | 可读芯片 | 精确时间足迹 |
|---|---:|---:|
| 2026-08-06 | 6 | 52 |
| 2026-08-07 | 7 | 65 |
| 2026-08-08 | 9 | 33 |
| 2026-08-09 | 5 | 31 |
| 2026-08-10 | 8 | 99 |
| 2026-08-11 | 7 | 125 |
| 2026-08-12 | 1 | 1 |
| 合计 | 43 | 406 |

切换前后，芯片数、足迹数、每条足迹的 ID、开始时间与结束时间完全一致。

## 4. 门控结果

- `npm run build:timetable`：通过。
- `scripts/qa_timetable_pcb_prototype.mjs`：通过全部七日；通过 1440×900、390×844、421×386、3840×2160；无页面或工具栏横向溢出；试验范围外自动回到普通版。
- `scripts/check_public_safety.py`：通过。
- Python 全库测试：246 项通过。
- `scripts/test_timeline_layout.mjs`：7 个布局用例通过。
- `qa_timetable_stratigraphic_detail.mjs`：桌面双主题、移动、短屏、4K、稀疏日通过。
- `qa_timetable_temporal_composition.mjs`：5 个尺寸通过；3829 条例行源事件保持完整。
- `qa_timetable_reverse_link_palette.mjs`：足迹与芯片双向联动通过。
- `qa_timetable_autonomous_mobile_card.mjs`：移动、短屏、桌面、4K 的自主作品方形预览与单滚动根通过。
- `qa_timetable_public_hierarchy.mjs`：两日 × 五尺寸通过。
- `qa_timetable_regressions.mjs`：通过；191 组独特任务短语与 87 组独特日程保持。
- 生产三端复跑 `qa_timetable_pcb_prototype.mjs`：自定义域、稳定 Pages 域、不可变部署全部通过相同的七日与四尺寸门控。
- 三个生产入口均返回 HTTP 200，并包含本次 PCB 切换控件：
  - <https://granted-hours.hyperint.net/timetable/>
  - <https://granted-hours.pages.dev/timetable/>
  - <https://bc1efbd8.granted-hours.pages.dev/timetable/>

## 5. 可回滚性

功能级回滚：在七日详情右上角点击 `NORMAL / 普通`，立即恢复既有视图；离开 2026-08-06—2026-08-12 会强制回到普通视图。刷新或从月历重新打开日期也以普通版为默认。

代码级回滚：功能改动集中在专用提交 `30c8c02`。若撤销该提交，普通日程数据、历史作品和自动发布数据链均不需要迁移或修复。PCB 样式全部受 `data-view-mode="pcb"` 作用域约束。

## 6. 后续自动更新

自动创作和非人日程数据生成链没有被改写，后续定时任务仍照常更新作品和非人日程表。由于这是封闭试验，新日期不会自行获得 PCB 按钮；只有 Simon 确认扩大范围后，才应修改范围策略。新门控可以在扩大范围前复用，以保证新日期仍满足主芯片、真实走线、双视图和响应式约束。

## 7. 待决策

已选择“保留现有普通版，将本试验撤回”。撤回提交、生产部署、自动链路与回滚证据见上述后续审计；本文件只作为七日试验的历史记录保留。
