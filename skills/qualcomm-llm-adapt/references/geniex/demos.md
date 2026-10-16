# 细节 Demo 索引

在skill根目录运行，Python脚本要求Python 3.11或更新版本。数值demo只依赖Python标准库；C++ demo依赖对应SDK或ARM编译器。静态例子均使用小张量，不能替代实际模型对照。

| 细节 | 可执行示例 | 演示内容 |
|---|---|---|
| 图清点 | `python3 scripts/inspect_bundle.py assets/demo-bundle` | graph AR/CL、I/O dtype/编码、missing context、状态pair与边界；fixture不是模型 |
| Fullgraph入口 | `python3 scripts/detail_demos.py fullgraph` | 整数入口单图可无hidden；多shard不可跳检查 |
| UF16/FP16与零码 | `python3 scripts/detail_demos.py quant` | encoding变换、实际零码、FP16位模式不可直接copy |
| 状态分类与reset | `python3 scripts/detail_demos.py state` | KV append、recurrent递推、reset不泄露历史 |
| Conv有效尾部 | `python3 scripts/detail_demos.py conv` | valid37 vs AR128，按plane/stride取窗口 |
| KV布局 | `python3 scripts/detail_demos.py layout` | 相同shape不同storage不能memcpy；非HMX格式实现 |
| CPU LUT | `python3 scripts/detail_demos.py embedding` | 小UF16表little-endian查行、去量化与越界 |
| concat RoPE | `python3 scripts/detail_demos.py rope` | 半频率重复、舍入与截断差别 |
| Mask | `python3 scripts/detail_demos.py mask` | 直接量化填充与float路径相同、causal/padding |
| Argmax | `python3 scripts/detail_demos.py greedy` | 共享scale单调性、最早tie、axis反例、FP16反例 |
| NEON实现 | `assets/cpp/argmax_neon.cpp` | ARM一次8值、tail与ties、标量参考；编译后自行运行 |
| 异步状态 | `python3 scripts/detail_demos.py schedule` | disjoint jobs、barrier、任务错误仍drain |
| AR1尾窗口 | `python3 scripts/detail_demos.py tail` | 128/129/256路由及最终logits来源 |
| 速度口径 | `python3 scripts/detail_demos.py metrics` | 补齐128不能算真实37token输入速率 |
| 全部本机demo | `python3 scripts/detail_demos.py all` | 运行全部纯CPU语义demo |
| C++调用 | `assets/cpp/chat.cpp` | reset/template/no-think/显式greedy、生命周期 |

## Android端wrapper

先部署匹配model/runtime/QAIRT，再push `scripts/run_android.sh`。它不自动推送SDK、改模型配置或电量报告。

```sh
# 在Android shell中
MODEL_DIR=/data/local/tmp/my-bundle/model \
RUNTIME_DIR=/data/local/tmp/my-bundle/runtime \
QAIRT_LIB_DIR=/data/local/tmp/my-bundle/qairt \
sh /data/local/tmp/run_android.sh --accuracy --no-think \
  --prompt-file /data/local/tmp/my-bundle/qa-prompts.txt -n 128
```

性能配置按已证实的模型选用：

```sh
# 主线程mask十六进制，0x10=CPU4；worker0x58=CPU3/4/6。
# concat及状态策略的适用条件先读numerics/state参考。
MODEL_DIR=/data/local/tmp/my-bundle/model \
RUNTIME_DIR=/data/local/tmp/my-bundle/runtime \
QAIRT_LIB_DIR=/data/local/tmp/my-bundle/qairt \
MAIN_CPU_MASK=10 GENIEX_DECODE_WORKERS=3 GENIEX_DECODE_CPUMASK=58 \
GENIEX_DECODE_POLL=1 GENIEX_CLOCK_KEEPER_THREADS=0 GENIEX_RECURRENT_WORKERS=3 \
GENIEX_EXACT_STATE_ZERO=1 GENIEX_DIRECT_QUANT_MASK=1 \
GENIEX_CONCAT_OFFICIAL_QUANT=1 GENIEX_AR1_PREFILL_TAIL=1 \
GENIEX_DEFER_DECODE_RECURRENT_PREFILL=1 GENIEX_DEFER_PREFILL_RECURRENT=1 \
sh /data/local/tmp/run_android.sh -p 2048 -n 512 -r 3
```

这是单次进程参数示例，不是所有模型默认设置。基线对照时逐项移除候选开关，并分别记录实际CPU可运行掩码。随机seed不能跨主机libc天然生成相同IDs，官方对照应读取同一输入文件。

## 本次示例验证范围（2026-10-14）

纯Python十二个语义demo已执行通过，目录与tar清点结果一致，并能报告缺失context及状态encoding不一致。C++ chat与argmax示例使用NDK r29、Android arm64/API28编译链接通过；NEON示例在当前USB8550上实跑通过整词表、同分值、tail、全零和空输入拒绝检查。Android wrapper已验证动态库路径及`--help`参数转发。本次未用新C++应用重跑整个模型；模型问答证据来自现有bench。所有toy例子仅说明对应不变量，不实现完整QNN/HMX或GatedDeltaNet计算。
