# StepFun 订阅方案给了什么

> 这是当时的分析，记录保留。此后看画、聊天、检查和老师评价改由 Spark 上的 Qwen3.6 负责，`step-3.7-flash` 只读几何草图、设计 3D 小玩偶；听写按次付费；动画在 Spark 上或阿里云的 Wan 3.0。现在的配置见[部署与运行指南](deployment-versions.md)。

**StepFun First 的每一次 StepFun 调用都走订阅**（转写除外，见下表），地址是
`https://api.stepfun.com/step_plan/v1`，不再是按量付费的 `https://api.stepfun.com/v1`。
此后，API First 和 Local First 按运营方决定归档，StepFun First 成为唯一方案
（[归档说明](../../studio/profiles/archive/README.md)）；原先"回滚就是 `--deployment api`"
这条退路随之不存在。要把某个位退回按量付费，在该位的 options 里写自己的 `base_url`。

订阅给了十个模型 —— 是从订阅地址自己的 `/models` 读回来的，不是从订阅页面抄的（文末有记录）。
下面把十个都写出来 —— **数出来不算答案，得说出名字**：用了哪三个、
另外七个为什么没用。空着的格子都写了为什么空着。

## 这台机器实测过的：三个

| 模型 | studio 里的位置 | 证据 |
|---|---|---|
| `step-3.7-flash` | 六个读画位（`vlm.studio`、`vlm.director`、`safety.image`、`vlm.sketch`、`vlm.creation`、`vlm.teacher`），靠 reasoning effort 区分角色 | 从项目早期起一直在跑；隐藏思考的坑记在 `studio/providers/stepfun.py` |
| `stepaudio-2.5-tts` | `tts.studio`，念给孩子听的声音 | 从项目早期起在用；预设声音在成人试听里选定 |
| `stepaudio-2.5-asr` | `speech.in`，听孩子说话。**这是孩子录音离开本机的那一个位**。**不走订阅**：订阅地址没有转写，一律回 404，一度每段录音都失败，直到操作者决定改走按量付费的 `.../v1`，每段录音从账户余额扣 | 操作者决定；整段说明在 `studio/providers/stepfun_asr.py` |

## 订阅里有、studio 没用的：七个

**下面"这是什么"一栏来自模型名字和 StepFun 的公开命名，不是这台机器实测的结论。**
本项目只跑过上面三个。

| 模型 | 这是什么（未实测） | 为什么没用 |
|---|---|---|
| `step-5-preview` | 最新的一代，preview | 没有任何实测。换掉读画位就等于换掉孩子听到的评语，得先拿七张真画走两个入口比过才谈得上 |
| `step-3.5-flash` | 比 3.7 早的 flash | 同上，且没有理由从 3.7 往回走 |
| `step-3.5-flash-2603` | `step-3.5-flash` 的固定快照版本 | 同上 |
| `step-router-v1` | 按请求自动挑模型的 router | 六个位是按 reasoning effort 分角色、刻意各挑各的模型的。交给 router 之后，哪一个模型回答了这句评语就不再是写定的，ledger 也记不准 |
| `stepaudio-2.5-chat` | 语音进、语音出的对话模型 | 现在的对话是文字走读画位，两头再接语音。换成它等于换掉整条对话链路 |
| `stepaudio-2.5-realtime` | 实时语音对话 | 孩子说完等一会儿再听到回答，换成实时是**新的一条入口，不是换个模型**。操作者把它留到单独一件事去做 |
| `step-image-edit-2` | StepFun 的改图模型 | **操作者决定排除**：先是决定所有运行方案都不用 StepFun 图像模型，改走订阅时又重新问过一次，答案是画面继续用 4090 上的 FLUX.2 Klein 4B。代码里 `is_disabled_stepfun_image_model()` 挡着它 |

## 和这次一起改的东西

- **八个位的地址**：六个读画位 + `tts.studio` + `speech.in`，都指向订阅地址。前六个是从
  `api.yaml` 继承来的，所以 `stepfun.yaml` 用 `provider_options` 给整个 provider 下默认值，
  而不是把八个位重抄一遍。4090 和 Replicate 的位没有被塞 StepFun 地址。
- **钱**：每个 step-3.7-flash 位带的 ¥ 折算单价（当时继承自 `api.yaml`，归档后抄进了 `stepfun.yaml`），在订阅下是假的 —— 调用之前就付过了。
  `included_in_plan: true` 让它不再算这笔钱，ledger 上是 0；Ledger 页面加了一句话说明这个 0
  是预付，不是免费。**让画动起来的视频仍然按次买 Replicate**，合计里就是它。
- **没动的**：图像、3D 仍在显卡机器上；Mac + 4090 时视频仍买 Replicate（订阅这十个模型里没有
  3D，也没有视频）。当时 API First 和 Local First 一个字没改；它们随后归档。

## 已经验证的

实测记录在
[两份目录](../measured/stepfun-plan-catalogue.md)：

- **密钥不用换。** `.env` 里现有的那把就是订阅页面上的默认密钥 —— 开头和结尾几位
  都对得上（只比对、不显示密钥）。所以 studio 一直用的就是订阅所在账户的密钥。它在订阅地址上
  也返回 200 —— 但那只是列模型，单凭这一条证明不了是同一个账户，是比对密钥这一条证明的。
- **上面这十个是从订阅地址自己的 `/models` 读回来的**，不是从截图抄的，和订阅页面列的一致。
- `studio.start --check --deployment stepfun` 十一个位全绿，八个 StepFun 位是拿订阅地址验的。
- 按量地址列 36 个，是订阅十个的超集，多出来的里面有整代更新的 `stepaudio-3-*`。
  **现在没有一个位用它们**，所以不损失什么；以后要用，单个位写回 `base_url` 即可。

自己再跑一次：

```bash
.venv/bin/python -m studio.start --check --deployment stepfun
```

## 还没验证的：一条

**哪个账户被扣钱，看不出来。** 本文假设发往旧地址 `.../v1` 的调用从账户余额扣，而不是走订阅。
两个地址收同一把密钥、都回 200，响应里也没有任何计费字段。两份目录不同是支持它的最强证据，
但它不是账单。跑一节课再看订阅页面的用量就能定下来；假设错了的代价只是订阅没被用上。
