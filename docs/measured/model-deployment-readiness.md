# 模型现状与 DGX Spark 离线部署评估

保存本次模型配置研究结果；这是检查时的快照，不是部署完成证明，也不授权更换模型、租用 GPU 或修改运行配置。

## 后续配置变更：Step1X-Edit

随后用户明确要求在线版并删除本地版后，`spark.image.edit` 已改用 Replicate，
三套配置统一锁定已实测版本，本地服务和内存占位已移除；未发现本机安装权重。
验证记录原在项目背景笔记里（该笔记后来已移除，git 历史中仍有）。
因此下文是变更前的检查快照，其中“全部离线”、Step1X 本地预算与媒体构建失败
不再适用于当前 `image.edit` 配置；其余问题没有因此自动解决。

## 结论与约束

- 最终目标：全部运行于 DGX Spark，只使用本地模型，支持离线环境。
- 开发阶段允许在线与本地混用；同一模型的远程部署更适合验证最终效果，替代模型只能验证部分流程。
- 模型路线基本可行，但当前不能直接切换 `spark` 配置完成全离线部署。
- 开发机减负建议：优先远程部署同一 Step3-VL-10B，保留本地 Whisper。此项是建议，尚未实施。

## 当前模型汇总

本机大小是磁盘权重大小，不是运行内存。“未发现”限定于项目指定目录及已检查的 Hugging Face、Whisper、LM Studio、Ollama 等常见模型目录；运行状态仅代表检查时刻。

| 模型／用途 | 当前开发环境 | 本机安装情况 | 能否改用在线版本 | DGX Spark 离线部署现状 |
|---|---|---|---|---|
| **Step3-VL-10B**：看画、对话、动画编排、几何识别 | `local` 使用本机；`cloud` 用 Qwen3-VL-8B 替代 | **已安装、正在运行**；Q4_K_M 权重＋使用中的投影器约 **8.38 GiB** | 未确认稳定现成 API；**可租 GPU 部署同一模型** | 有本地部署路线；需验证 Spark 兼容性、内存和速度 |
| **Qwen3-VL-8B**：开发阶段视觉替代模型 | OpenRouter 在线 | 未发现安装 | **已使用在线版** | 当前不是 Spark 目标；其测试结果不能直接代表 Step3-VL |
| **Step 3.7 Flash**：判卷、质量检查 | StepFun 在线 | 未发现安装 | **已使用在线版** | **主要阻碍**：配置预算 109 GB；课堂实时调用与“独占设备运行”方案冲突 |
| **ShieldGemma 2 4B**：安全检查 | 尚未接入，当前借用在线 director | 未发现安装 | 项目注释记录托管路线，实际接入仍需核实与适配 | **尚未接通**；安全分类输出不能直接替代现有作品判断和文字识别 |
| **Step1X-Edit**：图片编辑 | Replicate 在线 | 未发现安装 | **已使用在线版** | 目标为 v1 FP8，官方参考峰值约 34 GB；本地服务与媒体适配未完成 |
| **InstantMesh**：通用图片转 3D | 已配置 Replicate；**当前课堂几何重建未调用它** | 未发现安装 | **已配置在线版** | 本地服务未完成，需验证 ARM/CUDA；目前无需因配置存在就常驻 |
| **StepAudio 2.5 TTS → Step-Audio-EditX**：语音合成 | 已配置在线 StepAudio；页面仍使用浏览器朗读 | 两者均未发现安装 | StepAudio 已在线；不能视为 EditX 的同模型版本 | **未接入**；EditX 官方标准运行约 12–15 GB，当前 8 GB 预算偏低 |
| **Whisper small Q5_1**：录音转文字 | 本机 whisper-server | **已安装、正在运行**；权重约 **0.177 GiB** | 可以改云端，但常见服务不是相同版本；**建议保留本地** | 迁移难度相对低；需构建 Spark 版本并验证 |
| **Depth Anything V2 Small**：深度估计 | 仅预留 Spark 配置 | 未发现安装 | 可寻找托管路线，当前未接入 | 尚未接入业务与本地服务 |
| **Step1X-3D**：精细 3D | 仅预留 Spark 配置 | 未发现安装 | 未确认现成稳定 API；可远程自部署 | 尚未接入，完整运行内存与兼容性未验证 |
| **Qwen3.6-35B-A3B MLX 4bit** | **项目未使用**，属于 LM Studio 下载 | 已安装，权重约 **19.00 GiB**；未发现运行进程 | **有 OpenRouter 在线版** | 不在项目部署计划中；MLX 运行环境不能直接搬到 Spark |
| **Gemma-4-E4B-it MLX 4bit** | **项目未使用**，属于 LM Studio 下载 | 已安装，权重约 **6.36 GiB**；未发现运行进程 | 未确认稳定现成 API；可远程自部署 | 不在项目部署计划中；需更换适合 Spark 的推理环境 |

本机另有约 3.69 GiB 的旧 Step3-VL 视觉投影器，启动脚本使用另一份适配后的文件。旧文件占磁盘，不代表同时占用推理内存。检查时 7100、7130 健康接口返回 200；LM Studio 默认 1234 端口拒绝连接。

## 部署前需要解决的问题

1. **实时判卷与大模型独占冲突。** `Conversation` 的质量检查即时调用 director；Step 3.7 Flash 总参数约 198B，不能按每 token 激活约 11B 来估计权重内存。建议评估另一个小型视觉模型承担课堂独立判卷，将大模型留给课后批量评估；尚未改变产品规则或实现。
2. **预算不是运行峰值。** Spark 配置的 48 GB 常驻＋34 GB 轮换＝82 GB 混用了权重与运行占用。仅把 EditX 从 8 改按官方标准 12–15 GB 估算，账面值就达约 86–89 GB；这仍不是 Spark 测量值，也未补齐其他开销。InstantMesh 还依赖 Zero123++、前景分割等组件。
3. **本地媒体协议未完成。** 对 Spark 的 `image.edit`、`mesh.fast`、`tts.studio`、`tts.export` 进行无推理的构建检查，均因缺少任务声明报 `UnknownTask`；即使添加任务声明，当前媒体构建器仍不支持 `llamacpp`。
4. **安全模型不能直接替换。** ShieldGemma 2 的官方输出是政策违规 Yes/No 概率；现有安全脚本还要求五类作品判定与图片文字识别，需明确分工和适配。
5. **实际模型装卸未实现。** `watchdog` 维护状态和预算，没有真正启动或卸载服务；day-zero 模拟切换不能证明实机连续加载可靠。
6. **离线包及硬件兼容性未验证。** Spark 使用 ARM CPU、Blackwell GPU 和共享内存；Mac 二进制不能直接复用。需准备适配的依赖与容器、全部辅助模型、tokenizer、投影器和音频解码器，并验证断网冷启动。CPU offload 不代表拥有另一块独立物理内存。
7. **页面语音仍有独立依赖。** `speechSynthesis` 使用客户端浏览器语音，离线效果取决于客户端已安装资源；尚未接入配置中的 TTS 服务。
8. **版本与授权材料需固定。** 在线基础模型不保证与本机量化版本数值一致；应固定权重修订、量化、模板和参数。EditX 查阅的许可证说明明确覆盖代码，不能直接据此断定所有权重授权；ShieldGemma 下载需先完成官方条款访问流程。

当前工作区的素描 3D 已采用“视觉模型识别几何体＋程序重建”，动画由模型编排、浏览器播放；这两条实际流程均不需要专用扩散或网格生成模型。此前背景快照关于素描 3D 未接入的描述已落后于本次检查。

## 证据入口与验证范围

本次完成配置和调用链阅读、本机模型文件盘点、模型服务只读健康检查、无推理的媒体构建检查及官方资料核对。没有修改运行配置、停止模型、调用收费推理服务或进行 Spark 实机测试。检查时工作区存在并行变更，后续应重新读取当前代码。

项目依据：

- [cloud 配置](../../studio/profiles/cloud.yaml)、[local 配置](../../studio/profiles/local.yaml)、[spark 配置](../../studio/profiles/spark.yaml)
- [本机模型启动脚本](../../studio/ops/localmodels.sh)、[媒体适配器](../../studio/providers/__init__.py)
- [对话与判卷](../../studio/conversation/conversation.py)、[几何重建](../../studio/making/sketch.py)、[安全脚本](../../skills/studio-safety/scripts/safety.py)
- [内存预算状态机](../../studio/core/watchdog.py)、[转写客户端](../../studio/voice/transcribe.py)、[浏览器语音](../../studio/page/src/26-companion.js)

本次查阅的外部资料（可用性与依赖版本会变化）：

- [NVIDIA Spark 硬件：128 GB 共享内存、273 GB/s、ARM](https://docs.nvidia.com/dgx/dgx-spark/hardware.html)
- [NVIDIA Spark 依赖支持表](https://docs.nvidia.com/dgx/dgx-spark-porting-guide/porting/dependencies.html)
- [Step3-VL 官方模型卡与部署方法；当前无 HF Inference Provider](https://huggingface.co/stepfun-ai/Step3-VL-10B)
- [Step 3.7 Flash 官方模型卡](https://huggingface.co/stepfun-ai/Step-3.7-Flash)
- [ShieldGemma 2 官方模型卡与输出定义](https://huggingface.co/google/shieldgemma-2-4b-it)
- [Step1X-Edit 官方内存表](https://github.com/stepfun-ai/Step1X-Edit)
- [InstantMesh 安装说明](https://github.com/TencentARC/InstantMesh)、[完整推理依赖](https://github.com/TencentARC/InstantMesh/blob/main/run.py)
- [Step-Audio-EditX 官方运行内存与组件说明](https://github.com/stepfun-ai/Step-Audio-EditX)、[权重仓库许可证说明](https://huggingface.co/stepfun-ai/Step-Audio-EditX/blob/main/README.md)
- [Qwen3.6-35B-A3B 在线 API](https://openrouter.ai/qwen/qwen3.6-35b-a3b)
- [Gemma-4-E4B-it 官方页；当前无 HF Inference Provider](https://huggingface.co/google/gemma-4-E4B-it)
- [Replicate Whisper：当前常用版本为 large-v3](https://replicate.com/openai/whisper)
