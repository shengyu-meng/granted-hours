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
    <img class="card" src="./assets/preview.gif" alt="Animated preview for {escape(entry['title_en'])}" style="width:100%; border-radius:24px;">
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
        <a class="card" href="./{d['archive_url']}">
          <img src="./{d['gif']}" alt="Animated preview for {escape(d['title_en'])}">
          <div class="card-body">
            <div class="meta">{d['date']} · {d['variable_en']} / {d['variable_zh']}</div>
            <h3>{d['title_en']} / {d['title_zh']}</h3>
            <p>Live generative artwork; GIF preview plus runnable page.</p>
          </div>
        </a>
        """)
        md_items.append(f"""- **{d['date']} — {d['title_en']} / {d['title_zh']}**<br>
  Variable / 自由变量：{d['variable_en']} / {d['variable_zh']}<br>
  ![Animated preview]({img})<br>
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
    print(f'Imported {len(days)} live entries from {source}')

if __name__ == '__main__':
    main()
