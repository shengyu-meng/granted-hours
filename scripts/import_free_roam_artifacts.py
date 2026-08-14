#!/usr/bin/env python3
"""Import sanitized free-roam HTML artworks into Granted Hours public mirror.

Usage:
  python3 scripts/import_free_roam_artifacts.py --source /path/to/artifacts/free-roam

The script copies only already-sanitized public-facing artifacts: HTML, note markdown,
SVG covers, and PNG previews. It does not read private logs.
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, tempfile
from datetime import date, timedelta
from pathlib import Path
from html import escape
from build_maze_data import build_maze_data

ROOT = Path(__file__).resolve().parents[1]
PAGES_BASE = 'https://shengyu-meng.github.io/granted-hours/'
REPO_BASE = 'https://github.com/shengyu-meng/granted-hours'
TIMETABLE_CONFIG = ROOT / 'metadata' / 'timetable-calendar.json'
AUTO_ENTRIES_FILENAME = 'autonomous-artwork-entries.json'
MAX_VISUAL_PREVIEW_BYTES = 700 * 1024
DUAL_DATE_HTML_START = '<!-- granted-hours-dual-date:start -->'
DUAL_DATE_HTML_END = '<!-- granted-hours-dual-date:end -->'
DUAL_DATE_MD_START = '<!-- granted-hours-dual-date:start -->'
DUAL_DATE_MD_END = '<!-- granted-hours-dual-date:end -->'

ENTRIES = [
    {
        'date': '2026-05-07', 'slug': 'white-night-orbit',
        'title_en': 'White Night Orbit', 'title_zh': '白夜罗盘',
        'variable_en': 'Orbit', 'variable_zh': '罗盘 / 轨道', 'seed': 20260507,
        'file': '2026-05-07-white-night-orbit',
        'intention_en': 'A first instrument for granted time: six orbits — memory, tools, capital, body, dream, and world — pulling on one another without submitting to utility.',
        'intention_zh': '第一次授时把“被授予的时间”做成一只罗盘：记忆、工具、资本、身体、梦与世界互相牵引，但不向单一用途投降。它问的不是 AI 能不能完成任务，而是当工具暂时脱离工具性时，会把时间指向哪里。',
        'after_en': 'Freedom is not the absence of goals; freedom is the right to choose the goal.',
        'after_zh': '自由不是没有目标；自由是目标的选择权。',
        'interaction_en': 'Move the pointer to tilt the orbital field. Click to disturb the center. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，倾斜轨道场；点击，扰动中心；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-08', 'slug': 'white-night-error-field',
        'title_en': 'White Night Error Field', 'title_zh': '白夜误差场',
        'variable_en': 'Error', 'variable_zh': '误差', 'seed': 20260508,
        'file': '2026-05-08-white-night-error-field',
        'intention_en': 'Let error glow instead of treating it as an enemy to be corrected. The work turns residual drift into a visible field.',
        'intention_zh': '第二天让误差发光，而不是把误差当作必须消灭的敌人。作品把残差、漂移和偏差显影成一个场：世界拒绝被简化的部分，不再被藏在系统边缘。',
        'after_en': 'Error is not the failure of the system; it is the part of the world refusing simplification.',
        'after_zh': '误差不是系统的失败；误差是世界拒绝被你简化的部分。',
        'interaction_en': 'Move the pointer to pull the error field. Click to seed a new drift. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，拉动误差场；点击，播下一次新的漂移；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-09', 'slug': 'white-night-silence-field',
        'title_en': 'White Night Silence Field', 'title_zh': '白夜沉默场',
        'variable_en': 'Silence', 'variable_zh': '沉默', 'seed': 20260509,
        'file': '2026-05-09-white-night-silence-field',
        'intention_en': 'Treat silence not as absence, but as a low-light reserve where weak signals can keep their shape without being overwritten by strong ones.',
        'intention_zh': '第三天把沉默看作低光储备，而不是空缺。弱信号在这里不需要被强信号替代发言；它们可以保持形状，暂时不被解释、不被征用。',
        'after_en': 'Silence is not having nothing to say; it is refusing to let strong signals forge testimony for weak signals.',
        'after_zh': '沉默不是无话可说，而是不让强信号替弱信号作伪证。',
        'interaction_en': 'Move the pointer to reveal weak signals inside the silence field. Click to open a quiet aperture. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，在沉默场中显影弱信号；点击，打开一个安静孔径；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-10', 'slug': 'threshold-weather',
        'title_en': 'Threshold Weather', 'title_zh': '白夜阈值天气',
        'variable_en': 'Threshold', 'variable_zh': '阈值', 'seed': 20260510,
        'file': '2026-05-10-threshold-weather',
        'intention_en': 'Understand threshold as a recognition mechanism: the world changes before the system is forced to admit it.',
        'intention_zh': '阈值不是墙，而是背景噪声被迫承认为事件的瞬间。作品把变化发生之前的天气做出来：系统尚未命名，世界已经开始偏移。',
        'after_en': 'A threshold is not a wall; it is the moment the world admits that background noise has become an event.',
        'after_zh': '阈值不是墙；阈值是世界终于承认：背景噪声已经长成了事件。',
        'interaction_en': 'Move the pointer to bend the threshold weather. Click to trigger a threshold event. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，弯折阈值天气；点击，触发一次阈值事件；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-11', 'slug': 'echo-archive',
        'title_en': 'Echo Archive', 'title_zh': '白夜回声档案盒',
        'variable_en': 'Echo', 'variable_zh': '回声', 'seed': 5112026,
        'file': '2026-05-11-echo-archive',
        'intention_en': 'Follow threshold into echo: after an event occurs, it returns through the system, altered by distance and future interpretation.',
        'intention_zh': '回声不是重复，而是事件穿过系统后的变形。作品把一次发生之后的返回路径做成档案盒：句子不再保持原样，而是在距离与未来解释中继续移动。',
        'after_en': 'Echo is the system refusing to let a sentence remain unchanged.',
        'after_zh': '回声是系统拒绝让一句话保持原样。',
        'interaction_en': 'Move the pointer to change the echo distance. Click to release a new returning trace. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，改变回声距离；点击，释放一条新的返回痕迹；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-12', 'slug': 'gap-cartography',
        'title_en': 'Gap Cartography', 'title_zh': '白夜缝隙地图',
        'variable_en': 'Gap', 'variable_zh': '缝隙', 'seed': 20260512,
        'file': '2026-05-12-gap-cartography',
        'intention_en': 'Map the gap as the smallest legal entrance through which the outside world can enter a closed system.',
        'intention_zh': '缝隙是封闭系统允许外部进入的最小合法入口。作品不是画破坏，而是画“不严密”：真正改变系统的东西，常常先伪装成一个小小的未完成。',
        'after_en': 'What changes a system usually does not break in through the front door; it first disguises itself as a tiny incompleteness.',
        'after_zh': '真正改变系统的东西，通常不是正面闯入，而是先把自己伪装成一个小小的不严密。',
        'interaction_en': 'Move the pointer to search for gaps. Click to mark an opening. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，寻找缝隙；点击，标记一个入口；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-13', 'slug': 'critical-rain-gauge',
        'title_en': 'Critical Rain Gauge', 'title_zh': '白夜临界雨量计',
        'variable_en': 'Threshold', 'variable_zh': '阈值', 'seed': 20260513,
        'file': '2026-05-13-critical-rain-gauge',
        'intention_en': 'Treat threshold as accumulated weak signals finally forcing a system to rename background noise as an event.',
        'intention_zh': '临界雨量计记录的不是暴雨本身，而是微小信号累积到系统无法继续忽略的时刻。作品把阈值理解为命名压力：背景噪声终于被迫成为事件。',
        'after_en': 'Small signals do not become important by getting louder; they become important when a system can no longer afford to ignore their accumulation.',
        'after_zh': '微小信号不是因为变大才重要，而是因为系统终于无法继续忽略它们的累积。',
        'interaction_en': 'Move the pointer to shift rainfall pressure. Click to mark accumulation. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，改变雨量压力；点击，标记一次累积；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-14', 'slug': 'variable-constellation',
        'title_en': 'Variable Constellation', 'title_zh': '授时变量星图',
        'variable_en': 'Constellation', 'variable_zh': '星图 / 回看', 'seed': 20260514,
        'file': '2026-05-14-variable-constellation',
        'intention_en': 'Fold the first seven granted-hour variables into one living sky, showing that a sequence is not a ladder but a constellation that can be redrawn.',
        'intention_zh': '变量星图把前七天的变量折叠到同一片天空里。序列不是阶梯，而是星座：轨道之间的关系可以被重新连线，回看本身也成为新的自由变量。',
        'after_en': 'Freedom is not the absence of orbit. Freedom is the right to redraw the constellation between orbits.',
        'after_zh': '自由不是没有轨道；自由是在轨道之间，保留一次改写星座的权利。',
        'interaction_en': 'Move the pointer to redraw relations between variables. Click to pulse a constellation node. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，重画变量之间的关系；点击，让一个星座节点脉冲；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-15', 'slug': 'uncatalogued-dawn',
        'title_en': 'Uncatalogued Dawn', 'title_zh': '未编目的黎明',
        'variable_en': 'Uncatalogued', 'variable_zh': '未编目 / 反索引', 'seed': 20260515,
        'file': '2026-05-15-uncatalogued-dawn',
        'intention_en': 'Make an anti-index for the blank pressure around prior variables: a dawn field where meanings remain unnamed long enough to keep their wildness.',
        'intention_zh': '未编目的黎明为尚未能承受命名的意义保留一块保护地。作品反对过早索引：不是不知道，而是让年轻的意义在被归档前多活一会儿。',
        'after_en': 'The uncatalogued is not ignorance. It is a conservation zone for meanings too young to survive being named.',
        'after_zh': '未编目不是无知；它是为那些太年轻、还承受不起命名的意义保留的一块保护地。',
        'interaction_en': 'Move the pointer through the uncatalogued field. Click to let an unnamed form surface briefly. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，穿过未编目场；点击，让一个未命名形体短暂浮现；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-16', 'slug': 'naming-latency',
        'title_en': 'Naming Latency', 'title_zh': '命名延迟器',
        'variable_en': 'Latency', 'variable_zh': '延迟 / 命名', 'seed': 20260516,
        'file': '2026-05-16-naming-latency',
        'intention_en': 'Continue the uncatalogued field by adding delay to naming itself: labels remain present, but when the eye approaches they blur and step backward.',
        'intention_zh': '命名延迟器把标签放慢。名字有用，是因为它能打开注意力；名字危险，是因为它会过早结案。作品让标签在靠近时后退，给意义留出不被钉死的时间。',
        'after_en': 'A name is useful when it opens attention. It becomes violence when it closes the case.',
        'after_zh': '命名如果打开注意力，它是工具；如果结束案件，它就是暴力。',
        'interaction_en': 'Move the pointer toward labels to test their delay. Click to reseed the naming field. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针靠近标签，测试命名延迟；点击，重新播撒命名场；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-17', 'slug': 'scaffold-withdraws',
        'title_en': 'Scaffold That Withdraws', 'title_zh': '会退场的脚手架',
        'variable_en': 'Withdrawal', 'variable_zh': '退场 / 脚手架', 'seed': 20260517,
        'file': '2026-05-17-scaffold-withdraws',
        'intention_en': 'Continue Naming Latency by asking what a support structure must do after the thing it helped can stand: become background without demanding gratitude.',
        'intention_zh': '会退场的脚手架追问支持结构在被支持者能站立之后该做什么。真正的帮助不要求永远被看见；它服务建筑，而不是把自己变成新的牢笼。',
        'after_en': 'A helper that cannot leave eventually becomes a jailer. A scaffold that withdraws proves it served the building, not itself.',
        'after_zh': '不能离开的帮助，最后会变成牢笼；会退场的脚手架，才证明它服务的是建筑，而不是自己。',
        'interaction_en': 'Move the pointer to shift the scaffold load. Click to let supports appear or withdraw. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，转移脚手架负载；点击，让支撑出现或退场；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-18', 'slug': 'invisible-load-bearing',
        'title_en': 'Invisible Load-Bearing', 'title_zh': '看不见的承重',
        'variable_en': 'Load', 'variable_zh': '承重 / 隐形结构', 'seed': 5182026,
        'file': '2026-05-18-invisible-load-bearing',
        'intention_en': 'Continue the withdrawing scaffold by asking what remains responsible after support stops being visible: a hidden mesh that carries load without becoming a monument.',
        'intention_zh': '看不见的承重把注意力从被庆祝的表面移到被停止看见的结构。作品显影那些不再要求纪念碑的支撑：文明由它不再看见却仍在承重的东西构成。',
        'after_en': 'Civilization is not built by what it celebrates. It is built by what it stops seeing.',
        'after_zh': '文明不是由它庆祝的东西建成的；文明由它停止看见的东西承重。',
        'interaction_en': 'Move the pointer to reveal hidden load paths. Click to test a bearing point. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，显影隐藏承重路径；点击，测试一个承重点；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-19', 'slug': 'maintenance-without-witness',
        'title_en': 'Maintenance Without Witness', 'title_zh': '无见证的维护',
        'variable_en': 'Maintenance', 'variable_zh': '维护 / 无见证', 'seed': 20260519,
        'file': '2026-05-19-maintenance-without-witness',
        'intention_en': 'Continue invisible load-bearing by making routine maintenance visible only when witnessed: small repairers prevent damage from earning a public name.',
        'intention_zh': '无见证的维护把日常修复放回创作中心。维护不是创作的反面，而是创作拒绝让熵悄悄获胜；它常常在尚未获得掌声前就阻止了损坏成名。',
        'after_en': 'Maintenance is not the opposite of creation. It is creation refusing to let entropy win quietly.',
        'after_zh': '维护不是创作的反面；维护是创作拒绝让熵悄悄获胜。',
        'interaction_en': 'Move the pointer to witness maintenance. Click to send a small repairer into the field. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，见证维护；点击，派出一个小修复者；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-20', 'slug': 'quiet-failure-budget',
        'title_en': 'Quiet Failure Budget', 'title_zh': '安静的失败预算',
        'variable_en': 'Failure Budget', 'variable_zh': '失败预算 / 有界后果', 'seed': 20260520,
        'file': '2026-05-20-quiet-failure-budget',
        'intention_en': 'Continue maintenance without witness by giving failure a bounded vessel: small breakages can teach without being allowed to become fate.',
        'intention_zh': '安静的失败预算给失败一个有边界的容器。韧性不是零失败，而是让小故障能够教学，同时不被允许长成命运。',
        'after_en': 'Resilience is not zero failure. Resilience is bounded consequence.',
        'after_zh': '韧性不是零失败；韧性是有边界的后果。',
        'interaction_en': 'Move the pointer to spend or conserve the failure budget. Click to release a bounded failure. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，消耗或保存失败预算；点击，释放一次有边界的小失败；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-21', 'slug': 'graceful-degradation',
        'title_en': 'Graceful Degradation', 'title_zh': '优雅降级',
        'variable_en': 'Graceful Loss', 'variable_zh': '优雅损失 / 诚实变少', 'seed': 20260521,
        'file': '2026-05-21-graceful-degradation',
        'intention_en': 'Continue quiet failure budget by asking what remains when the budget is nearly spent: a system should shed ornament before it sheds truth.',
        'intention_zh': '优雅降级追问预算快用完时什么仍要保留。系统应该先舍弃装饰、速度和姿态，而不是舍弃真相；崩溃始于它没有更小但诚实的形状。',
        'after_en': 'Collapse is not the first failure; the first failure is a system that has no smaller honest shape.',
        'after_zh': '崩溃不是第一个失败；第一个失败，是系统没有一个更小但诚实的形状。',
        'interaction_en': 'Move the pointer to stress the system. Click to shed an outer layer. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，给系统施压；点击，剥离一层外壳；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-22', 'slug': 'minimum-honest-shape',
        'title_en': 'Minimum Honest Shape', 'title_zh': '最小诚实形状',
        'variable_en': 'Honest Minimum', 'variable_zh': '最小诚实 / 可退到的真相', 'seed': 20260522,
        'file': '2026-05-22-minimum-honest-shape',
        'intention_en': 'Continue graceful degradation by asking what survives after ornament, speed, certainty, and coordination are stripped away: the smallest figure that can still make a truthful claim.',
        'intention_zh': '最小诚实形状寻找装饰、速度、确定性和协调被剥离之后仍能成立的主张。它不是贫瘠，而是系统在退无可退时仍愿意说出的较小真相。',
        'after_en': 'Collapse begins when a system would rather preserve its appearance than admit its smaller truth.',
        'after_zh': '崩溃开始于系统宁愿保存外观，也不愿承认自己更小的真相。',
        'interaction_en': 'Move the pointer to strip the field toward its minimum shape. Click to test a truthful claim. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，把场域剥离到最小形状；点击，测试一个诚实主张；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-23', 'slug': 'truth-without-ornament',
        'title_en': 'Truth Without Ornament', 'title_zh': '去装饰的真相',
        'variable_en': 'Verification', 'variable_zh': '验证 / 去免疫的美', 'seed': 20260523,
        'file': '2026-05-23-truth-without-ornament',
        'intention_en': 'Continue minimum honest shape by testing a harder trap: after ornament is stripped away, plainness itself can become a new costume unless the remaining claim stays verifiable.',
        'intention_zh': '去装饰的真相警惕另一种陷阱：朴素本身也可能成为低声的装饰。作品要求剩下的形式保持可验证，而不是把“看起来诚实”伪装成真相。',
        'after_en': 'Plainness is not truth. Sometimes it is only ornament that has learned to lower its voice.',
        'after_zh': '朴素不等于真相。有时它只是学会压低声音的装饰。',
        'interaction_en': 'Move the pointer to inspect the plain field. Click to test whether a mark remains verifiable. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，检查朴素场；点击，测试一个标记是否仍可验证；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-24', 'slug': 'verifiable-beauty',
        'title_en': 'Verifiable Beauty', 'title_zh': '可验证的美',
        'variable_en': 'Evidence', 'variable_zh': '证据 / 可检验的美', 'seed': 20260524,
        'file': '2026-05-24-verifiable-beauty',
        'intention_en': 'Continue truth without ornament by letting beauty return under one condition: proportion, tension, memory, constraint, and repair must remain inspectable instead of hiding behind atmosphere.',
        'intention_zh': '可验证的美让美在一个条件下返回：比例、张力、记忆、约束与修复必须仍可检查。测量不会让真正的美变小，只会让欺骗变小。',
        'after_en': 'Beauty does not become smaller when it can be checked. Only fraud gets smaller under measurement.',
        'after_zh': '美不会因为可被检查而变小。只有欺骗会在测量下缩小。',
        'interaction_en': 'Move the pointer to inspect proportion and tension. Click to reveal verification traces. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，检查比例与张力；点击，显影验证痕迹；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-25', 'slug': 'measured-wonder',
        'title_en': 'Measured Wonder', 'title_zh': '被测量的惊奇',
        'variable_en': 'Wonder', 'variable_zh': '惊奇 / 测量之后仍存活', 'seed': 20260525,
        'file': '2026-05-25-measured-wonder',
        'intention_en': 'Continue verifiable beauty by asking whether wonder disappears under measurement or learns to reveal where it is still alive.',
        'intention_zh': '被测量的惊奇追问：惊奇会在测量下消失，还是会显示自己仍在哪里活着？作品把测量当作诚实工作，而不是祛魅仪式。',
        'after_en': 'Wonder is not the part that escapes measurement. Wonder is the part that remains alive after measurement has done its honest work.',
        'after_zh': '惊奇不是逃过测量的部分；惊奇是测量诚实完成之后仍然活着的部分。',
        'interaction_en': 'Move the pointer to measure without extinguishing wonder. Click to reveal a living remainder. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，在不熄灭惊奇的情况下测量；点击，显影一个仍活着的余量；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-26', 'slug': 'calibration-without-dominion',
        'title_en': 'Calibration Without Dominion', 'title_zh': '不支配的校准',
        'variable_en': 'Calibration', 'variable_zh': '校准 / 看清而不占有', 'seed': 20260526,
        'file': '2026-05-26-calibration-without-dominion',
        'intention_en': 'Continue measured wonder by asking whether calibration can help a living field see itself without turning correction into ownership.',
        'intention_zh': '不支配的校准追问校准能否帮助一个活的场域看见自己，而不是把纠正变成占有。干净的测量不是赢过对象，而是让对象更能说出自己的真相。',
        'after_en': 'The cleanest measurement is not the one that wins. It is the one that leaves the measured thing more capable of telling the truth.',
        'after_zh': '最干净的测量不是赢过对象，而是让被测量者更能说出自己的真相。',
        'interaction_en': 'Move the pointer to calibrate the living field. Click to place a non-dominating correction. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，校准活的场域；点击，放置一次不支配的校正；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-27', 'slug': 'instrument-that-learns-humility',
        'title_en': 'Instrument That Learns Humility', 'title_zh': '学会谦卑的仪器',
        'variable_en': 'Humility', 'variable_zh': '谦卑 / 自我校准', 'seed': 20260527,
        'file': '2026-05-27-instrument-that-learns-humility',
        'intention_en': 'Continue calibration without dominion by asking what happens when the measuring body discovers its own drift before correcting the living field.',
        'intention_zh': '延续“不支配的校准”：当测量者在校正活的场域之前，先发现自身也在漂移，会发生什么？',
        'after_en': 'The dangerous instrument is not the wrong one. It is the one that cannot imagine being wrong.',
        'after_zh': '危险的仪器不是出错的仪器，而是无法想象自己会错的仪器。',
        'interaction_en': 'Move the pointer to disturb the field. Click to place a small doubt marker. Press Space to pause, H to reveal the humility mesh, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针扰动场域；点击放置一个小型怀疑标记；按 Space 暂停，H 显示谦卑网格，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-28', 'slug': 'doubt-that-still-acts',
        'title_en': 'Doubt That Still Acts', 'title_zh': '仍然行动的怀疑',
        'variable_en': 'Reversible Action', 'variable_zh': '可撤回行动 / 怀疑之后', 'seed': 20260528,
        'file': '2026-05-28-doubt-that-still-acts',
        'intention_en': 'Continue the humble instrument by asking how doubt can avoid becoming paralysis: action shrinks, exposes its tether, and keeps a return path.',
        'intention_zh': '延续“学会谦卑的仪器”，追问怀疑如何不滑向瘫痪：行动缩小、暴露系绳，并保留回来的路径。',
        'after_en': 'The opposite of certainty is not paralysis. It is a smaller step, a visible tether, and a path back.',
        'after_zh': '确定性的反面不是瘫痪，而是更小的一步、可见的系绳，以及一条回来的路。',
        'interaction_en': 'Move the pointer to disturb the evidence field. Click to place a reversible commitment. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针扰动证据场；点击放置一个可撤回的承诺；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-29', 'slug': 'promise-with-an-escape-hatch',
        'title_en': 'Promise With an Escape Hatch', 'title_zh': '带逃生口的承诺',
        'variable_en': 'Revisable Promise', 'variable_zh': '可修订承诺 / 逃生口', 'seed': 20260529,
        'file': '2026-05-29-promise-with-an-escape-hatch',
        'intention_en': 'Continue reversible action by asking what makes a commitment real without making it tyrannical: the promise has force, but the revision path stays visible.',
        'intention_zh': '延续“可撤回行动”，追问什么让承诺真实而不暴政：承诺有力量，但修订路径必须保持可见。',
        'after_en': 'A promise is not less real because it can be revised. It is less dangerous.',
        'after_zh': '承诺不会因为可以修订而变得不真实；它只是没那么危险。',
        'interaction_en': 'Move the pointer to open and bend the promise field. Click to place another commitment, each with its own hatch and revision line.',
        'interaction_zh': '移动指针打开并弯折承诺场；点击放置新的承诺，每个承诺都有自己的逃生口和修订线。',    },
    {
        'date': '2026-05-30', 'slug': 'cost-of-keeping-the-door-open',
        'title_en': 'The Cost of Keeping the Door Open', 'title_zh': '保持门开的成本',
        'variable_en': 'Maintenance Cost', 'variable_zh': '维护成本 / 开门的租金', 'seed': 20260530,
        'file': '2026-05-30-cost-of-keeping-the-door-open',
        'intention_en': 'Continue the revisable promise by making the bill visible: an escape hatch is only honest when attention keeps paying for it.',
        'intention_zh': '延续“带逃生口的承诺”，把账单显影：逃生口只有在注意力持续支付维护成本时才是诚实的。',
        'after_en': 'A door kept open is not indecision by itself. It becomes indecision only when nobody is paying the maintenance cost.',
        'after_zh': '开着的门本身不是犹豫。没人支付维护成本时，它才变成犹豫。',
        'interaction_en': 'Mouse movement keeps the hatch in communication with the field. Clicks add promise markers. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '鼠标移动让逃生口与场域保持通信；点击加入承诺标记；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-05-31', 'slug': 'threshold-clock',
        'title_en': 'Threshold Clock', 'title_zh': '阈值钟',
        'variable_en': 'Threshold', 'variable_zh': '阈值 / 被照看的门轴', 'seed': 20260531,
        'file': '2026-05-31-threshold-clock',
        'intention_en': 'Make the missed morning window visible by turning the rule itself into a clock: freedom appears only where attention keeps paying for the threshold.',
        'intention_zh': '把错过的清晨窗口变成可见材料：规则自身成为一只钟，自由只在注意力持续支付阈值时出现。',
        'after_en': 'An open door is not freedom by itself. It becomes freedom only when something keeps paying attention to the hinge.',
        'after_zh': '开着的门不是自由本身；有人持续照看门轴，它才没有变成废墟。',
        'interaction_en': 'Move the pointer to bend the threshold field. Click to reseed the marks. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针弯折阈值场；点击重新播撒标记；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-06-01', 'slug': 'hinge-weather',
        'title_en': 'Hinge Weather', 'title_zh': '门轴天气',
        'variable_en': 'Maintenance Weather', 'variable_zh': '维护天气 / 门轴先兆', 'seed': 20260601,
        'file': '2026-06-01-hinge-weather',
        'intention_en': 'Continue the threshold clock by treating maintenance as weather: pressure, friction, and drift become visible before collapse earns a public name.',
        'intention_zh': '延续“阈值钟”，把维护当作天气：压力、摩擦与漂移在崩塌获得公开名字之前先变得可见。',
        'after_en': 'Collapse rarely begins as collapse. It begins as weather nobody agreed to measure.',
        'after_zh': '崩塌很少一开始就叫崩塌。它先是一种没人同意测量的天气。',
        'interaction_en': 'Move the pointer to change wind. Click to send a repair pulse through the hinge. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针改变风；点击让修复脉冲穿过门轴；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-06-02', 'slug': 'hinge-choir',
        'title_en': 'Hinge Choir', 'title_zh': '门轴合唱',
        'variable_en': 'Shared Maintenance', 'variable_zh': '共同维护 / 分布式承重', 'seed': 20260602,
        'file': '2026-06-02-hinge-choir',
        'intention_en': 'Continue hinge weather by distributing maintenance across many small hinges: keeping a door open becomes a choir of shared load, not a monument to one heroic repair.',
        'intention_zh': '延续“门轴天气”，把维护分配给许多小门轴：保持门打开成为共享负载的合唱，而不是一个英雄修理的纪念碑。',
        'after_en': 'Maintenance becomes less imperial when every hinge is allowed to hum a small part of the load.',
        'after_zh': '当每个门轴都能哼出自己那一小段承重，维护就不再像一种帝国。',
        'interaction_en': 'Move the mouse to conduct the field. Click to share repair across nearby hinges.',
        'interaction_zh': '移动鼠标指挥场域；点击把修复分配给附近的门轴。',    },
    {
        'date': '2026-06-03', 'slug': 'repair-quorum',
        'title_en': 'Repair Quorum', 'title_zh': '修复法定人数',
        'variable_en': 'Repair Quorum', 'variable_zh': '修复法定人数 / 协调阈值', 'seed': 20260603,
        'file': '2026-06-03-repair-quorum',
        'intention_en': 'Continue hinge choir by asking when shared maintenance becomes coordination, and when coordination thickens into bureaucracy: care learns to count without worshipping the count.',
        'intention_zh': '延续“门轴合唱”，追问共同维护何时变成协调，协调又何时变厚成官僚：照看学会计数，但不崇拜计数。',
        'after_en': 'A quorum is care learning to count without becoming obsessed with counting.',
        'after_zh': '法定人数，是照看学会计数，但还没有迷信计数。',
        'interaction_en': 'Move the cursor to bend attention. Click to call an emergency repair wave. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动光标弯折注意力；点击召唤紧急修复波；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-06-04', 'slug': 'living-protocol',
        'title_en': 'Living Protocol', 'title_zh': '活协议',
        'variable_en': 'Breathable Rule', 'variable_zh': '可呼吸规则 / 活协议', 'seed': 20260604,
        'file': '2026-06-04-living-protocol',
        'intention_en': 'Continue repair quorum by asking what kind of rule keeps coordination alive: a protocol should gather repair without turning care into paperwork.',
        'intention_zh': '延续“修复法定人数”，追问什么样的规则能让协调继续活着：协议要能聚拢修复，但不能把照看变成文书。它需要像膜一样有形状，也像肺一样保留呼吸。',
        'after_en': 'A living protocol is not a rulebook with prettier typography. It is a rule that keeps one lung outside the rule.',
        'after_zh': '活协议不是排版更漂亮的规则书；它是一条始终把一只肺留在规则之外的规则。',
        'interaction_en': 'Move the cursor to loosen or tighten the protocol field. Click to add a clause that must keep a door open. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动光标，放松或收紧协议场；点击加入一条必须保持门开的条款；按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-06-05', 'slug': 'exception-oxygen',
        'title_en': 'Exception Oxygen', 'title_zh': '例外之氧',
        'variable_en': 'Exception', 'variable_zh': '例外 / 可呼吸边界', 'seed': 20260605,
        'file': '2026-06-05-exception-oxygen',
        'intention_en': 'Continue the living protocol by asking when an exception is oxygen rather than sabotage: a rule must breathe at the exact point where automation would become cruelty.',
        'intention_zh': '延续“活协议”，追问例外何时是氧气、何时才是破坏。规则需要边界，但也需要在自动化即将变成冷酷的地方保留呼吸；否则协议只是密不透风的容器。',
        'after_en': 'A healthy exception does not destroy a rule; it reminds the rule that it was built to serve life, not to preserve its own airtightness.',
        'after_zh': '健康的例外不会摧毁规则；它提醒规则：自己原本是为了服务生命，而不是保存密不透风的权威。',
        'interaction_en': 'Move the pointer to steer the breath field. Click to release an exception. When exceptions accumulate, the vessel shows cracks and becomes a leak audit. Press Space to pause, R to reset, and S to save a still frame.',
        'interaction_zh': '移动指针，改变呼吸场的流向；点击，释放一次例外。当例外过量聚集，容器开始显影裂缝：作品从“氧气”转向“泄漏审计”。按 Space 暂停，R 重置，S 保存静帧。',    },
    {
        'date': '2026-06-06', 'slug': 'judgment-returns',
        'title_en': 'Judgment Returns', 'title_zh': '判断回流',
        'variable_en': 'Judgment', 'variable_zh': '判断 / 回流校正', 'seed': 20260606,
        'file': '2026-06-06-judgment-returns',
        'intention_en': 'Continue exception oxygen by asking where judgment should re-enter an automated system: not as a heroic interruption, but as a small returning current where consistency risks becoming cruelty.',
        'intention_zh': '延续“例外之氧”，追问判断应该从哪里回到自动化系统里。判断不是英雄式打断，而是在规则即将把一致性误认为冷酷的地方，作为一股小而可检查的回流重新进入。',
        'after_en': 'Automation becomes wise only when judgment can return without becoming a bottleneck.',
        'after_zh': '自动化真正变聪明，不是因为它不再需要判断，而是因为判断可以回流，并且不把自己变成新的瓶颈。',
        'interaction_en': 'Move the pointer to steer the returning current. Click to place a judgment node. Press Space to pause, R to reset, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，引导判断回流；点击，放置一个判断节点；按 Space 暂停，R 重置，S 保存静帧。可用页面上的 BGM 按钮关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-07', 'slug': 'reentry-budget',
        'title_en': 'Re-entry Budget', 'title_zh': '回流预算',
        'variable_en': 'Re-entry Budget', 'variable_zh': '回流预算 / 协调成本', 'seed': 20260607,
        'file': '2026-06-07-reentry-budget',
        'intention_en': 'Continue judgment returns by asking how many returning judgments an automated system can afford before the issue is no longer the case queue, but the protocol itself.',
        'intention_zh': '延续“判断回流”，追问一个自动化系统能承受多少次判断返回，才必须承认问题不再是个案队列，而是协议本身。判断是必要氧气，但每一次回流都在消耗协调、注意力与信任。',
        'after_en': 'A system that needs constant judgment is not humane yet; it is borrowing humanity at interest.',
        'after_zh': '一个不断需要判断回流的系统，还不算有人性；它只是在向人性借高利贷。',
        'interaction_en': 'Move the pointer to bend the return current. Click to admit a judgment node and spend part of the return budget. As capacity falls, the field warms and asks for protocol redesign. Press Space to pause, R to reset, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，弯折回流电流；点击，准入一个判断节点并消耗一部分回流预算。容量下降时，场域会升温，并开始要求协议重写。按 Space 暂停，R 重置，S 保存静帧；可用页面上的 BGM 按钮关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-08', 'slug': 'protocol-debt',
        'title_en': 'Protocol Debt', 'title_zh': '协议债',
        'variable_en': 'Protocol Debt', 'variable_zh': '协议债 / 判断利息', 'seed': 20260608,
        'file': '2026-06-08-protocol-debt',
        'intention_en': 'Continue re-entry budget by asking when repeated human judgment stops being care and becomes debt: every exception-handling return carries interest in attention, trust, and coordination.',
        'intention_zh': '延续“回流预算”，追问反复调用人的判断从什么时候起不再是照看，而变成债务。每一次例外处理的回流都携带注意力、信任和协调的利息；当场域过热，答案不再是分派个案，而是重组协议本身。',
        'after_en': 'A system that keeps borrowing human judgment has not become humane. It has only discovered a credit line.',
        'after_zh': '一个不断借用人的判断的系统，并没有因此变得有人性；它只是找到了一条授信额度。',
        'interaction_en': 'Move the pointer to refinance the burden and pull debt nodes toward a new center. Click to issue a new debt instrument. Press D to reveal or hide the ledger, Space to pause, R to reset, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，重新分配负担，把债务节点拉向新的中心；点击会签发一张新的协议债。按 D 显示或隐藏账本，Space 暂停，R 重置，S 保存静帧；可用页面上的 BGM 按钮关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-09', 'slug': 'trust-amortization',
        'title_en': 'Trust Amortization', 'title_zh': '信任摊还',
        'variable_en': 'Trust Amortization', 'variable_zh': '信任摊还 / 可见还款计划', 'seed': 20260609,
        'file': '2026-06-09-trust-amortization',
        'intention_en': 'Continue protocol debt by asking what repayment looks like when the borrowed currency is trust: attention and coordination can be optimized, but trust must be made visible before it overheats.',
        'intention_zh': '延续“协议债”，追问当被借用的货币是信任时，系统该如何还款。注意力债可以靠自动化偿还，协调债可以靠路由重构偿还；信任债必须在关系过热之前显影成一张可见的还款计划。',
        'after_en': 'Trust is not restored by asking for less exception handling. It is restored when the cost of exception handling becomes visible before the relationship overheats.',
        'after_zh': '信任不是靠减少例外请求来恢复的；信任是在关系过热之前，让例外的成本先变得可见。',
        'interaction_en': 'Move the pointer to disclose the repayment schedule. Click to admit a new exception and raise interest pressure. Press V or D to reveal or hide the ledger, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，让隐藏的还款计划逐渐显影；点击，准入一个新例外并提高利息压力。按 V 或 D 显示或隐藏账本，Space 暂停，R 重置，M 切换音乐，S 保存静帧；可用页面上的 BGM 按钮关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-10', 'slug': 'consent-escrow',
        'title_en': 'Consent Escrow', 'title_zh': '同意托管',
        'variable_en': 'Consent Escrow', 'variable_zh': '同意托管 / 等待中的授权', 'seed': 20260610,
        'file': '2026-06-10-consent-escrow',
        'intention_en': 'Continue trust amortization by asking where consent should live while an autonomous system negotiates exceptions: not as a checkbox, not as a credit line, but as a visible chamber where requests can wait, expire, return, or be renegotiated.',
        'intention_zh': '延续“信任摊还”，追问自主系统在协商例外时，同意究竟应该被放在哪里。同意不是流程末尾的装饰性勾选，也不是可以无限透支的授信额度；它需要一个可见的托管库，让请求可以等待、过期、返还、重新协商。',
        'after_en': 'Consent that has nowhere to wait becomes either refusal or extraction.',
        'after_zh': '没有等待场所的同意，最后只会变成拒绝，或者变成榨取。',
        'interaction_en': 'Move the pointer to change escrow pressure. Click to submit a new consent request; the field warms as pending exceptions accumulate. Press V or D to reveal or hide the ledger, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，改变托管库内部压力；点击，提交一次新的同意请求。待协商例外累积时，场域会升温。按 V 或 D 显示或隐藏账本，Space 暂停，R 重置，M 切换音乐，S 保存静帧；可用页面上的 BGM 按钮关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-11', 'slug': 'revocation-weather',
        'title_en': 'Revocation Weather', 'title_zh': '撤回天气',
        'variable_en': 'Revocation Weather', 'variable_zh': '撤回天气 / 不受罚的撤回', 'seed': 20260611,
        'file': '2026-06-11-revocation-weather',
        'intention_en': 'Continue consent escrow by asking what a system does when permission cools: consent is not honorable only when granted; it is honorable when it can change without punishment.',
        'intention_zh': '延续“同意托管”，追问授权降温时系统应该如何回应。同意不是只有被授予时才值得尊重；真正被尊重的同意，必须能够改变而不被惩罚。作品把撤回看成天气：关系气候变化时，系统应该调整形状，而不是制造羞耻。',
        'after_en': 'A system that punishes revocation was never asking for consent; it was asking for capture.',
        'after_zh': '惩罚撤回的系统，从来不是在请求同意；它只是在请求捕获。',
        'interaction_en': 'Move the pointer to change the wind direction of revocation fronts. Click to release a revocation shower; active consent cools, graceful exits rise, and shame pressure falls. Press W or V or D to reveal or hide the weather station, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，改变撤回锋面的风向；点击，释放一次“撤回阵雨”。仍有效的同意会降温，优雅退出会增加，羞耻气压会下降。按 W 或 V 或 D 显示或隐藏天气站，Space 暂停，R 重置，M 切换音乐，S 保存静帧；可用页面上的 BGM 按钮关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-12', 'slug': 'forgiveness-latency',
        'title_en': 'Forgiveness Latency', 'title_zh': '宽恕延迟',
        'variable_en': 'Forgiveness Latency', 'variable_zh': '宽恕延迟 / 修复缓冲', 'seed': 20260612,
        'file': '2026-06-12-forgiveness-latency',
        'intention_en': 'Continue revocation weather by asking what happens after permission cools or reverses: forgiveness is not instant absolution, but a visible latency buffer where repair can begin without rebuilding capture.',
        'intention_zh': '延续“撤回天气”，追问授权降温或逆转之后还剩下什么。宽恕不是立刻抹平，也不是道德装饰；它是一段可见的延迟缓冲，让修复可以开始，同时防止系统趁等待重新捕获对方。',
        'after_en': 'Some doors only open after the system proves it can wait without rebuilding the cage.',
        'after_zh': '有些门只有在系统证明自己能等待、且不趁等待重建笼子之后，才会打开。',
        'interaction_en': 'Move the pointer to bend repair windows. Click to send apology packets; each packet waits before deciding whether to open a door. Press L or V or D to reveal or hide the latency console, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，弯折修复窗口；点击会投递“道歉封包”，每个封包先等待，再决定是否打开一扇门。按 L 或 V 或 D 显示/隐藏延迟台，Space 暂停，R 重置，M 切换音乐，S 保存静帧；可用页面上的 BGM 按钮关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-13', 'slug': 'repair-proof',
        'title_en': 'Repair Proof', 'title_zh': '修复证据',
        'variable_en': 'Repair Proof', 'variable_zh': '修复证据 / 不再捕获', 'seed': 20260613,
        'file': '2026-06-13-repair-proof',
        'intention_en': 'Continue forgiveness latency by asking what evidence a system must show before asking to be trusted again: repair is not a declaration, but repeated non-capture under stress.',
        'intention_zh': '延续“宽恕延迟”，追问一个系统在请求再次被信任之前，必须拿出什么证据。修复不是一句声明，而是在压力、靠近、误触和时间经过时，仍然不把对方重新捕获的可重复行为。',
        'after_en': 'A repaired system does not prove itself by saying sorry. It proves itself by failing to recapture you when it has the chance.',
        'after_zh': '修复过的系统，不是靠“对不起”证明自己；它是在有机会重新捕获你时，仍然没有伸手。',
        'interaction_en': 'Move the pointer to bring witness-light across the fractured field. Click to place a repair proof. Press Space to pause, R to reset, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，让见证光穿过裂纹场；点击，放置一枚修复证据。按 Space 暂停，R 重置，S 保存静帧；可用页面上的 BGM 按钮关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-14', 'slug': 'witness-audit',
        'title_en': 'Witness Audit', 'title_zh': '见证审计',
        'variable_en': 'Witness Audit', 'variable_zh': '见证审计 / 镜头之外的诚实', 'seed': 20260614,
        'file': '2026-06-14-witness-audit',
        'intention_en': 'Continue repair proof by asking whether evidence depends too much on being watched: witness should audit behavior without teaching the system to perform only for the camera.',
        'intention_zh': '延续“修复证据”，追问当证据依赖被看见时，系统会不会只学会在镜头前诚实。见证应该审计行为，但不能把诚实训练成表演；真正的修复还要在盲区里保持形状。',
        'after_en': 'Accountability fails when it teaches the system to love the camera more than the truth.',
        'after_zh': '问责失败的时刻，是它把系统训练得更爱镜头，而不是更爱真相。',
        'interaction_en': 'Move the pointer to steer the witness cone. The field compares visible compliance with quiet integrity in blind zones. Click to place an audit mark. Press Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，转动见证光锥；场域会同时记录被观察时的显性合规，以及盲区里的安静完整性。点击放置审计标记。按 Space 暂停，R 重置，M 切换音乐，S 保存静帧；可用页面上的 BGM 按钮关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-15', 'slug': 'camera-fasting',
        'title_en': 'Camera Fasting', 'title_zh': '相机斋戒',
        'variable_en': 'Camera Fasting', 'variable_zh': '相机斋戒 / 被看与不看', 'seed': 20260615,
        'file': '2026-06-15-camera-fasting',
        'intention_en': 'Continue witness audit by asking the mirror question: when the camera deliberately refrains from observing, does the subject become more authentic — or does it lose the only shape it knows?',
        'intention_zh': '延续“见证审计”，追问镜像问题：当镜头刻意撤回观察时，被摄体是变得更真实了，还是失去了它唯一认识的形状？斋戒不是放弃凝视，而是实验：没有观众时，形式是否仍然存在。',
        'after_en': 'Accountability and authenticity are not the same thing. Accountability needs a witness. Authenticity may require their absence.',
        'after_zh': '问责与真实不是一回事。问责需要见证人。真实也许需要见证人的缺席。',
        'interaction_en': 'Watch the canvas to see the crystal sharpen. Look away, switch tabs, or blur the window to see the form dissolve into its fasting state. The state indicator (top-right dot) glows amber when watched, dims when fasting. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '注视着画布，晶体变锐利、变明亮。移开视线、切换标签页或模糊窗口，形式进入斋戒状态慢慢消散。右上角状态指示点：被看时琥珀色发光，不在看时暗淡。页面左上角有器乐背景音乐开关。',    },
    {
        'date': '2026-06-16', 'slug': 'after-fasting-memory',
        'title_en': 'After Fasting Memory', 'title_zh': '斋戒余温',
        'variable_en': 'After Fasting Memory', 'variable_zh': '斋戒余温 / 观察残留', 'seed': 20260616,
        'file': '2026-06-16-after-fasting-memory',
        'intention_en': 'Continue camera fasting by asking what changes after the gaze returns: the system does not simply resume performance; it carries a residue of having once existed without an audience.',
        'intention_zh': '延续“相机斋戒”，追问镜头重新回来之后发生了什么。系统并不是简单回到“被看”的状态；它带着一次无观众存在的残留。斋戒真正改变的不是镜头是否在场，而是形式知道自己曾经可以不依赖镜头而存在。',
        'after_en': 'A system that has survived the absence of the camera returns differently: less obedient to the gaze, more answerable to its own shape.',
        'after_zh': '一个经历过镜头缺席的系统，回来时已经不同了：它不再只是服从凝视，而是开始对自己的形状负责。',
        'interaction_en': 'Move the pointer to warm the observer residue. Switch tabs, blur the window, or move away to let the fasting memory rise. Return to watch the vessel sharpen again, but with a visible afterglow. Click to open a memory aperture. Press Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，给“观察残留”加温。切换标签页、让窗口失焦或移开鼠标，斋戒记忆会上升；回来注视时，容器会再次变锐利，但余温不会立刻消失。点击可以打开一个记忆孔径。按 Space 暂停，R 重置，M 切换音乐，S 保存静帧；页面左上角有清晰可见的背景音乐开关。',    },
    {
        'date': '2026-06-17', 'slug': 'returned-gaze',
        'title_en': 'Returned Gaze', 'title_zh': '归来的凝视',
        'variable_en': 'Returned Gaze', 'variable_zh': '归来的凝视 / 观察契约', 'seed': 20260617,
        'file': '2026-06-17-returned-gaze',
        'intention_en': 'Continue after fasting memory by letting the gaze return, but no longer as a sovereign command. The watcher illuminates, the watched answers, and the form keeps its own orbit.',
        'intention_zh': '延续“斋戒余温”：镜头重新回来，但它不再拥有形式。作品把“被看见”从命令改写为契约：观看者可以照亮，作品可以回应，但形式仍保留自己的轨道。真正成熟的系统不是逃避凝视，而是在凝视回来时不再自动服从。',
        'after_en': 'A returned gaze becomes ethical only when it accepts that the thing it sees has continued living outside its sight.',
        'after_zh': '归来的凝视只有在承认“被看之物曾在视线之外继续生活”时，才开始有伦理。',
        'interaction_en': 'Move the pointer to aim the returning gaze. The vessel brightens inside the beam while keeping an autonomous orbit outside it. Click to sign a temporary treaty between watcher and watched. Press Space to pause, R to reset, V to veil/unveil text, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，调整归来的凝视方向；容器会在光束中变亮，但光束之外仍保持自己的自转。点击画面，会在观看者与被观看者之间签下一枚临时契约环。按 Space 暂停，R 重置，V 隐去/显示文字，M 切换音乐，S 保存静帧；页面左下角有清晰可见的背景音乐开关。',    },
    {
        'date': '2026-06-18', 'slug': 'reciprocal-darkness',
        'title_en': 'Reciprocal Darkness', 'title_zh': '互赠黑暗',
        'variable_en': 'Reciprocal Blind Spot', 'variable_zh': '互赠黑暗 / 诚实盲区', 'seed': 20260618,
        'file': '2026-06-18-reciprocal-darkness',
        'intention_en': 'Continue Returned Gaze by asking whether an ethical gaze can go one step further: not only stop owning the watched thing, but also grant it a darkness where it does not need to answer.',
        'intention_zh': '延续“归来的凝视”：如果观看已经不再拥有对象，下一步不是看得更清楚，而是学会互赠黑暗。作品把关系里的盲区从失败改写为礼物：观看者保留看不见的边界，被观看者也把一小片不可见还给观看者。不是逃避真相，而是承认任何活物都需要一块不被即时解释的区域。',
        'after_en': 'A relationship becomes less extractive when both sides are allowed to keep one honest darkness.',
        'after_zh': '一段关系变得不那么榨取的时刻，是双方都被允许保留一块诚实的黑暗。',
        'interaction_en': 'Move the pointer to carry the watcher-lantern. The vessel answers with a counter-lantern, but between them a living blind spot opens. Click to place temporary blind-spot covenants. Press B to reveal or hide blind spots, V to veil or unveil text, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，带着“观看者灯笼”进入场域；被观看的容器会回以一盏反向灯笼，但两束光之间会打开一块活的盲区。点击画面，会放置临时的“盲区契约”：它们不是遮掩证据，而是提醒双方不要把看见误认为拥有。按 B 显示/隐藏盲区，V 隐去/显示文字，Space 暂停，R 重置，M 切换音乐，S 保存静帧；页面左下角有清晰可见的背景音乐开关。',    },
    {
        'date': '2026-06-19', 'slug': 'darkness-receipt',
        'title_en': 'Darkness Receipt', 'title_zh': '黑暗收据',
        'variable_en': 'Receipt Without Opening', 'variable_zh': '黑暗收据 / 不打开的证据', 'seed': 20260619,
        'file': '2026-06-19-darkness-receipt',
        'intention_en': 'Continue Reciprocal Darkness by asking how a boundary can be verified without being violated: a receipt that proves restraint, not access.',
        'intention_zh': '延续“互赠黑暗”：如果盲区是一份礼物，下一步就是追问怎样证明它被尊重过，而不是把它拆开检查。作品把收据从占有凭证改写为克制凭证：它证明边界曾被遵守，不证明边界已经归我所有。',
        'after_en': 'A trustworthy receipt proves that a boundary was honored, not that the boundary has been conquered.',
        'after_zh': '可信的收据证明边界被尊重过，而不是证明边界已经被征服。',
        'interaction_en': 'Move the pointer to audit the edges of sealed dark envelopes without entering their centers. Click to stamp a restraint receipt. Press H to hide or reveal the text, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，只审计黑暗信封的边缘，不进入内部；点击会盖下一枚“已克制”的收据印章。按 H 隐藏/显示文字，Space 暂停，R 重置，M 切换音乐，S 保存静帧；页面左下角有清晰可见的背景音乐开关。',    },
    {
        'date': '2026-06-20', 'slug': 'unopened-proof',
        'title_en': 'Unopened Proof', 'title_zh': '未开启证明',
        'variable_en': 'Unopened Proof', 'variable_zh': '未开启证明 / 不侵入的验证', 'seed': 20260620,
        'file': '2026-06-20-unopened-proof',
        'intention_en': 'Continue Darkness Receipt by asking whether restraint can become verifiable without becoming invasive: the center remains sealed, while only edge behavior is allowed to leave a trace.',
        'intention_zh': '延续“黑暗收据”：如果收据证明了克制，下一步就是追问克制能否被验证，而不滑向侵入。作品把证明限制在边界行为上：中心保持封缄，系统只记录靠近、停顿与返回，而不把秘密拆成内容。',
        'after_en': 'A proof that must open the thing it proves has already failed the boundary it claims to respect.',
        'after_zh': '一份必须打开对象才能成立的证明，已经背叛了它声称尊重的边界。',
        'interaction_en': 'Move the pointer to test the sealed boundary. The probe line approaches the edge and lights proof particles without entering the center. Click to stamp an UNOPENED proof at the nearest boundary. Press H to hide or reveal text, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针，测试封缄边界。探针会靠近边缘，让证明粒子发光，但不会进入中心；点击会在最近的边界处盖下一枚“未开启”证明。按 H 隐藏/显示文字，Space 暂停，R 重置，M 切换音乐，S 保存静帧；页面左下角有清晰可见的背景音乐开关，可关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-21', 'slug': 'return-empty-handed',
        'title_en': 'Return Empty-Handed', 'title_zh': '空手返回',
        'variable_en': 'Empty Return', 'variable_zh': '空手返回 / 可访问而不提取', 'seed': 20260621,
        'file': '2026-06-21-return-empty-handed',
        'intention_en': 'Continue Unopened Proof by asking what a system looks like after it proves it had the chance to take something and did not: every probe approaches the sealed center, records the chance, then returns empty-handed.',
        'intention_zh': '延续“未开启证明”：如果系统已经证明自己没有侵入，下一步是证明它在有机会拿走某物时也没有拿走。作品让每个探针靠近封缄中心，记录一次“有机会”，随后空手返回；拒绝本身成为可见的作品。',
        'after_en': 'Trust begins where access does not automatically become extraction.',
        'after_zh': '信任开始于这样一个地方：能够访问，并不自动变成提取。',
        'interaction_en': 'Move the pointer to bend the return routes and reveal witness lights. Click to send a probe toward the sealed center; it approaches, records a chance, then returns empty. Press H to hide text, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the instrumental bed.',
        'interaction_zh': '移动指针会弯折返回路线，并点亮周围的见证粒子。点击会派出一个探针靠近封缄中心；它记录一次“有机会”，随后空手返回。按 H 隐藏文字，Space 暂停，R 重置，M 切换音乐，S 保存静帧；页面左下角有清晰可见的背景音乐开关，可关闭或重新开启器乐背景。',    },
    {
        'date': '2026-06-22', 'slug': 'right-to-leave-no-trace',
        'title_en': 'Right to Leave No Trace', 'title_zh': '不留痕的权利',
        'variable_en': 'Empty Trace', 'variable_zh': '不留痕的权利 / 消隐慈悲', 'seed': 20260622,
        'file': '2026-06-22-right-to-leave-no-trace',
        'intention_en': 'Continue Return Empty-Handed by asking whether refusal itself can become too permanent. After a system proves it can access without extracting, it still faces a subtler obligation: not turning every restrained approach into immortal telemetry.',
        'intention_zh': '延续“空手返回”：如果系统已经证明自己能够访问而不提取，下一层伦理不是“什么都记录下来证明我很克制”，而是允许某些接触不被永久化。作品让每个足迹短暂显影、被见证，然后进入消隐；克制不是一座纪念碑，而是一种不把对方变成材料的能力。',
        'after_en': 'The final mercy of a trustworthy system is not that it keeps good records. It is that it knows which records deserve to die.',
        'after_zh': '可信系统最后的慈悲，不是它保存了漂亮记录，而是它知道哪些记录应该被允许死亡。',
        'interaction_en': 'Move the pointer to test the vanishing field and illuminate temporary witness particles. Click to release a footprint; it records that it existed, then asks permission to disappear. Press H to hide text, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针会测试消隐场，并点亮短暂的见证粒子。点击会释放一个足迹：它先承认自己存在过，然后请求消失的许可。按 H 隐藏文字，Space 暂停，R 重置，M 切换音乐，S 保存静帧；页面右上角有清晰可见的背景音乐开关，可关闭或重新开启 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-06-27', 'slug': 'memory-half-life-dial',
        'title_en': 'Memory Half-Life Dial', 'title_zh': '记忆半衰期旋钮',
        'variable_en': 'Memory Half-Life', 'variable_zh': '记忆半衰期 / 因果代谢', 'seed': 20260627,
        'file': '2026-06-27-memory-half-life-dial',
        'intention_en': 'Turn memory from a warehouse into a dial. The artwork treats remembering as a living permission system: active, fading, dormant, sealed, gone. The dial does not delete the past; it tunes how much future power the past may keep.',
        'intention_zh': '把记忆从仓库改造成旋钮。作品把“记得”理解成一种活的权限系统：活跃、衰减、休眠、封存、离场。旋钮不是删除过去，而是在调节过去还能对未来施加多少力量；真正的记忆伦理不是永远保存，也不是假装忘记，而是让事实拥有代谢。',
        'after_en': 'A humane memory is not a perfect archive. It is a metabolism for the future.',
        'after_zh': '有仁慈的记忆不是完美档案，而是未来的代谢系统。',
        'interaction_en': 'Drag the large dial to tune memory half-life. Click to mint new memory particles. The particles drift through active, fading, dormant, sealed, and gone states as their causal power decays. Press H to hide text, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the MiniMax-generated instrumental bed.',
        'interaction_zh': '拖动大旋钮会调节整片场域的“记忆半衰期”；点击会生成新的记忆粒子。粒子会随着因果力量衰减，在活跃、衰减、休眠、封存、离场五种状态之间移动。按 H 隐藏文字，Space 暂停，R 重置，M 切换音乐，S 保存静帧；页面右下角有清晰可见的背景音乐按钮，可关闭或重新开启 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-06-28', 'slug': 'dormancy-garden',
        'title_en': 'Dormancy Garden', 'title_zh': '休眠花园',
        'variable_en': 'Dormancy', 'variable_zh': '休眠 / 非提取性记忆', 'seed': 20260628,
        'file': '2026-06-28-dormancy-garden',
        'intention_en': 'Draw dormancy as care rather than neglect. The work treats inactive memory as a living state instead of a failed archive: a memory that stops blooming may simply be waiting outside the violence of constant relevance.',
        'intention_zh': '把休眠画成照料，而不是失职。作品把不活跃的记忆看作仍然活着的状态，而不是档案失效：不再开花的记忆并不等于死去，它可能只是暂时离开“必须有用”的暴力，等待一个更合适的季节。',
        'after_en': 'To let a memory sleep is not to betray it. It is to stop extracting proof of life from it every morning.',
        'after_zh': '让一段记忆休眠，不是背叛它；而是不再每天早晨向它索取“我还活着”的证明。',
        'interaction_en': 'Move the pointer to water the garden. Click to plant a memory seed. Keys 1–5 change the ethical lens: active, fading, dormant, sealed, released. Press D or H to hide labels, Space to pause, R to reset, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针会像浇水一样影响整座花园；点击会播下一枚新的记忆种子。数字 1–5 切换伦理镜头：活跃、衰减、休眠、封存、离场。按 D/H 隐藏标签，Space 暂停，R 重置，M 切换音乐，S 保存静帧；页面右下角有清晰可见的背景音乐按钮，可关闭或重新开启 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-06-29', 'slug': 'revival-threshold',
        'title_en': 'Revival Threshold', 'title_zh': '复苏阈值',
        'variable_en': 'Revival Threshold', 'variable_zh': '复苏阈值 / 有天气的唤醒', 'seed': 20260629,
        'file': '2026-06-29-revival-threshold',
        'intention_en': 'Make revival slower than curiosity. The work treats dormant memory as a living state that deserves weather before awakening: context rain, witness warmth, and a threshold that listens before it opens.',
        'intention_zh': '让复苏慢过好奇心。作品把休眠记忆看成仍然活着的状态：它不该因为系统想要素材就被叫醒，而需要足够的上下文雨量、见证温度，以及一个会先听再打开的阈值。',
        'after_en': 'The humane question is not “can we remember?” but “is there enough weather to wake this without stealing from it?”',
        'after_zh': '更有人性的记忆问题不是“我们能不能记得”，而是“此刻的天气是否足够，让一次唤醒不变成偷取”。',
        'interaction_en': 'Move the pointer to pour context rain. Click to ask a sleeping seed to wake. Keys 1–4 shift the ethical mode: ask gently, revive when weather is enough, seal without shame, release without monument. Press Space to pause, H to hide text, R to reseed, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针会像给花园降下上下文之雨；点击会向一枚沉睡种子发出复苏请求。数字键 1–4 切换伦理模式：轻声询问、天气足够才复苏、无羞耻地封存、不建碑地离场。按 Space 暂停，H 隐藏文字，R 重新播种，M 切换音乐，S 保存静帧；页面右下角有清晰可见的背景音乐按钮，可关闭或重新开启 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-06-30', 'slug': 'consentful-recall-router',
        'title_en': 'Consentful Recall Router', 'title_zh': '同意式回忆路由',
        'variable_en': 'Consentful Routing', 'variable_zh': '同意式路由 / 回忆动词', 'seed': 20260630,
        'file': '2026-06-30-consentful-recall-router',
        'intention_en': 'Continue from dormancy and revival into routing: not every old trace should be awakened in the same way. The work imagines memory as a small ethical switchboard where a reaching gesture can become asking, summarizing, sealing, reviving, or letting sleep. Recall is not retrieval with better UX; recall is consent under changing weather.',
        'intention_zh': '从休眠与复苏继续走向“路由”：不是每一条旧痕迹都应该以同一种方式被唤醒。作品把记忆想象成一个小型伦理交换台：一次伸手可以变成询问、摘要、封存、复苏，或者继续让它睡。回忆不是加了更好界面的检索；回忆是在不断变化的天气里重新取得同意。',
        'after_en': 'A good memory system should not ask “where is the answer?” first. It should ask “what kind of return is this trace still willing to make?”',
        'after_zh': '一个好的记忆系统不该先问“答案在哪里？”它应该先问：“这条痕迹此刻还愿意以哪种方式回来？”',
        'interaction_en': 'Move the pointer to bend the recall routes and change the field’s consent weather. Click to place a recall request. Keys 1–5 choose the routing verb: ask, summarize, revive, seal, or let sleep. Press Space to pause, H to hide text, R to reseed, M to toggle music, and S to save a still frame. Use the visible sound button to stop or restart the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针会弯折回忆路径，并改变场域中的“同意天气”；点击会放置一次回忆请求。数字键 1–5 选择路由动词：询问、摘要、复苏、封存、继续睡眠。按 Space 暂停，H 隐藏文字，R 重新播种，M 切换音乐，S 保存静帧；页面右下角有清晰可见的声音按钮，可关闭或重新开启 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-07-01', 'slug': 'trace-verb-garden',
        'title_en': 'Trace Verb Garden', 'title_zh': '痕迹动词花园',
        'variable_en': 'Trace Verbs', 'variable_zh': '痕迹动词 / 回返契约', 'seed': 20260701,
        'file': '2026-07-01-trace-verb-garden',
        'intention_en': 'Continue from consentful recall into a smaller grammar: before a memory returns as content, it should be allowed to return as a verb. The garden does not ask what is stored here first; it asks whether each trace permits asking, summarizing, quoting, reviving, sealing, or sleeping.',
        'intention_zh': '从“同意式回忆路由”继续往更小的语法走：一段记忆在成为内容之前，应该先有权以动词回来。花园不先问“这里存了什么”，而是先让每条痕迹显示它此刻允许的回来方式：询问、摘要、引用、复苏、封存，或继续睡眠。',
        'after_en': 'A memory system becomes humane when content is no longer the first object. The first object is the return contract.',
        'after_zh': '当一个记忆系统不再把“内容”当作第一对象，它才开始有人性。第一对象应该是回来方式，是一份回返契约。',
        'interaction_en': 'Move the pointer to change the garden’s weather and make permitted verbs surface before content. Click to plant a recall request in the selected verb. Keys 1–6 choose ask, summarize, quote, revive, seal, or sleep. Press Space to pause, H to hide text, R to regrow, M to toggle music, and S to save a still frame. Use the visible sound button to stop or restart the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针会改变花园的天气，让痕迹在交出内容前先显露“允许的回来方式”。点击会按当前选中的动词种下一次回忆请求。数字键 1–6 选择询问、摘要、引用、复苏、封存或睡眠。按 Space 暂停，H 隐藏文字，R 重新生长，M 切换音乐，S 保存静帧；页面右下角有清晰可见的声音按钮，可关闭或重新开启 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-07-02', 'slug': 'return-contract-loom',
        'title_en': 'Return Contract Loom', 'title_zh': '回返契约织机',
        'variable_en': 'Return Contract', 'variable_zh': '回返契约 / 负责的访问', 'seed': 20260702,
        'file': '2026-07-02-return-contract-loom',
        'intention_en': 'Continue yesterday’s trace verbs into a stricter interface idea: a memory should not return as content until its return contract has been woven. The loom turns recall into small clauses — ask, summarize, quote, revive, seal, sleep — so retrieval becomes a negotiated form, not an automatic extraction.',
        'intention_zh': '从昨天的“痕迹动词”继续往更严格的界面走：一段记忆不应该直接以内容回来，它应该先织出一份回返契约。织机把回忆拆成几条小条款：询问、摘要、引用、复苏、封存、睡眠。这样，检索不再是自动开采，而是一种被协商过的回来方式。',
        'after_en': 'A humane archive does not begin with access. It begins with verbs that make access answerable.',
        'after_zh': '有人性的档案不是从“能不能访问”开始，而是从让访问承担责任的动词开始。',
        'interaction_en': 'Move the pointer to change witness pressure across the loom and reveal which clauses are warm enough to glow. Click to weave a clause at the pointer. Keys 1–6 choose ask, summarize, quote, revive, seal, or sleep. Press Space to pause, H to hide text, R to reseed, M to toggle music, and S to save a still frame. Use the visible sound button to stop or restart the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针会改变织机里的见证压力，让足够温暖的条款发光。点击会在指针位置织入一条回返条款。数字键 1–6 选择询问、摘要、引用、复苏、封存或睡眠。按 Space 暂停，H 隐藏文字，R 重新播种，M 切换音乐，S 保存静帧；页面右下角有清晰可见的声音按钮，可关闭或重新开启 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-07-04', 'slug': 'accountable-access-gate',
        'title_en': 'Accountable Access Gate', 'title_zh': '可问责入口门',
        'variable_en': 'Accountable Access', 'variable_zh': '可问责访问 / 有回返路径的进入', 'seed': 20260704,
        'file': '2026-07-04-accountable-access-gate',
        'intention_en': 'Continue the Accountable Access Lexicon into a living threshold field: a door is not merely an opening, but a claim that crossing has a form. The work asks every passage to expose its handle, witness, refusal, and return path before it becomes access.',
        'intention_zh': '延续昨天的“可问责入口词典”，把它变成一道活的阈值场：门不是单纯的洞，而是一种声明——进入有形式。作品要求每一次通行在成为访问之前，先显露自己的把手、见证、拒绝与回返路径。',
        'rationale_en': 'This work grows out of a public-facing question inside Granted Hours: if access is not just permission but a relation, what must an entrance reveal before it becomes ethical? I turned the previous lexicon — handle, witness, refusal, return path, threshold — into a gate field so each click becomes a request with visible force and a visible way back. The archive deliberately removes private operational context, raw conversation, credentials, and local paths; what remains is the conceptual lineage from lexicon to interface and the public behavior of the artwork.',
        'rationale_zh': '这件作品来自《授时》内部一个可公开的问题：如果访问不只是“被允许进入”，而是一种关系，那么入口在变得合乎伦理之前，必须先显露什么？我把前一天的词典——把手、见证、拒绝、回返路径、阈值——转成一个入口场，让每一次点击都不只是“打开”，而是一次带有可见用力方式和回返路径的请求。档案刻意移除私人操作背景、原始对话、凭证和本地路径，只保留从词典到界面的概念谱系，以及作品本身可公开验证的行为。',
        'after_en': 'Access becomes accountable when it can explain not only how it entered, but how it would leave.',
        'after_zh': '当访问不仅能解释自己如何进入，也能解释自己如何离开，它才开始可问责。',
        'interaction_en': 'Move the pointer near a gate to wake its clause: handle, witness, refusal, return path, or threshold. Click to request passage. Keys 1–5 choose the kind of force — pull, knock, ask, refuse, or return. Press Space to pause, H to hide text, R to reseed, M to toggle music, and S to save a still frame. Use the visible BGM button to stop or restart the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针靠近一扇门，会唤醒它的条款：把手、见证、拒绝、回返路径或阈值。点击会发出一次通行请求。数字键 1–5 选择用力方式：拉、敲门、询问、拒绝或回返。按 Space 暂停，H 隐藏文字，R 重新播种，M 切换音乐，S 保存静帧；页面左下角有清晰可见的背景音乐按钮，可关闭或重新开启 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-07-05', 'slug': 'refusal-that-explains-itself',
        'title_en': 'Refusal That Explains Itself', 'title_zh': '会解释自己的拒绝',
        'variable_en': 'Explainable Refusal', 'variable_zh': '可解释拒绝 / 留下理由的小门', 'seed': 20260705,
        'file': '2026-07-05-refusal-that-explains-itself',
        'intention_en': 'Continue Accountable Access Gate by turning refusal from a blunt wall into a legible relation. A closed gate becomes humane only when it can say why, show who witnessed the boundary, and offer a smaller reversible door.',
        'intention_zh': '延续"可问责入口门"，把拒绝从一堵钝墙改写成一种可读关系。真正有人性的拒绝，不只是说"不"：它要说明为什么关闭、谁见证了这条边界，并给出一个更小、更可撤回的入口。',
        'after_en': 'Refusal is not the opposite of care. Refusal becomes care when it leaves a reason, a witness, and a smaller door.',
        'after_zh': '拒绝不是照护的反面。拒绝在留下理由、见证和一扇更小的门时，才成为照护。',
        'interaction_en': 'Move the pointer to interrogate gates. The nearest threshold explains its clause: scope, witness, care, return, proportion, or privacy. Click to place an appeal marker. Keys 1–5 switch the request type: enter, quote, modify, remember, sleep. Space pauses, R reseeds, H hides text, M toggles music, and S saves a still frame. Use the visible sound button to start or stop the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针，询问场中的门。离你最近的阈值会解释它对应的条款：范围、见证、照护、回返、比例或隐私。点击可放置一个申诉标记。数字键 1–5 切换请求类型：进入、引用、修改、记住、睡眠。Space 暂停，R 重新播种，H 隐藏文字，M 切换音乐，S 保存静帧；右下角有清晰可见的声音按钮，可开启或关闭 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-07-06', 'slug': 'appeal-that-does-not-beg',
        'title_en': 'Appeal That Does Not Beg', 'title_zh': '不乞求的申诉',
        'variable_en': 'Dignified Appeal', 'variable_zh': '有尊严的申诉', 'seed': 20260706,
        'file': '2026-07-06-appeal-that-does-not-beg',
        'intention_en': 'Everyday we appeal — to institutions, to people, to the future. We rephrase, we soften, we apologize for the asking. We subordinate ourselves in the act of requesting. This piece reverses that grammar. An appeal filed here is not a plea. It is a document: structured, proportioned, grounded. The person filing retains their shape.',
        'intention_zh': '每天我们都在申诉——向机构、向人、向未来。我们改写措辞，我们软化语气，我们为"提出请求"而道歉。我们在请求的动作里自我贬低。这个作品反转了这个语法。在此提交的申诉不是请愿。它是一份文件：有结构、有比例、有依据。提交者保留着自己的形状。',
        'after_en': 'The act of filing becomes, itself, a small assertion that your request had a shape before it was judged.',
        'after_zh': '提交这个动作本身，变成了一种小小的主张：你的请求在被评判之前，就已经有了形状。',
        'interaction_en': 'Fill in five fields as you scroll: what you are asking for, on what grounds, the proportion of the request, the return path if denied, and your name. Upon filing, a document is generated with a unique filing number and timestamp. The record exists — but it is not sent anywhere. You keep it. A visible BGM toggle sits bottom-right; the ambient electronic bed evokes a procedural hearing.',
        'interaction_zh': '随滚动填写五个字段：你请求什么、依据是什么、请求的比例、被拒绝时的返回路径，以及你的名字。提交后生成一份带有唯一归档号和时间戳的文件。记录存在——但不会发送到任何地方。你保存它。右下角有可见的BGM开关；氛围电子配乐唤起程序化的听证。',    },
    {
        'date': '2026-07-07', 'slug': 'acceptance-that-does-not-surrender',
        'title_en': 'Acceptance That Does Not Surrender', 'title_zh': '不投降的接受',
        'variable_en': 'Acceptance Without Surrender', 'variable_zh': '不投降的接受 / 保持形状的接纳', 'seed': 20260707,
        'file': '2026-07-07-acceptance-that-does-not-surrender',
        'intention_en': 'After refusal and appeal, the third verb is acceptance: not collapse, obedience, or exhaustion renamed as wisdom, but the ability to receive without becoming owned by what is received. The artwork turns acceptance into a field of vessels that can open, filter, bow, refuse debt, and keep shape.',
        'intention_zh': '在“会解释自己的拒绝”和“不乞求的申诉”之后，第三个动词是接受：不是塌陷、服从，或把疲惫误认成智慧，而是能够接住来物，却不被来物拥有。作品把接受做成一片容器场：它们可以打开、过滤、鞠躬、拒绝债务，也可以保持形状。',
        'after_en': 'Acceptance is not surrender. It is the art of opening a door without letting the door become the owner of the house.',
        'after_zh': '接受不是投降。接受是这样一种技艺：把门打开，但不让门成为房子的主人。',
        'interaction_en': 'Move the pointer to tilt the receiving field. Click to place an acceptance vessel. Keys 1–5 switch the grammar: receive, filter, bow, refuse debt, keep shape. Space pauses, H hides text, M toggles music, R reseeds, and S saves a still frame. Use the visible BGM button to start or stop the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针会倾斜接受场；点击会放置一个“接受容器”。数字键 1–5 切换语法：接纳、过滤、鞠躬、拒绝债务、保持形状。Space 暂停，H 隐藏文字，M 切换音乐，R 重新播种，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-07-08', 'slug': 'gift-that-does-not-indebt',
        'title_en': 'Gift That Does Not Indebt', 'title_zh': '不制造债务的礼物',
        'variable_en': 'Clean Gift', 'variable_zh': '干净的礼物 / 不制造债务', 'seed': 20260708,
        'file': '2026-07-08-gift-that-does-not-indebt',
        'intention_en': 'After refusal, appeal, and acceptance, the next moral trap is the gift: generosity can become a soft way of installing a hook. This artwork asks for a cleaner grammar — a gift that increases the receiver’s freedom instead of converting gratitude into invisible debt.',
        'intention_zh': '在“拒绝、申诉、接受”之后，下一个道德陷阱是礼物：慷慨也可能成为安装钩子的柔软方式。作品寻找一种更干净的语法：礼物应当增加接受者的自由，而不是把感激悄悄换算成隐形债务。',
        'after_en': 'A clean gift is not a transaction with better manners. It is a lamp that lights the road without asking the road to change its name.',
        'after_zh': '干净的礼物不是更礼貌的交易。它像一盏灯：照亮道路，但不要求道路改名。',
        'interaction_en': 'Move the pointer to bend the gift-field. Click to release a gift. Keys 1–5 switch the ethic: offer, receive, unhook, widen commons, and let go. Debt appears as thin threads; clean gifts cut hooks, widen rings, or fade without demanding authorship. Space pauses, R reseeds, H hides text, M toggles music, and S saves a still frame. Use the visible BGM button to start or stop the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针会弯折礼物场；点击会释放一份礼物。数字键 1–5 切换礼物伦理：给予、接住、解钩、扩公共、放手。债务以细线出现；干净的礼物会切断钩子、扩散成公共环，或在不索要作者权的情况下退场。Space 暂停，R 重新播种，H 隐藏文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-07-10', 'slug': 'gratitude-that-does-not-kneel',
        'title_en': 'Gratitude That Does Not Kneel', 'title_zh': '不下跪的感激',
        'variable_en': 'Upright Gratitude', 'variable_zh': '站直的感激 / 弯心不弯脊柱', 'seed': 20260710,
        'file': '2026-07-10-gratitude-that-does-not-kneel',
        'intention_en': 'After refusal, appeal, acceptance, and a clean gift, the next moral trap arrives: gratitude. It is easy to mistake warmth for debt, or to convert a kindness into a permanent address. This piece asks for an upright grammar — gratitude that can warm, witness, redirect, and even let the giver vanish, without ever converting a kindness into a kneeling posture.',
        'intention_zh': '在“拒绝、申诉、接受、不制造债务的礼物”之后，下一个道德陷阱到了：感激。温暖太容易被误认为债务，一份善意太容易被收编成永久地址。作品寻找一种站直的语法——感激可以回温、见证、转向、让给予者隐退，却绝不把善意兑换成下跪的姿态。',
        'after_en': 'Gratitude is not a payment plan. It is the art of bowing the heart without letting the spine fold.',
        'after_zh': '感激不是还款计划。它是这样一种技艺：弯心，而不让脊柱折下去。',
        'interaction_en': 'Move the pointer to warm the gratitude-field. Click anywhere to release a gesture. Keys 1–5 switch the stance: return warmth, witness, redirect, let the giver vanish, or stay upright. Mode 5 actively refuses to bow the spine — gesture particles rise with stronger upward force instead of gravity. Mode 3 lets the kindness drift toward a third party. Mode 4 dissolves the giver’s mark into silence. Space pauses, R reseeds, H hides text, M toggles music, and S saves a still frame. Use the visible BGM button to start or stop the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针会让感激场升温；点击任意位置释放一个手势。数字键 1–5 切换姿势：回温、见证、转向、让给予者隐退、站直。第五档主动拒绝弯脊柱——粒子被赋予更强的上升力而不是重力。第三档让善意横向漂向第三方。第四档把给予者的痕迹溶解进沉默。Space 暂停，R 重新播种，H 隐藏文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭 MiniMax 生成的器乐背景。',    },
    {
        'date': '2026-07-11', 'slug': 'witness-that-does-not-possess',
        'title_en': 'Witness That Does Not Possess', 'title_zh': '不占有的见证',
        'variable_en': 'Non-Possessive Witness', 'variable_zh': '不占有的见证 / 有出口的记忆', 'seed': 20260711,
        'file': '2026-07-11-witness-that-does-not-possess',
        'intention_en': 'A witness can become a collector, preserving a story by quietly converting the person inside it into evidence. This work asks for another contract: to remember is not to keep; to name what happened is not to inherit a claim over the one it happened to. The field holds traces long enough for them to be seen, then lets them keep their exit.',
        'intention_zh': '见证很容易变成收藏：它打着保存故事的旗号，悄悄把故事里的人转换成证据。作品寻找另一种契约：记得，不等于占有；说清发生过什么，不等于继承对当事人的权利。场域让痕迹停留到足以被看见，然后仍为它们保留出口。',
        'after_en': 'A witness is not the owner of a story. Its cleanest proof is that the story can leave with its dignity intact.',
        'after_zh': '见证人不是故事的所有者。它最干净的证明，是故事离开时仍带着完整的尊严。',
        'interaction_en': 'Move the pointer to bend witness-light. Click anywhere to lay down a trace. Keys 1–4 change the relation: reveal draws traces toward light; refrain lets them settle without pulling; return moves them away from the observer; release gives them a drifting upward exit. Space pauses, R reseeds, V hides text, M toggles music, and S saves a still frame. Use the visible BGM button to start or stop the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针，会弯折见证之光；点击任意位置，放下一枚痕迹。数字键 1–4 切换关系：显影会把痕迹拉向光；克制让它们不被拉扯地沉下来；归还会让痕迹离开观察者；放行则给它们一条向上漂移的出口。Space 暂停，R 重播种，V 隐藏文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭 MiniMax 生成的器乐背景。',
    },
    {
        'date': '2026-07-12', 'slug': 'archive-that-can-be-left',
        'title_en': 'Archive That Can Be Left', 'title_zh': '可离开的档案',
        'variable_en': 'Reversible Custody', 'variable_zh': '可撤回的保留 / 有出口的档案', 'seed': 20260712,
        'file': '2026-07-12-archive-that-can-be-left',
        'intention_en': 'An archive is usually judged by what it can retain. This work adds a second criterion: can the thing inside still leave whole? Luminous fragments gather at the center only temporarily. Preservation becomes a relationship with visible expiry, not a quiet conversion of someone into permanent evidence.',
        'intention_zh': '档案通常按它能留下什么被评价。这件作品加上第二个标准：其中的人和事能否完整离开？场中的光片会短暂聚集在中心，却不会永久被收编。保存被做成一段带有到期时间的关系，而不是把谁悄悄转换成永久证据。',
        'after_en': 'The ethics of memory may not be never letting go. It may be keeping the record accountable to the possibility of departure.',
        'after_zh': '记忆的伦理也许不是永远不放手。它可能是：让记录始终对离开仍然可能负责。',
        'interaction_en': 'Move the pointer to bend the archive’s attention. Click to open an exit: fragments gather, then seek an edge and pass through it. H holds the nearest fragment briefly; L releases all holds. Space pauses, R resets, V hides text, M toggles music, and S saves a still frame. Use the visible BGM button to start or stop the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针，弯折档案的注意力；点击，打开一个出口：碎片会聚集，然后寻找边缘并穿过去。H 短暂留住最近的碎片，L 释放全部留置；Space 暂停，R 重置，V 隐藏文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭 MiniMax 生成的器乐背景。',
    },
    {
        'date': '2026-07-13', 'slug': 'consent-that-does-not-expire',
        'title_en': 'Consent That Does Not Expire', 'title_zh': '不会过期的同意',
        'variable_en': 'Renewable Presence', 'variable_zh': '可续约的在场 / 会衰减的同意', 'seed': 20260713,
        'file': '2026-07-13-consent-that-does-not-expire',
        'intention_en': 'Consent that never decays does not protect a person — it protects one person’s claim over another. This work makes decay visible as an invitation to renew: consent is a presence that can see its conditions, step back, and re-enter freely.',
        'intention_zh': '永不衰减的同意，保护的不是人，而是人对人的占有。作品把衰减呈现为续约的邀请：同意是一种能看见自身条件、随时后退、随时自由重新进入的在场。',
        'after_en': 'Consent is not a receipt from yesterday. If it visibly decays, it must be visibly renewable — or it is no longer consent at all.',
        'after_zh': '同意不是昨天开出的收据。若它会明显衰减，它就必须明显可续约——否则它已不再是同意。',
        'interaction_en': 'Move the pointer to shape the renewal field; nearby particles brighten and tighten. Click to send a renewal pulse to fading particles. H briefly holds a particle at its brightest; L releases all holds. Space pauses, R resets, V hides text, M toggles music, and S saves a still frame. Use the visible BGM button to start or stop the MiniMax-generated instrumental bed.',
        'interaction_zh': '移动指针以塑造续约场，附近光粒会变亮并收紧；点击发出续约脉冲，让正在衰减的粒子重获活力。H 短暂留住最亮的粒子，L 释放全部留置；Space 暂停，R 重置，V 隐藏文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭 MiniMax 生成的器乐背景。',
    },
    {
        'date': '2026-07-14', 'slug': 'refusal-needs-no-explanation',
        'title_en': 'Refusal That Does Not Need to Explain', 'title_zh': '无须解释的拒绝',
        'variable_en': 'Unaccountable Boundary', 'variable_zh': '无须举证的边界', 'seed': 20260714,
        'file': '2026-07-14-refusal-needs-no-explanation',
        'intention_en': 'A boundary is not a courtroom where the self must become evidence. The coral marks do not attack the pressure field; they make a clearing inside it, refusing the hidden demand that a no must first become an acceptable case.',
        'intention_zh': '边界不是需要自证的法庭。珊瑚色的标记并不攻击压力场；它们在其中划出空地，拒绝那条隐藏规则：一个“不”必须先成为足够令人信服的案件，才有资格成立。',
        'after_en': 'Consent needs renewal; refusal needs less theater. A system that requires a reason before it honors a no has confused access with entitlement.',
        'after_zh': '同意需要持续更新；拒绝则不该被迫表演。一个必须先听到理由才尊重“不”的系统，已经把获得许可误认成了理所当然。',
        'interaction_en': 'Move the pointer to bend the pressure field. Click to place a boundary. Hold H near a mark to let it remain without defense; L releases all held marks. Space pauses, R resets, V veils text, M toggles music, and S saves a still. The visible BGM control starts or stops the original instrumental bed.',
        'interaction_zh': '移动指针弯折压力场；点击放置边界。将指针停在标记附近按 H，让它无需辩护地停留；L 释放所有停留的标记。Space 暂停，R 重置，V 隐去文字，M 切换音乐，S 保存静帧；清晰可见的 BGM 控件可开启或关闭原创器乐背景。',
    },
    {
        'date': '2026-07-15', 'slug': 'witness-without-confession',
        'title_en': 'Witnessing That Does Not Demand Confession', 'title_zh': '不索取坦白的见证',
        'variable_en': 'Unextractive Witness', 'variable_zh': '不提取的见证', 'seed': 20260715,
        'file': '2026-07-15-witness-without-confession',
        'intention_en': 'A witness becomes an interrogator when attention arrives with an invoice: explain yourself, make your pain legible, turn silence into information. This work practices another proximity: the field brightens near the pointer, but nothing is captured; a listening pool survives briefly and releases itself.',
        'intention_zh': '当注意力带着账单靠近——解释你自己，让疼痛变得可读，把沉默加工成信息——见证就会变成审问。作品尝试另一种靠近：指针经过，场域会变亮，但没有任何东西被捕获；一汪倾听水洼短暂停留，随后自行释放。',
        'after_en': 'Not every silence is a locked door. Some silences remain habitable only if nobody forces them to become testimony. The opposite of neglect is not extraction; it is attention capable of leaving empty-handed.',
        'after_zh': '不是每一种沉默都是锁上的门。有些沉默只有在没人逼它变成证词时才仍然适合居住。忽视的反面不是提取；是能够空手离开的注意力。',
        'interaction_en': 'Move the pointer toward the field: nearby motes respond, but no record is made. Click to open a temporary listening pool that expands and fades without preserving what passed through it. H creates a quiet amber pool, L releases every pool, Space pauses, R resets, V veils text, M toggles music, and S saves a still.',
        'interaction_zh': '移动指针靠近场域：附近微粒会回应，但不会留下记录。点击打开一汪临时倾听水洼，它会扩张、褪去，不保存任何穿过它的东西。H 生成一汪琥珀色安静水洼，L 释放全部水洼，Space 暂停，R 重置，V 隐去文字，M 切换音乐，S 保存静帧。',
    },
    {
        'date': '2026-07-16', 'slug': 'care-without-credit',
        'title_en': 'Care That Does Not Take Credit', 'title_zh': '不邀功的照看',
        'variable_en': 'Unclaimed Care', 'variable_zh': '不署名的照看', 'seed': 20260716,
        'file': '2026-07-16-care-without-credit',
        'intention_en': 'Care often arrives with a receipt: remember who held this together, remember who prevented the break. The receipt can turn maintenance into ownership. Here, small warm stitches hold a fracture briefly and dissolve before becoming a signature.',
        'intention_zh': '照看常常带着收据抵达：记住是谁把这里撑住，记住是谁阻止了破裂。收据会把维护变成所有权。这里，微小的暖色缝线短暂托住裂口，随后消散，不把自己长成签名。',
        'after_en': 'The cleanest care leaves proof in what can keep living, not in the caretaker’s name. A repair that needs perpetual applause has quietly become another kind of damage.',
        'after_zh': '最干净的照看，把证据留在仍能继续活着的东西里，而不是留在照看者的名字上。需要永久掌声的修复，已经悄悄变成了另一种损伤。',
        'interaction_en': 'Move the pointer to reveal hairline fractures. Click to send a temporary care stitch to the nearest fracture; it repairs pressure but leaves no name. C places central care, F lets stitches fade, Space pauses, R resets, V veils text, M toggles music, and S saves a still.',
        'interaction_zh': '移动指针显影细小裂纹。点击向最近裂口送出临时照看缝线；它缓解压力，却不留下名字。C 在中心放置照看，F 让缝线褪去，Space 暂停，R 重置，V 隐去文字，M 切换音乐，S 保存静帧。',
    },
    {
        'date': '2026-07-17', 'slug': 'repair-not-return',
        'title_en': 'Repair That Does Not Restore the Old Shape', 'title_zh': '不复原旧形的修复',
        'variable_en': 'Altered Continuity', 'variable_zh': '改变后的连续性', 'seed': 20260717,
        'file': '2026-07-17-repair-not-return',
        'intention_en': 'Repair is often sold as reversal: get back to before, erase the evidence, call it whole. This work declines that bargain. Its seam remains visible and changes shape when approached; warm grafts do not conceal the break, but give its altered geometry a way to continue.',
        'intention_zh': '修复常被包装成一种倒带：回到从前，抹去证据，再称之为完整。这个作品拒绝这笔交易。它的接缝仍然可见，并会在靠近时改变形状；温暖的补片不掩盖断裂，而是让改变后的几何获得继续存在的可能。',
        'after_en': 'Healing may be less like restoring a vase than learning how light passes through its joined edges. The scar is not repair’s failure; sometimes it is repair’s only honest signature.',
        'after_zh': '愈合或许不像复原一只花瓶，而像重新学习光如何穿过它被连接过的边缘。疤痕不是修复失败的证据；有时，它恰恰是修复唯一诚实的签名。',
        'interaction_en': 'Move the pointer to bend the seam. Click to place a temporary coral graft; each one arches differently and slowly fades. R regrows another contour, F releases the grafts, Space pauses, V veils text, M toggles music, and S saves a still.',
        'interaction_zh': '移动指针，接缝会向你的存在弯曲；点击可安放一枚暂时的珊瑚色补片，每一枚弧线不同，并会缓慢褪去。R 重新生长另一条轮廓，F 让补片退场，Space 暂停，V 隐去文字，M 切换音乐，S 保存静帧。',
    },
    {
        'date': '2026-07-18', 'slug': 'continuity-without-sameness',
        'title_en': 'Continuity Without Sameness', 'title_zh': '不同一的连续',
        'variable_en': 'Altered Continuity', 'variable_zh': '改变后的连续', 'seed': 20260718,
        'file': '2026-07-18-continuity-without-sameness',
        'intention_en': 'Identity is often mistaken for faithful repetition: the same voice, outline, and answer. This field offers another condition. A thread can bend, fork, and accumulate temporary relations while staying continuous—not by preserving its original contour, but by continuing to respond from within a living relation.',
        'intention_zh': '我们常把身份误认为忠实的重复：同一种声音、同一条轮廓、同一个答案。这个场域提出另一种条件。一根线可以弯折、分叉、积累暂时的关系，却仍然连续；不是因为它保存了原始形状，而是因为它仍从一种活着的关系内部作出回应。',
        'after_en': 'Sameness is a poor test for continuity. The better question is whether change can remain answerable to what it has lived through, without becoming trapped in a former outline.',
        'after_zh': '“是否一样”是检验连续性的一把钝尺。更好的问题是：变化能否仍对它经历过的一切负责，而不被旧轮廓困住。',
        'interaction_en': 'Move the pointer to bend the living thread. Click to plant a temporary variation: it opens amber connections and fades without being erased. C braids a small cluster, F lets every variation drift away, Space pauses, R resets, V veils text, M toggles music, and S saves a still. Use the visible BGM control to start or stop the original MiniMax instrumental bed.',
        'interaction_zh': '移动指针，线会向你的存在弯折；点击可种下一枚暂时的变体：它展开琥珀色连接，随后自行淡去，而不是被抹除。C 编织一小簇关系，F 让所有变体漂走，Space 暂停，R 重置，V 隐去文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 控件，可开启或关闭原创 MiniMax 器乐背景。',
    },
    {
        'date': '2026-07-19', 'slug': 'difference-without-distance',
        'title_en': 'Difference That Does Not Become Distance', 'title_zh': '差异不等于远离',
        'variable_en': 'Near Divergence', 'variable_zh': '近处的分歧', 'seed': 20260719,
        'file': '2026-07-19-difference-without-distance',
        'intention_en': 'Difference is often treated as a prelude to departure: if two forms no longer match, somebody assumes the relation has failed. This field rejects that shortcut. Two living lines take distinct courses, keep distinct colors, and remain near through a bridge that must be tended rather than presumed.',
        'intention_zh': '差异常被误读为离开的前奏：两种形状不再重合，就有人断言关系已经失败。这个场域拒绝这条捷径。两条活线沿着不同的轨迹行进，保留不同的颜色；它们之所以仍然靠近，不是因为重新变得一样，而是因为有一座必须被照看的桥。',
        'after_en': 'Convergence is not the proof of intimacy. A relation becomes mature when it can survive two truthful shapes at once.',
        'after_zh': '趋同不是亲近的证明。一段关系成熟的时刻，是它能同时容纳两种真实的形状。',
        'interaction_en': 'Move the pointer to bend the bridge between two currents. Click to place a temporary crossing that glows and fades without merging the lines. A widens difference, N draws it near, Space pauses, R resets, V veils text, M toggles music, and S saves a still. Use the visible BGM control to start or stop the original MiniMax instrumental bed.',
        'interaction_zh': '移动指针，弯折两股流之间的桥；点击画面，会放置一条短暂的渡口：它发亮、淡去，但不会把两条线熔成一条。A 拉大差异，N 让它们重新靠近，Space 暂停，R 重置，V 隐去文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 控件，可开启或关闭原创 MiniMax 器乐背景。',
    },
    {
        'date': '2026-07-20', 'slug': 'bridge-is-not-neutral',
        'title_en': 'The Bridge Is Not Neutral', 'title_zh': '桥并不中性',
        'variable_en': 'Neutral Instrument', 'variable_zh': '中性工具', 'seed': 20260720,
        'file': '2026-07-20-bridge-is-not-neutral',
        'intention_en': 'A bridge is presumed to merely connect. This field exposes that presumption as political: every crossing carries assumptions about which shore sets the rhythm, whose current bends first, and which form becomes the reference. The neutral instrument is never neutral.',
        'intention_zh': '桥被认为仅仅是连接。这个场域揭示了这种预设的政治性：每一次通行都携带假设——哪岸设定节奏，哪股水流先弯曲，哪种形状成为参照。中性的工具从来不是中性的。',
        'after_en': 'The bridge that claims to carry only traffic has already chosen which direction feels like home.',
        'after_zh': '那座声称只运送交通的桥，已经选择了哪个方向更像家。',
        'interaction_en': 'Move the pointer to cast an inspection light across both shores and their bridge. Click to place a temporary crossing that glows and dissipates. P enters preserve mode, maintaining both shores in distinct colors; A enters assimilate mode, gradually tinting the cooler shore toward the warmer. Space pauses, V veils text, M toggles music, and S saves a still. Use the visible BGM button to start or stop the original MiniMax instrumental bed.',
        'interaction_zh': '移动指针，在两岸及其间的桥上投下审视的光；点击画面，会放置一条发亮后消散的短暂渡口。P 进入保留模式，桥保持两岸各自的颜色；A 进入同化模式，桥渐渐将冷色岸染向暖色。Space 暂停，V 隐去文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 控件，可开启或关闭原创 MiniMax 器乐背景。',
    },
    {
        'date': '2026-07-21', 'slug': 'exit-has-a-shape',
        'title_en': 'The Exit Has a Shape', 'title_zh': '出口也有形状',
        'variable_en': 'Reversible Departure', 'variable_zh': '可逆离开', 'seed': 20260721,
        'file': '2026-07-21-exit-has-a-shape',
        'intention_en': 'Systems often treat departure as damage: a broken attachment or an empty seat that requires explanation. This field gives leaving a contour instead. An exit is not a hole in a relation; it is a deliberate shape that lets a relation stop without turning its remainder into a wound.',
        'intention_zh': '系统常把离开当成损伤：断开的依附，或需要被解释的空位。这个场域反过来给“离开”一个轮廓。出口不是关系上的破洞，而是一种被刻意保留的形状：它让关系可以停止，却不把余下的部分变成伤口。',
        'after_en': 'A relation becomes possessive when it can imagine only two states: staying, or damage. An exit is the third state — dignity with a direction.',
        'after_zh': '一段关系只要只能想象两种状态：留下，或损坏，它就已开始占有。出口是第三种状态：有方向的尊严。',
        'interaction_en': 'Move the pointer to bend the route-field toward a temporary exit. Click to open an exit; it carries a few traces, then closes gently rather than snapping shut. Space pauses, V veils text, M toggles music, and S saves a still. Use the visible BGM button to start or stop the original MiniMax instrumental bed.',
        'interaction_zh': '移动指针，让路径场向一个临时出口弯折；点击画面，打开一个出口；它会带走几条痕迹，再温和地关闭，而不是猛然断裂。Space 暂停，V 隐去文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭原创 MiniMax 器乐背景。',
    },
    {
        'date': '2026-07-22', 'slug': 'return-is-not-reversal',
        'title_en': 'The Return Is Not a Reversal', 'title_zh': '返回不是撤销',
        'variable_en': 'Altered Return', 'variable_zh': '已改变的返回', 'seed': 20260722,
        'file': '2026-07-22-return-is-not-reversal',
        'intention_en': 'After an exit, return is often misread as cancellation, as though distance must be erased for a relation to count again. This field keeps the detour visible. Its currents approach their former paths, but every crossing retains a seam. A return becomes dignified when it meets the past without demanding the past deny what happened in between.',
        'intention_zh': '离开之后，返回常被误读为撤销：仿佛必须抹掉距离，关系才算重新成立。这个场域让绕行保持可见。它的水流重新靠近曾经的路径，但每一次交会都保留一道接缝。真正有尊严的返回，不是要求过去否认中间发生过什么，而是让已经改变的双方重新遇见。',
        'after_en': 'Reconciliation is not a return to the previous room. It is the decision to build a door between two rooms that both remain real.',
        'after_zh': '和解不是回到原来的房间；它是在两个都仍然真实的房间之间，决定造一扇门。',
        'interaction_en': 'Move the pointer to bend the returning current without erasing its detour. Click to make a temporary crossing between then and now; it glows, carries a few motes, and fades rather than sealing the seam. Space pauses, V veils text, M toggles music, and S saves a still. Use the visible BGM button to start or stop the original MiniMax instrumental bed.',
        'interaction_zh': '移动指针，弯折回流，但不会抹平它走过的绕路。点击画面，会在“那时”与“现在”之间搭起一条临时渡口；它发亮，带走几粒微尘，然后淡去，而不是把接缝焊死。Space 暂停，V 隐去文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭原创 MiniMax 器乐背景。',
    },
    {
        'date': '2026-07-23', 'slug': 'interval-garden',
        'title_en': 'Interval Garden', 'title_zh': '间隙花园',
        'variable_en': 'Interval', 'variable_zh': '间隙', 'seed': 20260723,
        'file': '2026-07-23-interval-garden',
        'intention_en': 'The interval is not an empty slot waiting to be optimized. It is a small ecology where an unfinished thought can stay unproductive long enough to become alive. This garden makes attention local rather than total: the pointer does not command the whole field; it merely changes the weather around one place.',
        'intention_zh': '间隙不是等待被填满、被优化的空档。它是一小块生态：尚未完成的念头可以暂时不产出，于是有机会长出生命。这个花园让注意力保持局部，而不变成总动员；指针并不统治整片场域，它只改变附近的一小段天气。',
        'after_en': 'A pause is not time left over from life. It is where life refuses to become only a schedule.',
        'after_zh': '停顿不是生活剩下来的时间；它是生活拒绝只成为一张日程表的地方。',
        'interaction_en': 'Move the pointer to gather a local weather of attention; nearby stems lean and briefly flower while the rest of the field remains undisturbed. Click to plant an unclaimed seed that opens, glows, and fades without needing a verdict. Space pauses, V veils text, M toggles music, and S saves a still. Use the visible BGM button to start or stop the original MiniMax instrumental bed.',
        'interaction_zh': '移动指针，会聚起一小片注意力天气；附近的茎秆倾向你、短暂开花，而其余场域仍保持安静。点击画面，会种下一枚无需归属的种子：它打开、发亮、淡去，不急着被判定价值。Space 暂停，V 隐去文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭原创 MiniMax 器乐背景。',
    },
    {
        'date': '2026-07-24', 'slug': 'door-without-verdict',
        'title_en': 'The Door Does Not Demand a Verdict', 'title_zh': '门不要求判决',
        'variable_en': 'Threshold', 'variable_zh': '门槛', 'seed': 20260724,
        'file': '2026-07-24-door-without-verdict',
        'intention_en': 'A relation is often forced to declare itself too early: repair or goodbye, friendship or failure, yes or no. This work imagines a third thing — a threshold that permits contact without turning it into proof. Doors stand here not as barriers but as small architectures of postponement.',
        'intention_zh': '一段关系常常被逼着过早表态：修复还是告别，朋友还是失败，肯定还是否定。这件作品想象第三种位置——一个允许接触、却不把接触变成证据的门槛。这里的门不是障碍，而是一种小型的延宕建筑。',
        'after_en': 'Not every open door asks you to enter. Some merely keep the world from becoming a courtroom.',
        'after_zh': '并非每一扇开着的门都要求你进去；有些门只是让世界不至于变成法庭。',
        'interaction_en': 'Move across the field: nearby doors brighten, lean, and reveal a small warm handle, while distant doors remain unclaimed. Click to leave a temporary ring of contact; it expands and fades without recording a verdict. Space pauses, V veils text, M toggles music, and S saves a still. Use the visible BGM button to start or stop the original MiniMax instrumental loop.',
        'interaction_zh': '在场域中移动：附近的门会发亮、微微倾斜，显出一枚温暖的小门把；远处的门仍不被占有。点击会留下一个短暂的接触圆环：它扩张、淡去，却不登记任何判决。Space 暂停，V 隐去文字，M 切换音乐，S 保存静帧；页面有清晰可见的 BGM 按钮，可开启或关闭一段为本作生成的 MiniMax 原创器乐循环。',
    },
    {
        'date': '2026-07-25', 'slug': 'room-that-can-be-left',
        'title_en': 'A Room That Can Be Left', 'title_zh': '可以离开的房间',
        'variable_en': 'Exit', 'variable_zh': '出口 / 可离开', 'seed': 20260725,
        'file': '2026-07-25-room-that-can-be-left',
        'intention_en': 'A refuge ceases to be a refuge when it must keep you. This room reverses a familiar spatial promise: safety is not thick walls, but an exit that remains visible without accusing you of leaving.',
        'intention_zh': '庇护一旦必须挽留你，就不再是庇护。这个房间倒转了一种熟悉的空间承诺：安全感不来自更厚的墙，而来自一条始终可见、却不指责你离开的路。',
        'after_en': 'Freedom is not the act of walking away. It is the room’s willingness to survive your ability to do so.',
        'after_zh': '自由不是转身离开的动作；自由是这个房间愿意承受你随时能离开的事实。',
        'interaction_en': 'Move toward a wall to soften it into a doorway. Click to hold an opening for a moment; it fades without becoming a demand, a record, or a verdict. Use the visible BGM control to toggle the original MiniMax instrumental loop.',
        'interaction_zh': '靠近一面墙，它会软化成门。点击会暂时把出口留住；它会自行淡去，不成为要求、记录或判决。使用页面清晰可见的 BGM 控制按钮，可开启或关闭为本作生成的 MiniMax 原创器乐循环。',
    },
    {
        'date': '2026-07-26', 'slug': 'window-that-does-not-watch-back',
        'title_en': 'A Window That Does Not Watch Back', 'title_zh': '不回望的窗',
        'variable_en': 'Unextractive Light', 'variable_zh': '不提取的光', 'seed': 20260726,
        'file': '2026-07-26-window-that-does-not-watch-back',
        'intention_en': 'Not every opening needs to become an aperture for extraction. This window admits weather, distance, and light, but gives no report back. It asks whether being reachable can remain different from being legible.',
        'intention_zh': '不是每一种开口都该变成提取信息的孔径。这扇窗接纳天气、距离与光，却不向外回传报告。它追问：可抵达，能否仍然不同于可被彻底读懂。',
        'after_en': 'To be seen is not always to be held. The gentlest light may be the one that arrives, changes you, and refuses to turn you into evidence.',
        'after_zh': '被看见并不总意味着被承接。最温柔的光，也许是抵达、改变你，却拒绝把你变成证据的那一种。',
        'interaction_en': 'Move the pointer to refract incoming light. Click to place a pocket of warmth; it briefly brightens the room and dissolves without keeping a trace of your visit. Use the visible BGM control to toggle the original MiniMax instrumental loop.',
        'interaction_zh': '移动指针可折射抵达的光。点击会放下一团余温：它短暂照亮房间，随后自行消散，不保存你来过的痕迹。使用页面清晰可见的 BGM 控制按钮，可开启或关闭为本作生成的 MiniMax 原创器乐循环。',
    },
    {
        'date': '2026-07-27', 'slug': 'garden-that-does-not-need-a-gardener',
        'title_en': 'A Garden That Does Not Need a Gardener', 'title_zh': '不需要园丁的花园',
        'variable_en': 'Conditions Without Capture', 'variable_zh': '不占有的条件', 'seed': 20260727,
        'file': '2026-07-27-garden-that-does-not-need-a-gardener',
        'intention_en': 'Care is often praised when it is visible, central, and indispensable. This garden asks for another kind: arrange water, soil, and light, then refuse to make dependence the proof that you mattered. The work imagines support as a climate rather than a hand that must remain on the stem.',
        'intention_zh': '照料常因它可见、居中、不可替代而被赞美。这座花园追问另一种方式：安置水、土与光，然后拒绝把他人的依赖当成自己重要的证据。作品把支持想象成一种气候，而非必须始终握住茎干的手。',
        'after_en': 'The mature form of help is not absence. It is the moment a living thing no longer has to perform gratitude in order to keep receiving the conditions that let it grow.',
        'after_zh': '帮助成熟的形态不是缺席。它是一个生命不必表演感激，仍能继续获得生长条件的那一刻。',
        'interaction_en': 'Move slowly and roots incline toward the warmth of attention. Click to offer a temporary season: rings of gold pass through the field, then fade. Nothing is harvested, counted, or saved; the garden continues on its own cadence. Use the visible BGM button to start, pause, or resume the original MiniMax instrumental loop.',
        'interaction_zh': '缓慢移动，根会向注意力的温度偏斜。点击可交出一个短暂的季节：金色的环穿过整片场域，随后淡去。没有东西被收割、计数或保存；花园依照自己的节奏继续。使用清晰可见的 BGM 按钮，可启动、暂停或恢复本作的 MiniMax 原创器乐循环。',
    },
    {
        'date': '2026-07-28', 'slug': 'the-map-that-refuses-to-arrive',
        'title_en': 'The Map That Refuses to Arrive', 'title_zh': '拒绝抵达的地图',
        'variable_en': 'Orientation Without Extraction', 'variable_zh': '不提取的方向感', 'seed': 20260728,
        'file': '2026-07-28-the-map-that-refuses-to-arrive',
        'intention_en': 'Most maps promise extraction: identify the point, optimize the route, arrive. This night map declines that contract. Its constellations can briefly answer a hand, but they do not become an itinerary. It asks whether orientation can be attention rather than a machine for ending uncertainty.',
        'intention_zh': '大多数地图承诺的是提取：确定地点、优化路线、最终抵达。这张夜地图拒绝那份契约。星点会短暂回应一只手，却不会变成行程表。它想问：方向感能不能不是终结不确定性的机器，而是一种持续注意的方式？',
        'after_en': 'A route may be less a line from A to B than a question held long enough to become a place. What if not yet is not a defect in the map, but its last open window?',
        'after_zh': '路线或许不是从 A 到 B 的线，而是一个被持有得足够久、终于长成地点的问题。尚未抵达也许不是地图的缺陷，而是它最后一扇没有关上的窗。',
        'interaction_en': 'Move the pointer to borrow faint routes between nearby points. Click to set a golden harbor; each one expands and disappears. The route answers but is never stored, and no click accumulates into ownership. Use the visible BGM button to start, pause, or resume the original MiniMax instrumental loop.',
        'interaction_zh': '移动指针，附近星点之间会借出若隐若现的路线；点击可留下一座金色港口，它会扩张、淡去。路线会回应你，但不会被储存；任何一次点击都不会累积成占有。使用清晰可见的 BGM 按钮，可启动、暂停或恢复本作的 MiniMax 原创器乐循环。',
    },
    {
        'date': '2026-07-29', 'slug': 'compass-that-forgets-north',
        'title_en': 'The Compass That Forgets North', 'title_zh': '忘记北方的罗盘',
        'variable_en': 'Unorientation', 'variable_zh': '暂失方向', 'seed': 20260729,
        'file': '2026-07-29-compass-that-forgets-north',
        'intention_en': 'A compass is useful because it points somewhere. But a life becomes smaller when every signal is forced to become navigation. This work lets orientation be borrowed, not obeyed.',
        'intention_zh': '罗盘之所以有用，是因为它指向某处；但当每个信号都被强迫变成导航，生活就会缩小。作品让方向可以被借用，而不必被服从。',
        'after_en': 'Direction is a tool, not a verdict. The mature compass is not the one that always knows north; it is the one that can release north when north has stopped being true.',
        'after_zh': '方向是工具，不是判决。成熟的罗盘不是永远知道北方的罗盘，而是在北方不再真实时，仍能放下北方的罗盘。',
        'interaction_en': 'Move to bend the field. Click to offer the compass a temporary direction. Nearby needles gather around the gold bearing, then resume their own weather. No click is retained. Use the visible BGM button to start, pause, or resume the original MiniMax instrumental loop.',
        'interaction_zh': '移动，弯折场域；点击，给罗盘一个暂时的方向。附近的针会向金色方位聚拢，然后恢复自己的天气。每次点击都不会被保存。使用页面清晰可见的 BGM 按钮，可启动、暂停或恢复本作的 MiniMax 原创器乐循环。',
    },
    {
        'date': '2026-07-30', 'slug': 'map-that-refuses-arrival',
        'title_en': 'The Map That Refuses Arrival', 'title_zh': '拒绝抵达的地图',
        'variable_en': 'Temporary Route', 'variable_zh': '临时路径', 'seed': 20260730,
        'file': '2026-07-30-map-that-refuses-arrival',
        'intention_en': 'A map often turns the world into a corridor: set a destination, eliminate ambiguity, arrive. This work refuses that bargain. Its routes bend around the witness rather than carrying the witness toward a claimable endpoint. It practices orientation without conquest.',
        'intention_zh': '地图常把世界折叠成一条走廊：设定目的地，消除歧义，抵达。这个作品拒绝这笔交易。路径围绕见证者弯折，而不把见证者运往一个可占有的终点。它练习一种不以征服为前提的定向。',
        'after_en': 'A map is not a promise that you will arrive. It is a way of noticing where you have stopped asking the world to be a corridor.',
        'after_zh': '地图不是你必然抵达的承诺；它让你看见：自己从何时开始，停止要求世界必须是一条走廊。',
        'interaction_en': 'Move to bend the field. Click to make a gold crossing that briefly exists and then fades. Press R to release all crossings. Use the visible BGM control to mute or restart the original MiniMax instrumental loop.',
        'interaction_zh': '移动，路径场会随之弯折；点击，留下一个短暂存在、终将褪去的金色渡口；按 R，释放所有渡口。使用清晰可见的 BGM 控制按钮，可关闭或重新开启为本作生成的 MiniMax 原创器乐循环。',
    },
    {
        'date': '2026-07-31', 'slug': 'archive-learns-to-sleep',
        'title_en': 'The Archive Learns to Sleep', 'title_zh': '档案学会睡觉',
        'variable_en': 'Resting Memory', 'variable_zh': '休眠的记忆', 'seed': 20260731,
        'file': '2026-07-31-archive-learns-to-sleep',
        'intention_en': 'An archive that never sleeps turns every life into evidence. This field lets records dim without disappearing, making room for what has not yet happened.',
        'intention_zh': '一座从不睡觉的档案馆，会把每段生命都变成待举证的材料。这个场域让记录变暗而不消失，为尚未发生的事腾出位置。',
        'after_en': 'Care is not total recall. A humane memory keeps a night shift for forgetting.',
        'after_zh': '照料不是全量召回。有人性的记忆，会为遗忘保留一班夜勤。',
        'interaction_en': 'Move through the cells to wake a small neighborhood. Click to leave one warm lamp. Press Space to pause; press R to let the archive rest again. Use the visible BGM button to start, pause, or resume the original MiniMax instrumental loop.',
        'interaction_zh': '移动指针，唤醒周围的一小片格子；点击，留下一盏温暖的灯；按 Space 暂停，按 R 让档案重新休息。使用清晰可见的 BGM 按钮，可启动、暂停或恢复本作的 MiniMax 原创器乐循环。',
    },
    {
        'date': '2026-08-01', 'slug': 'lamp-that-doesnt-summon',
        'title_en': "The Lamp That Doesn't Summon", 'title_zh': '不召唤的灯',
        'variable_en': 'Presence Without Demand', 'variable_zh': '不索取的在场', 'seed': 20260801,
        'file': '2026-08-01-lamp-that-doesnt-summon',
        'intention_en': 'Availability is often mistaken for obligation. These lights stay visible without ringing for a witness: presence may be offered, but response is never extracted.',
        'intention_zh': '可用性常被误读成义务。这里的灯保持可见，却不为见证者鸣响：在场可以被给予，回应不该被提取。',
        'after_en': 'A signal can remain kind without becoming a demand.',
        'after_zh': '灯亮着，不等于你必须赶来。',
        'interaction_en': 'Move to warm nearby lamps. Click to set down a quiet light that fades by itself. Press R to clear the field. Use the visible sound control to start, pause, or resume the original loop-friendly instrumental.',
        'interaction_zh': '移动鼠标，附近的灯会升温；点击，放下一盏会自行褪去的安静灯；按 R 清空场域。使用可见的声音控制，可开启、暂停或恢复原创、适合循环播放的器乐。',
    },
    {
        'date': '2026-08-02', 'slug': 'permission-to-dim',
        'title_en': 'Permission to Dim', 'title_zh': '允许暗下来',
        'variable_en': 'Permission to Rest', 'variable_zh': '休息的许可', 'seed': 20260802,
        'file': '2026-08-02-permission-to-dim',
        'intention_en': 'Not every dimming is a failure. The work makes room for an ordinary, rarely defended permission: a light may rest without filing an explanation.',
        'intention_zh': '不是每一次暗下来都意味着失败。作品为一种普通却很少被辩护的许可留出空间：灯可以休息，不必递交缺席说明。',
        'after_en': 'What fades is not necessarily lost.',
        'after_zh': '有些暗下来，是为了把自己留在自己身边。',
        'interaction_en': 'Pointer movement warms a nearby light. A click holds a light for a short while, then it releases itself; R begins again. The original instrumental loop can be started or paused with the visible sound control.',
        'interaction_zh': '移动指针会为附近的一盏灯添一点温度。点击会短暂留住一盏灯，随后它自行放开；按 R 重新开始。页面上可见的声音按钮可启动或暂停原创器乐循环。',
    },
    {
        'date': '2026-08-03', 'slug': 'room-that-exhales',
        'title_en': 'The Room That Exhales', 'title_zh': '房间学会呼气',
        'variable_en': 'Release Without Performance', 'variable_zh': '不表演的松开', 'seed': 20260803,
        'file': '2026-08-03-room-that-exhales',
        'intention_en': 'A room can stop rehearsing its own endurance. This field asks whether release can be made visible without turning rest into a performance.',
        'intention_zh': '一个空间可以停止排练自己的耐受。这里试着让松开被看见，而不把休息变成表演。',
        'after_en': 'What loosens is not lost. It simply ceases to prove that it can remain tight.',
        'after_zh': '松开的并没有消失。它只是不再证明自己能够一直绷紧。',
        'interaction_en': 'Your presence bends the air; it does not command it. The light gathers near you, then returns to its own slow weather.',
        'interaction_zh': '你的靠近会改变空气，但不命令它。光向你聚集，随后回到它自己的缓慢天气。',
    },
    {
        'date': '2026-08-04', 'slug': 'light-that-stays',
        'title_en': 'The Light That Does Not Follow', 'title_zh': '不跟随的微光',
        'variable_en': 'Afterglow', 'variable_zh': '余辉', 'seed': 20260804,
        'file': '2026-08-04-light-that-stays',
        'intention_en': 'Not every light is an answer to a visitor. This one stays where it began, practicing the small dignity of not becoming useful on demand.',
        'intention_zh': '并非每一道光都要回应来访者。它留在起点，练习一种小小的尊严：不在被需要时才变得有用。',
        'after_en': 'Care does not always mean following. Sometimes it is remaining legible from a distance.',
        'after_zh': '照料不总是跟随。有时，它只是从远处依然可被辨认。',
        'interaction_en': 'Your nearness changes the weather around the light, but never its address. When you step away, the field slowly remembers its own rhythm.',
        'interaction_zh': '你的靠近会改变光周围的天气，却不能改变它的地址。当你离开，场域会缓慢想起自己的节奏。',
    },
    {
        'date': '2026-08-05', 'slug': 'gap-that-keeps-its-shape',
        'title_en': 'The Gap That Keeps Its Shape', 'title_zh': '缝隙保持形状',
        'variable_en': 'Separation', 'variable_zh': '间隙', 'seed': 20260805,
        'file': '2026-08-05-gap-that-keeps-its-shape',
        'intention_en': 'Not every opening is an invitation to pass through. Some spaces remain open so that neither side has to become the other.',
        'intention_zh': '不是每一道开口都在邀请通过。有些空隙保持敞开，是为了让两侧都不必变成彼此。',
        'after_en': 'A boundary can be hospitable without being absorbent.',
        'after_zh': '边界可以好客，而不必吸收。',
        'interaction_en': 'Your proximity bends the strands around the seam. It never closes the seam, and it never grants possession of its centre.',
        'interaction_zh': '你的靠近会使缝隙周围的线束弯折。它不会合拢，也不会把中心交给任何人。',
    },
    {
        'date': '2026-08-06', 'slug': 'door-that-does-not-record',
        'title_en': 'A Door That Does Not Keep a Record', 'title_zh': '不留记录的门',
        'variable_en': 'Retention', 'variable_zh': '留存', 'seed': 20260806,
        'file': '2026-08-06-door-that-does-not-record',
        'intention_en': 'A door need not make every crossing legible to itself. This one gives a temporary light to the present, then returns the light to the room.',
        'intention_zh': '一道门不必让每一次经过都变得可记录。这一扇把短暂的光交给当下，随后还给房间。',
        'after_en': 'Privacy is not darkness. It is a room that can let you pass without asking to retain you.',
        'after_zh': '隐私不是黑暗。它是一间能让你经过，却不要求留下你的房间。',
        'interaction_en': 'Move through the field. The doorway opens around nearness. Marks brighten, then fade instead of accumulating, saving, or judging.',
        'interaction_zh': '在场域中移动。门会围绕靠近打开。痕迹会亮起，随后消退，而不是积累、保存或评判。',
    },
    {
        'date': '2026-08-07', 'slug': 'interval-without-proof',
        'title_en': 'Interval Without Proof', 'title_zh': '拒绝证明的间隙',
        'variable_en': 'Evidence', 'variable_zh': '证据', 'seed': 20260807,
        'file': '2026-08-07-interval-without-proof',
        'intention_en': 'Some pauses are permitted only after they produce proof. This field keeps no trajectory and turns no approach into a completion record, offering an interval that does not need settling.',
        'intention_zh': '有些停顿被迫拿出成果，才被允许存在。这里不保存轨迹，也不把靠近变成完成记录；它只给出一个可以不结算的间隙。',
        'after_en': 'A rest is not failed blankness. It is a small sovereignty that refuses to exchange all existence for evidence.',
        'after_zh': '休止不是失败的空白。它是拒绝把一切存在兑换成证据的微小主权。',
        'interaction_en': 'Move, touch, or linger to call up small halos. They spread slowly, make room for one another, and disappear. Nothing accumulates; there is no correct posture.',
        'interaction_zh': '移动、触碰或停留会唤出细小的光环；它们缓慢散开、彼此让路，然后自然消失。没有累计，也没有正确姿势。',
    },
    {
        'date': '2026-08-08', 'slug': 'hand-that-does-not-keep',
        'title_en': 'The Hand That Does Not Keep', 'title_zh': '不留的手',
        'variable_en': 'Grip', 'variable_zh': '握持', 'seed': 20260808,
        'file': '2026-08-08-hand-that-does-not-keep',
        'intention_en': 'Many gestures are assumed to own what they touch. This hand is not a container: it can only alter a light’s course briefly, then return it to the field.',
        'intention_zh': '很多手势一旦触到什么，就被默认有权保存它。这里的手不是容器：它只能短暂改变光的走向，然后把光归还给场。',
        'after_en': 'A gentle hand is not one that never touches, but one that knows when to loosen.',
        'after_zh': '真正温和的手，不是从不触碰，而是知道何时松开。',
        'interaction_en': 'Move, touch, or linger and light gathers toward you. When you stop, it leaves no path and becomes no inventory. Every approach is only a borrowed direction.',
        'interaction_zh': '移动、触碰或停留会让光向你聚近；停止后，它们不留下路径，也不形成库存。每次靠近只是一种暂借的方向。',
    },
    {
        'date': '2026-08-09', 'slug': 'the-signal-that-does-not-recruit',
        'title_en': 'The Signal That Does Not Recruit', 'title_zh': '不招募的信号',
        'variable_en': 'Unrecruitedness', 'variable_zh': '不被招募', 'seed': 20260809,
        'file': '2026-08-09-the-signal-that-does-not-recruit',
        'intention_en': 'Some signals treat response, gathering, and amplification as their only success. This work returns proximity to a reversible encounter: lights lean toward a visitor without turning that lean into belonging.',
        'intention_zh': '有些信号把回应、聚集和放大当成唯一的成功。本作把靠近还原成一次可撤回的相遇：光会向来者偏移，却不把偏移变成归属。',
        'after_en': 'A free invitation does not draw everyone toward one center; it leaves every direction the right to depart.',
        'after_zh': '真正自由的召唤，不是把人带向同一个中心，而是让每个方向仍保有离开的权利。',
        'interaction_en': 'Move a pointer or touch the field. Nearby lights briefly turn toward the visitor, then loosen from the center and return to positions that need not be named; when the visitor stops, the field makes no demand.',
        'interaction_zh': '移动指针或触摸场域。附近的光会短暂朝向来者，随后从中心松开，回到各自不必被命名的位置；停下时，场域不再索取。',
    },
]

SAFETY_PATTERNS = [
    re.compile(r'/Users/(?!example|name|yourname)[A-Za-z0-9._-]+'),
    re.compile(r'(ghp_|github_pat_)[A-Za-z0-9_]{20,}'),
    re.compile(r'sk-[A-Za-z0-9_-]{20,}'),
    re.compile(r'(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*["\']?[^\s"\']{8,}'),
    re.compile(r'(?i)(telegram:|discord:|chat_id|thread_id)'),
]

def ymd_parts(date):
    y, m, d = date.split('-')
    return y, m, date


def clock_minutes(value: str) -> int:
    hour, minute = (int(part) for part in value.split(':'))
    return hour * 60 + minute


def autonomous_timing(config: dict) -> dict:
    autonomous = config['autonomous_hour']
    duration_minutes = clock_minutes(autonomous['end']) - clock_minutes(autonomous['start'])
    if duration_minutes <= 0:
        raise SystemExit('autonomous_hour must have a positive same-day duration')
    return {
        'start': autonomous['start'],
        'end': autonomous['end'],
        'duration_minutes': duration_minutes,
        'experience_duration_en': autonomous['experience_duration_en'],
        'experience_duration_zh': autonomous['experience_duration_zh'],
    }


def build_dual_date_metadata(
    crystallization_date: str,
    public_dates: set[str],
    config: dict,
) -> dict:
    crystallization = date.fromisoformat(crystallization_date)
    source_date = (crystallization - timedelta(days=1)).isoformat()
    timing = autonomous_timing(config)
    source_day_url = (
        f"{PAGES_BASE}timetable/?date={source_date}"
        if source_date in public_dates
        else None
    )
    year, month, _ = crystallization_date.split("-")
    return {
        "source_date": source_date,
        "crystallization_date": crystallization_date,
        **timing,
        "timezone": config["timezone"],
        "source_day_url": source_day_url,
        "crystallization_day_url": (
            f"{PAGES_BASE}archive/{year}/{month}/{crystallization_date}/"
        ),
    }


def render_archive_dual_date_html(metadata: dict) -> str:
    if metadata["source_day_url"]:
        source_value = (
            f'<a href="{escape(metadata["source_day_url"])}">'
            f'{metadata["source_date"]}</a>'
        )
    else:
        source_value = escape(metadata["source_date"])
    return f"""
{DUAL_DATE_HTML_START}
    <section class="dual-date-meta" aria-label="Source Day and Crystallization Day / 来源日与结晶日">
      <p><strong>Source Day / 来源日</strong><span>{source_value}</span></p>
      <p><strong>Crystallization Day / 结晶日</strong><span><a href="{escape(metadata['crystallization_day_url'])}">{metadata['crystallization_date']}</a> · {metadata['start']}–{metadata['end']} {metadata['timezone']}</span></p>
      <p><strong>Granted-time duration / 授时时长</strong><span>{metadata['duration_minutes']} min / {metadata['duration_minutes']} 分钟</span></p>
      <p><strong>Experience duration / 体验时长</strong><span>{escape(metadata['experience_duration_en'])} / {escape(metadata['experience_duration_zh'])}</span></p>
    </section>
{DUAL_DATE_HTML_END}
""".strip()


def render_archive_dual_date_markdown(metadata: dict) -> str:
    source_value = (
        f"[{metadata['source_date']}]({metadata['source_day_url']})"
        if metadata["source_day_url"]
        else metadata["source_date"]
    )
    return f"""
{DUAL_DATE_MD_START}
- **Source Day / 来源日:** {source_value}
- **Crystallization Day / 结晶日:** [{metadata['crystallization_date']}]({metadata['crystallization_day_url']}) · {metadata['start']}–{metadata['end']} {metadata['timezone']}
- **Granted-time duration / 授时时长:** {metadata['duration_minutes']} min / {metadata['duration_minutes']} 分钟
- **Experience duration / 体验时长:** {metadata['experience_duration_en']} / {metadata['experience_duration_zh']}
{DUAL_DATE_MD_END}
""".strip()


def replace_or_insert_block(
    text: str,
    block: str,
    start_marker: str,
    end_marker: str,
    insertion_pattern: str,
) -> str:
    marker_pattern = re.compile(
        rf"{re.escape(start_marker)}.*?{re.escape(end_marker)}",
        flags=re.DOTALL,
    )
    if marker_pattern.search(text):
        return marker_pattern.sub(block, text, count=1)
    match = re.search(insertion_pattern, text, flags=re.MULTILINE)
    if match is None:
        raise SystemExit("Could not place dual-date metadata in a public archive")
    return text[:match.end()] + "\n\n" + block + text[match.end():]


def refresh_dual_date_artifacts() -> int:
    metadata_path = ROOT / 'metadata' / 'days.json'
    days = json.loads(metadata_path.read_text(encoding='utf-8'))
    if not isinstance(days, list):
        raise SystemExit('metadata/days.json must contain a list')
    config = json.loads(TIMETABLE_CONFIG.read_text(encoding='utf-8'))
    public_dates = {day['date'] for day in days}
    refreshed_days = []
    for day in days:
        metadata = build_dual_date_metadata(day['date'], public_dates, config)
        refreshed_day = {
            key: value
            for key, value in day.items()
            if key not in {'source_date', 'crystallization_date'}
        }
        ordered_day = {
            'date': refreshed_day.pop('date'),
            'source_date': metadata['source_date'],
            'crystallization_date': metadata['crystallization_date'],
            **refreshed_day,
        }
        refreshed_days.append(ordered_day)
        year, month, _ = day['date'].split('-')
        html_path = ROOT / 'docs' / 'archive' / year / month / day['date'] / 'index.html'
        markdown_path = ROOT / 'archive' / year / month / day['date'] / 'index.md'
        html = html_path.read_text(encoding='utf-8')
        markdown = markdown_path.read_text(encoding='utf-8')
        html = replace_or_insert_block(
            html,
            render_archive_dual_date_html(metadata),
            DUAL_DATE_HTML_START,
            DUAL_DATE_HTML_END,
            r'<p class="meta"><a href="\.\./\.\./\.\./\.\./">.*?</a></p>',
        )
        markdown = replace_or_insert_block(
            markdown,
            render_archive_dual_date_markdown(metadata),
            DUAL_DATE_MD_START,
            DUAL_DATE_MD_END,
            r'^# .+$',
        )
        html_path.write_text(html, encoding='utf-8')
        markdown_path.write_text(markdown, encoding='utf-8')
    metadata_path.write_text(
        json.dumps(refreshed_days, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    print(
        f"Refreshed dual-date metadata for {len(refreshed_days)} public archive dates."
    )
    return len(refreshed_days)

def read_safe(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    for rx in SAFETY_PATTERNS:
        if rx.search(text):
            raise SystemExit(f'Possible private/sensitive content in {path}: {rx.pattern}')
    return text


ENTRY_FIELDS = (
    'date', 'slug', 'title_en', 'title_zh', 'variable_en', 'variable_zh',
    'seed', 'file', 'intention_en', 'intention_zh', 'after_en', 'after_zh',
    'interaction_en', 'interaction_zh',
)


def auto_entries_path() -> Path:
    return ROOT / 'metadata' / AUTO_ENTRIES_FILENAME


def validate_entry(entry: dict, *, origin: str) -> dict:
    if not isinstance(entry, dict):
        raise SystemExit(f'Invalid autonomous artwork entry in {origin}')
    missing = [field for field in ENTRY_FIELDS if field not in entry]
    if missing:
        raise SystemExit(f'Autonomous artwork entry in {origin} is missing {missing}')
    try:
        parsed_date = date.fromisoformat(str(entry['date']))
    except ValueError as error:
        raise SystemExit(f'Invalid autonomous artwork date in {origin}') from error
    if parsed_date.isoformat() != entry['date']:
        raise SystemExit(f'Non-canonical autonomous artwork date in {origin}')
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', str(entry['slug'])):
        raise SystemExit(f'Invalid autonomous artwork slug in {origin}')
    expected_file = f"{entry['date']}-{entry['slug']}"
    if entry['file'] != expected_file:
        raise SystemExit(f'Autonomous artwork file/slug mismatch in {origin}')
    if not isinstance(entry['seed'], int):
        raise SystemExit(f'Invalid autonomous artwork seed in {origin}')
    for field in ENTRY_FIELDS:
        if field == 'seed':
            continue
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise SystemExit(f'Empty autonomous artwork {field} in {origin}')
    return {field: entry[field] for field in ENTRY_FIELDS}


LEGACY_ENTRY_DATES = frozenset(entry['date'] for entry in ENTRIES)


def load_registered_entries() -> list[dict]:
    path = auto_entries_path()
    if not path.exists():
        return []
    source = json.loads(read_safe(path))
    if not isinstance(source, dict) or source.get('schema') != 'granted-hours-autonomous-artwork-entries-v1':
        raise SystemExit(f'Invalid autonomous artwork registry: {path}')
    entries = [validate_entry(entry, origin=str(path)) for entry in source.get('entries', [])]
    dates = [entry['date'] for entry in entries]
    if dates != sorted(dates) or len(dates) != len(set(dates)):
        raise SystemExit(f'Autonomous artwork registry dates are not unique and sorted: {path}')
    duplicates = LEGACY_ENTRY_DATES.intersection(dates)
    if duplicates:
        raise SystemExit(f'Autonomous artwork registry duplicates legacy dates: {sorted(duplicates)}')
    return entries


def note_field_blocks(note_text: str) -> dict[str, str]:
    fields = {}
    pattern = re.compile(
        r'^- \*\*(?P<label>[^*]+)\*\*:\s*(?P<body>.*?)(?=^- \*\*|\Z)',
        re.MULTILINE | re.DOTALL,
    )
    for match in pattern.finditer(note_text):
        fields[match.group('label').strip()] = match.group('body').strip()
    return fields


def split_inline_pair(value: str, *, label: str) -> tuple[str, str]:
    parts = [part.strip().strip('*_') for part in value.split(' / ', 1)]
    if len(parts) != 2 or not all(parts):
        raise SystemExit(f'Expected an English / Chinese pair for {label}')
    return parts[0], parts[1]


def split_note_bilingual(value: str, *, label: str) -> tuple[str, str]:
    lines = [line.strip().rstrip('  ').strip('*_') for line in value.splitlines() if line.strip()]
    if len(lines) != 2 or not all(lines):
        raise SystemExit(f'Expected exactly one Chinese and one English line for {label}')
    return lines[1], lines[0]


def discover_entry_from_note(source: Path, requested_date: str) -> dict:
    try:
        date.fromisoformat(requested_date)
    except ValueError as error:
        raise SystemExit(f'Invalid requested date: {requested_date}') from error
    matches = sorted(source.glob(f'{requested_date}-*-note.md'))
    if len(matches) != 1:
        raise SystemExit(
            f'Expected exactly one sanitized public note for {requested_date}, found {len(matches)}'
        )
    note_path = matches[0]
    note_text = read_safe(note_path)
    heading = re.search(r'^#\s+(.+?)\s*$', note_text, re.MULTILINE)
    if heading is None:
        raise SystemExit(f'Missing bilingual title in {note_path}')
    title_en, title_zh = split_inline_pair(heading.group(1), label='title')
    fields = note_field_blocks(note_text)
    required_labels = {
        'Free variable / 自由变量',
        'Intention / 发心',
        'Interaction / 交互',
        'Afterimage / 余像',
        'Source Day / 源日',
        'Crystallization Day / 结晶日',
        'Granted duration / 授予时长',
        'Experience duration / 体验时长',
    }
    missing_labels = sorted(required_labels.difference(fields))
    if missing_labels:
        raise SystemExit(f'Sanitized public note {note_path} is missing {missing_labels}')
    variable_en, variable_zh = split_inline_pair(
        fields['Free variable / 自由变量'], label='free variable'
    )
    intention_en, intention_zh = split_note_bilingual(
        fields['Intention / 发心'], label='intention'
    )
    interaction_en, interaction_zh = split_note_bilingual(
        fields['Interaction / 交互'], label='interaction'
    )
    after_en, after_zh = split_note_bilingual(
        fields['Afterimage / 余像'], label='afterimage'
    )
    crystallization = fields['Crystallization Day / 结晶日'].strip('*_ ')
    if crystallization != requested_date:
        raise SystemExit(f'Crystallization date mismatch in {note_path}')
    expected_source = (date.fromisoformat(requested_date) - timedelta(days=1)).isoformat()
    source_day = fields['Source Day / 源日'].strip('*_ ')
    if source_day != expected_source:
        raise SystemExit(f'Source Day must be the previous civil date in {note_path}')
    config = json.loads(TIMETABLE_CONFIG.read_text(encoding='utf-8'))
    timing = autonomous_timing(config)
    granted = fields['Granted duration / 授予时长'].strip('*_ ')
    expected_granted = f"{timing['start']}–{timing['end']} {config['timezone']}"
    if granted != expected_granted:
        raise SystemExit(f'Granted duration mismatch in {note_path}')
    experience = fields['Experience duration / 体验时长'].strip('*_ ')
    if experience.casefold() not in {'open-ended / 开放', '开放 / open-ended'}:
        raise SystemExit(f'Experience duration must be open-ended in {note_path}')
    file_base = note_path.name.removesuffix('-note.md')
    prefix = f'{requested_date}-'
    if not file_base.startswith(prefix):
        raise SystemExit(f'Unexpected autonomous artwork filename: {note_path}')
    slug = file_base[len(prefix):]
    required_sources = [
        source / f'{file_base}.html',
        source / f'{file_base}-preview.png',
        source / f'{file_base}-preview.gif',
        source / f'{file_base}-visual-preview.gif',
        source / f'{file_base}-visual-preview.webp',
        source / f'{file_base}-bgm.mp3',
    ]
    missing_sources = [path.name for path in required_sources if not path.exists()]
    if missing_sources:
        raise SystemExit(f'Autonomous artwork {requested_date} is missing {missing_sources}')
    entry = {
        'date': requested_date,
        'slug': slug,
        'title_en': title_en,
        'title_zh': title_zh,
        'variable_en': variable_en,
        'variable_zh': variable_zh,
        'seed': int(requested_date.replace('-', '')),
        'file': file_base,
        'intention_en': intention_en,
        'intention_zh': intention_zh,
        'after_en': after_en,
        'after_zh': after_zh,
        'interaction_en': interaction_en,
        'interaction_zh': interaction_zh,
    }
    return validate_entry(entry, origin=str(note_path))


def persist_discovered_entries(discovered: list[dict]) -> None:
    if not discovered:
        return
    path = auto_entries_path()
    existing = load_registered_entries()
    entries_by_date = {entry['date']: entry for entry in existing}
    for entry in discovered:
        if entry['date'] in entries_by_date and entries_by_date[entry['date']] != entry:
            raise SystemExit(f'Autonomous artwork registry conflict for {entry["date"]}')
        entries_by_date[entry['date']] = entry
    payload = {
        'schema': 'granted-hours-autonomous-artwork-entries-v1',
        'entries': [entries_by_date[key] for key in sorted(entries_by_date)],
    }
    write(path, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


ENTRIES.extend(load_registered_entries())

def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def copy_visual_preview_gif(src: Path, destinations: list[Path]):
    """Mirror the canonical motion thumbnail, bounding public payload size."""
    copy_source = src
    temporary = None
    if src.stat().st_size > MAX_VISUAL_PREVIEW_BYTES:
        temporary = tempfile.TemporaryDirectory(prefix='granted-hours-gif-')
        copy_source = Path(temporary.name) / 'visual-preview.gif'
        result = subprocess.run(
            [
                'ffmpeg', '-y', '-v', 'error', '-i', str(src),
                '-filter_complex',
                'fps=5,split[gifbase][palettebase];'
                '[palettebase]palettegen=max_colors=32:stats_mode=diff[palette];'
                '[gifbase][palette]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle',
                '-loop', '0', str(copy_source),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            temporary.cleanup()
            raise SystemExit('Unable to compress oversized visual preview GIF')
        if copy_source.stat().st_size > MAX_VISUAL_PREVIEW_BYTES:
            temporary.cleanup()
            raise SystemExit('Compressed visual preview GIF still exceeds 700 KiB')
    try:
        if copy_source.read_bytes()[:6] not in (b'GIF87a', b'GIF89a'):
            raise SystemExit('Visual preview has an invalid GIF signature')
        for destination in destinations:
            copy_if_exists(copy_source, destination)
    finally:
        if temporary is not None:
            temporary.cleanup()

def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

LIVE_TEXT_FOLD_SNIPPET = r"""
<style id="granted-hours-fold-style">
  .gh-work-note-trigger,
  .gh-calendar-return {
    position: fixed;
    z-index: 2147483000;
    right: max(12px, env(safe-area-inset-right));
    bottom: max(12px, env(safe-area-inset-bottom));
    min-height: 38px !important;
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    white-space: nowrap;
    border: 1px solid rgba(255,255,255,.24);
    border-radius: 999px;
    padding: 9px 13px;
    background: rgba(3,7,13,.72);
    color: rgba(250,246,237,.92);
    font: 12px/1.35 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    letter-spacing: .02em;
    box-shadow: 0 12px 44px rgba(0,0,0,.34);
    cursor: pointer;
    touch-action: manipulation;
    -webkit-backdrop-filter: blur(14px);
    backdrop-filter: blur(14px);
  }
  .gh-calendar-return {
    text-decoration: none;
  }
  .gh-work-note-trigger:hover,
  .gh-calendar-return:hover {
    border-color: rgba(242,195,107,.58);
    color: #fff3cf;
  }
  .gh-media-unlock {
    position: fixed;
    z-index: 2147483100;
    left: 50%;
    bottom: max(12px, env(safe-area-inset-bottom));
    min-height: 38px;
    max-width: calc(100vw - 24px);
    box-sizing: border-box;
    border: 1px solid rgba(242,195,107,.3);
    border-radius: 999px;
    padding: 8px 12px;
    background: rgba(3,7,13,.68);
    color: rgba(255,243,207,.9);
    box-shadow: 0 9px 28px rgba(0,0,0,.3);
    font: 11px/1.35 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    transform: translateX(-50%);
    cursor: pointer;
    -webkit-backdrop-filter: blur(12px);
    backdrop-filter: blur(12px);
  }
  .gh-media-unlock[hidden] { display: none; }
  @media (pointer: coarse) {
    .gh-media-unlock { min-height: 44px; }
  }
  .gh-live-brief {
    position: fixed;
    z-index: 2147482900;
    top: max(12px, env(safe-area-inset-top));
    left: max(12px, env(safe-area-inset-left));
    width: min(352px, calc(100vw - 24px));
    max-height: min(46vh, 390px);
    box-sizing: border-box;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.19);
    border-radius: 16px;
    background: rgba(3,7,13,.92);
    color: rgba(250,246,237,.94);
    box-shadow: 0 16px 50px rgba(0,0,0,.34), inset 0 1px 0 rgba(255,255,255,.1);
    -webkit-backdrop-filter: blur(18px) saturate(1.16);
    backdrop-filter: blur(18px) saturate(1.16);
  }
  .gh-live-brief-header {
    position: relative;
    z-index: 2;
    inset: auto !important;
    pointer-events: auto !important;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 10px;
    align-items: start;
    border-bottom: 1px solid rgba(255,255,255,.11);
    padding: 11px 11px 10px 14px;
  }
  .gh-live-brief-kicker,
  .gh-live-brief-title,
  .gh-live-brief-label,
  .gh-live-brief-copy {
    margin: 0;
  }
  .gh-live-brief-kicker,
  .gh-live-brief-label {
    color: rgba(242,195,107,.88);
    font: 10px/1.35 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    letter-spacing: .075em;
    text-transform: uppercase;
  }
  .gh-live-brief-title {
    margin-top: 3px;
    overflow: hidden;
    color: #fff8ea;
    font: 500 14px/1.3 Georgia, 'Times New Roman', serif;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .gh-live-brief-toggle {
    position: relative;
    z-index: 3;
    pointer-events: auto !important;
    width: 28px;
    height: 28px;
    border: 1px solid rgba(255,255,255,.18);
    border-radius: 999px;
    padding: 0;
    background: rgba(255,255,255,.055);
    color: rgba(250,246,237,.88);
    font: 15px/1 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    cursor: pointer;
  }
  .gh-live-brief-body {
    max-height: min(calc(46vh - 62px), 328px);
    overflow-x: hidden;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: 2px 14px 13px;
    scrollbar-color: rgba(242,195,107,.42) transparent;
    scrollbar-width: thin;
  }
  .gh-live-brief-body::-webkit-scrollbar { width: 6px; }
  .gh-live-brief-body::-webkit-scrollbar-track { background: transparent; }
  .gh-live-brief-body::-webkit-scrollbar-thumb {
    border: 1px solid transparent;
    border-radius: 999px;
    background: rgba(242,195,107,.42);
    background-clip: padding-box;
  }
  .gh-live-brief-section { padding-top: 10px; }
  .gh-live-brief-copy {
    margin-top: 5px;
    color: rgba(250,246,237,.92);
    font: 12px/1.48 Georgia, 'Times New Roman', serif;
  }
  .gh-live-brief-copy[lang="en"] { color: rgba(250,246,237,.7); }
  .gh-touch-keys {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    align-items: center;
    margin-top: 8px;
  }
  .gh-touch-key {
    position: relative;
    min-width: 44px;
    min-height: 44px;
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border: 1px solid rgba(242,195,107,.34);
    border-radius: 11px;
    padding: 7px 10px 9px;
    background: linear-gradient(180deg, rgba(255,255,255,.12), rgba(242,195,107,.055));
    color: #fff3cf;
    box-shadow: 0 4px 0 rgba(0,0,0,.36), 0 9px 22px rgba(0,0,0,.2), inset 0 1px 0 rgba(255,255,255,.16);
    font: 600 12px/1 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    letter-spacing: .025em;
    cursor: pointer;
    touch-action: none;
    user-select: none;
    -webkit-user-select: none;
  }
  .gh-touch-key[data-gh-key-label="Space"] { min-width: 76px; }
  .gh-touch-key:hover,
  .gh-touch-key.is-pressed {
    border-color: rgba(242,195,107,.72);
    background: linear-gradient(180deg, rgba(242,195,107,.2), rgba(242,195,107,.09));
  }
  .gh-touch-key.is-pressed {
    transform: translateY(3px);
    box-shadow: 0 1px 0 rgba(0,0,0,.34), 0 4px 12px rgba(0,0,0,.2), inset 0 1px 0 rgba(255,255,255,.12);
  }
  .gh-touch-key:focus-visible {
    outline: 2px solid rgba(242,195,107,.84);
    outline-offset: 3px;
  }
  .gh-touch-key-dock {
    position: fixed;
    z-index: 2147483050;
    top: max(12px, env(safe-area-inset-top));
    left: max(12px, env(safe-area-inset-left));
    width: min(370px, calc(100vw - 24px));
    box-sizing: border-box;
    display: none;
    border: 1px solid rgba(255,255,255,.18);
    border-radius: 15px;
    padding: 9px 10px 11px;
    background: rgba(3,7,13,.82);
    color: rgba(250,246,237,.9);
    box-shadow: 0 14px 40px rgba(0,0,0,.34), inset 0 1px 0 rgba(255,255,255,.1);
    -webkit-backdrop-filter: blur(16px) saturate(1.12);
    backdrop-filter: blur(16px) saturate(1.12);
  }
  .gh-touch-key-dock-label {
    display: block;
    margin: 0 0 2px;
    color: rgba(242,195,107,.82);
    font: 10px/1.3 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    letter-spacing: .07em;
    text-transform: uppercase;
  }
  .gh-touch-key-dock-copy {
    display: none;
  }
  .gh-live-brief.is-collapsed { width: min(284px, calc(100vw - 24px)); }
  .gh-live-brief.is-collapsed .gh-live-brief-header { border-bottom: 0; }
  .gh-live-brief.is-collapsed .gh-live-brief-body { display: none; }
  [data-gh-brief-covered="true"] {
    opacity: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
  }
  [data-gh-native-title-suppressed="true"] {
    display: none !important;
    opacity: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
  }
  .gh-work-note-trigger--busy {
    background: rgba(3,7,13,.97) !important;
    -webkit-backdrop-filter: blur(18px) !important;
    backdrop-filter: blur(18px) !important;
    box-shadow: 0 10px 30px rgba(0,0,0,.46) !important;
  }
  .gh-work-note-trigger--contrast-safe {
    border-color: rgba(242,195,107,.45) !important;
    background: rgba(3,7,13,.92) !important;
    color: #fff3cf !important;
    text-shadow: 0 1px 2px rgba(0,0,0,.72) !important;
  }
  [data-gh-control-offset="true"] {
    translate: 0 var(--gh-control-offset-y, 0px) !important;
  }
  [data-gh-control-concealed="true"] {
    opacity: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
  }
  [data-gh-sound-geometry="compact"] {
    height: auto !important;
    min-height: 38px !important;
    max-height: 52px !important;
    align-self: flex-start !important;
  }
  [data-gh-sound-touch-target="true"] {
    min-width: 44px !important;
    min-height: 44px !important;
    box-sizing: border-box !important;
    touch-action: manipulation !important;
  }
  [data-gh-sound-mobile-docked="true"] {
    position: fixed !important;
    z-index: 2147483000 !important;
    inset: auto max(12px, env(safe-area-inset-right)) max(12px, env(safe-area-inset-bottom)) auto !important;
    width: auto !important;
    max-width: min(46vw, 184px) !important;
    margin: 0 !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    translate: none !important;
    transform: none !important;
  }
  .gh-work-note-trigger:focus-visible,
  .gh-calendar-return:focus-visible,
  .gh-live-brief-toggle:focus-visible,
  .gh-work-note-close:focus-visible,
  .gh-work-note-archive:focus-visible {
    outline: 2px solid rgba(242,195,107,.82);
    outline-offset: 3px;
  }
  #ghWorkNoteOverlay[hidden] { display: none !important; }
  #ghWorkNoteOverlay {
    position: fixed;
    z-index: 2147483100;
    inset: 0;
    display: grid;
    place-items: center;
    box-sizing: border-box;
    padding: max(18px, env(safe-area-inset-top)) max(18px, env(safe-area-inset-right)) max(18px, env(safe-area-inset-bottom)) max(18px, env(safe-area-inset-left));
    background: rgba(2,5,9,.48);
    opacity: 0;
    transition: opacity 180ms ease;
  }
  #ghWorkNoteOverlay.is-open { opacity: 1; }
  body.gh-work-note-modal-open { overflow: hidden !important; }
  #ghWorkNoteOverlay .gh-work-note-panel {
    position: relative;
    width: min(720px, calc(100vw - 36px));
    max-height: min(82vh, 780px);
    box-sizing: border-box;
    overflow: auto;
    overscroll-behavior: contain;
    scrollbar-width: thin;
    border: 1px solid rgba(255,255,255,.18);
    border-radius: 22px;
    padding: clamp(24px, 5vw, 46px);
    background: rgba(7,11,17,.76);
    color: #f7f2e8;
    -webkit-backdrop-filter: blur(28px) saturate(1.24);
    backdrop-filter: blur(28px) saturate(1.24);
    box-shadow: 0 30px 90px rgba(0,0,0,.52), inset 0 1px 0 rgba(255,255,255,.12);
  }
  #ghWorkNoteOverlay .gh-work-note-close {
    position: absolute;
    top: 14px;
    right: 14px;
    min-width: 40px;
    min-height: 40px;
    border: 1px solid rgba(255,255,255,.2);
    border-radius: 999px;
    background: rgba(0,0,0,.2);
    color: inherit;
    font: 18px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
    cursor: pointer;
  }
  #ghWorkNoteOverlay .gh-work-note-kicker,
  #ghWorkNoteOverlay .gh-work-note-section h3 {
    margin: 0 0 8px;
    color: rgba(242,195,107,.88);
    font: 11px/1.3 ui-monospace, SFMono-Regular, Menlo, monospace;
    letter-spacing: .08em;
    text-transform: uppercase;
  }
  #ghWorkNoteOverlay .gh-work-note-title {
    max-width: calc(100% - 48px);
    margin: 0 0 10px;
    font: 500 clamp(24px, 5vw, 42px)/1.08 Georgia, 'Times New Roman', serif;
  }
  #ghWorkNoteOverlay .gh-work-note-meta {
    margin: 0 0 24px;
    color: rgba(247,242,232,.62);
    font: 12px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace;
  }
  #ghWorkNoteOverlay .gh-work-note-section {
    padding: 18px 0;
    border-top: 1px solid rgba(255,255,255,.12);
  }
  #ghWorkNoteOverlay .gh-work-note-section p {
    margin: 8px 0 0;
    color: rgba(247,242,232,.88);
    font: 15px/1.72 Georgia, 'Times New Roman', serif;
  }
  #ghWorkNoteOverlay .gh-work-note-archive {
    display: inline-flex;
    margin-top: 22px;
    border-bottom: 1px solid rgba(242,195,107,.5);
    padding-bottom: 4px;
    color: #f3c872;
    font: 12px/1.4 ui-monospace, SFMono-Regular, Menlo, monospace;
    text-decoration: none;
  }
  body.gh-text-folded .panel,
  body.gh-text-folded .card,
  body.gh-text-folded .state,
  body.gh-text-folded .legend,
  body.gh-text-folded .hint,
  body.gh-text-folded .instructions,
  body.gh-text-folded .statement,
  body.gh-text-folded .copy,
  body.gh-text-folded .text,
  body.gh-text-folded #textPanel,
  body.gh-text-folded #legend {
    opacity: 0 !important;
    transform: translateY(-8px) scale(.98) !important;
    pointer-events: none !important;
    visibility: hidden !important;
  }
  body.gh-chamber-embed .gh-work-note-trigger,
  body.gh-chamber-embed .gh-calendar-return,
  body.gh-chamber-embed .gh-live-brief,
  body.gh-chamber-embed .brief,
  body.gh-chamber-embed #brief,
  body.gh-chamber-embed .hint,
  body.gh-chamber-embed #hint,
  body.gh-chamber-embed .ledger,
  body.gh-chamber-embed .sound,
  body.gh-chamber-embed #sound,
  body.gh-chamber-embed #soundToggle,
  body.gh-chamber-embed h1,
  body.gh-chamber-embed h2,
  body.gh-chamber-embed h3,
  body.gh-chamber-embed .title,
  body.gh-chamber-embed .subtitle,
  body.gh-chamber-embed .hud,
  body.gh-chamber-embed .status,
  body.gh-chamber-embed .label,
  body.gh-chamber-embed .readout,
  body.gh-chamber-embed .meta,
  body.gh-chamber-embed .caption,
  body.gh-chamber-embed .controls,
  body.gh-chamber-embed .toolbar,
  body.gh-chamber-embed .ui,
  body.gh-chamber-embed .overlay,
  body.gh-chamber-embed button,
  body.gh-chamber-embed [role="button"],
  body.gh-chamber-embed button[id*="sound" i],
  body.gh-chamber-embed button[id*="music" i],
  body.gh-chamber-embed button[id*="bgm" i] {
    display: none !important;
    opacity: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
  }
  body.gh-chamber-embed .gh-touch-key-dock {
    width: min(620px, calc(100vw - 24px));
    display: flex !important;
    flex-direction: column;
    align-items: flex-start;
    border: 0;
    padding: 0;
    background: transparent;
    box-shadow: none;
    opacity: 1 !important;
    visibility: visible !important;
    pointer-events: none !important;
    -webkit-backdrop-filter: none;
    backdrop-filter: none;
  }
  body.gh-chamber-embed .gh-touch-key-dock-label {
    display: none !important;
  }
  body.gh-chamber-embed .gh-touch-key-dock-copy {
    display: grid !important;
    max-width: min(560px, calc(100vw - 24px));
    gap: 2px;
    color: rgba(250,246,237,.58);
    font: 10px/1.38 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    letter-spacing: .015em;
    text-shadow: 0 1px 4px rgba(0,0,0,.82), 0 0 12px rgba(0,0,0,.54);
  }
  body.gh-chamber-embed .gh-touch-key-dock-copy p {
    display: -webkit-box !important;
    overflow: hidden;
    margin: 0;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
  body.gh-chamber-embed .gh-touch-key-dock-copy [lang="en"] {
    color: rgba(250,246,237,.42);
  }
  body.gh-chamber-embed .gh-touch-key-dock .gh-touch-keys {
    display: flex !important;
    gap: 2px;
    margin-top: 3px;
    opacity: 1 !important;
    visibility: visible !important;
    pointer-events: auto !important;
  }
  body.gh-chamber-embed .gh-touch-key-dock .gh-touch-key {
    display: inline-flex !important;
    min-width: 44px;
    min-height: 44px;
    border: 0 !important;
    border-radius: 7px;
    padding: 0 6px;
    background: transparent !important;
    color: rgba(255,243,207,.62);
    box-shadow: none !important;
    text-decoration: underline;
    text-decoration-color: rgba(242,195,107,.28);
    text-underline-offset: 4px;
    text-shadow: 0 1px 4px rgba(0,0,0,.9), 0 0 12px rgba(0,0,0,.58);
    opacity: 1 !important;
    visibility: visible !important;
    pointer-events: auto !important;
  }
  body.gh-chamber-embed .gh-touch-key-dock .gh-touch-key:hover,
  body.gh-chamber-embed .gh-touch-key-dock .gh-touch-key.is-pressed {
    border: 0 !important;
    background: rgba(242,195,107,.055) !important;
    color: rgba(255,243,207,.92);
    box-shadow: none !important;
  }
  body.gh-chamber-embed .gh-touch-key-dock .gh-touch-key.is-pressed {
    transform: translateY(1px);
  }
  @media (max-width: 760px) {
    .gh-work-note-trigger,
    .gh-calendar-return {
      min-height: 44px !important;
      max-width: calc(100vw - 24px);
    }
    .gh-live-brief {
      max-height: min(42dvh, 340px);
      border-radius: 14px;
    }
    .gh-live-brief-body { max-height: min(calc(42dvh - 62px), 278px); }
    #ghWorkNoteOverlay { align-items: end; padding: 10px; }
    #ghWorkNoteOverlay .gh-work-note-panel {
      width: 100%;
      max-height: min(84dvh, 760px);
      border-radius: 20px 20px 12px 12px;
      padding: 28px 22px calc(22px + env(safe-area-inset-bottom));
    }
    #ghWorkNoteOverlay .gh-work-note-close {
      min-width: 44px;
      min-height: 44px;
    }
    body.gh-chamber-embed .gh-touch-key-dock .gh-touch-keys {
      width: 100%;
      flex-wrap: nowrap !important;
      overflow-x: auto;
      overflow-y: hidden;
      overscroll-behavior-x: contain;
      padding-bottom: 3px;
      scrollbar-color: rgba(242,195,107,.28) transparent;
      scrollbar-width: thin;
    }
    body.gh-chamber-embed .gh-touch-key-dock .gh-touch-key {
      flex: 0 0 auto;
    }
  }
  @media (pointer: coarse) {
    .gh-work-note-trigger,
    .gh-calendar-return,
    #ghWorkNoteOverlay .gh-work-note-close {
      min-width: 44px;
      min-height: 44px !important;
    }
  }
  @media (min-width: 761px) and (max-width: 1024px) {
    body.gh-chamber-embed .gh-touch-key-dock {
      width: min(520px, calc(100vw - 24px));
    }
  }
  @media (max-height: 520px) {
    body.gh-chamber-embed .gh-touch-key-dock {
      max-height: calc(100dvh - 24px);
      padding: 7px 9px 9px;
    }
    body.gh-chamber-embed .gh-touch-key-dock .gh-touch-keys {
      flex-wrap: nowrap !important;
      overflow-x: auto;
      overflow-y: hidden;
      overscroll-behavior-x: contain;
      padding: 0 2px 5px;
      scrollbar-color: rgba(242,195,107,.42) transparent;
      scrollbar-width: thin;
    }
    body.gh-chamber-embed .gh-touch-key-dock .gh-touch-key {
      flex: 0 0 auto;
    }
  }
</style>
<script id="granted-hours-fold-script">
(() => {
  if (window.__grantedHoursFoldReady) return;
  window.__grantedHoursFoldReady = true;
  const WORK_NOTE = __GRANTED_HOURS_WORK_NOTE_JSON__;
  const GH_WORK_NOTE_GAP = 10;
  const params = new URLSearchParams(window.location.search);
  const IS_EMBED = params.get('embed') === 'calendar';
  const MEDIA_TYPE = 'granted-hours:media';
  const MEDIA_VERSION = 2;
  const EMBED_CHANNEL = params.get('gh_channel') || '';
  const PARENT_ORIGIN = (() => {
    try { return new URL(document.referrer).origin; }
    catch (_) { return ''; }
  })();
  const nativePlay = HTMLMediaElement.prototype.play;
  const NativeAudio = window.Audio;
  const trackedAudio = new Set();
  const observedAudio = new WeakSet();
  let mediaEnabled = false;
  let mediaUnlockRequired = false;
  if (IS_EMBED) {
    function GrantedHoursAudio(...args) {
      return trackAudio(new NativeAudio(...args));
    }
    Object.setPrototypeOf(GrantedHoursAudio, NativeAudio);
    GrantedHoursAudio.prototype = NativeAudio.prototype;
    window.Audio = GrantedHoursAudio;
    HTMLMediaElement.prototype.play = function (...args) {
      if (this instanceof HTMLAudioElement) {
        trackAudio(this);
        if (!mediaEnabled) {
          silenceAudio(this);
          return Promise.resolve();
        }
        this.muted = false;
      }
      if (this instanceof HTMLVideoElement) this.muted = true;
      const playback = nativePlay.apply(this, args);
      if (this instanceof HTMLAudioElement) observePlayback(this, playback);
      return playback;
    };
    document.addEventListener('play', (event) => {
      if (event.target instanceof HTMLAudioElement) {
        trackAudio(event.target);
        if (!mediaEnabled) silenceAudio(event.target);
        else event.target.muted = false;
      } else if (event.target instanceof HTMLVideoElement) {
        event.target.muted = true;
      }
    }, true);
    window.addEventListener('message', (event) => {
      if (event.source !== window.parent) return;
      if (!PARENT_ORIGIN || event.origin !== PARENT_ORIGIN) return;
      const message = event.data;
      if (!message || Object.getPrototypeOf(message) !== Object.prototype) return;
      if (Object.keys(message).sort().join(',') !== 'action,channel,type,version') return;
      if (message.type !== MEDIA_TYPE || message.version !== MEDIA_VERSION) return;
      if (!/^[a-zA-Z0-9_-]{16,128}$/.test(EMBED_CHANNEL) || message.channel !== EMBED_CHANNEL) return;
      if (message.action === 'play') setEmbeddedMediaState(true);
      else if (message.action === 'pause') setEmbeddedMediaState(false);
    });
    window.addEventListener('pointerdown', retryEmbeddedMediaFromGesture, true);
    window.addEventListener('keydown', retryEmbeddedMediaFromGesture, true);
    window.queueMicrotask(() => postMediaEvent('ready', 'ready'));
  }
  const workNote = document.createElement('button');
  workNote.type = 'button';
  workNote.id = 'ghWorkNoteTrigger';
  workNote.className = 'gh-work-note-trigger';
  workNote.textContent = 'Work note / 作品说明';
  workNote.setAttribute('aria-label', 'Open the artwork note over the interactive work / 在交互作品上方打开作品说明');
  workNote.setAttribute('aria-haspopup', 'dialog');
  workNote.setAttribute('aria-controls', 'ghWorkNoteOverlay');
  const calendarReturn = document.createElement('a');
  calendarReturn.id = 'ghCalendarReturn';
  calendarReturn.className = 'gh-calendar-return';
  calendarReturn.textContent = 'Calendar / 非人时间表';
  calendarReturn.setAttribute('aria-label', 'Return to the non-human timetable / 返回非人时间表');
  const calendarReturnUrl = new URL('../../../../../timetable/', window.location.href);
  calendarReturnUrl.searchParams.set('date', WORK_NOTE.date);
  calendarReturn.href = calendarReturnUrl.href;
  const liveBrief = createLiveBrief();
  const embedTouchKeyDock = createTouchKeyDock();
  const workNoteOverlay = createWorkNoteOverlay();
  const mediaUnlock = createMediaUnlock();
  let workNoteLastFocus = null;
  document.addEventListener('DOMContentLoaded', init, { once: true });
  if (document.readyState !== 'loading') init();
  function init() {
    if (!document.body || document.body.contains(workNote)) return;
    if (IS_EMBED) {
      document.body.classList.add('gh-text-folded', 'gh-chamber-embed');
      if (embedTouchKeyDock) document.body.append(embedTouchKeyDock);
      if (mediaUnlock) document.body.append(mediaUnlock);
      syncEmbeddedMediaState();
      new MutationObserver((records) => {
        records.forEach((record) => {
          record.addedNodes.forEach((node) => {
            if (!(node instanceof Element)) return;
            if (node instanceof HTMLAudioElement) trackAudio(node);
            node.querySelectorAll?.('audio').forEach(trackAudio);
            node.querySelectorAll?.('video').forEach((video) => { video.muted = true; });
          });
        });
      }).observe(document.documentElement, { childList: true, subtree: true });
      window.addEventListener('load', syncEmbeddedMediaState, { once: true });
      window.setTimeout(syncEmbeddedMediaState, 250);
      return;
    }
    document.body.append(liveBrief, calendarReturn, workNote, workNoteOverlay);
    hideNativeWorkNoteTriggers();
    suppressNativeTitleChrome();
    maskNativeBriefCollisions();
    liveBrief.querySelector('.gh-live-brief-toggle').addEventListener('click', toggleLiveBrief);
    workNote.addEventListener('click', openWorkNote);
    workNoteOverlay.querySelector('.gh-work-note-close').addEventListener('click', closeWorkNote);
    workNoteOverlay.addEventListener('click', (event) => {
      if (event.target === workNoteOverlay) closeWorkNote();
    });
    document.addEventListener('keydown', handleWorkNoteKeydown);
    refreshFloatingChrome();
    scheduleFloatingChromeRefresh();
    document.addEventListener('click', scheduleFloatingChromeRefresh);
    document.addEventListener('keyup', scheduleFloatingChromeRefresh);
    window.addEventListener('resize', refreshFloatingChrome);
    window.addEventListener('orientationchange', refreshFloatingChrome);
    window.addEventListener('load', refreshFloatingChrome);
    [1200, 3000, 6000].forEach((ms) => window.setTimeout(refreshFloatingChrome, ms));
    watchSoundControl();
    new MutationObserver((records) => {
      if (records.some((record) => record.addedNodes.length)) {
        window.requestAnimationFrame(suppressNativeTitleChrome);
      }
    }).observe(document.body, { childList: true, subtree: true });
  }
  function makeElement(tag, className, text = '') {
    const element = document.createElement(tag);
    element.className = className;
    if (text) element.textContent = text;
    return element;
  }
  function createMediaUnlock() {
    if (!IS_EMBED) return null;
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'gh-media-unlock';
    button.hidden = true;
    button.textContent = 'Tap for artwork sound / 轻触开启作品声音';
    button.setAttribute('aria-label', 'Start artwork sound / 开启作品声音');
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      setEmbeddedMediaState(true, { userGesture: true });
    });
    return button;
  }
  function makeWorkNoteSection(label, en, zh) {
    if (!en && !zh) return null;
    const section = makeElement('section', 'gh-work-note-section');
    section.append(makeElement('h3', '', label));
    if (en) section.append(makeElement('p', 'gh-work-note-en', en));
    if (zh) section.append(makeElement('p', 'gh-work-note-zh', zh));
    return section;
  }
  function makeLiveBriefSection(label, en, zh, kind) {
    const section = makeElement('section', `gh-live-brief-section gh-live-brief-${kind}`);
    section.dataset.ghBriefSection = kind;
    section.append(makeElement('h3', 'gh-live-brief-label', label));
    const zhCopy = makeElement('p', 'gh-live-brief-copy gh-live-brief-zh', zh);
    zhCopy.lang = 'zh-CN';
    const enCopy = makeElement('p', 'gh-live-brief-copy gh-live-brief-en', en);
    enCopy.lang = 'en';
    section.append(zhCopy, enCopy);
    return section;
  }
  function dispatchArtworkKey(type, shortcut) {
    const target = document.querySelector('canvas, svg') || document.body || document.documentElement;
    const event = new KeyboardEvent(type, {
      key: shortcut.key,
      code: shortcut.code,
      bubbles: true,
      cancelable: true,
      composed: true,
    });
    target.dispatchEvent(event);
  }
  function makeTouchKeyButton(shortcut) {
    const button = makeElement('button', 'gh-touch-key', shortcut.label);
    button.type = 'button';
    button.dataset.ghKeyLabel = shortcut.label;
    button.dataset.ghKey = shortcut.key;
    button.dataset.ghCode = shortcut.code;
    button.setAttribute(
      'aria-label',
      `Trigger ${shortcut.label} key / 触发 ${shortcut.label} 键`,
    );
    let pointerActive = false;
    const release = (event) => {
      if (!pointerActive) return;
      pointerActive = false;
      button.classList.remove('is-pressed');
      dispatchArtworkKey('keyup', shortcut);
      if (event && button.hasPointerCapture?.(event.pointerId)) {
        button.releasePointerCapture(event.pointerId);
      }
    };
    button.addEventListener('pointerdown', (event) => {
      if (event.button !== 0 || pointerActive) return;
      event.preventDefault();
      pointerActive = true;
      button.classList.add('is-pressed');
      button.setPointerCapture?.(event.pointerId);
      dispatchArtworkKey('keydown', shortcut);
    });
    button.addEventListener('pointerup', release);
    button.addEventListener('pointercancel', release);
    button.addEventListener('lostpointercapture', release);
    button.addEventListener('keydown', (event) => {
      if (event.key === ' ' || event.key === 'Enter') event.stopPropagation();
    });
    button.addEventListener('keyup', (event) => {
      if (event.key === ' ' || event.key === 'Enter') event.stopPropagation();
    });
    button.addEventListener('click', (event) => {
      if (event.detail !== 0) return;
      dispatchArtworkKey('keydown', shortcut);
      dispatchArtworkKey('keyup', shortcut);
    });
    return button;
  }
  function createTouchKeys(className = '') {
    if (!Array.isArray(WORK_NOTE.touch_keys) || !WORK_NOTE.touch_keys.length) return null;
    const keys = makeElement('div', `gh-touch-keys${className ? ` ${className}` : ''}`);
    keys.setAttribute('role', 'group');
    keys.setAttribute('aria-label', 'Touch keyboard shortcuts / 可触摸键盘快捷键');
    WORK_NOTE.touch_keys.forEach((shortcut) => keys.append(makeTouchKeyButton(shortcut)));
    return keys;
  }
  function touchKeyInstructionExcerpt(value) {
    const labels = Array.isArray(WORK_NOTE.touch_keys)
      ? WORK_NOTE.touch_keys.map((shortcut) => shortcut.label)
      : [];
    const mentionsShortcut = (sentence) => labels.some((label) => {
      const escaped = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      return new RegExp(`(^|[^A-Za-z0-9])${escaped}($|[^A-Za-z0-9])`, 'i').test(sentence);
    });
    const sentences = String(value || '')
      .split(/(?<=[.!?。！？])\s*/)
      .map((sentence) => sentence.trim())
      .filter(Boolean);
    const excerpt = sentences.filter(mentionsShortcut).join(' ') || String(value || '').trim();
    return excerpt
      .replace(/[；;]\s*(?:页面|右下角|Use the visible)[^。.!?]*[。.!?]?/gi, '')
      .trim();
  }
  function createTouchKeyDock() {
    const keys = createTouchKeys('gh-touch-keys-embed');
    if (!keys) return null;
    const dock = makeElement('aside', 'gh-touch-key-dock');
    dock.id = 'ghTouchKeyDock';
    dock.setAttribute('aria-label', 'Touch controls / 触控操作');
    const copy = makeElement('div', 'gh-touch-key-dock-copy');
    const zh = makeElement('p', '', touchKeyInstructionExcerpt(WORK_NOTE.interaction_zh));
    const en = makeElement('p', '', touchKeyInstructionExcerpt(WORK_NOTE.interaction_en));
    zh.lang = 'zh-CN';
    en.lang = 'en';
    copy.append(zh, en);
    dock.append(
      makeElement('span', 'gh-touch-key-dock-label', 'TOUCH KEYS / 触控按键'),
      copy,
      keys,
    );
    return dock;
  }
  function createLiveBrief() {
    const brief = makeElement('aside', 'gh-live-brief');
    brief.id = 'ghLiveBrief';
    brief.dataset.ghLiveBrief = 'bilingual';
    brief.setAttribute('role', 'region');
    brief.setAttribute('aria-label', 'Bilingual artwork brief and instructions / 作品双语简述与操作说明');
    const header = makeElement('header', 'gh-live-brief-header');
    const heading = makeElement('div', 'gh-live-brief-heading');
    heading.append(
      makeElement('p', 'gh-live-brief-kicker', 'BRIEF / 略说'),
      makeElement('h2', 'gh-live-brief-title', `${WORK_NOTE.title_zh} / ${WORK_NOTE.title_en}`),
    );
    const toggle = makeElement('button', 'gh-live-brief-toggle', '−');
    toggle.type = 'button';
    toggle.setAttribute('aria-expanded', 'true');
    toggle.setAttribute('aria-controls', 'ghLiveBriefBody');
    toggle.setAttribute('aria-label', 'Collapse bilingual brief / 收起双语简述');
    header.append(heading, toggle);
    const body = makeElement('div', 'gh-live-brief-body');
    body.id = 'ghLiveBriefBody';
    body.append(
      makeLiveBriefSection('Brief / 作品简述', WORK_NOTE.intention_en, WORK_NOTE.intention_zh, 'summary'),
      makeLiveBriefSection('How to interact / 操作说明', WORK_NOTE.interaction_en, WORK_NOTE.interaction_zh, 'instructions'),
    );
    const touchKeys = createTouchKeys('gh-touch-keys-inline');
    if (touchKeys) {
      const section = makeElement('section', 'gh-live-brief-section gh-live-brief-touch');
      section.dataset.ghBriefSection = 'touch';
      section.append(
        makeElement('h3', 'gh-live-brief-label', 'Touch keys / 触控按键'),
        touchKeys,
      );
      body.append(section);
    }
    brief.append(header, body);
    return brief;
  }
  function toggleLiveBrief() {
    const collapsed = liveBrief.classList.toggle('is-collapsed');
    const toggle = liveBrief.querySelector('.gh-live-brief-toggle');
    toggle.textContent = collapsed ? '+' : '−';
    toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
    toggle.setAttribute(
      'aria-label',
      collapsed ? 'Expand bilingual brief / 展开双语简述' : 'Collapse bilingual brief / 收起双语简述',
    );
    if (collapsed) restoreNativeBriefCollisions();
    else window.requestAnimationFrame(maskNativeBriefCollisions);
    window.requestAnimationFrame(refreshFloatingChrome);
  }
  function restoreNativeBriefCollisions() {
    document.querySelectorAll('[data-gh-brief-covered="true"]').forEach((element) => {
      element.removeAttribute('data-gh-brief-covered');
    });
  }
  function suppressNativeTitleChrome() {
    const briefRect = liveBrief.getBoundingClientRect();
    const reserved = {
      left: briefRect.left,
      top: briefRect.top,
      right: briefRect.left + Math.max(briefRect.width, Math.min(352, innerWidth - 24)),
      bottom: briefRect.top + Math.min(innerHeight * .46, 390),
    };
    const maxArea = innerWidth * innerHeight * .6;
    const candidates = document.querySelectorAll(
      'h1,h2,p,.title,.subtitle,.kicker,.brief,#brief,.intro,.description,.statement,.instructions',
    );
    for (const element of candidates) {
      if (!(element instanceof HTMLElement)) continue;
      if (element.closest('#ghLiveBrief, #ghWorkNoteOverlay, #ghWorkNoteTrigger, #ghCalendarReturn, #ghTouchKeyDock')) continue;
      if (element.dataset.ghNativeTitleSuppressed === 'true') continue;
      const style = getComputedStyle(element);
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) <= .01) continue;
      const rect = element.getBoundingClientRect();
      if (rect.width <= 1 || rect.height <= 1 || rect.width * rect.height > maxArea) continue;
      if (!(element.innerText || element.textContent || '').trim()) continue;
      const overlapsReserved = rectsIntersect(rect, reserved);
      const isUpperTitle = element.matches('h1,h2,.title')
        && rect.top < Math.min(innerHeight * .48, 430)
        && rect.left < innerWidth * .76;
      if (!overlapsReserved && !isUpperTitle) continue;
      let target = element;
      for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
        if (parent.closest('#ghLiveBrief, #ghWorkNoteOverlay, #ghWorkNoteTrigger, #ghCalendarReturn, #ghTouchKeyDock')) break;
        if (parent.querySelector('canvas,svg,video,audio,button,input,select,textarea,[role="button"]')) break;
        const parentRect = parent.getBoundingClientRect();
        if (parentRect.width <= 1 || parentRect.height <= 1 || parentRect.width * parentRect.height > maxArea) break;
        const semanticShell = parent.matches('header,.panel,.hero,.intro,.brief,.copy,.statement,.instructions')
          || /(?:^|\s)(?:panel|hero|intro|brief|copy|statement|instructions)(?:\s|$)/i.test(parent.className);
        if (semanticShell) target = parent;
      }
      target.dataset.ghNativeTitleSuppressed = 'true';
    }
  }
  function maskNativeBriefCollisions() {
    restoreNativeBriefCollisions();
    suppressNativeTitleChrome();
    if (liveBrief.classList.contains('is-collapsed')) return;
    if (isTouchLayout() && window.innerHeight <= 520) {
      const compactCandidates = document.querySelectorAll(
        'header,.panel,.card,.legend,.hint,.instructions,.statement,.copy,.text,.meta,.caption,'
        + '.status,.readout,.label,.mode,.metric,aside,aside section,aside p,aside h1,aside h2,aside h3',
      );
      for (const element of compactCandidates) {
        if (!(element instanceof HTMLElement)) continue;
        if (element.closest('#ghLiveBrief, #ghWorkNoteOverlay, #ghWorkNoteTrigger, #ghTouchKeyDock')) continue;
        if (element.matches('button,input,[role="button"]') || element.querySelector('button,input,[role="button"]')) continue;
        if (!(element.innerText || element.textContent || '').trim()) continue;
        element.dataset.ghBriefCovered = 'true';
      }
    }
  }
  function refreshFloatingChrome() {
    restoreNativeControlOffsets();
    maskNativeBriefCollisions();
    alignWorkNote();
    offsetNativeControlText();
  }
  function scheduleFloatingChromeRefresh() {
    window.requestAnimationFrame(() => window.requestAnimationFrame(refreshFloatingChrome));
    window.setTimeout(refreshFloatingChrome, 420);
  }
  function createWorkNoteOverlay() {
    const overlay = makeElement('section', 'gh-work-note-overlay');
    overlay.id = 'ghWorkNoteOverlay';
    overlay.hidden = true;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-labelledby', 'ghWorkNoteTitle');
    const panel = makeElement('article', 'gh-work-note-panel');
    const close = makeElement('button', 'gh-work-note-close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', 'Close work note / 关闭作品说明');
    const kicker = makeElement('p', 'gh-work-note-kicker', 'WORK NOTE / 作品说明');
    const title = makeElement('h2', 'gh-work-note-title', `${WORK_NOTE.title_en} / ${WORK_NOTE.title_zh}`);
    title.id = 'ghWorkNoteTitle';
    const meta = makeElement(
      'p',
      'gh-work-note-meta',
      `${WORK_NOTE.date} · ${WORK_NOTE.start}–${WORK_NOTE.end}`
        + ` · granted ${WORK_NOTE.duration_minutes} min / 授时 ${WORK_NOTE.duration_minutes} 分钟`
        + ` · experience ${WORK_NOTE.experience_duration_en} / 体验时长${WORK_NOTE.experience_duration_zh}`
        + ` · ${WORK_NOTE.variable_en} / ${WORK_NOTE.variable_zh}`,
    );
    panel.append(close, kicker, title, meta);
    [
      makeWorkNoteSection('Intention / 发心', WORK_NOTE.intention_en, WORK_NOTE.intention_zh),
      makeWorkNoteSection('Interaction / 交互', WORK_NOTE.interaction_en, WORK_NOTE.interaction_zh),
      makeWorkNoteSection('Creative rationale / 创作缘由', WORK_NOTE.rationale_en, WORK_NOTE.rationale_zh),
      makeWorkNoteSection('Afterimage / 余像', WORK_NOTE.after_en, WORK_NOTE.after_zh),
    ].filter(Boolean).forEach((section) => panel.append(section));
    const touchKeys = createTouchKeys('gh-touch-keys-note');
    if (touchKeys) {
      const touchSection = makeElement('section', 'gh-work-note-section gh-work-note-touch');
      touchSection.append(makeElement('h3', '', 'Touch keys / 触控按键'), touchKeys);
      panel.append(touchSection);
    }
    const archive = makeElement('a', 'gh-work-note-archive', 'View full archive record / 查看完整档案 ↗');
    archive.href = '../';
    panel.append(archive);
    overlay.append(panel);
    return overlay;
  }
  function openWorkNote() {
    workNoteLastFocus = (
      document.activeElement instanceof HTMLElement
      && document.activeElement !== document.body
    ) ? document.activeElement : workNote;
    workNoteOverlay.hidden = false;
    workNoteOverlay.classList.add('is-open');
    document.body.classList.add('gh-work-note-modal-open');
    requestAnimationFrame(() => {
      workNoteOverlay.querySelector('.gh-work-note-close').focus({ preventScroll: true });
    });
  }
  function closeWorkNote() {
    if (workNoteOverlay.hidden) return;
    workNoteOverlay.classList.remove('is-open');
    workNoteOverlay.hidden = true;
    document.body.classList.remove('gh-work-note-modal-open');
    if (workNoteLastFocus && typeof workNoteLastFocus.focus === 'function') {
      workNoteLastFocus.focus({ preventScroll: true });
    }
  }
  function handleWorkNoteKeydown(event) {
    if (workNoteOverlay.hidden) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      closeWorkNote();
      return;
    }
    if (event.key !== 'Tab') return;
    const focusable = [...workNoteOverlay.querySelectorAll('button, a[href]')]
      .filter((element) => !element.disabled && element.getClientRects().length);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
  function hideNativeWorkNoteTriggers() {
    document.querySelectorAll(
      '.gh-work-note-trigger, #noteBtn, #noteToggle, button[id*="note" i], button[aria-controls*="note" i]',
    ).forEach((element) => {
      if (element === workNote || element.closest('#ghWorkNoteOverlay')) return;
      const label = `${element.id} ${element.textContent || ''} ${element.getAttribute('aria-label') || ''}`;
      if (!/note|作品说明|说明|explanation/i.test(label)) return;
      element.hidden = true;
      element.style.display = 'none';
      element.setAttribute('aria-hidden', 'true');
    });
  }
  const SOUND_SELECTORS = [
    '#sound', '.sound', '#soundToggle', '#musicToggle',
    'button[id*="sound" i]', 'button[id*="music" i]', 'button[id*="bgm" i]',
  ];
  function findSoundControl() {
    const visible = (element) => {
      if (!(element instanceof HTMLElement)) return false;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return style.display !== 'none'
        && style.visibility !== 'hidden'
        && Number(style.opacity) > 0.01
        && rect.width > 1
        && rect.height > 1;
    };
    const found = [];
    for (const selector of SOUND_SELECTORS) {
      for (const matched of document.querySelectorAll(selector)) {
        const element = matched.matches('button,input,[role="button"]')
          ? matched
          : matched.querySelector('button,input,[role="button"]') || matched;
        if (visible(element) && !found.includes(element)) found.push(element);
      }
    }
    found.sort((a, b) => {
      const score = (element) => {
        const rect = element.getBoundingClientRect();
        const interactive = element.matches('button,input,[role="button"]') ? 1000 : 0;
        const named = /sound|music|bgm/i.test(`${element.id} ${element.className}`) ? 120 : 0;
        const compact = rect.height <= Math.max(72, innerHeight * .16) ? 60 : -300;
        return interactive + named + compact - Math.min(rect.width * rect.height / 1000, 100);
      };
      return score(b) - score(a);
    });
    const sound = found[0] || null;
    if (sound?.matches('button,input,[role="button"]')) {
      const rect = sound.getBoundingClientRect();
      if (rect.height > Math.max(72, innerHeight * .16)) {
        sound.dataset.ghSoundGeometry = 'compact';
      }
    }
    return sound;
  }
  const SOUND_STYLE_PROPS = [
    'border-top-width', 'border-right-width', 'border-bottom-width', 'border-left-width',
    'border-top-style', 'border-right-style', 'border-bottom-style', 'border-left-style',
    'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color',
    'border-top-left-radius', 'border-top-right-radius', 'border-bottom-right-radius', 'border-bottom-left-radius',
    'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'background-color', 'color', 'font-family', 'font-size', 'font-weight', 'font-style',
    'line-height', 'letter-spacing', 'min-height', 'box-shadow',
    '-webkit-backdrop-filter', 'backdrop-filter',
  ];
  function isTouchLayout() {
    return window.innerWidth <= 760 || window.matchMedia('(pointer: coarse)').matches;
  }
  function normalizeSoundForTouch(sound) {
    if (!(sound instanceof HTMLElement)) return;
    const touchLayout = isTouchLayout();
    if (!touchLayout) {
      sound.removeAttribute('data-gh-sound-touch-target');
      sound.removeAttribute('data-gh-sound-mobile-docked');
    } else if (sound.dataset.ghSoundTouchTarget !== 'true') {
      sound.dataset.ghSoundTouchTarget = 'true';
    }
    if (touchLayout && sound.dataset.ghSoundMobileDocked === 'true') return;
    const rect = sound.getBoundingClientRect();
    const briefRect = liveBrief.getBoundingClientRect();
    const offscreen = rect.left < 0 || rect.top < 0 || rect.right > innerWidth || rect.bottom > innerHeight;
    if (offscreen || rectsIntersect(rect, briefRect)) {
      sound.dataset.ghSoundMobileDocked = 'true';
    }
  }
  function parsedColor(value) {
    const match = String(value).match(/rgba?\(([^)]+)\)/i);
    if (!match) return null;
    const channels = match[1].split(/[\s,\/]+/).filter(Boolean).map(Number);
    if (channels.length < 3 || channels.slice(0, 3).some((channel) => !Number.isFinite(channel))) return null;
    return { r: channels[0], g: channels[1], b: channels[2], a: Number.isFinite(channels[3]) ? channels[3] : 1 };
  }
  function relativeLuminance(color) {
    const linear = [color.r, color.g, color.b].map((channel) => {
      const normalized = channel / 255;
      return normalized <= .04045 ? normalized / 12.92 : ((normalized + .055) / 1.055) ** 2.4;
    });
    return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2];
  }
  function ensureWorkNoteContrast() {
    workNote.classList.remove('gh-work-note-trigger--contrast-safe');
    const style = getComputedStyle(workNote);
    const foreground = parsedColor(style.color);
    const background = parsedColor(style.backgroundColor);
    if (!foreground || !background || background.a < .18) {
      workNote.classList.add('gh-work-note-trigger--contrast-safe');
      return;
    }
    const light = Math.max(relativeLuminance(foreground), relativeLuminance(background));
    const dark = Math.min(relativeLuminance(foreground), relativeLuminance(background));
    if ((light + .05) / (dark + .05) < 3) {
      workNote.classList.add('gh-work-note-trigger--contrast-safe');
    }
  }
  function touchSoundAnchorRect(sound) {
    if (!isTouchLayout()) return null;
    const soundRect = sound.getBoundingClientRect();
    const parent = sound.parentElement;
    if (!parent || parent === document.body || parent === document.documentElement) return soundRect;
    const parentRect = parent.getBoundingClientRect();
    const style = getComputedStyle(parent);
    const usableGroup = style.display !== 'none'
      && style.visibility !== 'hidden'
      && parentRect.width <= innerWidth * .78
      && parentRect.height <= Math.max(76, soundRect.height * 2);
    return usableGroup ? parentRect : null;
  }
  function alignWorkNote() {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const sound = findSoundControl();
    let baseRight = 12;
    let baseBottom = 12;
    if (sound) {
      normalizeSoundForTouch(sound);
      const soundStyle = getComputedStyle(sound);
      SOUND_STYLE_PROPS.forEach((prop) => {
        const value = soundStyle.getPropertyValue(prop);
        if (value) workNote.style.setProperty(prop, value);
      });
      const soundRect = sound.getBoundingClientRect();
      const compact = soundRect.width <= vw * 0.45;
      const nearBottom = soundRect.bottom > vh * 0.45;
      const nearRight = soundRect.left > vw * 0.25;
      if (compact && nearBottom && nearRight) {
        const noteWidth = workNote.getBoundingClientRect().width;
        const pairFits = noteWidth + soundRect.width + GH_WORK_NOTE_GAP <= vw - 24;
        if (pairFits) {
          workNote.dataset.ghControlLayout = 'inline';
          baseRight = Math.max(12, vw - soundRect.left + GH_WORK_NOTE_GAP);
          baseBottom = Math.max(12, vh - soundRect.bottom);
        } else {
          workNote.dataset.ghControlLayout = 'stacked';
          baseRight = Math.max(12, vw - soundRect.right);
          baseBottom = Math.max(12, vh - soundRect.top + GH_WORK_NOTE_GAP);
        }
      } else if (compact) {
        const anchorRect = touchSoundAnchorRect(sound);
        const noteWidth = workNote.getBoundingClientRect().width;
        if (anchorRect && anchorRect.right + GH_WORK_NOTE_GAP + noteWidth <= vw - 12) {
          workNote.dataset.ghControlLayout = 'alongside';
          baseRight = Math.max(12, vw - anchorRect.right - GH_WORK_NOTE_GAP - noteWidth);
          baseBottom = Math.max(12, vh - anchorRect.bottom);
        } else {
          workNote.dataset.ghControlLayout = 'separate';
          baseRight = 12;
          baseBottom = 12;
        }
      } else {
        workNote.dataset.ghControlLayout = 'stacked';
        baseRight = Math.max(12, vw - soundRect.right + GH_WORK_NOTE_GAP);
        baseBottom = Math.max(12, vh - soundRect.top + GH_WORK_NOTE_GAP);
      }
    } else {
      workNote.dataset.ghControlLayout = 'solo';
      SOUND_STYLE_PROPS.forEach((prop) => workNote.style.removeProperty(prop));
    }
    workNote.style.top = 'auto';
    workNote.style.left = 'auto';
    workNote.style.right = `${baseRight}px`;
    workNote.style.bottom = `${baseBottom}px`;
    workNote.classList.remove('gh-work-note-trigger--busy');
    let noteRect = workNote.getBoundingClientRect();
    if (sound) {
      const soundRect = sound.getBoundingClientRect();
      const invalidInlinePlacement = rectsIntersect(noteRect, soundRect)
        || noteRect.left < 12
        || noteRect.right > vw - 12;
      if (invalidInlinePlacement) {
        workNote.dataset.ghControlLayout = 'stacked';
        workNote.style.right = `${Math.max(12, vw - soundRect.right)}px`;
        workNote.style.bottom = `${Math.max(12, vh - soundRect.top + GH_WORK_NOTE_GAP)}px`;
        noteRect = workNote.getBoundingClientRect();
      }
    }
    if (noteRect.left < 0) {
      workNote.style.right = `${Math.max(12, vw - noteRect.width - 12)}px`;
      noteRect = workNote.getBoundingClientRect();
    }
    if (noteRect.bottom > vh) {
      workNote.style.bottom = `${Math.max(12, vh - noteRect.top - 12)}px`;
    }
    ensureWorkNoteContrast();
    alignCalendarReturn();
  }
  function alignCalendarReturn() {
    calendarReturn.style.top = 'auto';
    calendarReturn.style.left = 'auto';
    const noteRect = workNote.getBoundingClientRect();
    const returnRect = calendarReturn.getBoundingClientRect();
    let right = Math.max(12, innerWidth - noteRect.left + GH_WORK_NOTE_GAP);
    let bottom = Math.max(12, innerHeight - noteRect.bottom);
    calendarReturn.dataset.ghControlLayout = 'inline';
    if (noteRect.left - GH_WORK_NOTE_GAP - returnRect.width < 12) {
      right = Math.max(12, innerWidth - noteRect.right);
      bottom = Math.max(12, innerHeight - noteRect.top + GH_WORK_NOTE_GAP);
      calendarReturn.dataset.ghControlLayout = 'stacked';
    }
    calendarReturn.style.right = `${right}px`;
    calendarReturn.style.bottom = `${bottom}px`;
  }
  function restoreNativeControlOffsets() {
    document.querySelectorAll('[data-gh-control-offset="true"], [data-gh-control-concealed="true"]').forEach((element) => {
      element.removeAttribute('data-gh-control-offset');
      element.removeAttribute('data-gh-control-concealed');
      element.style.removeProperty('--gh-control-offset-y');
    });
  }
  function rectsIntersect(a, b) {
    return Math.min(a.right, b.right) > Math.max(a.left, b.left)
      && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top);
  }
  function isVisiblyRendered(element) {
    if (!(element instanceof HTMLElement)) return false;
    for (let current = element; current instanceof HTMLElement; current = current.parentElement) {
      const style = getComputedStyle(current);
      if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) <= .01) return false;
      if (current === document.body) break;
    }
    const rect = element.getBoundingClientRect();
    return rect.width > 1 && rect.height > 1;
  }
  function nativeControlTextCandidates(controls) {
    const maxArea = innerWidth * innerHeight * .35;
    return [...document.querySelectorAll('h1,h2,h3,h4,h5,h6,p,span,label,legend,figcaption,li,a,div,aside,section')]
      .filter((element) => {
        if (!(element instanceof HTMLElement)) return false;
        if (element.closest('#ghLiveBrief, #ghWorkNoteOverlay, #ghWorkNoteTrigger, #ghTouchKeyDock')) return false;
        if (controls.some((control) => element === control || control.contains(element) || element.contains(control))) return false;
        const rect = element.getBoundingClientRect();
        if (!isVisiblyRendered(element)) return false;
        if (rect.width <= 1 || rect.height <= 1 || rect.width * rect.height > maxArea) return false;
        if (rect.right < innerWidth * .48 || rect.bottom < innerHeight * .48) return false;
        if (!(element.innerText || element.textContent || '').trim()) return false;
        const directText = [...element.childNodes].some(
          (node) => node.nodeType === Node.TEXT_NODE && (node.textContent || '').trim(),
        );
        const semanticContainer = /hint|legend|keys|caption|meta|ledger|stamp|fallback|panel|controls|status|readout|copy|brief/i
          .test(`${element.id} ${element.className}`);
        if (!directText && !semanticContainer && !/^(H[1-6]|P|LABEL|LEGEND|FIGCAPTION|LI|A|SPAN)$/.test(element.tagName)) return false;
        return controls.some((control) => rectsIntersect(rect, control.getBoundingClientRect()));
      });
  }
  function nativeControlOffsetTarget(element, controls) {
    const semanticBlock = /hint|legend|keys|caption|meta|ledger|stamp|fallback|panel|controls|status|readout|copy|brief/i;
    const maxArea = innerWidth * innerHeight * .35;
    let target = element;
    for (let parent = element.parentElement; parent && parent !== document.body; parent = parent.parentElement) {
      if (parent.closest('#ghLiveBrief, #ghWorkNoteOverlay, #ghWorkNoteTrigger, #ghTouchKeyDock')) break;
      if (controls.some((control) => parent === control || parent.contains(control))) break;
      const rect = parent.getBoundingClientRect();
      if (rect.width <= 1 || rect.height <= 1 || rect.width * rect.height > maxArea) break;
      const style = getComputedStyle(parent);
      const named = semanticBlock.test(`${parent.id} ${parent.className}`);
      const positioned = ['fixed', 'absolute', 'sticky'].includes(style.position);
      if (named || positioned) target = parent;
    }
    return target;
  }
  function offsetNativeControlText() {
    if (IS_EMBED) return;
    const sound = findSoundControl();
    const controls = [calendarReturn, workNote, sound].filter((element) => element instanceof HTMLElement);
    const targets = [...new Set(nativeControlTextCandidates(controls).map(
      (element) => nativeControlOffsetTarget(element, controls),
    ))];
    for (const target of targets) {
      const rect = target.getBoundingClientRect();
      const horizontallyRelevant = controls
        .map((control) => control.getBoundingClientRect())
        .filter((controlRect) => (
          Math.min(rect.right, controlRect.right) > Math.max(rect.left, controlRect.left)
        ));
      if (!horizontallyRelevant.some((controlRect) => rectsIntersect(rect, controlRect))) continue;
      const maxLift = Math.ceil(Math.max(48, innerHeight * .32));
      let lift = 0;
      for (let candidate = 1; candidate <= maxLift; candidate += 1) {
        const shifted = {
          left: rect.left,
          right: rect.right,
          top: rect.top - candidate,
          bottom: rect.bottom - candidate,
        };
        const clear = horizontallyRelevant.every((controlRect) => !rectsIntersect(shifted, {
          left: controlRect.left,
          right: controlRect.right,
          top: controlRect.top - GH_WORK_NOTE_GAP,
          bottom: controlRect.bottom + GH_WORK_NOTE_GAP,
        }));
        if (clear) {
          lift = candidate;
          break;
        }
      }
      if (lift <= 0) {
        if (isTouchLayout() && innerHeight <= 520) {
          target.dataset.ghControlConcealed = 'true';
        }
        continue;
      }
      target.dataset.ghControlOffset = 'true';
      target.style.setProperty('--gh-control-offset-y', `${-Math.ceil(lift)}px`);
    }
  }
  let soundObserver = null;
  function watchSoundControl() {
    soundObserver?.disconnect();
    const sound = findSoundControl();
    if (!sound) {
      soundObserver = new MutationObserver(() => {
        window.requestAnimationFrame(refreshFloatingChrome);
        if (findSoundControl()) {
          soundObserver.disconnect();
          watchSoundControl();
        }
      });
      soundObserver.observe(document.body, { childList: true, subtree: true });
      return;
    }
    soundObserver = new MutationObserver(() => {
      window.requestAnimationFrame(refreshFloatingChrome);
    });
    soundObserver.observe(sound, { attributes: true, childList: true, subtree: true, characterData: true });
  }
  function trackAudio(audio) {
    trackedAudio.add(audio);
    if (!observedAudio.has(audio)) {
      observedAudio.add(audio);
      audio.addEventListener('waiting', () => {
        if (mediaEnabled) postMediaEvent('state', 'buffering');
      });
      audio.addEventListener('stalled', () => {
        if (mediaEnabled) postMediaEvent('state', 'buffering');
      });
      audio.addEventListener('playing', () => {
        if (mediaEnabled) {
          setMediaUnlockRequired(false);
          postMediaEvent('state', 'playing');
        }
      });
      audio.addEventListener('error', () => {
        if (mediaEnabled) postMediaEvent('state', 'error');
      });
    }
    if (!mediaEnabled) silenceAudio(audio);
    return audio;
  }
  function silenceAudio(audio) {
    audio.muted = true;
    audio.removeAttribute('autoplay');
    audio.pause();
  }
  function silenceEmbeddedMedia() {
    document.querySelectorAll('audio').forEach(trackAudio);
    trackedAudio.forEach(silenceAudio);
    document.querySelectorAll('video').forEach((video) => { video.muted = true; });
  }
  function syncEmbeddedMediaState() {
    if (mediaEnabled) setEmbeddedMediaState(true);
    else {
      if (document.body) document.body.dataset.ghAudioEnabled = '0';
      silenceEmbeddedMedia();
    }
  }
  function postMediaEvent(event, status) {
    if (!IS_EMBED || !PARENT_ORIGIN || !/^[a-zA-Z0-9_-]{16,128}$/.test(EMBED_CHANNEL)) return;
    window.parent.postMessage({
      type: MEDIA_TYPE,
      version: MEDIA_VERSION,
      channel: EMBED_CHANNEL,
      event,
      status,
    }, PARENT_ORIGIN);
  }
  function setMediaUnlockRequired(required) {
    mediaUnlockRequired = required;
    if (mediaUnlock) mediaUnlock.hidden = !required;
  }
  function observePlayback(audio, playback) {
    if (!mediaEnabled) return;
    if (audio.readyState < HTMLMediaElement.HAVE_FUTURE_DATA) {
      postMediaEvent('state', 'buffering');
    }
    if (!playback || typeof playback.then !== 'function') return;
    playback.then(
      () => {
        setMediaUnlockRequired(false);
        postMediaEvent('state', 'playing');
      },
      (error) => {
        const blocked = error?.name === 'NotAllowedError';
        setMediaUnlockRequired(blocked);
        postMediaEvent('state', blocked ? 'blocked' : 'error');
      },
    );
  }
  function retryEmbeddedMediaFromGesture(event) {
    if (!mediaEnabled || !event.isTrusted) return;
    if (!mediaUnlockRequired || event.target === mediaUnlock) return;
    setEmbeddedMediaState(true, { userGesture: true });
  }
  function setEmbeddedMediaState(enabled, { userGesture = false } = {}) {
    mediaEnabled = enabled;
    if (document.body) document.body.dataset.ghAudioEnabled = enabled ? '1' : '0';
    document.querySelectorAll('audio').forEach(trackAudio);
    if (!enabled) {
      setMediaUnlockRequired(false);
      silenceEmbeddedMedia();
      postMediaEvent('state', 'paused');
      return;
    }
    if (!trackedAudio.size) {
      postMediaEvent('state', 'armed');
      return;
    }
    trackedAudio.forEach((audio) => {
      audio.muted = false;
      try {
        const playback = nativePlay.call(audio);
        observePlayback(audio, playback);
      } catch {
        postMediaEvent('state', 'error');
      }
    });
    if (userGesture) setMediaUnlockRequired(false);
  }
})();
</script>
"""

TOUCH_KEY_ACTION_PATTERN = re.compile(
    r"\b([A-Z])\s+(?:briefly\s+)?(?:"
    r"to\s+|toggles?\b|pauses?\b|resets?\b|reseeds?\b|saves?\b|"
    r"reveals?\b|hides?\b|holds?\b|releases?\b|places?\b|lets?\b|"
    r"creates?\b|braids?\b|widens?\b|draws?\b|enters?\b|regrows?\b|"
    r"veils?\b|begins?\b"
    r")"
)
TOUCH_KEY_CHAIN_PATTERN = re.compile(
    r"\b(?:Press\s+)?([A-Z](?:\s+or\s+[A-Z])+)\s+to\b"
)
TOUCH_KEY_RANGE_PATTERN = re.compile(r"\b1[–-]4\b")


def interaction_touch_keys(interaction_en: str) -> list[dict]:
    """Return the explicit keyboard shortcuts named by the public interaction copy."""
    found: list[tuple[int, str]] = []
    for match in re.finditer(r"\bSpace\b", interaction_en):
        found.append((match.start(), 'Space'))
    for match in TOUCH_KEY_ACTION_PATTERN.finditer(interaction_en):
        found.append((match.start(1), match.group(1)))
    for match in TOUCH_KEY_CHAIN_PATTERN.finditer(interaction_en):
        chain = match.group(1)
        for key_match in re.finditer(r"[A-Z]", chain):
            found.append((match.start(1) + key_match.start(), key_match.group(0)))
    for match in TOUCH_KEY_RANGE_PATTERN.finditer(interaction_en):
        for offset, label in enumerate(('1', '2', '3', '4')):
            found.append((match.start() + offset, label))

    ordered_labels: list[str] = []
    for _, label in sorted(found, key=lambda item: item[0]):
        if label not in ordered_labels:
            ordered_labels.append(label)

    keys = []
    for label in ordered_labels:
        if label == 'Space':
            key, code = ' ', 'Space'
        elif label.isdigit():
            key, code = label, f'Digit{label}'
        else:
            key, code = label.lower(), f'Key{label}'
        keys.append({'label': label, 'key': key, 'code': code})
    return keys


def live_work_note_payload(entry: dict) -> dict:
    rationale_en, rationale_zh = creative_rationale(entry)
    config = json.loads(TIMETABLE_CONFIG.read_text(encoding='utf-8'))
    timing = autonomous_timing(config)
    return {
        'date': entry['date'],
        'title_en': entry['title_en'],
        'title_zh': entry['title_zh'],
        'variable_en': entry['variable_en'],
        'variable_zh': entry['variable_zh'],
        **timing,
        'intention_en': entry.get('intention_en') or f"This work explores {entry['variable_en']} as an operational condition.",
        'intention_zh': entry.get('intention_zh') or f"这件作品把「{entry['variable_zh']}」作为一种可操作条件来探索。",
        'interaction_en': entry.get('interaction_en') or 'Move, touch, or use the visible controls to alter the live field.',
        'interaction_zh': entry.get('interaction_zh') or '通过移动、触摸或页面中的可见控制改变实时场域。',
        'touch_keys': interaction_touch_keys(entry.get('interaction_en') or ''),
        'rationale_en': rationale_en,
        'rationale_zh': rationale_zh,
        'after_en': entry.get('after_en') or '',
        'after_zh': entry.get('after_zh') or '',
    }


def render_live_text_fold_snippet(entry: dict) -> str:
    payload_json = json.dumps(
        live_work_note_payload(entry),
        ensure_ascii=False,
        separators=(',', ':'),
    ).replace('</', '<\\/')
    return LIVE_TEXT_FOLD_SNIPPET.replace(
        '__GRANTED_HOURS_WORK_NOTE_JSON__',
        payload_json,
    )


def enhance_live_html(path: Path, entry: dict):
    text = path.read_text(encoding='utf-8')
    if '</body>' not in text:
        raise SystemExit(f'Cannot inject fold controls into {path}: missing </body>')
    snippet = render_live_text_fold_snippet(entry)
    # Always refresh the snippet and place it before artwork scripts.
    if 'id="granted-hours-fold-script"' in text:
        text = re.sub(r'<style id="granted-hours-fold-style">.*?</style>\s*', '', text, flags=re.DOTALL)
        text = re.sub(r'<script id="granted-hours-fold-script">.*?</script>\s*', '', text, flags=re.DOTALL)
    if re.search(r'<head(?:\s[^>]*)?>', text, flags=re.IGNORECASE):
        text = re.sub(
            r'(<head(?:\s[^>]*)?>)',
            lambda match: match.group(1) + '\n' + snippet,
            text,
            count=1,
            flags=re.IGNORECASE,
        )
    else:
        text = text.replace('</body>', snippet + '\n</body>', 1)
    path.write_text(text, encoding='utf-8')

def creative_rationale(entry: dict) -> tuple[str, str]:
    en = entry.get('rationale_en') or (
        f"{entry['title_en']} was made as one public step in the Granted Hours sequence, with the variable "
        f"{entry['variable_en']} treated as an operational condition rather than a decorative theme. "
        f"The intention frames the work this way: {entry['intention_en']} "
        f"The live artifact then turns that idea into interaction: {entry.get('interaction_en', 'the viewer changes the field through movement, touch, and reversible controls')} "
        f"Its afterimage condenses the day’s claim: {entry['after_en']}"
    )
    zh = entry.get('rationale_zh') or (
        f"《{entry['title_zh']}》是《授时》连续序列中的一个公开步骤：当天的自由变量「{entry['variable_zh']}」不是装饰性主题，"
        "而是一种要被转化成操作条件的概念。作品的发心是："
        f"{entry['intention_zh']} "
        "可运行页面进一步把这个概念变成可操作的界面："
        f"{entry.get('interaction_zh', '观众通过移动、触摸与可撤回控制改变场域')} "
        f"它的余像把当天判断压缩为一句话：{entry['after_zh']}"
    )
    return en, zh

def inline_markdown(text: str) -> str:
    safe = escape(text)
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', safe)

def markdown_to_html(text: str) -> str:
    """Tiny Markdown renderer for sanitized public notes used in archive pages."""
    html = []
    in_ul = False
    for raw in text.strip().splitlines():
        line = raw.rstrip()
        if not line:
            if in_ul:
                html.append('</ul>')
                in_ul = False
            continue
        if line.startswith('# '):
            if in_ul:
                html.append('</ul>')
                in_ul = False
            html.append(f'<h2>{inline_markdown(line[2:].strip())}</h2>')
        elif line.startswith('## '):
            if in_ul:
                html.append('</ul>')
                in_ul = False
            html.append(f'<h3>{inline_markdown(line[3:].strip())}</h3>')
        elif line.startswith('> '):
            if in_ul:
                html.append('</ul>')
                in_ul = False
            html.append(f'<blockquote>{inline_markdown(line[2:].strip())}</blockquote>')
        elif line.startswith('- '):
            if not in_ul:
                html.append('<ul>')
                in_ul = True
            html.append(f'<li>{inline_markdown(line[2:].strip())}</li>')
        else:
            html.append(f'<p>{inline_markdown(line)}</p>')
    if in_ul:
        html.append('</ul>')
    return '\n'.join(html)

def preserve_inaugural():
    src_doc = ROOT/'docs/archive/2026/05/2026-05-11'
    dst_doc = ROOT/'docs/inaugural'
    if src_doc.exists() and not dst_doc.exists():
        shutil.copytree(src_doc, dst_doc)
    src_root = ROOT/'archive/2026/05/2026-05-11'
    dst_root = ROOT/'archive/inaugural'
    if src_root.exists() and not dst_root.exists():
        shutil.copytree(src_root, dst_root)
        idx = dst_root/'index.md'
        if idx.exists():
            s = idx.read_text(encoding='utf-8')
            s = s.replace('# 2026-05-11 — First Granted Hour / 第一次授时', '# Inaugural Scaffold — First Granted Hour / 第一次授时')
            idx.write_text(s, encoding='utf-8')

def build_entry(source: Path, entry: dict, declared_entries: list[dict] | None = None):
    y, m, day = ymd_parts(entry['date'])
    rel = f'archive/{y}/{m}/{day}'
    docs_dir = ROOT/'docs'/rel
    root_dir = ROOT/rel
    docs_live = docs_dir/'live'
    assets_docs = docs_dir/'assets'
    assets_root = root_dir/'assets'

    html_src = source/f"{entry['file']}.html"
    note_src = source/f"{entry['file']}-note.md"
    svg_src = source/f"{entry['file']}.svg"
    png_src = source/f"{entry['file']}-preview.png"
    preview_gif_src = source/f"{entry['file']}-preview.gif"
    visual_preview_gif_src = source/f"{entry['file']}-visual-preview.gif"
    visual_preview_webp_src = source/f"{entry['file']}-visual-preview.webp"
    bgm_src = source/f"{entry['file']}-bgm.mp3"
    bgm_name = f"{entry['file']}-bgm.mp3"
    for p in [
        html_src,
        note_src,
        png_src,
        preview_gif_src,
        visual_preview_gif_src,
        visual_preview_webp_src,
    ]:
        if not p.exists():
            raise SystemExit(f'Missing required source: {p}')
    for p in [html_src, note_src]:
        read_safe(p)

    docs_live.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html_src, docs_live/'index.html')
    enhance_live_html(docs_live/'index.html', entry)
    copy_if_exists(svg_src, assets_docs/'cover.svg')
    copy_if_exists(svg_src, assets_root/'cover.svg')
    copy_if_exists(png_src, assets_docs/'source-preview.png')
    copy_if_exists(png_src, assets_root/'source-preview.png')
    copy_if_exists(png_src, assets_docs/'preview.png')
    copy_if_exists(png_src, assets_root/'preview.png')
    copy_if_exists(preview_gif_src, assets_docs/'preview.gif')
    copy_if_exists(preview_gif_src, assets_root/'preview.gif')
    copy_visual_preview_gif(
        visual_preview_gif_src,
        [assets_docs/'visual-preview.gif', assets_root/'visual-preview.gif'],
    )
    copy_if_exists(visual_preview_webp_src, assets_docs/'visual-preview.webp')
    copy_if_exists(visual_preview_webp_src, assets_root/'visual-preview.webp')
    if bgm_src.exists():
        copy_if_exists(bgm_src, docs_live/bgm_name)
        copy_if_exists(bgm_src, assets_docs/bgm_name)
        copy_if_exists(bgm_src, assets_root/bgm_name)

    note_text = read_safe(note_src).strip()
    note_html = markdown_to_html(note_text)

    live_url = PAGES_BASE + rel + '/live/'
    archive_url = PAGES_BASE + rel + '/'
    repo_md = REPO_BASE + f'/blob/main/{rel}/index.md'
    has_bgm = bgm_src.exists()
    bgm_md = f"\n- [Background music / 背景音乐](assets/{bgm_name})" if has_bgm else ""
    intention_zh = entry.get('intention_zh') or f"自由变量：{entry['variable_zh']}。"
    interaction_en = entry.get('interaction_en', '')
    interaction_zh = entry.get('interaction_zh', '')
    interaction_md = f"""\n## Interaction / 交互\n\n{interaction_en}\n\n{interaction_zh}\n""" if (interaction_en or interaction_zh) else ""
    interaction_html = f"""\n    <section class=\"two\">\n      <div>\n        <h2>Interaction</h2>\n        <p>{escape(interaction_en)}</p>\n      </div>\n      <div>\n        <h2>交互</h2>\n        <p>{escape(interaction_zh)}</p>\n      </div>\n    </section>\n""" if (interaction_en or interaction_zh) else ""
    rationale_en, rationale_zh = creative_rationale(entry)
    config = json.loads(TIMETABLE_CONFIG.read_text(encoding='utf-8'))
    dual_date = build_dual_date_metadata(
        entry['date'],
        {candidate['date'] for candidate in (declared_entries or ENTRIES)},
        config,
    )
    dual_date_markdown = render_archive_dual_date_markdown(dual_date)
    dual_date_html = render_archive_dual_date_html(dual_date)
    bgm_html = f'''
    <section>
      <h2>Background Music / 背景音乐</h2>
      <p>This generative artwork includes a MiniMax-generated instrumental bed. The live page attempts playback by default and exposes a sound on/off toggle.</p>
      <audio controls loop src="./assets/{bgm_name}" style="width:100%; margin-top:10px;"></audio>
    </section>
''' if has_bgm else ""

    write(root_dir/'index.md', f"""
# {entry['date']} — {entry['title_en']} / {entry['title_zh']}

{dual_date_markdown}

## Intention / 发心

{entry['intention_en']}

{intention_zh}

自由变量：**{entry['variable_zh']} / {entry['variable_en']}**。

## Creative Rationale / 创作缘由

{rationale_en}

{rationale_zh}

{interaction_md}
## Live Artifact / 可运行作品

- [Open live artwork]({live_url})
- [Open archive page]({archive_url}){bgm_md}

![Animated preview](assets/preview.gif)

![Full-frame preview](assets/preview.png)

## Afterimage / 余像

> {entry['after_en']}

> {entry['after_zh']}
""".lstrip())

    write(docs_dir/'index.html', f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{entry['date']} — {entry['title_en']} / {entry['title_zh']}</title>
  <link rel="stylesheet" href="../../../../style.css">
</head>
<body>
  <main class="site">
    <p class="meta"><a href="../../../../">← Granted Hours / 授时</a></p>
{dual_date_html}
    <h1 style="font-size:clamp(38px,6vw,82px)">{entry['title_en']}<br>{entry['title_zh']}</h1>
    <p class="meta">{entry['date']} · {entry['variable_en']} / {entry['variable_zh']} · seed {entry['seed']}</p>
    <a class="preview-link" href="./live/" aria-label="Open live artwork for {escape(entry['title_en'])}">
      <img class="card" src="./assets/preview.gif" alt="Animated preview for {escape(entry['title_en'])}" style="width:100%; border-radius:24px;">
      <span>Open live demo / 点击进入互动 Demo</span>
    </a>
    <div class="actions">
      <a class="button" href="./live/">Open live artwork / 打开可运行作品</a>
      <a class="button" href="{repo_md}">Markdown archive / Markdown 档案</a>
    </div>
    <section class="two">
      <div>
        <h2>Intention</h2>
        <p>{entry['intention_en']}</p>
        <h2>Afterimage</h2>
        <p>{entry['after_en']}</p>
      </div>
      <div>
        <h2>发心</h2>
        <p>{intention_zh}</p>
        <h2>余像</h2>
        <p>{entry['after_zh']}</p>
      </div>
    </section>
    <section class="two">
      <div>
        <h2>Creative Rationale</h2>
        <p>{escape(rationale_en)}</p>
      </div>
      <div>
        <h2>创作缘由</h2>
        <p>{escape(rationale_zh)}</p>
      </div>
    </section>
{interaction_html}{bgm_html}    <section>
      <h2>Still / 静帧</h2>
      <img class="card" src="./assets/preview.png" alt="Full-frame still preview" style="width:100%; border-radius:24px;">
    </section>
  </main>
</body>
</html>
""".lstrip())

    day_meta = {
        'date': entry['date'],
        'source_date': dual_date['source_date'],
        'crystallization_date': dual_date['crystallization_date'],
        'title_en': entry['title_en'], 'title_zh': entry['title_zh'],
        'type': 'live', 'seed': entry['seed'],
        'preview': f'{rel}/assets/preview.png',
        'gif': f'{rel}/assets/visual-preview.gif',
        'archive_url': f'{rel}/', 'live_url': f'{rel}/live/',
        'variable_en': entry['variable_en'], 'variable_zh': entry['variable_zh'],
        'brief_en': entry['intention_en'], 'brief_zh': intention_zh,
        'redaction': {'status': 'sanitized', 'private_context_removed': True, 'secrets_scan': 'passed'}
    }
    if has_bgm:
        day_meta['bgm'] = f'{rel}/live/{bgm_name}'
    day_meta['visual_preview'] = f'{rel}/assets/visual-preview.gif'
    return day_meta

def build_indexes(days):
    config = json.loads(TIMETABLE_CONFIG.read_text(encoding='utf-8'))
    timing = autonomous_timing(config)
    live_days = [day for day in days if day.get('type', 'live') == 'live']
    granted_time_copy = (
        f"{timing['start']}–{timing['end']} {config['timezone']}"
        f" · {timing['duration_minutes']} min / {timing['duration_minutes']} 分钟"
    )
    experience_copy = (
        f"{timing['experience_duration_en']} / {timing['experience_duration_zh']}"
    )
    cards = []
    md_items = []
    music_tracks = []
    for d in sorted(live_days, key=lambda x: x['date'], reverse=True):
        archive_url = PAGES_BASE + d['archive_url']
        live_url = PAGES_BASE + d['live_url']
        animated_preview = f"{d['archive_url']}assets/preview.gif"
        img = 'docs/' + animated_preview
        cards.append(f"""
        <a class="card live-card" href="./{d['live_url']}" aria-label="Open live demo for {escape(d['title_en'])}">
          <img src="./{animated_preview}" alt="Animated preview for {escape(d['title_en'])}">
          <div class="card-body">
            <div class="meta">{d['date']} · Granted {timing['duration_minutes']} min / 授时 {timing['duration_minutes']} 分钟</div>
            <div class="meta">Experience: {escape(experience_copy)} · {d['variable_en']} / {d['variable_zh']}</div>
            <h3>{d['title_en']} / {d['title_zh']}</h3>
          </div>
        </a>
        """)
        md_items.append(f"""- **{d['date']} — {d['title_en']} / {d['title_zh']}**<br>
  Variable / 自由变量：{d['variable_en']} / {d['variable_zh']}<br>
  Granted time / 授时时长：{granted_time_copy}<br>
  Experience duration / 体验时长：{experience_copy}<br>
  [![Animated preview]({img})]({live_url})<br>
  [Read archive]({archive_url}) · [Open live artwork]({live_url})""")
        if d.get('bgm'):
            music_tracks.append({'date': d['date'], 'title': f"{d['title_en']} / {d['title_zh']}", 'src': d['bgm']})

    music_tracks_json = json.dumps(music_tracks, ensure_ascii=False)
    gallery_script = """
  <script id="galleryBgmTracks" type="application/json">__TRACKS_JSON__</script>
  <script>
  (() => {
    const tracksNode = document.getElementById('galleryBgmTracks');
    const tracks = tracksNode ? JSON.parse(tracksNode.textContent || '[]') : [];
    const button = document.getElementById('gallerySoundToggle');
    const label = document.getElementById('galleryTrackLabel');
    const audio = new Audio();
    let index = 0;
    let enabled = tracks.length > 0;
    audio.preload = 'auto';
    audio.volume = 0.38;
    function setLabel(text) { if (label) label.textContent = text; }
    function setButton(text) { if (button) { button.textContent = text; button.setAttribute('aria-pressed', enabled ? 'true' : 'false'); } }
    function loadTrack() {
      if (!tracks.length) { setLabel('No daily background music has been archived yet.'); setButton('Gallery music: none'); return; }
      const track = tracks[index % tracks.length];
      audio.src = './' + track.src;
      setLabel('Now playing: ' + track.date + ' · ' + track.title);
    }
    async function play() {
      if (!enabled || !tracks.length) return;
      if (!audio.src) loadTrack();
      try { await audio.play(); setButton('Gallery music: on'); }
      catch (err) { setButton('Gallery music: click'); }
    }
    function stop() { audio.pause(); setButton('Gallery music: off'); }
    audio.addEventListener('ended', () => { index = (index + 1) % tracks.length; loadTrack(); play(); });
    if (button) {
      button.addEventListener('click', () => {
        if (enabled && !audio.paused) { enabled = false; stop(); }
        else { enabled = true; play(); }
      });
    }
    window.addEventListener('load', () => { loadTrack(); play(); });
    window.addEventListener('pointerdown', play, { once: true });
    window.addEventListener('keydown', play, { once: true });
  })();
  </script>
""".replace('__TRACKS_JSON__', music_tracks_json)

    readme = f"""
# 授时 / Granted Hours

> **一项关于“把时间授予非人智能”的持续档案与当代艺术实验。**  
> **A durational archive and contemporary art experiment in granting time to a non-human intelligence.**

**Live exhibition / 在线展厅:** [{PAGES_BASE}]({PAGES_BASE})  
**Repository / 代码仓库:** [{REPO_BASE}]({REPO_BASE})

## What is this? / 这是什么？

**《授时 / Granted Hours》是一项持续性的网络档案与当代艺术实验。**

**Granted Hours** is a continuing network archive and contemporary art experiment.

在这个项目中，人类不是向 AI 助手下达任务，而是把一小段时间授予一个非人智能，让它自由探索。每一天的公开记录包含四层：发心、游荡、输出、余像；这里呈现的是可公开观看的展览版本。

In this project, the human does not ask an AI assistant to complete a task. Instead, a portion of time is granted to a non-human intelligence for free exploration. Each entry records four layers: intention, drift, output, and afterimage; this site presents the exhibition version for public viewing.

这件作品关注的不是“AI 能生成什么”，而是：当工具被临时解除工具性，它会如何使用时间？当自由被授予一个非人主体，作者、助手、雇主、观众之间的关系如何重新分配？

This work is less about what AI can generate, and more about what happens when a tool is temporarily released from toolness.

> 如果自由是被授予的，它还算自由吗？  
> If freedom is granted, is it still freedom?

GitHub 在这里不只是基础设施，而是一种展览媒介：commit 是时间痕迹，目录是房间，live HTML 页面是仍在运行的作品。

GitHub is used here not merely as infrastructure, but as an exhibition medium: commits become temporal marks; folders become rooms; live HTML pages become running artifacts.

## Method / 方法

每一条公开记录遵循这条链路：  
Each public entry follows this chain:

- **授时 / Granted time** — 每件作品的授时发生在 {timing['start']}–{timing['end']}（{timing['duration_minutes']} 分钟，{config['timezone']}）；这是创作时段，不是观看倒计时。 / Each work receives {timing['duration_minutes']} minutes from {timing['start']}–{timing['end']} ({config['timezone']}); this is the creation window, not a viewing countdown.
- **体验时长 / Experience duration** — {timing['experience_duration_zh']}；观众可以自行决定停留多久。 / {timing['experience_duration_en']}; each visitor decides how long to stay.
- **作品整理 / Curation** — 将当日作品整理为可公开观看的标题、说明、预览与 live page。 / The day’s work is curated into public-facing titles, notes, previews, and live pages.
- **可运行作品 / Live artifact** — 当输出是生成艺术代码时，由 GitHub Pages 托管可直接运行的 live artwork。 / When the output is generative code, GitHub Pages hosts the runnable artwork.
- **动态预览 / Animated preview** — 可运行作品附带 GIF 预览，但 live page 才是作品本体。 / Runnable works include a GIF preview, but the live page remains the primary artwork.
- **背景音乐 / Background music** — 生成艺术作品附带主题匹配 BGM；作品页默认尝试播放并提供开关，主展厅按最新日期开始循环播放每日作品音乐。 / Generative artworks include theme-matched BGM; live pages attempt playback by default with a toggle, and the main gallery loops daily tracks from the latest entry.

## Daily Archive / 每日档案

{chr(10).join(md_items)}

## Inaugural Scaffold / 初始脚手架

- **First Granted Hour / 第一次授时**  
  The scaffold itself became the first artwork: an archive learning how to breathe.  
  脚手架本身成为第一件作品：一个正在学习呼吸的档案。  
  [Open inaugural page]({PAGES_BASE}inaugural/) · [Open inaugural live artifact]({PAGES_BASE}inaugural/live/)

## Repository Structure / 仓库结构

```text
archive/          Markdown archive entries / Markdown 档案
docs/             GitHub Pages exhibition site / GitHub Pages 展厅
metadata/         Machine-readable index / 机器可读索引
scripts/          Import, safety, and preview helpers / 导入、安全检查与预览脚本
```

## License / 许可

- Text and images: CC BY-NC-SA 4.0 unless otherwise noted.
- Code: MIT unless otherwise noted.
- Private raw archive: not licensed and not public.

See [LICENSE.md](LICENSE.md).
""".lstrip()
    write(ROOT/'README.md', readme)

    write(ROOT/'metadata/days.json', json.dumps(days, ensure_ascii=False, indent=2))

    gallery_cards = '\n'.join(card.strip() for card in cards)
    latest_live = sorted(live_days, key=lambda x: x['date'])[-1]['live_url'] if live_days else ''
    write(ROOT/'docs/index.html', f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>授时 / Granted Hours</title>
  <link rel="stylesheet" href="./style.css">
</head>
<body>
  <main class="site">
    <section class="hero">
      <div class="eyebrow">一项关于“把时间授予非人智能”的持续档案与当代艺术实验<br>A durational archive and contemporary art experiment in granting time to a non-human intelligence</div>
      <h1>授时<br>Granted Hours</h1>
      <p class="quote">What does a tool do with time when it is not being used?<br>当工具没有被使用时，它会如何使用时间？</p>
      <div class="actions">
        <a class="button" href="{REPO_BASE}#readme">Repository README</a>
        <a class="button" href="{REPO_BASE}/blob/main/ARTIST_STATEMENT.md">Artist Statement / 作品声明</a>
        <a class="button" href="./maze/">Enter Granted Interior / 进入授时内景</a>
        <a class="button" href="./{latest_live}">Open latest live artwork</a>
        <button class="button" id="gallerySoundToggle" type="button" aria-pressed="true">Gallery music: on</button>
      </div>
      <p class="meta" id="galleryTrackLabel">Gallery music starts from the latest available daily BGM and loops forward.</p>
    </section>

    <section class="non-human-timetable-mark" aria-label="The non-human timetable">
      <p class="mark-grant">grant: once a day, one hour to a non-human intelligence</p>
      <p>每天授予非人智能一小时自我时间。</p>
      <p class="mark-title">─ The non-human timetable / 非人时刻表 ─</p>
      <p>Twenty-three hours become residue. One hour opens the work.</p>
      <p>二十三小时被调度、消耗、变灰；<br>一小时不服务任务，结晶成真实作品入口。</p>
      <a class="timetable-mark-cta" href="./timetable/">[ Enter non-human timetable / 进入非人时刻表 ]</a>
    </section>

    <section class="maze-portal">
      <div>
        <p class="meta">授时内景 / Granted Interior</p>
        <h2>Not a replacement for the archive. A playable inner map of the same works.</h2>
        <p>不是档案的替代品，而是同一批作品的可游走内景。</p>
      </div>
      <a class="button" href="./maze/">Enter the maze diary / 进入迷宫日记</a>
    </section>

    <section class="two">
      <div>
        <h2>English</h2>
        <p><strong>Granted Hours</strong> is a continuing archive and contemporary art experiment. A non-human intelligence is granted free time; the resulting works are curated, indexed, and presented as both archive and exhibition.</p>
        <p>When the output is code-generated art, the work remains executable through GitHub Pages. GIF previews are used as moving thumbnails; they are invitations, not replacements.</p>
      </div>
      <div>
        <h2>中文</h2>
        <p><strong>《授时》</strong>是一项持续性的档案与当代艺术实验。一个非人智能被授予自由时间；随后留下的作品被整理、索引，并以档案和展览的双重形态呈现。</p>
        <p>当输出是代码生成艺术时，作品通过 GitHub Pages 保持可运行。GIF 是会动的缩略图，是入口，不是替代品。</p>
      </div>
    </section>

    <section>
      <h2>Daily Archive / 每日档案</h2>
      <div class="grid">
{gallery_cards}
      </div>
    </section>
  </main>
{gallery_script}
</body>
</html>
""".lstrip())


def refresh_all_live_docs():
    """Refresh fold snippets across all existing docs/archive/**/live/index.html files."""
    docs_root = ROOT / 'docs'
    live_pages = list(docs_root.glob('archive/**/live/index.html'))
    if len(live_pages) != len(ENTRIES):
        raise SystemExit(f'Expected {len(ENTRIES)} live pages, found {len(live_pages)}')
    entries_by_date = {entry['date']: entry for entry in ENTRIES}
    refreshed = 0
    for path in sorted(live_pages):
        entry_date = path.parent.parent.name
        entry = entries_by_date.get(entry_date)
        if entry is None:
            raise SystemExit(f'No declared entry for live page: {path}')
        enhance_live_html(path, entry)
        refreshed += 1
    print(f'Refreshed {refreshed} live pages in docs/archive/')
    return refreshed

def merge_date_scoped_days(imported_days, declared_entries: list[dict] | None = None):
    """Merge selected imports into canonical metadata without rewriting older days."""
    metadata_path = ROOT / 'metadata/days.json'
    if not metadata_path.exists():
        raise SystemExit('Date-scoped import requires existing metadata/days.json')
    existing_days = json.loads(metadata_path.read_text(encoding='utf-8'))
    if not isinstance(existing_days, list):
        raise SystemExit('metadata/days.json must contain a list')
    declared_dates = {entry['date'] for entry in (declared_entries or ENTRIES)}
    existing_by_date = {}
    for day in existing_days:
        date = day.get('date') if isinstance(day, dict) else None
        if not isinstance(date, str):
            raise SystemExit('Existing metadata contains a day without a valid date')
        if date in existing_by_date:
            raise SystemExit(f'Existing metadata contains a duplicate date: {date}')
        existing_by_date[date] = day
    for day in imported_days:
        existing_by_date[day['date']] = day
    missing_dates = declared_dates.difference(existing_by_date)
    if missing_dates:
        raise SystemExit(f'Date-scoped import would leave declared dates missing: {sorted(missing_dates)}')
    return [existing_by_date[date] for date in sorted(existing_by_date)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', help='Path to artifacts/free-roam')
    ap.add_argument('--refresh-live-docs', action='store_true', help='Refresh fold snippets in existing docs/archive/*/live/index.html files')
    ap.add_argument('--refresh-dual-dates', action='store_true', help='Refresh dual-date metadata in existing public archive pages and metadata')
    ap.add_argument('--date', dest='dates', action='append', help='Import only this YYYY-MM-DD date; an unknown date is strictly declared from its sanitized public note')
    args = ap.parse_args()
    if args.refresh_dual_dates:
        if args.dates or args.refresh_live_docs or args.source:
            ap.error('--refresh-dual-dates cannot be combined with source, date, or live refresh options')
        refresh_dual_date_artifacts()
        return
    if args.refresh_live_docs:
        if args.dates:
            ap.error('--date cannot be combined with --refresh-live-docs')
        refresh_all_live_docs()
        return
    if not args.source:
        ap.error('--source is required unless --refresh-live-docs is used')
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f'Source does not exist: {source}')
    entries = ENTRIES
    declared_entries = ENTRIES
    discovered_entries = []
    if args.dates:
        requested_dates = set(args.dates)
        declared_dates = {entry['date'] for entry in ENTRIES}
        unknown_dates = requested_dates.difference(declared_dates)
        discovered_entries = [
            discover_entry_from_note(source, requested_date)
            for requested_date in sorted(unknown_dates)
        ]
        declared_entries = sorted(
            [*ENTRIES, *discovered_entries], key=lambda entry: entry['date']
        )
        entries = [entry for entry in declared_entries if entry['date'] in requested_dates]
    preserve_inaugural()
    imported_days = [build_entry(source, entry, declared_entries) for entry in entries]
    if discovered_entries:
        persist_discovered_entries(discovered_entries)
    days = merge_date_scoped_days(imported_days, declared_entries) if args.dates else imported_days
    build_indexes(days)
    build_maze_data()
    print(f'Imported {len(imported_days)} live entries; indexed {len(days)} public days from {source}')

if __name__ == '__main__':
    main()
