# 画里画外 · 大殿篇 — 九十秒讲解稿

给站在台上的人。页面在 `http://127.0.0.1:7090/`，按 [docs/measured/demonstration-dashboard.md](../measured/demonstration-dashboard.md) 里的方式启动；
**现场** 在这座大殿上真跑：展台用 `--quick --model output/foguang-east-hall/foguang-east-hall-v25.blend` 启动（launch 配置 `showpiece-exhibit`），渲染用小图快出；五个录播不受影响。
开场前把语言切到观众的语言（右上角 EN / 中文），把浏览器放到全屏。

**开场一句（按表之前先说，约十秒）：** 「画里画外，说的是让画走出纸面：孩子的一幅画，在课堂里变成动画、3D 和绘本。大殿篇把同一套 Agent Skills 和 Harness 用在一座真殿上——从一张照片、一段描述，走到一座经得起重力和地震的大殿。课堂上，每一步有安全和教学规则守着孩子；这里，每一步有 Harness 守着大殿。」

| 秒 | 你按什么 | 你说什么 | 观众看到什么 |
|---|---|---|---|
| 0–10 | 什么都不按 | 「这是佛光寺东大殿，8,017 个构件。不是视频，是一个大模型在开六个 Agent Skill，每一步都看得见。」 | 3D 大殿在屏幕上慢慢转 |
| 10–25 | **盖起来** | 「一句话：把大殿从零盖到屋脊。模型先清点构件，再算谁托着谁，排出 36 个阶段，然后出片。」 | 左边一步步打出来：思考、清点、承托、阶段，每张卡片写着用了多少秒；右边渲染帧数往上跳；二十秒后大殿在 3D 里一幕一幕立起来 |
| 25–40 | **拆开来** | 「换一句：把角柱头的斗拱拆开。它自己挑了拆榫卯这个技能，拱在栌斗里怎么交叉，一层一层拉开。」 | 同样一步步走完；十几秒后斗拱在 3D 里散开；按「成片」看真渲染 |
| 40–55 | **松开手** | 「最狠的一句：把所有构件松开，看它站不站得住。6,264 块木头在重力下松开，掉了 0 块，动了 0 块。」 | 走完步骤后 3D 里大殿纹丝不动；卡片上写着 SETTLE 6264 pieces fell 0 shifted 0 |
| 55–70 | 提示词那一排，任选一条 | 「这几条是录播——大殿一条要渲染十到三十分钟，我们把模型真跑过的那次回放给你看：它在想、在渲染、每一帧在画。」 | 和一键演示一样一步步走，但慢一倍、像现场：左边打字，右边一帧一帧画，左栏控制台里技能一个个亮起来；结束时成片放大 |
| 70–85 | **现场** 里选一条（认构件约 2 分钟；拆开来约 4 分钟，出小图快渲染的成片） | 「不信是活的？现在就在这座大殿上现场跑。模型自己挑技能，命令、输出、退出码都在卡片上；渲染用小图，所以几分钟。」 | 实时那一行亮起，思考真的在等，工具真的在跑，每张卡片写着 `$ blender …`，斗拱在 3D 里拆开 |
| 85–90 | 什么都不按 | 「六个技能，六道题：有技能，六道全做完；没技能，只做完两道。这就是 Skill 的价值。」 | 后台监控上的计数 |

**必说的一句真话：** 大殿那五条是录播，标着「录播」；现场那条是真的。判官问「这是实时的吗」之前先说。

**别做的事：** 别在大殿上现场跑（十到三十分钟一个工具）；别把 3D 拖得太快（帧率是 61，但投影仪不一定跟得上）。

**对话上方是三段开关：** 一键演示 / 提示词 / 现场，一次只露一种；上台前切到「一键演示」，讲到录播时切「提示词」，最后切「现场」。

**一键演示每个按钮约二十秒走完**（思考、三四张工具卡、渲染帧数往上跳、最后 3D 动起来）；不必等它走完，下一个按钮随时可以按，上一段就停。

**左栏是后台控制台：** 机器四条、组件和六个技能的进程表、管线树、日志尾巴；判官问「六个技能在哪」就指着进程表数。

**判官问「Harness 是什么」：** 打开 `http://127.0.0.1:7090/harness`（Harness 页，独立于大殿）。图上是 harness 的十二个部件，用业界通用的叫法：Agent loop、Tools、Skills、工具前后和停止时的三种 Hook、Subagent、Permissions、Memory、Transcript、Evals。按任一个技能按钮（聊聊你的画、让画动起来、拆开来……），它的请求就走一遍图，每步一句说明；点任何一个部件翻出卡片：通用叫法是什么、我们这里是哪个文件、差在哪。先说一句：这一页是按代码和实测数字写好的演示，不是现场运行；卡片上的「差在哪」就是判官会问的问题，先答为敬。

**顺手的事：** 画面右上角 **⤢** 让画面铺满整个窗口（Esc 退出）；跑完的一次，按 **重播** 可以再看一遍，不花 token；
投影仪 1080p 下整页一屏放得下，不用滚动；切 EN / 中文随时可以，3D 不会丢。

**万一：** 页面空白 → 刷新，再按一次；3D 没出来 → 右上角 **3D 模型** 按钮点一下；
现场跑一次超过两分钟 → 说「模型在排队，StepFun 每分钟十次」，切回录播继续。

---

## English, for a mixed room

Open with, before the table (about ten seconds): "Beyond Canvas — 画里画外 — is about pictures stepping off the page: in class a child's drawing becomes a clip, a 3D figure, a storybook. The hall chapter, 大殿篇, puts the same Agent Skills and harness to work on a real temple: from one photograph and a description to a hall that stands up to gravity and an earthquake. In class, safety and teaching rules guard every step for the child; here, the harness guards every step for the hall."

| s | press | say | they see |
|---|---|---|---|
| 0–10 | nothing | "The East Hall of Foguang, 8,017 pieces. Not a video: one model driving six Agent Skills, every step in view." | the 3D hall turning |
| 10–25 | **build it** | "One line: build the hall from nothing to the ridge. It counts the pieces, works out who carries whom, 36 stages, then films it." | its thought, then the tool cards one by one with their seconds, the render's frames counting up on the screen; after twenty seconds the hall rises scene by scene in 3D |
| 25–40 | **take it apart** | "Another line: take the corner bracket set apart. It chose the joint skill itself; the arms cross in the big block, tier by tier." | the same steps, briskly; then the bracket set opening in 3D (the film is one button away) |
| 40–55 | **let it settle** | "The hardest line: let every piece go. 6,264 timbers under gravity: none fell, none shifted." | after the steps, the hall unmoved in 3D; the card reads fell 0 shifted 0 |
| 55–70 | any prompt chip | "These are recordings: a hall run renders for ten to thirty minutes, so we replay the real one: thinking, rendering, frame by frame." | the same steps at half the speed, as if live: typing, frames painting, skills lighting on the console; the film large at the end |
| 70–85 | **live**, pick one (name the pieces, about 2 min; take it apart, about 4 min, a quick-render film) | "Not convinced it's alive? Live, now, on this hall. The model picks its own skills; command, output and exit code sit on every card; quick renders, so a few minutes." | the live row lights; the thinking really waits, the tools really run, each card shows `$ blender …`, the bracket set opens in 3D |
| 85–90 | nothing | "Six skills, six tasks: with the skills all six finished; without them, two. That is what a skill is worth." | the counters |

Say before you are asked: the five hall runs are recordings and are badged so; the live row runs for real on the same hall.

Each one-press button plays out in about twenty seconds (thought, three or four tool cards, frames counting up, then the 3D moving); the next press cuts in at once.

If a judge asks "what is the harness": open `http://127.0.0.1:7090/harness`, the Harness page, separate from the temple. The board holds the harness's twelve parts under the general names the field uses: Agent loop, Tools, Skills, the hooks before a tool, after a tool and on stop, Subagent, Permissions, Memory, Transcript, Evals. Press any skill button and its request travels the board, one line of explanation per step; click any part for its card: what it is generally called, which of our files sits there, and the gap. Say first that the page is a demonstration written from the code and measured numbers, not a live run; the gap line on each card is the question a judge would ask, so answer it before they do.

Handy: **⤢** on the screen panel fills the window (Esc leaves); the page is one screen at 1080p; switching language is safe.
