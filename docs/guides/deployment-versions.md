# 部署与运行指南

写给要把本项目跑起来的协作者。本文改写过两次：先是 **StepFun First 成为唯一的方案**
（API First 与 Local First 归档，配置在 [studio/profiles/archive/](../../studio/profiles/archive/README.md)
仅供参考）；随后运营方决定**整个项目搬到托管的 DGX Spark 上运行，Mac 只用于开发**，
Mac + 4090 的运行方式也一并归档。

**一分钟版本**：课堂在 Spark 上。浏览器打开 `https://{Spark 的地址}:7100`，第一次会提示
"连接不是私密连接"（证书是项目自己签的），继续访问后输入课堂密码即可。Mac 不开机也能上课。

---

## StepFun First

方案回答的问题是：**这些模型跑在谁的机器上**。名称保持英文，与代码和界面一致。

| 工作 | 在哪里 |
|---|---|
| 看画、反馈、聊天、规则检查、老师评价、安全检查 | DGX Spark：Qwen3.6-35B-A3B（思考关闭），另有 NVIDIA Nemotron 3.5 Content Safety 再看一次 |
| 素描 3D：几何体由 Step 3.7 Flash 读形、电脑搭实体；其余用 TRELLIS.2（Pixal3D 已停用） | StepFun 订阅 + DGX Spark |
| 彩画 3D 小玩偶 | StepFun 订阅（step-3.7-flash 写零件、复查） |
| 让画动起来 | DGX Spark（Wan 2.2 I2V A14B）；设了 DashScope 密钥时改用阿里云 Wan 3.0（按次付费，画会发给阿里云） |
| 故事书的绘本页与朗读 | DGX Spark（FLUX.2 Klein 4B；VoxCPM2 用孩子自己的声音） |
| 说话给孩子听 | StepFun 订阅（stepaudio-2.5-tts） |
| 听孩子说话 | StepFun 按次付费（stepaudio-2.5-asr，订阅里没有听写） |
| 页面、课堂、课程档案（Portfolio）、示例画 | DGX Spark |

- StepFun 的说话、读草图和 3D 小玩偶走订阅，地址是 `.../step_plan/v1`；听写走按次付费的
  `.../v1`。订阅里有哪些模型：[StepFun 订阅方案给了什么](stepfun-plan-models.md)。
- 3D、Spark 上的动画和故事书都在 Spark 上。FLUX.2 Klein 4B 只画故事书的绘本页；过去的
  静态姿势图已停用。过去从 Mac 运行时，图片与 3D 走隧道到 4090，视频向
  Replicate 购买（4090 只装得下 5B）；这套配置归档在
  [studio/profiles/archive/stepfun-mac-4090.yaml](../../studio/profiles/archive/stepfun-mac-4090.yaml)，
  4090 本身保持原样、不再使用。

归档的方案做过什么、为什么归档、怎么恢复：
[studio/profiles/archive/README.md](../../studio/profiles/archive/README.md)。

---

## 上课

1. 浏览器打开 `https://{Spark 的地址}:7100`。第一次会出现证书警告，选择继续访问。
2. 输入课堂密码。密码只存在 Spark 上（`~/.config/beyond-canvas/door/password`），不进仓库；
   同一个浏览器七天内不用再输。
3. **iPad / iPhone 要用摄像头和麦克风**：在登录页点"先安装这张证书"，安装描述文件后到
   「设置 → 通用 → 关于本机 → 证书信任设置」打开信任。安卓与电脑上的 Chrome 继续访问后
   即可使用。

为什么要证书：浏览器只在"安全地址"上允许网页使用摄像头和麦克风，普通 http 地址不行，
而课堂拍照和听孩子说话都要用到（运营方选择了"自签证书、首次提示一次"）。

---

## 开发（在 Mac 上）

Python 3.13 与 uv，虚拟环境固定为 `.venv`。

```bash
git clone https://github.com/FelixZhang1020/beyond-canvas.git
cd beyond-canvas
uv sync                                   # 依据 pyproject.toml 与 uv.lock 建出 .venv
cp .env.example .env                      # 只需要填 STEPFUN_API_KEY
sh deploy/spark/test-on-spark.sh sh studio/page/build.sh   # 改过 studio/page/src/ 之后在 Spark 上重新生成 index.html，结果自动带回 Mac
sh deploy/spark/sync.sh                   # 把代码送到 Spark，同时把 Spark 上的课程档案取回一份
sh deploy/spark/tunnel.sh                 # 开发时从 Mac 访问同一个课堂：http://localhost:7070/
```

**测试不在 Mac 上跑，一律在 Spark 上跑**（运营方的决定：Mac 只留开发环境）。
下面这一条命令把当前代码连同测试送到节点上的 `~/beyond-canvas-test`，在那里跑完再把结果带回来，
不会碰到正在上课的那一份：

```bash
sh deploy/spark/test-on-spark.sh          # Python 测试、页面构建与检查、打包与签名
```

在 Spark 上启动或补起服务（**有课时不要执行**，会中断正在进行的生成）：

```bash
sh ~/beyond-canvas/deploy/spark/start.sh
```

### 申请自己的密钥

**每人用自己的密钥，不要共用一套。** `.env` 只留在自己的电脑上，永远不要提交；提交前先确认它不在其中。

| 密钥 | 去哪里申请 | 什么时候需要 |
|---|---|---|
| `STEPFUN_API_KEY` | https://platform.stepfun.com | 始终需要 |
| `DASHSCOPE_API_KEY` | 阿里云百炼 | 只在要用在线的 Wan 3.0 动画时需要 |

`sync.sh` 只把这两把密钥写到 Spark 上，`.env` 里的其他内容不会离开本机。

`REPLICATE_API_KEY` 与 `FAL_KEY` StepFun First 都不再需要。`.env.example` 里的
`OPENROUTER_API_KEY`、`SILICONFLOW_API_KEY`、`REPLICATE_API_KEY` 属于评测用的
`cloud` / `local` 配置。

---

## 模型服务联系不上时

Spark 上的课堂启动时会逐位检查；缺了的模型会在页面「系统管理 → 系统状态」里标出来，
**不会退回到别的方案**。先在 Spark 上确认服务在跑：

```bash
curl http://127.0.0.1:7260/v1/models     # 视频；3D 是 7240 / 7250
```

以前保存过 API First 或 Local First 的机器，启动时会说明它已归档并直接用 StepFun First。

---

## 每张画大概花多少钱

- 看画、反馈、聊天、检查、老师评价：在 Spark 上的 Qwen3.6 运行，不按次花钱。
- 说话、读草图、3D 小玩偶：在 StepFun 订阅里，按次不再另计费（订阅本身的费用照付）。
- 听写（stepaudio-2.5-asr）和在线的 Wan 3.0 动画：按次付费。
- 3D、Spark 上的动画、故事书：在 Spark 上运行，不按次花钱。

---

## Spark 上有什么

脚本都在 [deploy/spark/](../../deploy/spark/)：

| 脚本 | 做什么 |
|---|---|
| `sync.sh` | 从 Mac 送代码；结束时取回一份课程档案 |
| `start.sh` | 在 Spark 上起服务（只起没在运行的） |
| `door-setup.sh` / `door.py` | 课堂的安全入口：自签证书、课堂密码，公网 7100 → Spark 本机 7000 → 课堂 7060 |
| `send-class-data.sh` | 把课程档案与示例画送到 Spark（需先停掉 Spark 上的课堂） |
| `pull-portfolio.sh` | 把 Spark 上的课程档案取回 Mac，保留最新一份和最近三份带日期的 |
| `snapshot-portfolio.sh` | 在 Spark 上每天 03:00 给课程档案拍一份快照，保留最近七份不同的，放在 `~/portfolio-snapshots` |
| `test-on-spark.sh` | 在 Spark 上跑全部测试；给它一条命令，就改跑那条命令（评测、就绪检查），写出的文件带回 Mac |
| `build-blender.sh` / `bin/blender` | Spark 上的 Blender：Ubuntu 26.04 的 5.0.1 装在容器里；出图用 NVIDIA 芯片（同一段大殿动画 79 秒，用处理器要 1498 秒），占芯片约四分之一、2.4 GiB，其余留给课堂；大殿重建和展品的实时运行都在 Spark 上做 |
| `fetch-model.sh` | 想在 Mac 的 Blender 里看某个模型时，把它从 Spark 下载到 Mac 并打开；`--list` 列出 Spark 上的模型 |

**Spark 没有备份，比赛结束后磁盘会被清空。** 所以 Mac 上保留课程档案与示例画
的副本，每次 `sync.sh` 也会取回一份最新的课程档案。Spark 上的每日快照只防误写，随节点一起清空。
**最后一堂课之后、比赛结束之前，再运行一次 `sh deploy/spark/pull-portfolio.sh`**。

---

## 隐私：这件事请先读完再分享给别人

本项目面向儿童，请如实向任何人说明数据去了哪里：

- **孩子的画**在 Spark 上由 Qwen3.6 读图、反馈和做安全检查；素描几何体和 3D 小玩偶会发给 StepFun；
  选了在线动画时会发给阿里云。
- **孩子的录音会发给 StepFun 转写**（`stepaudio-2.5-asr`），每一堂课都是如此。Local First
  曾能把录音留在自己的硬件上；它已归档，运营方是在知道这一后果的情况下
  做的决定。转写外发本身是运营方更早的决定，代码里 `studio/providers/stepfun_asr.py` 与
  `studio/voice/transcribe.py` 都写明了它推翻的那句承诺。
- **每幅画最多保留一段录音**：孩子第一次开口的回答，最多 10 秒，连同听到的文字留在 Spark 上，
  用来让故事书用孩子自己的声音朗读。撤回回答、清空聊天、删除画作或课程时一并删除；Spark 的每日快照
  和取回 Mac 的副本在它们各自过期前仍保留。其余录音不保存。
- 课程档案与示例画存放在 Spark 上。示例画是 AI 生成或运营方自有的公开数据（运营方
  说明），不是儿童个人数据。

以下内容**绝不能进仓库**：密钥（`.env`）、示例画、工作室的本地状态（`.studio/`：课程档案、账本、日志）。
`.env` 也不离开开发机（上面两把密钥是唯一例外）。

---

## 常见问题

**密钥看起来是对的却被拒绝。** StepFun 的密钥只在 `api.stepfun.com` 上有效。
`api.stepfun.ai` 也会响应，并把正确的密钥报成 "Incorrect API key provided"，看起来像密钥
错了，其实是域名错了。

**回复是空的。** Step 3.7 Flash 关不掉推理，`max_tokens` 给小了会被隐藏的推理吃光，返回空
内容。配置里已设为 `reasoning.effort = low` 且 `max_tokens ≥ 1000`，改动前请留意。

**端口。** 本项目开的端口都在 7000–7700 之间且以 0 结尾，规则写在
[studio/server/ports.py](../../studio/server/ports.py)。

**打不开课堂地址。** 先确认 Spark 上 `tmux ls` 里有 `door` 和 `studio`；没有就运行
`start.sh`。忘了密码：在 Spark 上读 `~/.config/beyond-canvas/door/password`；要换密码，删掉
这个文件再运行 `start.sh`，会生成新的。

---

## 不在本文范围

共用密钥；恢复已归档的方案（见归档说明）；4090 的模型服务（归档前的说明在
[deploy/gpu-media/README.md](../../deploy/gpu-media/README.md)）。
