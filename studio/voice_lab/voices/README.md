# 对话伙伴的合成参考声音

两段均为 VoxCPM2 在本机通过文字描述设计的成年合成声音，没有使用真人录音。
来源、模型固定版本和生成脚本见
[试听记录](../../../docs/measured/voxcpm2-cosyvoice3-audition.md)。

- `gentle-female.wav`：原 `vox-female-reference.wav`，温柔亲切成年女声。
- `gentle-male.wav`：原 `vox-male-reference.wav`，温暖柔和成年男声。
- 内容：“晚上好，今天过得怎么样？我们可以坐下来，轻松地聊一会儿。”

它们只供对话伙伴固定声线使用，不代表用户本人声线，也不是 StepAudio 2.5 的预设音色。
用户录音不保存在此目录，运行时也不向此目录写文件。

## 回顾童声

当前 `soft-child.wav` 为用户试听后选定的 A，逐字节复制自
`outputs/voice-audition/child-v3/toddler-natural.wav`。
VoxCPM2 在本机按“三岁小男孩，稚嫩的高音奶音，咬字不清，天真，轻声说话”
文字设计生成，无真人录音。seed 17、cfg 2.0、10 步，48 kHz 单声道 PCM16，8.48 秒。
年龄仅为设计目标；用户选择的是 A 试听，不使用 B 的改词与叠词。

参考正文：“我画了一只大象，还有两只长颈鹿。大象用长鼻子喷水，大家都很开心。”
脚本：`scratch/voice-candidates/generate_child_v3.py`。
孩子回答、回顾描述和故事书显式选用，伙伴回应仍用成人声。运行中服务需重新加载后使用该参考。
之前两版试听仍保留在输出目录，不再作为当前参考。
