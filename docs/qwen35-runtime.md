# Qwen3.5 optimized QAIRT runtime

This branch pins the matching Qwen3.5 stateful QAIRT plugin in the LudovicoYIN fork. Clone recursively to include the implementation:

```sh
git clone --branch feat/qwen35-runtime-speed-20261014 --recurse-submodules https://github.com/LudovicoYIN/GenieX.git
```

See [plugin runtime notes](../third-party/geniex-qairt/docs/qwen35-runtime.md) for numerical policies, scheduling switches, affinity, benchmark conditions and validation limits. Model binaries and proprietary QAIRT runtime libraries must be supplied separately.

The SDK can optionally reuse a compatible unchanged Rust model-manager static library with `-DGENIEX_PREBUILT_MODEL_MANAGER=/path/to/libgeniex_model.a`; leave unset for normal Cargo source builds. The speed measurements used unchanged text processor and model-manager code; only the text runtime was validated.

## Older text-reference fullgraph benchmark

On the same optimized runtime and CPU affinity, using2048 input / actual512 output tokens, explicit greedy, seed43, no warmup and three runs per mode:

| Model | Ordinary decode tok/s | Deferred decode tok/s | Ordinary input / TTFT tok/s | Deferred input / TTFT tok/s |
|---|---:|---:|---:|---:|
| Older text-reference fullgraph | 30.81 | 31.17 | 879 | 882 |
| Direct-stock fullgraph, previous final-runtime runs | 37.26 (one run) | 37.57 (three runs) | 1761 (one run) | 1742 (three runs) |

The older graph execution path takes31.54ms/token versus32.08ms total in deferred mode; encoded greedy sampling takes0.030ms/token. Model graph execution now dominates. This random-token throughput benchmark does not revalidate the older model PPL or question-answer accuracy. Each model retains its own positional-encoding configuration. Per-run data and artifact hashes are in [older fullgraph results](qwen35-old-fullgraph-results.json).

## 提速归因：运行环境与引擎优化

本轮引擎优化没有重新转换或修改模型context。应分别比较老text-reference fullgraph和新direct-stock fullgraph，不能把跨模型速度差全部归为引擎收益。

| 模型 | 本轮引擎优化前普通反馈 | 本轮引擎优化前延后反馈 | 优化后普通反馈 | 优化后延后反馈 |
|---|---:|---:|---:|---:|
| 老 text-reference fullgraph | 25.61 tok/s | 26.66 tok/s | 30.81 tok/s | 31.17 tok/s |
| 新 direct-stock fullgraph | 29.83 tok/s | 31.18 tok/s | 37.26 tok/s（单次） | 37.57 tok/s |

优化前数据来自同日的电量限制解除后测试；优化后除新模型普通反馈为单次外均为三次均值。输入2048 token、实际输出512 token、seed43、无warmup。优化前工作线程允许CPU0–2、主线程未固定，原采样设置与最终显式贪心不同；优化后主线程CPU4、工作线程CPU3/4/6。因此本表呈现整体部署优化效果，不是只改变某一个因素的严格消融实验。

前期从十几提升到二十多，包含纠正虚拟电量报告引发的限频、CPU调度和减少日志等调整，不能简单写成“关闭日志就到了二十多”。本轮进一步提升来自编码logits的NEON贪心采样、减少conv/recurrent状态重复复制、提前提交KV工作并并行反馈、直接生成量化mask，以及主线程和工作线程绑核。仅拉取最新上游代码几乎没有提速。

可概括为：老模型通过运行环境调整达到二十多tok/s，再通过引擎优化达到约31tok/s；新模型在同套优化引擎上达到约37tok/s。老、新模型是不同的编译图，但各自在本轮优化前后context保持不变。

普通反馈每步维护AR1/AR128状态输入；延后反馈及时更新实际执行的AR1，推迟更新闲置AR128镜像，decode结束再同步。新模型两者只差约0.8%，普通反馈也已基本追平官方37.40tok/s。官方genie-app没有我们这个普通/延后反馈开关，其内部状态副本策略尚未确认。
