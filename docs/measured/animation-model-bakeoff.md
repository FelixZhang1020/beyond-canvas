# 儿童画局部动画：七种 Replicate 模型实测

结论范围：两张用户指定真实画、每模型每图一次、固定 seed 42。
本轮真实调用 Replicate 产生 **14 个成功输出**，不是模拟；没有在 DGX Spark 上执行。
用户已明确允许上传这两张画至 Replicate 进行付费测试，随后要求比较其他可离线部署模型。
未调用 Step3-VL-10B，未替换生产配置，未将图片编辑结果或旧前端形变冒充视频模型输出。

## 结论

**优先继续验证 FLUX.2 Klein 4B 生成局部动作关键帧的路线。** 它在这两张图上比
Step1X 更能保留构图，指定士兵抬手成功，但仍会改动脸、双臂和笔触；尚不是合格的
完整动画方案。Qwen Image Edit 2511 的动作更明确，同时更容易把孩子的画重新规整。

本轮四种直接图生视频均未同时满足「指定角色有动作、原画笔触与角色不重画、背景固定」。
不能因为 API 成功或视频能播放就认定功能修复完成，也不能由两个样本否定模型全部能力。
进一步路线应先验证受限局部编辑／原画背景保留，再验证中间帧的一致性；不能直接把整图
编辑结果淡入淡出当作已完成角色动画。本轮没有实现这条新路线。

## 实际结果与计时

下表「计算」来自 API `metrics.predict_time`；「服务总时长」来自 `metrics.total_time`，
包含服务端启动和排队。均是云端计时。客户端轮询可能延迟观察，不能拿轮询完成时间当
模型运行速度；两张图的结果按「狮子／城堡」排序。Klein 两次均经历约百秒启动／排队，
1 秒计算时间不能描述首次用户等待。

| 模型 | 输出 | 计算秒 | 服务总时长秒 | 两图观察 |
|---|---|---:|---:|---|
| FLUX.2 Klein 4B | 单张关键帧 | 1.14 / 1.27 | 100.73 / 111.03 | 狮子头部与笔触改变；指定士兵抬手、其他人物保留，但双臂和细节也变化 |
| Qwen Image Edit 2511 | 单张关键帧 | 18.85 / 18.78 | 20.61 / 33.17 | 抬头／挥手清楚；狮子脸卡通化，人物形态和画面位置改变 |
| Step1X-Edit v1 | 单张关键帧 | 58.01 / 52.08 | 160.65 / 52.15 | 狮子与幼狮明显重画；城堡多个人物丢失，出现拉长空白区域 |
| Wan 2.2 5B Fast | 3.33 秒视频 | 6.01 / 5.90 | 6.10 / 5.97 | 两图很快被改成更规整、高饱和卡通，超出指定局部 |
| Wan 2.2 I2V A14B | 3.375 秒视频 | 30.90 / 36.90 | 30.99 / 36.98 | 狮子卡通化并站起；城堡末尾凭空生成拿笔的人手 |
| LTX-Video 0.9.1 | 3.88 秒视频 | 13.42 / 17.78 | 101.11 / 75.71 | 狮子图主要是画面漂移；城堡几乎静止，指定动作不明显 |
| LTX-2 Distilled | 3.375 秒视频 | 9.64 / 7.84 | 9.96 / 7.93 | 整幅画平移／放大，其他内容被裁切，没有固定背景的局部动作 |

检查了全部六张生成图与八段视频各五个等距抽样帧；浏览器逐个执行视频播放和解码检查。
视觉结论来自人工观察抽样帧，不是独立盲评、逐帧视频质量评估或自动质量分数。
LTX-2 输出还含音轨，展示默认静音；未评价音频质量。

## 参数与可复现范围

- 相同原始输入，经现有 `to_data_uri` 处理，最长边 1024。两张都是用户指定画；不在 Git 保存。
- 图像模型使用相同英文编辑指令；视频模型使用相同对应场景英文动作指令。
  指定左下大狮子微抬头／轻呼吸，或上层阳台黑帽红衣士兵微抬前臂；其他部分与相机保持静止。
- Step1X size 1024，固定平台版本；Klein 1 MP、`go_fast=false`；Qwen `go_fast=false`。
- Wan 5B 为平台 Fast 变体、480p、81 帧、24 fps，输出实际 80 帧；Wan A14B 为普通变体、
  480p、30 步、81 帧、24 fps。Wan 5B 接口只列 16:9/9:16，但实测 I2V 输出仍随输入比例并对齐尺寸。
- LTX-Video 平台仅提供 0.9/0.9.1，本轮 0.9.1、97 帧、target_size 640、30 步、CFG 3、
  image_noise_scale 0.05，实际 25 fps。**不是** LTX-Video 0.9.8 蒸馏模型。
- LTX-2 Distilled 81 帧、image_strength 1、enhance_prompt false。该平台版本不开放分辨率、
  步数或量化参数，实际约 1 MP。不是当前上游后续 2.3/2.5 版本。
- 所有平台公开安全选项保持默认开启。服务端截止时间 Step1X 3 分钟，其他 5 分钟。
- 一共 8 次 HTTP 429 拒绝没有创建任务；等待后只补发明确拒绝的请求。
  没有重跑已接受任务。保存意图和预测 ID 后再轮询，避免不确定 POST 被自动重复计费。

| Replicate 模型 | 固定版本 |
|---|---|
| `zsxkib/step1x-edit` | `12b5a5a61e3419f792eb56cfc16eed046252740ebf5d470228f9b4cf2c861610` |
| `black-forest-labs/flux-2-klein-4b` | `8e9c42d77b10a2a41af823ac4500f7545be6ebc4e745830fc3f3de10de200542` |
| `qwen/qwen-image-edit-2511` | `a0670a7f47d5975347c105b6ce71456c4377d511993975988127dee03ca6c729` |
| `wan-video/wan-2.2-5b-fast` | `c92ab4265c9b3b5ea9ac9a87df839ebfd662ee3a820d62c21305bf6501a73fe1` |
| `wan-video/wan-2.2-i2v-a14b` | `2c62e0842338726c74ad99a3c469255ce3f4c1f66ee000c265451b87754ac0c9` |
| `lightricks/ltx-video` | `8c47da666861d081eeb4d1261853087de23923a268a69b63febdf5dc1dee08e4` |
| `lightricks/ltx-2-distilled` | `6707072d3b2a513cee6ab771021d355b5aa52997dded5e1c97d1bebe8d93f920` |

平台没有对所有封装公开实际 GPU、精度、检查点校验和和加速器实现；某些元数据显示 CPU
只是封装入口，不应据此说视频在 CPU 上生成。固定 API 版本仍不等于已验证离线逐位复现。
尤其 Wan Fast 的托管优化与开放基础模型须分开验收。

## 离线部署与 DGX Spark

Spark 的 [NVIDIA 官方规格](https://www.nvidia.com/en-us/products/workstations/dgx-spark/)
为 128 GB CPU/GPU 一致性统一内存、273 GB/s 内存带宽、20 核 Arm CPU。FP4 稀疏峰值
不是这些模型 BF16／FP8 的生成吞吐，不能由此推算本轮云端秒数。

| 模型 | 官方离线依据 | 对本项目 Spark 的判断（非到机实测） |
|---|---|---|
| Klein 4B | [官方模型卡](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)：Apache 2.0，4 步，约 13 GB VRAM，Diffusers／ComfyUI | 体量与本轮效果最值得优先验证；参考 VRAM 含卸载条件，仍需实测统一内存总峰值 |
| Step1X v1 | [官方代码与内存表](https://github.com/stepfun-ai/Step1X-Edit)：Apache 2.0；1024 FP8 参考约 34 GB，未卸载全精度约 49.8 GB | 可以作为单模型轮换候选，效果在本轮不合格；这些是 H800 数据，不是 Spark |
| Qwen 2511 | [官方模型卡](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)：Apache 2.0，公开本地推理 | 更重的备选。20B 生成模型仅 BF16 权重已约 40 GB，另有编码器／激活；不是 40 GB 峰值承诺 |
| Wan 5B | [官方实现](https://github.com/Wan-Video/Wan2.2)：Apache 2.0；720p I2V 可用 24 GB GPU 配合卸载 | 比 A14B 更适合先测资源，但本轮 Fast 保真失败；CPU 卸载在统一内存上不等于减少系统总占用 |
| Wan A14B | 同上：约 27B 总专家参数、每步 14B 激活；官方 720p 单卡示例至少 80 GB VRAM | 仅作较重效果对照。480p＋量化可继续评估，不能与多个大模型同时常驻或保证课堂即时 |
| LTX-Video 0.9.1 | [官方仓库](https://github.com/Lightricks/LTX-Video)有 0.9.1 发布记录和本地代码；后来版本改为 OpenRail-M | 旧 2B 轻量基线，实际动作不足；具体旧权重许可需按部署版本核对，不能将最新许可与性能直接套用 |
| LTX-2 Distilled | [官方权重](https://huggingface.co/Lightricks/LTX-2)提供 19B 蒸馏／量化权重与本地代码 | 可离线评估，但需算上文本编码器、VAE 与解码峰值；本轮没有充分证据保证 90 GB 课堂预算内运行 |

LTX-2 使用[社区许可证](https://huggingface.co/Lightricks/LTX-2/blob/main/LICENSE)，不是 Apache 2.0；
其条款含企业年收入达到 1,000 万美元需取得付费商业许可等条件。离线前应按实际实体及
具体版本核对，不能把 Replicate 托管使用权当作无限制本地商用授权。

[NVIDIA ComfyUI Spark 指南](https://build.nvidia.com/spark/comfyui/video-gen-workflow)
证明存在本地图像／视频工作流路径，但其中 Wan 2.1、FLUX.1 等示例不是本轮版本的实测。
该指南也提示统一内存设备从低档开始、必要时降低帧数和分辨率；不能把 128 GB 全部
分配给媒体模型。仍须核对 Arm64 容器、GB10 CUDA／PyTorch／注意力算子、模型加载与卸载
峰值，且媒体任务串行运行，给课堂常驻模型和系统保留空间。

本轮筛选的是七种有离线路径、不同体量的代表性候选，不是 Replicate 全站穷举。
未验证 `tencent/hunyuan-video-1.5` 精确端点（404），不能说整个平台没有 Hunyuan，
也没有用不明替代端点或闭源视频模型补充样本。

## 费用与私有产物

按本轮读取的各模型公开页面计价配置与 API 计量，估算共 **$1.2086（约 $1.21）**。
**未读取账户账单，不能当作已核销费用。** 当前按输出计价的模型优先使用输出费率，
不套用页面遗留 GPU 秒价或示例中位费用。

| 模型 | 计价依据 | 两次合计估算 USD |
|---|---|---:|
| [Klein 4B](https://replicate.com/black-forest-labs/flux-2-klein-4b) | 输入／输出各 $1 / 1000 MP；本轮每次各计 1 MP | 0.0040 |
| [Qwen 2511](https://replicate.com/qwen/qwen-image-edit-2511) | $0.03 / 输出图 | 0.0600 |
| [Step1X](https://replicate.com/zsxkib/step1x-edit) | $0.0014 / 计算秒 | 0.1541 |
| [Wan 5B](https://replicate.com/wan-video/wan-2.2-5b-fast) | 本轮 480p $0.0125 / 视频 | 0.0250 |
| [Wan A14B](https://replicate.com/wan-video/wan-2.2-i2v-a14b) | 本轮 480p $0.40 / 视频 | 0.8000 |
| [LTX-Video](https://replicate.com/lightricks/ltx-video) | $0.000975 / 计算秒 | 0.0304 |
| [LTX-2](https://replicate.com/lightricks/ltx-2-distilled) | $0.02 / 输出视频秒 | 0.1350 |

全部输入副本、提示词、原始输出、固定版本 schema、私有预测 ID、脱敏报告、计价页面片段、
抽样帧、对比页与浏览器检查均留在 Git 忽略目录 `outputs/model-animation-bakeoff/`；
Step1X 原报告在 `outputs/step1x-animation/`。没有在本记录中保存预测访问 URL、儿童画、
个人信息或凭据。预览仅通过本机回环地址提供，不是公网部署。

## 用户选择与归档

完成对比后，用户认为 FLUX.2 Klein 4B 与 Qwen Image Edit 的图片效果更好，也认可
Wan 2.2 I2V A14B 的视频效果。用户决定当前功能先使用 **FLUX.2 Klein 4B**。
Qwen 保留为图片备选，Wan A14B 保留为视频候选；此前按严格局部保真标准作出的观察
保留为测试记录，不代表用户否定这些输出。没有由此次选择推断 Spark 已验收。

14 个原始生成结果、两张输入、提示词、版本／计量、对比页面和本报告的评测快照
已打包到私有忽略目录 `outputs/evaluations/animation-model-bakeoff.zip`。
包内含 SHA-256 文件清单，已通过 ZIP 完整性检查；可在云端输出链接过期后继续查看。
同目录的 `animation-model-bakeoff-manifest.json` 记录选择与文件校验值。
归档不是 Git 提交或公网发布，未包含环境文件与 API 密钥。
