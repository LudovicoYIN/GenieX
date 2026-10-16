---
name: qualcomm-llm-adapt
description: 将已转换的高通 QAIRT/QNN 大模型适配到 GenieX，检查图接口、KV/recurrent 状态、量化编码与聊天模板，完成 Android HTP 部署、精度验证和性能排查；同时维护模型转换到运行时的交付接口。适用于 Qwen3/Qwen3.5 等模型迁移，模型转换算法由转换部分补充。
---

# 高通大模型转换与 GenieX 适配

此 skill 有两部分：模型转换与 GenieX 适配。当前 GenieX 部分已按 Qwen3.5/QCS8550 实践整理；转换部分只定义交付契约，尚未实现转换教程，不能把契约当作已完成的转换流水线。

若当前源码分支已集成 Qwen3.5 适配，直接检查现有实现；`assets/patches/` 是旧官方基线的迁移参考，不重复应用。仓库分支与上游同步规则以所在仓库的团队指南为准，skill 本身保持可独立复制。

## 按任务选择入口

| 当前任务 | 先读 | 后续按需要读 |
|---|---|---|
| 转换模型、修改导出图 | [模型转换交付接口](references/model-conversion/handoff.md) | 转换人补充的脚本；确认改图后同步 encodings 和状态接口 |
| 新模型首次接 GenieX | [适配流程](references/geniex/workflow.md) | [图接口](references/geniex/graph-contract.md)、[状态](references/geniex/state-feedback.md)、[数值](references/geniex/numerics.md)、[构建部署](references/geniex/build-deploy.md) |
| 加载失败、1002、输出错误 | [问题索引](references/geniex/pitfalls.md) | 按首个失败阶段定位，不按错误数字猜原因 |
| 速度低、分析流水线 | [性能与 profiling](references/geniex/performance.md) | [验证](references/geniex/validation.md)、[实际结果](references/geniex/evidence.md) |
| C++ 接入或交付同事 | [构建部署](references/geniex/build-deploy.md) | [C++ 示例](assets/cpp/chat.cpp)、[CMake 示例](assets/cpp/CMakeLists.txt) |
| 查看每个细节的 demo | [Demo 索引](references/geniex/demos.md) | 只运行对应脚本，不默认执行板端修改 |

## 必须保留的适配边界

- GenieX 自行实现输入准备、采样和状态反馈，同一个 context 不代表与 libGenie 的行为天然相同。
- 先记录模型、runtime 和设备身份及哈希，隔离构建与部署；不要混用旧 core、插件、头文件及 QAIRT host/stub/skel。
- shape、dtype、scale、offset、axis encoding、KV layout 和状态寿命属于图接口。名称相似不足以证明可 memcpy。
- AR1 下一步读取前完成实际状态反馈；“延后副本”只能作用于当前闲置图。异常退出、取消和切图都要收尾。
- 正确性与速度分开验收。零状态 forward、随机 token 吞吐、输出文字看起来合理均不足以证明正常对话或连续状态正确。
- 本 skill 中的 CPU4/CPU3,4,6、V73/VTCM8、concat RoPE 舍入策略和 env 开关都是已测案例；依据模型包和目标板选择，不作为所有高通模型默认值。
- 用户提供已转换包时先适配现有 context。发现图内问题再说明需改图的证据；不要为了 runtime 性能优化直接重做量化。

## 最小行动顺序

1. 用 `scripts/inspect_bundle.py` 清点包与图信息；读转换交付接口。
2. 明确 embedding/Transformer/head 各在哪执行，以及 AR、CL、shard、输入输出和状态映射。
3. 最小加载和单步数值对照，再验连续状态、尾窗口、reset 和聊天模板。
4. 将稳定基线与候选分开，按性能参考测日志、采样、复制、线程、图执行。
5. 报告实际输入/输出数、停止原因、采样、反馈策略、有效与纯图 prefill 区别，明确未验证项。

完成后交付可复现命令、源代码版本与子模块指针、模型/库哈希、速度及精度证据。只有实际执行过的结果写成“已验证”。
