# 离线语音候选与当前等待时间

用户报告个人语音实验已能朗读，但处理慢、对话伙伴的声音机器感强，
要求优先检查 Step 可离线部署的模型，不适合时比较其他模型。
本轮为现有调用链检查、页面只读测量和官方资料核对，没有安装模型或切换正在使用的页面。

后续已实际生成 [Qwen 本机与 Step 云端的四段新试听](dialogue-voice-audition.md)，
其中 Qwen 0.6B CustomVoice 的本地合成已经跑通。以下“未安装”是本次研究时点的状态，
最新实测以该记录为准；正在使用的对话工具仍未切换声音。

## 当前证据

- 当前开发机系统信息：Apple M5 Pro，64 GB 统一内存；没有 NVIDIA CUDA。
- 对话伙伴通过 `studio/voice_lab/app.js` 的 `speak()` 调用浏览器 `speechSynthesis`，
  中文优先选择系统 Tingting 等声音。它没有调用 StepAudio 2.5 或 Step 离线 TTS。
- 用户本人音色的文章朗读才调用 StepAudio 2.5 云端 `audio/voices/preview`。
- 7250 在用页面显示：参考片段 8.38 秒，转写 0.4 秒，对话回复 2.51 秒；
  27 字测试短句的生成任务显示 9 秒，输出音频 5.52 秒，播放器 `readyState=4`。
  页面报告云端参考文件已删除。9 秒是页面所见任务耗时，包含网络、合成、清理与
  进度读取等环节，不能当作模型纯推理时间。
- 当前录音先后进行整段与参考片段两次转写；对话回复完整返回后才交给朗读；
  文章分段串行合成，全部完成后才拿到播放器。这些等待环节与模型音色质量是两类问题。
- 用户报告“可以了”证明这次播放恢复，不证明旧 HTTP 400 的原因已查明，也不代表
  音色相似度或自然度验收通过。未将用户的录音或文字保存到此记录。

## Step 优先路线

**Step-Audio-EditX（3B）**：有开源权重与零样本音色复刻，支持中文与情绪／说话风格控制。
官方环境为 Linux、NVIDIA CUDA；标准运行估算约 12–15 GB，官方另提供节省内存与
量化路径。此数字不是 Spark 实測。当前官方 `tts.py` 的 `clone()` 先生成完整 token，
再调用 `token2wav_nonstream()`，因此直接接入默认示例不能证明更低的首音延迟。
适合作为 Spark 上优先试听的合成／复刻候选，Mac 不能直接照搬官方方案。

**Step-Audio 2 mini（8B）**：支持语音输入与语音输出的对话，官方推荐 vLLM 流式推理，
声码器实现包含流式缓存。官方实现有显式 CUDA 调用，不是现成的 Mac MLX 方案。
它会替换比 TTS 更多的对话链路；仅改善对方说话音质时，无需首先做这种大范围替换。
未发现可据以承诺本项目 Spark 首音时间、全链路延迟和并发内存的实机证据。

## 其他候选

| 模型 | 可用能力 | 当前项目适用判断 |
|---|---|---|
| Qwen3-TTS 0.6B／1.7B | 中文等十种语言；CustomVoice 提供预设声音，Base 提供参考录音复刻；支持流式 | 当前 Mac 的优先试验候选。MLX Audio 有对应实现；迁到 Spark 需改用适配 NVIDIA 的推理环境，MLX 运行时不能搬过去 |
| Fun-CosyVoice3-0.5B-2512 | 中文、多语言、参考音色与流式合成 | Spark 的轻量对照候选；应与 EditX 用同样短句、参考录音和硬件实测，不能用参数量代替延迟结论 |

Qwen3-TTS 的 0.6B CustomVoice 与 Base 是不同权重，不能把预设音色版本当作已经
支持用户克隆。已确认存在 MLX 8bit 转换，模型页分别标示约 1.97 GB、1.99 GB；
这是模型文件信息，不是完整运行内存。当前项目环境没有安装 MLX Audio 或这些权重。
开源模型的官方演示和厂商指标不能代替用户的自然度试听，量化版本也须单独验证。

## 建议验收与改造顺序

1. 先替换对话伙伴的浏览器朗读，保留现有对话文本模型与本地转写。
2. 对照自然陈述、追问、安慰回应三类中文短句，试听预设声音，再测试本人录音复刻。
3. 同时记录冷启动、热模型首段音频时间、总合成耗时、音频时长与峰值内存。
   模型常驻、开场白缓存和边生成边播放分别测量，避免混成一个“速度”数字。
4. 优先将首音等待控制在可接受范围；“生成整篇完成”与“开始听到第一句话”应分别显示。
5. 参考片段的转写可以考虑放到后台，不让它阻塞对话；实际使用这份参考前仍应核对
   与声音对应的文字，不能为省时间把裁剪录音直接配上整段转写。
6. 最后用本地权重路径与禁止联网的运行环境确认启动、对话朗读和音色复刻均不再下载
   隐藏依赖。未完成这一步之前，不将配置为 localhost 描述为已验证的全离线部署。

## 官方资料

- [Step-Audio-EditX：能力、依赖和内存](https://github.com/stepfun-ai/Step-Audio-EditX)
- [EditX 当前合成实现](https://github.com/stepfun-ai/Step-Audio-EditX/blob/main/tts.py)
- [Step-Audio 2：流式运行方案](https://github.com/stepfun-ai/Step-Audio2)
- [Step-Audio 2 mini 模型卡：8B、CUDA 与授权](https://huggingface.co/stepfun-ai/Step-Audio-2-mini)
- [Qwen3-TTS：Base 与 CustomVoice 的区别](https://github.com/QwenLM/Qwen3-TTS)
- [MLX Audio 的 Qwen3-TTS 合成与流式接口](https://github.com/Blaizzy/mlx-audio/blob/main/mlx_audio/tts/models/qwen3_tts/README.md)
- [MLX 0.6B CustomVoice 8bit](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-CustomVoice-8bit)
- [MLX 0.6B Base 8bit](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit)
- [CosyVoice 官方仓库](https://github.com/QwenAudio/CosyVoice)
- [Fun-CosyVoice3-0.5B-2512 模型卡](https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512)
