# 历史模型优化与失败实验

本页补充 2026-09-27 至 10-13 的图改写路线；最终引擎优化与官方模型对照见 [当前证据](evidence.md)。数据来自当时试验 README、结果汇总和分段 profile，未重新运行。完整原始板端日志未随 skill 发布。

## 图改写的速度路线

以下为同一 USB QCS8550、HTP V73、8 MiB VTCM、QAIRT 2.50。前八项使用 CPU LUT embedding、两个 Transformer context 和独立 head，最后两项改变了部署结构。输入为 128 个随机 token ID、输出 128 个连续 token、无 warmup、每次 reset；随机输入只用于吞吐。有效 prefill = 实际输入 token 数 / TTFT，包含首 token 路径，不含模型加载。

为简洁只列各阶段已测较快配置，状态副本同步策略和 runtime 曾变化，**本表不能视为同一引擎下的纯模型消融，也不能直接与 2048 输入 / 512 输出的最终速度表计算增幅**。当时日志为 temperature=0，与后期显式贪心的配置不同。

| 候选及主要变化 | Decode tok/s | 有效 prefill tok/s | 统计和限制 |
|---|---:|---:|---|
| W4 SeqMSE SHA | 10.18 | 320.1 | Decode 单次；prefill 来自普通配置 5 次，非同一配置配对 |
| all-Conv SHA | 约 12.1 | 371.1 | Decode 为 3 次分段实验；prefill 来自普通配置 3 次 |
| all-Conv SHA input-A16 | 13.213 | 410.0 | Decode 为 3 次 profile；prefill 来自普通配置 3 次 |
| graphopt + state-A16 r2 | 13.858 | 463.2 | 修正量化零点后，3 次 |
| attention 分组 / KV 布局 + SiLU 编码 | 15.270 | 482.3 | 与上一行同修正 runtime，3 次 |
| KV8 fullquant 初版 | 7.115 | 324.4 | 单次，状态编码不匹配的失败包 |
| KV8 fullquant r2 | 15.617 | 457.2 | 3 次；真实中文问题输出乱码，speed-only |
| Stateful SeqMSE SHA | 14.439 | 493.1 | 3 次；no-think 短题 5/8，未精度验收 |
| Text-reference 单 Transformer，head 独立 | 17.326 | 525.6 | 10/13，3 次；CPU embedding |
| Text-reference fullgraph | 18.388 | 546.1 | 10/13，3 次；embedding / Transformer / head 全在同一 HTP 图 |

前 3 行的 decode / prefill 采用不同配置，特意标注而非拼成同条件结果。对应普通配置 decode 分别为 9.811、11.513、12.411 tok/s。后 7 行两列来自各自行的同配置试验。

W4 非 SHA 与 SHA 的更早配对短测为 **2.92 → 9.70–9.77 tok/s**，34-token 中文输入、32-token 输出，TTFT **608 → 约 377.5 ms**；只替换两个 Transformer context，embedding、head 和 runtime 相同。它说明早期 SHA 的收益，不能混入持续 decode 表。旧 Wi-Fi 板 W8 非 SHA 约 3.1、SHA 约 8.0 tok/s，设备不同，也不能与本表做 W8/W4 因果对照。

## 为什么改、收益具体来自哪里

| 改动 | 已测证据 | 能据此做出的判断 |
|---|---|---|
| MHA → SHA、移除 KV expand | 上述 W4 短测约 3.3 倍；旧 W8 profile 的 KV expand 占比约 34% → 1% cycles | full-attention 的重复扩展曾是大热点；linear attention 不可直接套用该收益 |
| Linear → Conv、参数对齐 | 普通 decode 9.811 → 11.513；head 32.33 → 13.10 ms/token，Transformer 合计 56.55 → 61.01 ms/token | 主要收益来自 head，不能称每个 Conv 投影都更快；参数对齐也是变量 |
| 补齐 down_proj / o_proj 输入 A16 编码 | 普通 11.513 → 12.411，约 +7.8%；Transformer 合计省约 7.1 ms/token | 减少投影输入转换和执行开销，改图需同步编码 |
| Conv1d state-window、布局去重、recurrent K A16 | 同修正 runtime 的 recurrent feedback 9.474 → 4.340 ms/token；AR128 每分片 Gather 约 96–99 M → 3.8 M cycles | 状态反馈与 prefill 图工作同时改善，cycles 不能直接换算业务毫秒 |
| 闲置 AR128 状态副本按需同步 | graphopt 13.411 → 13.858，约 +3.3%；recurrent feedback 4.340 → 2.215 ms/token | 下一步 AR1 的实际状态仍须完成；多轮、切图、异常需要同步保护 |
| attention 分组 / KV 布局 + SiLU 编码 | 同 runtime 13.858 → 15.270；两 Transformer 合计省约 6.7 ms/token，head 基本不变；AR1 每分片 MatMul 54 → 18 | 收益集中在 Transformer；这些图变化没有完全分开消融 |
| KV8 fullquant r2 配对 recurrent 编码 | 初版反馈 79.37 → 2.40 ms/token；相对 attention/SiLU 15.270 → 15.617，仅约 +2.3% | 7.1 → 15.6 是修复回退；不能写成 KV8 本身带来翻倍；精度仍失败 |
| Stateful SeqMSE / recurrent V FP16 | 10/08 同板同 runtime：旧 KV8 r2 15.518 → 14.439，约 -7.0%；图合计 58.99 → 63.76 ms/token | 输出更连贯但图执行变慢；prefill 略快与 decode 变慢可同时成立 |
| 两 Transformer 合并为一个 | 当天同 runtime：15.916 → 17.326；Transformer 包装耗时 43.878 → 39.234 ms/token，head 基本不变 | 约 +8.8%；含图执行和边界处理，不能全部归因于少一次调用 |
| embedding / Transformer / head 合为 fullgraph | 同修正 core：单 Transformer 对照 17.197 → 18.388；shard 包装合计 52.439 → 48.963 ms/token | 约 +6.9%；同时改变 embedding 执行位置和编译图结构，未独立隔离贡献 |

旧 W4 SHA Transformer + 新 Conv head 的混合试验为普通 **12.282**、较快配置 **12.97 tok/s**，也支持 all-Conv 阶段主要由 head 提速，而非 Transformer 全面加速。

## 长输入与持续输出的核对

| 候选 | 输入 / 输出 token | Decode tok/s | 有效 prefill tok/s | 统计 |
|---|---|---:|---:|---|
| attention / SiLU | 128 / 512 | 约 15.1 | 本项未列 | 单次持续生成 |
| KV8 r2 | 128 / 512 | 约 15.6 | 本项未列 | 单次；精度失败 |
| Stateful | 128 / 512 | 约 14.5 | 本项未列 | 单次 |
| 单 Transformer | 2048 / 128 | 17.431 | 527.6 | 单次 |
| 单 Transformer | 128 / 512 | 17.650 | 548.3 | 单次 |
| fullgraph | 2048 / 128 | 18.137 | 550.9 | 单次 |
| fullgraph | 128 / 512 | 18.439 | 560.9 | 单次 |

这些结果支持数百步持续生成，不能替代接近 CL4096 上限的完整压力测试。短回复的 25–70 tok/s 不作为长序列成果。fullgraph 后续同模型通过日志、虚拟电量报告纠正、引擎与调度优化到 **31.17 tok/s**；其 2048 / 512 阶段对照见 [当前证据](evidence.md)。

## 自转换 fullgraph：18 → 31 tok/s

以下沿用同一自转换 fullgraph context，未重新转换模型。测试口径为 2048 输入 / 实际 512 输出；阶段之间日志、QAIRT、采样、电量报告及 CPU 调度发生变化，因此列为累计部署优化。该路线与上面的 128 / 128 图改写表分开。

| 累积改动 | Decode tok/s | 为什么做、具体做了什么 |
|---|---:|---|
| 原适配，QAIRT 2.50，详细 QNN 日志 | 18.35 | 历史长输入基线；模型已经是 fullgraph |
| QNN 后端日志改 WARN | 23.68 | 减少逐步执行日志及输出开销；需要控制 QNN/DSP 后端日志，仅过滤应用输出不够；单次 |
| QAIRT 升到 2.51，保持 WARN | 23.55 | 匹配新版 host/stub/skel，3 次均值；升级本身未观察到额外提速 |
| 纠正虚拟电量报告限频，3 个 worker 允许 CPU0–2，轮询等待 | 26.66 | 消除模拟电量异常触发的性能限制，并调整状态反馈线程与等待策略；三项没有独立拆测，3 次均值 |
| 引擎与调度优化，主线程 CPU4、反馈线程允许 CPU3/4/6 | **31.17** | 显式贪心 + 编码 logits 的 NEON argmax；有效 conv 状态直接复制，减少 recurrent/conv 重复副本；提前提交 KV 并与 recurrent 更新重叠；直接生成量化 mask；按需维护闲置状态副本；3 次均值 |

最后一步相对 26.66 提升约 **4.50 tok/s / 17%**。这个值是整套引擎与调度的组合收益；没有自转换模型逐项开关的完整消融，不能把下一张官方模型的每步差值当成自转换模型的贡献。

最终自转换模型有效 prefill 为 **882 tok/s**，每步约 **32.08 ms**，其中 shard 图执行包装路径约 **31.54 ms**、采样 **0.030 ms**、顶层等待 **0.500 ms**。包装路径不是纯 NPU 算子时间，但说明最终剩余开销主要在图执行。本轮没有重测 PPL；历史 PPL 不等于最新引擎重新验收。

## 官方转换 fullgraph：31 → 37.57 tok/s

这是另一套 direct-stock context，相同当前 USB QCS8550、2048 输入 / 实际 512 输出，本轮 context 不变；多数为三次均值。这里展示已测较快配置的累计优化路线。阶段间数值策略、采样与 affinity 有变化，属于阶段对照，不是最终版逐项关闭的完整消融。

| 累积改动 | Decode tok/s | 为什么做、具体做了什么 |
|---|---:|---|
| 最新上游 + 原适配 | 31.19 | 验证更新上游是否足够；仅拉最新代码几乎没有收益 |
| 对齐 RoPE、显式贪心，仍用标量扫描 | 31.26 | 按模型参考路径对齐 concat RoPE 的量化与舍入；明确贪心采样配置，仍逐个扫描词表；含数值及配置调整 |
| 加 NEON argmax | **33.65** | 共享正 scale 等前提满足时直接比较 UF16 编码，不必转换整个 248320 词表；用 NEON 一次比较多个元素，保持首次最大值等语义 |
| conv 状态直接复制 | **34.07** | 按实际 valid_tokens 取有效尾部；布局及编码确认一致后直拷，减少中间 vector 和重复搬运 |
| 提前提交 KV 更新 | **34.30** | KV 结果可用后尽早入队，与独立 recurrent 更新重叠，缩短下一步前的等待；读取状态前仍须 barrier |
| recurrent 三线程，CPU0–2 | 34.01 | 将独立 recurrent 状态分片并行；该 CPU 配置反而变慢，不能只按线程数判断收益 |
| 反馈线程改用 CPU3/4/6，主线程未绑定 | **35.19** | 把反馈线程的允许核改到更合适的 CPU 集合，改善状态并行处理；允许核集合不等于每线程独占一个核 |
| 数值修正及中间试验后，加量化 mask、推迟闲置 AR1 镜像更新 | 35.57 | mask 直接填等价量化值，省去浮点生成再量化；prefill 期间推迟维护当前未执行的 AR1 状态副本，切入 AR1 前同步；前后还有其他改动，不能独立归因 |
| 主线程绑 CPU4 | **37.65** | 固定负责图调用、输入准备和采样的主线程，减少迁移并使用已测较快核；检查实际 TID affinity，官方引擎也受益 |
| 尾窗口修复、异常保护后的最终版 | **37.57** | 正确选择尾窗口实际执行图的 logits，处理异步任务异常收尾及 buffer 生命周期；3 次均值，修复重点是正确性与退出保护 |

NEON、conv 直拷、提前 KV、主线程绑核有较直接的相邻对照；mask、镜像同步和 recurrent 并行没有全部独立拆测。不能将全部相邻差值相加当作各项独立收益。**37.65 是中间版本，37.57 才是最终报告值。** 最终有效 prefill 为 **1742 tok/s**；同模型官方 genie-app 为 **37.40 decode / 1766 有效 prefill tok/s**。最新问答仍有错误和重复，不能因速度追平官方认定精度通过。

两条路线的最终部署、质量与哈希见 [当前证据](evidence.md)；受条件保护的采样与状态更新细节见 [数值](numerics.md)、[状态反馈](state-feedback.md) 和 [性能](performance.md)。

## 失败和未采用的尝试

- 早期绕过插件直接 argmax 曾省约 2.3 ms/token，但真实文本变化，已撤回；它与后来受条件保护、对齐显式贪心的 NEON 实现不是同一个实验。
- 增加 worker 曾无可靠持续收益，0 worker 出现过卡住；后期 recurrent 三线程固定 CPU0–2 也曾变慢。线程数量和允许 CPU 必须在目标板重测。
- prefill 睡眠、先复制 logits 再扫描、自定义 NEON state memcpy 未观察到收益，没有纳入最终配置。
- AR128 head 只取最后位置的设想需在 head 前选择 hidden state；当时尚未形成板端实测成果。PPL 仍需要完整位置 logits，不能直接套该裁剪。
- 图间 hidden-state CPU 连接曾约 0.012 ms/token，远小于两个 Transformer execute；这个计时本身不足以预测合图收益。

## 精度与证据边界

历史 fullgraph 的相同 WikiText-2 test 十块、40950 个目标 AR128 PPL 为 **12.55134210**；两 Transformer + CPU LUT 为 **12.58136726**。差异约 -0.24%，不是精度完全一致的证明；AR1 连续 teacher-forcing、多轮对话须单独测。对应 HF 为 10.77739771、QuantSim 为 12.76339327。单 Transformer 仅测首块 PPL 11.99947169，不能与十块总 PPL直接比较。

上述摘要保留历史结果、测试规模与局限，不包含个人仓库地址、私有分支或设备序列号。未附原始日志的历史项用于指导新实验；正式验收仍需重新保存实际命令、token IDs、模型/库哈希、原始日志和 profile。
