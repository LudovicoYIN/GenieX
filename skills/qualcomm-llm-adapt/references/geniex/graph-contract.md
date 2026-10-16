# 图接口与版本识别

## 图名和图数量

当前案例包含 `ar128_cl4096_1_of_1` 与 `ar1_cl4096_1_of_1`；旧包是`*_S_of_4`，不一定仍按4分区部署。用元数据/实际QNN introspection为准，不能依据文件名猜模型分工。映射为phase(AR)、CL、shard后，核对每个变体的所有特殊输入。

`input_ids`整数入口不需要CPU embedding；hidden浮点或量化入口才要LUT/embedding graph。末图输出`logits`的最后维是vocab；各shard的hidden边界用前一图输出名匹配后一图输入，并核对shape、dtype与编码。若编译器改名，需要显式对应表，不能选“第一个非特殊输入”就宣称接通。

## Fullgraph hidden_size 坑

原core要求推断hidden_size，但input_ids→logits单图没有外露hidden边界，加载完QNN后仍返回`-100201`。只对“单shard、整数入口、logits出口”放宽必填要求；保留vocab校验，不虚构hidden=2048。多shard仍必须有真实连接宽度。

Demo：`python3 scripts/detail_demos.py fullgraph`。源码定位：`LLMModel::inferSpecFromGraphs()`，补丁见`assets/patches/qwen35-plugin.patch`。

## shape相同不足以 memcpy

| 情况 | 处理 |
|---|---|
| shape/dtype/scale/offset/axis encoding/layout全部相同 | 检查字节数、寿命后可直接复制 |
| UF16输出 → FP16输入 | 反量化成实数，再编码成FP16，不能把两个16bit表示当同一种数 |
| UF16输入输出scale不同 | 反量化再量化，检查截断、饱和率和轴参数 |
| flat KV → HMX tiled KV | 按目标QNN布局专用路径重排与rebase |
| 同样HMX但stride/AR不同 | 核对stride和写游标，不能只判断layout字符串 |

轴量化转换未实现时，应给出具体tensor错误，不静默用第一个scale。runtime检查shape变化、缺失配对或编码变化后停止该路径。

## SDK与硬件

较新context用旧QAIRT加载会报`Using newer context binary on old SDK`；切换host库时同时匹配V73 stub/skel、HTP扩展及System库。编译插件的`qairt_version=2.50`不等于实际加载runtime版本，记录context buildId和`/proc/maps`。

“1002”可能来自不同层，不等于权限或内存。确定先失败的是动态加载、QNN context初始化、图解析、分配还是execute；保留完整调用链。VTCM不是全部模型权重的存储池；板子16MiB并不保证16MiB编译预算一定成功。当前案例VTCM8是已测配置，不能泛化为硬件上限。

清点demo：`python3 scripts/inspect_bundle.py assets/demo-bundle`；它不会把JSON静态报告冒充真实context运行验证。
