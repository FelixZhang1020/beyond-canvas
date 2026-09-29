# 订阅地址和按量地址，两份目录

**实测**，不是从订阅页面抄的。用 `.env` 里现有的那把 `STEPFUN_API_KEY`
对两个地址各发一次 `GET /models`，只读，不做推理，不花钱。

复现：

```bash
.venv/bin/python -m studio.start --check --deployment stepfun
```

## 结果

| 地址 | HTTP | 模型数 |
|---|---|---|
| `https://api.stepfun.com/step_plan/v1`（订阅） | 200 | 10 |
| `https://api.stepfun.com/v1`（按量） | 200 | 36 |

**同一把密钥在两个地址都能用**，两边都返回 200。**`.env` 里这把就是订阅页面上的默认密钥**：
开头和结尾几位与订阅页面显示的一致（脚本只输出是否相同，不输出密钥）。
单看 `/models` 返回 200 证明不了这一点 —— 任何有效密钥可能都能列目录 —— 是比对密钥证明的。
所以 `.env` 不用换密钥；也所以，一个位
如果被漏在旧地址上，它会完全正常地工作 —— 这正是危险的地方，调用方这边看不出区别。

订阅地址上的十个（和订阅页面列的一字不差）：

```
step-3.5-flash          step-3.5-flash-2603     step-3.7-flash
step-5-preview          step-image-edit-2       step-router-v1
stepaudio-2.5-asr       stepaudio-2.5-chat      stepaudio-2.5-realtime
stepaudio-2.5-tts
```

studio 用到的三个 —— `step-3.7-flash`、`stepaudio-2.5-tts`、`stepaudio-2.5-asr` —— 都在里面。
`studio.start --check --deployment stepfun` 十一个位全绿，其中八个 StepFun 位是拿订阅地址
的目录验的。

## 两份目录不一样，这是本次唯一的意外

按量地址那 36 个是订阅十个的**超集**，多出来的里面有整代更新的语音模型：

```
stepaudio-3-asr-max       stepaudio-3-chat-preview    stepaudio-3-gen-preview
stepaudio-3-music-preview stepaudio-3-realtime-preview stepaudio-3-tts
step-audio-2 / -mini / -think    step-tts-2 / -mini / -vivid
step-asr / -1.1 / -1.1-stream    step-1o-audio  step-1o-turbo-vision
step-2x-large  step-gui  step-overture-preview  dr-search-api  search-image
```

**代价说清楚**：StepFun First 换到订阅地址之后，这些模型在那个方案里够不着了。现在没有一个位
用它们 —— 语音用的是 `stepaudio-2.5-tts`、`stepaudio-2.5-asr`，订阅里都有 —— 所以目前不损失
任何东西。但以后想试 `stepaudio-3-tts`，要么在那个位上单独写回旧地址（`provider_options` 的
默认值可以被单个位的 `base_url` 覆盖），要么用 API First。

## 仍然没有实测的一件事

**哪一个账户被扣钱，看不出来。** 两个地址收同一把密钥、都回 200，响应里没有任何计费字段
（StepFun 本来就不返回 cost，见 `studio/providers/stepfun.py`）。所以"发往订阅地址的调用走
订阅、发往旧地址的走余额"这一条，仍然是推断。两份目录不同是支持它的最强证据 —— 订阅地址只
认订阅买下的那十个 —— 但它不是账单。

**怎么定下来**：用 StepFun First 跑一节课，然后看订阅页面的用量有没有涨。如果这个推断错了，
代价只是订阅没被用上，不会多花钱。
