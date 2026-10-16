# 第二部分：GenieX 适配流程

## 1. 固定事实

运行 `python3 scripts/inspect_bundle.py MODEL_DIR` 或对tar直接清点，不先上传整个大包。记录包哈希、context文件列表、graph报告、模板与LUT。`adb devices -l`辨认本次目标；serial显示`?`时可用`adb -t TRANSPORT_ID`，旧记录的serial/IP不能默认沿用。

建立 model/runtime/logs 独立目录，记录CLI、libgeniex、plugin、core、proc、QAIRT host/stub/skel版本和SHA256。在多runtime目录并存时用`/proc/PID/maps`确认实际加载路径。

## 2. 画出实际部署分工

先确定三种部署中的哪一种：

- CPU LUT → 两段Transformer HTP → 独立lm_head HTP。
- CPU LUT → 单Transformer HTP → 独立head HTP。
- input_ids → embedding/Transformer/head 全在HTP fullgraph。

Qwen3.5的18个线性注意力层、6个full-attention层是当前2B案例，不是通用常量。按实际config和图I/O核实。不要把full-attention的MHA→SHA收益推广给线性注意力的recurrent更新。

## 3. 适配源码

主仓库是公共API、plugin bridge、bench；`third-party/geniex-qairt`才是核心图/状态实现。按以下顺序修改：

1. graph名称与AR/CL/shard索引；确认没有把诊断AR变体误选成decode。
2. special输入分类：KV、recurrent、conv、RoPE、cache_index、linear_attn_mask。
3. hidden边界连接或fullgraph整数输入路径。
4. KV布局、recurrent/conv配对、初始化和量化转换。
5. mask、RoPE、padding与有效tail。
6. tokenizer/template、EOS/BOS、显式采样语义。

详细映射读[图接口](graph-contract.md)、[状态](state-feedback.md)、[数值](numerics.md)。只有日志级别与CPU调度变更不能用来解释数值修复。

## 4. 验证与性能

加载后先选一组固定token IDs，对比第一步logits与状态；继续多步反馈，并测128/129及长输入。正常问题必须用chat template，不能用随机token生成质量代替。查看[验证](validation.md)。

有稳定正确基线后再按[性能](performance.md)逐项改；若上游软件更新后速度不变，不要继续将更新版本当成优化证据。

## 5. 交付

交付模型文件、匹配SDK/依赖、头文件、模板、最小C++程序、启动脚本、哈希及结果。软链接到实验目录的context/LUT不能算自包含交付。GenieX与插件分仓提交：先把插件提交推到用户可访问的fork，再更新主仓库gitlink和`.gitmodules`；只提交主仓库CMake不会带走core优化。

本skill仅提供已有源码补丁与实践，不默认推远端、不自动修改thermal/sysfs、不停止其他服务。后续行动依据当前用户任务授权。

## 源码修改定位

路径相对 QAIRT plugin 仓库；公共 API 路径另标 GenieX。具体接口会随上游版本变化，以固定提交为准。

| 适配点 | 源码与入口 |
|---|---|
| graph/AR/CL/shard推断、fullgraph入口、特殊tensor识别 | `core/src/llm/llm_model.cpp`：`inferSpecFromGraphs()`；`core/src/llm/llm_spec_loader.cpp` |
| mask/cache_index/linear_attn_mask | `LLMModel::runShard()` |
| KV输出布局与更新 | `LLMModel::updateKV()`、KV布局初始化/stride路径；`core/src/llm/llm_utils.cpp` |
| recurrent/conv反馈及编码转换 | `LLMModel::updateRecurrentState()`、`resetKVCache()` |
| AR128分窗、有效tail、AR1尾步 | `LLMModel::prefillChunks()`与`generate()` |
| concat RoPE及舍入策略 | `core/src/llm/input_provider.cpp`：`ConcatRoPEInputProvider::write()` |
| 贪心快速路径与NEON | `LLMModel::sampleNextToken()`、`core/src/graph.cpp`：`Graph::argmaxOutput()` |
| 线程池与退出同步 | `core/src/threadpool.cpp`、`LLMModel::generate()`中的drain guard |
| 模板/default system/API配置 | GenieX `sdk/plugins/qairt/src/llm.cpp`，plugin tokenizer/pipeline接口 |
| benchmark模板、实际/补齐计数 | GenieX `sdk/benchmark/run.c`、`options.c` |

本次两个源代码补丁已验证可正向应用到注明基线，并通过反向还原文件与基线Git blob哈希核对；补丁不包含模型或QAIRT二进制。
