# 对话伙伴声音试听实测

延续[离线语音候选检查](offline-voice-options.md)，
用户要求继续试听其他与自己对话的语音模型。本次实际新生成两种模型、四种预设声音，
没有使用用户录音或测试音色复刻，也没有切换或重启正在使用的个人语音实验。

## 产物与范围

- 试听页：`outputs/voice-audition/index.html`，本次本机服务端口 7260。
- 同目录存放四个 WAV、`qwen-metrics.json`、`step-metrics.json` 和 `audio-checks.json`。
  产物目录已被 Git 忽略；上述文件是本地生成物，不随代码提交。
- 独立开发环境和生成脚本位于被忽略的 `scratch/voice-audition/`，没有增加项目运行依赖。
- 测试句：今天有没有一件让你觉得开心的小事？不着急，慢慢说，我在听。
- Step 请求另包含自然、放松、温柔闲聊的语气指令；Qwen 0.6B 未传语气指令。
  这是各候选实际试听条件，不是严格控制所有合成参数的模型排名。

## 本机合成

Apple M5 Pro、64 GB。MLX Audio 0.5.1、MLX/MLX Metal 0.32.2、Python 3.13.12。
使用 `mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit`，权重 revision
`049ef77fe8816b536193c0c25f9a214d17921282`，下载文件合计约 1.974 GB。

下载后以本地路径加载，设置 Hugging Face／Transformers 离线模式并拦截 Python
socket 连接和数据报发送；生成过程中记录 0 次网络尝试。此证据限于本次预设声音合成，
不等于整个对话和克隆链路已离线，也不是操作系统层面的全流量审计。

模型加载并完成参数求值耗时 2.165 秒。随后冷运行“你好。”首段 3.7045 秒、
总生成 3.885 秒、输出 0.96 秒。以下两种声音在同一个已预热模型内依次生成，
每次随机种子为 42，`stream=True`、`streaming_interval=0.32`、`max_tokens=300`。
每个非空音频块先执行 `mx.eval` 再记录收到时间，拼接写入 24 kHz、单声道 PCM16 WAV。

| 模型／声音 | 运行方式 | 首个音频块 | 完整生成耗时 | 音频时长 |
|---|---|---:|---:|---:|
| Qwen3-TTS 0.6B / Serena | Mac MLX 8bit | 0.0985 秒 | 1.366 秒 | 5.68 秒 |
| Qwen3-TTS 0.6B / Vivian | Mac MLX 8bit | 0.1072 秒 | 1.818 秒 | 7.28 秒 |
| StepAudio 2.5 / elegantgentle-female | 云端 | 未测 | 4.547 秒 | 6.24 秒 |
| StepAudio 2.5 / wenrounansheng | 云端 | 未测 | 4.737 秒 | 6.32 秒 |

每种声音只测一次。Qwen 首个音频块长 0.32 秒，收到块不等于已经通过浏览器听到声音；
总合成耗时不含录音、转写或对话文本模型。MLX 记录峰值分配 2.558 GB，
不是整个进程或整机占用。本次没有测试真实麦克风对话的连续流式播放。

Step 使用项目已有客户端调用 `stepaudio-2.5-tts` 的 `audio/speech`，
`response_format=wav`、`sample_rate=24000`、`speed=1`，每个声音调用一次。
表内耗时含网络及完整音频返回，不是纯推理或首音延迟。它是云端音色对照，
不是 Step-Audio-EditX 本地部署。没有向 Step 上传录音。

## 验证与当前结论

- 四个 WAV 均能读出有效音频，PCM 样本没有削波；音频 RMS 分别为
  Serena 0.04946、Vivian 0.09023、Step 女声 0.04023、Step 男声 0.09866，未做响度归一化。
- 现有本机 Whisper 识别覆盖完整测试句，个别输出存在“一件／意见”“在／再”等
  同音字差异。这只能排查空音频、明显缺句，不能代替自然度试听或证明逐字发音无误。
- 通过默认网络环境访问本机识别服务时首次返回 502，改用 `trust_env=False`
  直连本机后四次识别均完成；未修改服务或项目客户端。
- 浏览器检查四个播放器的时长与文件一致，`readyState=4`、无媒体错误；
  已通过页面播放按钮启动 Serena 试听。页面会在播放一段时暂停其他段。
- 用户原有 7050／7250 页面保持原状态；新页明确区分本地和云端、预设声音和本人复刻。

Qwen 0.6B 在当前 Mac 已具备可试听的本地输出，短句合成速度值得继续测完整对话。
自然度由用户试听判断。当前对话工具仍使用浏览器朗读，尚未接入本次候选；
也未测试 Qwen Base 的用户音色复刻权重。

## 资料

- [Qwen3-TTS 官方仓库](https://github.com/QwenLM/Qwen3-TTS)
- [本次 MLX 权重](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit)
- [MLX Audio 的 Qwen3-TTS 实现](https://github.com/Blaizzy/mlx-audio/tree/main/mlx_audio/tts/models/qwen3_tts)
- [Step 合成接口](https://platform.stepfun.com/docs/zh/api-reference/audio/create-audio)
