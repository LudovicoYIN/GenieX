# 性能优化与profiling

## 可比较的测量

记录实际token IDs、采样、输入/实际输出数、reset、warmup、EOS、runtime库哈希、CPU affinity、power与thermal状态。固定长度随机IDs用于吞吐；真实聊天用于质量。不可把只输出2token的瞬时速度与512token持续decode混比。

GenieX `ProfileData`的effective prefill=prompt_tokens/prompt_time，本例prompt_time=TTFT，包含首token路径；text prompt bench可按AR128补齐计数，必须额外记录实际token长度，避免高估。decode计数也可能含EOS，官方边界略异。Demo：`detail_demos.py metrics`。

先WARN再测性能；TRACE仅短时诊断，日志写板端文件后pull，避免adb终端/UI刷新阻塞。只过滤SDK callback未必关闭QNN/DSP内部日志，本例`GENIEX_QNN_LOG_WARN=1`另控制后端。

## 优化顺序与收益边界

| 原开销 | 改动 | 核对 |
|---|---|---|
| 词表转换/采样约2.7ms/token | 受条件保护的encoded贪心+UF16 NEON | 本例CPU4采样约0.029ms；差值包含采样配置对齐 |
| conv中间vector与重复镜像 | 直接tail复制、闲置图按需同步 | shape/encoding正确；实际下一步状态不延后 |
| KV提交晚，反馈串行 | 提前enqueue；recurrent分片 | disjoint writes、下一读之前wait、异常drain |
| CPU线程迁移或较慢核 | 主CPU4，3worker允许CPU3/4/6 | 此8550实测方案，换板重测；官方也受益 |
| float mask后再量化 | 直接填两种量化码 | causal/history/padding与cache_index一致 |

参数demo在`run_android.sh`，开关完整说明在[numerics](numerics.md)与[state](state-feedback.md)。main mask用hex`10`、worker hex`58`分别是CPU4与CPU3/4/6，worker允许掩码不等于每线程固定独立核。

较新上游本身未提速；prefill睡眠、先copy logits再scan、自定义NEON state memcpy未观察到收益。recurrent分线程固定CPU0–2反而慢。不要把尝试过写成有效优化。

## 分层分析

1. 顶层：每token total、图execute包装、sample、wait、state copy。worker时间与图时间重叠，不求和当墙钟。
2. 图级：同一context取AR1/AR128代表输入，保留位置/状态/量化原生文件；`qnn-net-run --use_native_input_files --use_native_output_files --shared_buffer`。测零状态input需标明，不冒充真实长序列状态。
3. 算子级：匹配SDK的`qnn-profile-viewer`解析profile；先读该版本`--help`。cycles是计数/成本，不是毫秒。融合算子、并行、频率及事件类型决定如何解释，不能简单逐行相加或固定频率换算成token耗时。
4. 时间线/内存：optrace reader需要生成该context时配套的schematic。`No Valid Input Schematics`时可继续报告可用算子cycles，但不能宣称已经证明DRAM带宽或VTCM spill瓶颈。

查看dump命令示例：

```sh
qnn-net-run --retrieve_context MODEL.bin --backend libQnnHtp.so   --input_list INPUT_LIST --output_dir profile-output --profiling_level detailed   --perf_profile burst --num_inferences 3 --keep_num_outputs 0   --use_native_input_files --use_native_output_files --shared_buffer --log_level warn
qnn-profile-viewer --help
```

INPUT_LIST必须按实际graph选择，不复用本案例的`__,...`多图索引。profile重生成一般不需要重新量化；改图/编码则需要重新验证转换。fullgraph含head的每个AR128窗口都会执行head，分图可在非最后窗口跳过独立head；是否分成2图更快要测，不能只按调用次数判断。

如果板上虚拟电量触发socd限频，先核对thermal类型、冷却状态和真实温度。仅在用户明确授权且已证实传感器模拟异常的范围纠正报告；不把历史thermal_zone82编号或echo值写成通用调速脚本，不关闭真实温度保护。
