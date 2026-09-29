# Qwen 本地语音小工具

用户排除不能公开自部署的 StepAudio 2.5，随后要求改试 Qwen。
本次在 Apple M5 Pro / 64 GB 上实际接入并生成语音；未部署到 Spark 或儿童课堂。

## 当前入口与模型

新版地址 `http://127.0.0.1:7300/`，此前 7050、7250、7270、7290 的进程与录音会话保留。
旧进程仍运行旧实现，不会因为新版上线自动变为 Qwen。

- 对话伙伴：**Qwen3-TTS 1.7B CustomVoice，MLX 8bit**。Serena 温柔女声、Uncle Fu
  温和男声可在设置切换，带自然、温柔闲聊的语气指令。不是 Step 2.5 预设音色的复现。
- 本人参考音色读文章：**Qwen3-TTS 0.6B Base，MLX 8bit**。参考 WAV 在内存中解码，
  按模型采样率重采样，再传入参考音频数组与核对后的文字。
- 转写继续使用本机 Whisper，文字对话继续使用本机 Step3-VL-10B。
  Qwen 此处负责发声与音色复刻，没有替换文字对话模型。

本轮接入时 `studio/voice_lab.py` 默认选择 Qwen；随后用户选定
[VoxCPM2](voxcpm2-voice-lab.md)，当前复现 Qwen 需显式指定
`--speech-provider qwen`，旧云端路径使用 `--speech-provider step-cloud`。
本地路径不自动退回云端。页面模型标签、音色选项、生成说明和清理提示来自实际配置，
本地模式不显示云端收费估算。

## 实测

固定公共短句：“今天有没有一件让你觉得开心的小事？不着急，慢慢说，我在听。”

| 项目 | 本次结果 |
|---|---|
| 两个模型加载 | 6.96 秒 |
| 冷运行“你好” | 首块 4.06 秒，完整 4.22 秒 |
| 热模型 Serena | 完整合成 1.92 秒，输出 6.64 秒 |
| 热模型 Uncle Fu | 完整合成 2.33 秒，输出 8.16 秒 |
| 新版页面实际开场 | 女声等待 2.5 秒，男声 2.7 秒；原生播放器均可播放、无媒体错误 |
| HTTP 完整流程中的录音处理 | 0.35 秒，含整段与参考片段两次本机转写 |
| HTTP 追问文字 | 3.23 秒，返回模式 `local` |
| HTTP 追问男声 | 1.90 秒，输出 6.4 秒 |
| 同一问题、同一声音重听 | 0.0007 秒，复用服务端音频缓存 |
| 参考音色读测试短句 | 首次独立测试 25.82 秒；后续 HTTP 测试 1.5 秒 |

这是一组单次、短句测试，不是平均值或实时课堂保证。对话发声的 1.9–2.7 秒不包含
用户录音和文字模型思考。模型热运行首个音频块约 0.12–0.13 秒，但当前网页仍收齐
整句后播放，不能把这个模型内部指标当作用户首音等待。

首次音色复刻使用此前保存的公共合成女声作参考，读“午后的阳光落在窗边，桌上的茶
还冒着一点热气。”；Whisper 转写覆盖目标全文。男女声的转写存在“在／再”等同音字
及“有没有／又没有”差异，不能仅凭转写判定听感。未使用用户真实录音做代理测试，
本人音色相似度仍需用户录音、回听判断。

测量音频和 JSON 位于忽略目录 `outputs/voice-audition/qwen/`。
独立生成脚本屏蔽 Python 网络连接并设置离线加载，记录 **0 次网络尝试**。
真实 HTTP 流程仅使用 loopback 服务，不同于阻断所有连接的独立模型测试。

## 隔离与验证

- `studio/providers/qwen_voice.py` 使用单一工作线程加载和推理，防止并发请求混用
  MLX 的解码状态；对话和复刻共享这个串行执行器。
- 文章结束、失败或取消时清理参考 token／文字缓存与流式解码状态；不创建长期音色。
  页面结束后，正在处理的文章会在下一个音频块检查取消状态。
- 设置只接受当前模型的音色白名单。缓存仍按会话、问题和音色区分，迟到的语音不会
  在新会话或录音中开始播放。
- 32 项 Python 语音专项检查、8 项页面播放检查通过；JavaScript 语法检查通过。
  Python 中的模型桩不证明真实推理，真实模型生成与 HTTP 闭环是另外执行的检查。
- 浏览器验证了模型标注、女声开场、设置切换男声与播放。实际 HTTP 闭环验证了录音、
  转写、核对、追问、TTS、重听、文章生成和结束后无法访问音频。
- 所有新增依赖只放在 `scratch/voice-audition/venv`，没有改变生产依赖清单。

## 复现与来源

从仓库根目录启动：

```sh
scratch/voice-audition/venv/bin/python -m studio.voice_lab --speech-provider qwen --port 7300
```

需使用已安装 MLX Audio 的隔离环境，首次权重准备需要联网；启动和合成使用本地路径。
可通过 `--qwen-dialogue-path` / `--qwen-clone-path` 指向同版本模型目录。

| 权重 | 固定版本 | 文件总量 |
|---|---|---|
| `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit` | `41d3337e8b7f2843a75841595fc14e4b9a7a4b96` | 3.08 GB |
| `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit` | `50f45ef0047cde7e84c2ef04326acb8ada2436a7` | 1.99 GB |

文件大小不等于运行峰值内存。运行时为 MLX Audio 0.5.1、MLX 0.32.2；MLX 运行时
不能直接迁移到 NVIDIA Spark，届时需使用 Qwen 官方支持的推理实现并重新测量。

- [Qwen 官方：CustomVoice、Base、指令控制与部署](https://github.com/QwenLM/Qwen3-TTS)
- [1.7B CustomVoice MLX 权重](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit)
- [0.6B Base MLX 权重](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit)
- [MLX Audio Qwen 实现](https://github.com/Blaizzy/mlx-audio/tree/main/mlx_audio/tts/models/qwen3_tts)
