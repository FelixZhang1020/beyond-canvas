# VoxCPM2 与 CosyVoice 3 本地试听

Apple M5 Pro / 64 GB。用户要求试听两者，随后补充：若 VoxCPM2
不原生支持 Mac，则只测试 CosyVoice 3。本次确认 VoxCPM2 官方实现直接提供 MPS
路径，并成功使用该路径生成音频；没有修改模型代码来移植到 Mac。

## 试听结果与边界

入口：`http://127.0.0.1:7310/`。静态页面提供男女声切换、两个模型的同句对照，
以及上一轮 Qwen 预设声音回听；播放一个音频时暂停其他音频。当前 7300 Qwen
对话工具及之前的录音会话保留，没有把这两个候选接入实时对话或用户录音复刻。

固定测试句：“今天有没有一件让你觉得开心的小事？不着急，慢慢说，我在听。”

| 模型 / 声音 | 实际运行方式 | 首个音频块 | 整句生成 | 音频长度 |
|---|---|---:|---:|---:|
| VoxCPM2 女声，预热复测 | 官方 PyTorch MPS / float32 | 0.326 秒 | 4.429 秒 | 4.96 秒 |
| VoxCPM2 男声，预热复测 | 官方 PyTorch MPS / float32 | 0.324 秒 | 5.000 秒 | 5.60 秒 |
| CosyVoice 3 女声 | 官方 PyTorch CPU / float32 / 8 线程 | 7.003 秒 | 17.098 秒 | 6.52 秒 |
| CosyVoice 3 男声 | 同上 | 7.311 秒 | 12.491 秒 | 6.52 秒 |

这些是单次短句合成测量，包括参考音频处理，不包含文字模型思考、用户录音、
浏览器传输与播放。首块时间不是完整对话的首音延迟；静态试听页播放预先生成的文件。
不是统一硬件加速条件下的模型排行榜，也不是 NVIDIA Spark 性能测试。

VoxCPM2 首次模型加载约 15.10 秒；首次参考音频处理使女声整句等待 37.97 秒。
后续重新加载约 10.92 秒、参考音频预热整句 7.10 秒，再做上表的两次复测。
首次参考处理的具体慢点没有独立分段计时，不能全部归因为模型推理。
复测和首次生成的对应男女声音频 SHA-256 一致。MPS driver 已分配内存约 11.67 GB，
不是完整进程或整机峰值内存。CosyVoice 3 加载约 11.65 秒。

## 声线与验证

- VoxCPM2 先通过文字描述设计成年男女声，用公共句子“晚上好，今天过得怎么样？
  我们可以坐下来，轻松地聊一会儿。”生成两段参考。两种候选使用同一组参考声音
  读测试句。CosyVoice 3 使用 `inference_instruct2`，附温柔亲切、自然语速的指令。
- 没有使用真人或儿童录音。这里验证的是公共合成参考的条件生成，不证明用户本人
  音色相似度，也没有复现 StepAudio 2.5 的专有预设声音。
- 四段候选 WAV 都有有效、有限且非静音的音频数据。VoxCPM2 输出 48 kHz，
  CosyVoice 3 输出 24 kHz。
- 本机 Whisper 转写覆盖目标内容；出现“在/再”“一件/意见”等同音字差异。
  这只能检查读出的内容，不能替代用户对自然度、情绪和音色的试听判断。
- 浏览器检查六段音频（含 Qwen 回听）均加载到 `readyState=4`、没有媒体错误；
  VoxCPM2 和 CosyVoice 3 女声实际进入播放状态，男女声切换显示正确数据。
  用户随后在试听页操作，未继续打断其播放来重复检查男声。
- 推理脚本设置离线加载并拦截 Python socket 连接。VoxCPM2 两次成功运行均为
  0 次联网尝试。CosyVoice 3 初始化可选 wetext 前端时有 1 次被拦截的联网尝试，
  随后使用官方无前端回退；生成调用显式设置 `text_frontend=False`，没有云端合成。
  不能把 CosyVoice 3 描述为初始化阶段完全不尝试联网。后续集成应准备本地前端资源
  或显式控制该可选前端初始化，而不是依赖异常回退。

## 运行环境与固定版本

所有依赖、源码、权重和生成脚本都在忽略目录 `scratch/voice-candidates/`；
没有增加生产依赖或改动现有语音 provider。模型推理已退出，试听页只运行静态 HTTP。

| 项目 | 版本 |
|---|---|
| VoxCPM 官方源码 | `f772e498a45fbb5fb8e13fbf9b9c48be9fe33e69` |
| `openbmb/VoxCPM2` 权重 | `32279effe8c19989596f05d353d1447f51d9e915`，约 4.96 GB |
| VoxCPM 运行时 | Python 3.11，PyTorch 2.14.0，Transformers 4.57.6；MPS float32，`optimize=False` |
| CosyVoice 官方源码 | `074ca6dc9e80a2f424f1f74b48bdd7d3fea531cc` |
| `FunAudioLLM/Fun-CosyVoice3-0.5B-2512` 权重 | `29e01c4e8d000f4bcd70751be16fa94bf3d85a18`，仅下载此次推理需要的文件，约 5.42 GB |
| CosyVoice 运行时 | Python 3.11，PyTorch / torchaudio 2.6.0，Transformers 4.51.3，ONNX Runtime 1.18.0；CPU |

VoxCPM2 第一次用旧 PyTorch 2.6.0 运行在 MPS 分组注意力处崩溃，升级实验环境的
PyTorch 后官方代码成功运行。没有使用 CPU 模拟 GPU，也没有为跑通修改模型的注意力实现。
CosyVoice 3 使用官方自动选择的 CPU 路径，未额外移植到 MPS。

音频、页面、JSON 位于 `outputs/voice-audition/vox-cosy/`。
`vox-metrics.json` 保留首次结果，`vox-warm-metrics.json` 为复测，`cosy-metrics.json`
为 CosyVoice 3 实测。两个 `*-asr-checks.json` 保存公共音频转写检查。

复现脚本：`generate_vox.py`、`generate_cosy.py --reference-family vox`、
`generate_vox.py --reuse-references`、`build_audition.py`，均位于上述 scratch 目录。
需要使用对应 `vox-venv` / `cosy-venv`。静态页只服务本轮公开合成产物目录，绑定 loopback。

## 官方来源

- [VoxCPM2：MPS 入口、声音设计与参考音频 API](https://github.com/OpenBMB/VoxCPM)
- [CosyVoice 3 官方实现](https://github.com/QwenAudio/CosyVoice)
- [CosyVoice 3 模型卡](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)

两者都有公开权重，官方模型说明为 Apache 2.0。此次运行成功只证明本机短句试听，
没有验证课堂并发、连续长对话、长期稳定性或 Spark 部署。
