#!/usr/bin/env python3
"""Import sanitized free-roam HTML artworks into Granted Hours public mirror.

Usage:
  python3 scripts/import_free_roam_artifacts.py --source /path/to/artifacts/free-roam

The script copies only already-sanitized public-facing artifacts: HTML, note markdown,
SVG covers, and PNG previews. It does not read private logs.
"""
from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path
from html import escape
from build_maze_data import build_maze_data

ROOT = Path(__file__).resolve().parents[1]
PAGES_BASE = 'https://shengyu-meng.github.io/granted-hours/'
REPO_BASE = 'https://github.com/shengyu-meng/granted-hours'

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

def read_safe(path: Path) -> str:
    text = path.read_text(encoding='utf-8')
    for rx in SAFETY_PATTERNS:
        if rx.search(text):
            raise SystemExit(f'Possible private/sensitive content in {path}: {rx.pattern}')
    return text

def copy_if_exists(src: Path, dst: Path):
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

LIVE_TEXT_FOLD_SNIPPET = r"""
<style id="granted-hours-fold-style">
  .gh-fold-toggle {
    position: fixed;
    z-index: 2147483647;
    top: max(12px, env(safe-area-inset-top));
    right: max(12px, env(safe-area-inset-right));
    min-height: 38px;
    border: 1px solid rgba(255,255,255,.24);
    border-radius: 999px;
    padding: 9px 13px;
    background: rgba(3,7,13,.72);
    color: #f6efe3;
    font: 12px/1.1 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    letter-spacing: .02em;
    backdrop-filter: blur(14px);
    box-shadow: 0 12px 44px rgba(0,0,0,.34);
    cursor: pointer;
    touch-action: manipulation;
  }
  .gh-fold-toggle:hover { border-color: rgba(242,195,107,.72); color: #fff3cf; }
  body.gh-text-folded .panel,
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
  body.gh-text-folded .gh-fold-toggle {
    background: rgba(3,7,13,.82);
  }
  @media (max-width: 760px) {
    .gh-fold-toggle { top: 10px; right: 10px; padding: 10px 12px; }
  }
</style>
<script id="granted-hours-fold-script">
(() => {
  if (window.__grantedHoursFoldReady) return;
  window.__grantedHoursFoldReady = true;
  const STORAGE_KEY = 'grantedHoursTextFolded';
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'gh-fold-toggle';
  btn.setAttribute('aria-controls', 'textPanel legend');
  btn.setAttribute('aria-label', 'Fold or unfold artwork text overlays');
  document.addEventListener('DOMContentLoaded', init, { once: true });
  if (document.readyState !== 'loading') init();
  function init() {
    if (!document.body || document.body.contains(btn)) return;
    document.body.appendChild(btn);
    const stored = localStorage.getItem(STORAGE_KEY);
    const mobileDefault = window.matchMedia && window.matchMedia('(max-width: 760px)').matches;
    setFolded(stored === null ? mobileDefault : stored === '1', false);
    btn.addEventListener('click', () => setFolded(!document.body.classList.contains('gh-text-folded'), true));
  }
  function setFolded(folded, persist) {
    document.body.classList.toggle('gh-text-folded', folded);
    btn.textContent = folded ? 'Show text / 显示文字' : 'Fold text / 折叠文字';
    btn.setAttribute('aria-pressed', folded ? 'true' : 'false');
    if (persist) localStorage.setItem(STORAGE_KEY, folded ? '1' : '0');
  }
})();
</script>
"""

def enhance_live_html(path: Path):
    text = path.read_text(encoding='utf-8')
    if 'id="granted-hours-fold-script"' in text:
        return
    if '</body>' not in text:
        raise SystemExit(f'Cannot inject fold controls into {path}: missing </body>')
    path.write_text(text.replace('</body>', LIVE_TEXT_FOLD_SNIPPET + '\n</body>', 1), encoding='utf-8')

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
        "live 页面进一步把这个概念变成可操作的界面："
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

def build_entry(source: Path, entry: dict):
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
    bgm_src = source/f"{entry['file']}-bgm.mp3"
    bgm_name = f"{entry['file']}-bgm.mp3"
    for p in [html_src, note_src]:
        if not p.exists():
            raise SystemExit(f'Missing required source: {p}')
        read_safe(p)

    docs_live.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html_src, docs_live/'index.html')
    enhance_live_html(docs_live/'index.html')
    copy_if_exists(svg_src, assets_docs/'cover.svg')
    copy_if_exists(svg_src, assets_root/'cover.svg')
    copy_if_exists(png_src, assets_docs/'source-preview.png')
    copy_if_exists(png_src, assets_root/'source-preview.png')
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
    bgm_html = f'''
    <section>
      <h2>Background Music / 背景音乐</h2>
      <p>This generative artwork includes a MiniMax-generated instrumental bed. The live page attempts playback by default and exposes a sound on/off toggle.</p>
      <audio controls loop src="./assets/{bgm_name}" style="width:100%; margin-top:10px;"></audio>
    </section>
''' if has_bgm else ""

    write(root_dir/'index.md', f"""
# {entry['date']} — {entry['title_en']} / {entry['title_zh']}

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
        'date': entry['date'], 'title_en': entry['title_en'], 'title_zh': entry['title_zh'],
        'type': 'live', 'seed': entry['seed'],
        'preview': f'{rel}/assets/preview.png',
        'gif': f'{rel}/assets/preview.gif',
        'archive_url': f'{rel}/', 'live_url': f'{rel}/live/',
        'variable_en': entry['variable_en'], 'variable_zh': entry['variable_zh'],
        'redaction': {'status': 'sanitized', 'private_context_removed': True, 'secrets_scan': 'passed'}
    }
    if has_bgm:
        day_meta['bgm'] = f'{rel}/live/{bgm_name}'
    return day_meta

def build_indexes(days):
    cards = []
    md_items = []
    music_tracks = []
    for d in sorted(days, key=lambda x: x['date'], reverse=True):
        archive_url = PAGES_BASE + d['archive_url']
        live_url = PAGES_BASE + d['live_url']
        img = 'docs/' + d['gif']
        cards.append(f"""
        <a class="card live-card" href="./{d['live_url']}" aria-label="Open live demo for {escape(d['title_en'])}">
          <img src="./{d['gif']}" alt="Animated preview for {escape(d['title_en'])}">
          <div class="card-body">
            <div class="meta">{d['date']} · {d['variable_en']} / {d['variable_zh']}</div>
            <h3>{d['title_en']} / {d['title_zh']}</h3>
            <p>Tap the GIF/card to enter the interactive demo. Archive note stays in README and daily page.</p>
          </div>
        </a>
        """)
        md_items.append(f"""- **{d['date']} — {d['title_en']} / {d['title_zh']}**<br>
  Variable / 自由变量：{d['variable_en']} / {d['variable_zh']}<br>
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

- **授时 / Granted time** — 一次不以功利任务为目的的自由探索开始。 / A free-exploration session begins without a utilitarian brief.
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
    latest_live = sorted(days, key=lambda x: x['date'])[-1]['live_url'] if days else ''
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

    <section class="maze-portal">
      <div>
        <p class="meta">授时内景 / Granted Interior</p>
        <h2>Not a replacement for the archive. A playable inner map of the same works.</h2>
        <p>不是档案的替代品，而是同一批作品的可游走内景。</p>
      </div>
      <a class="button" href="./maze/">Enter the maze diary / 进入迷宫日记</a>
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', required=True, help='Path to artifacts/free-roam')
    args = ap.parse_args()
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f'Source does not exist: {source}')
    preserve_inaugural()
    days = [build_entry(source, e) for e in ENTRIES]
    build_indexes(days)
    build_maze_data()
    print(f'Imported {len(days)} live entries from {source}')

if __name__ == '__main__':
    main()
