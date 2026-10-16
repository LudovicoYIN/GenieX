# 已踩问题索引

| 现象/误判 | 真实检查或处理 | Demo / 参考 |
|---|---|---|
| 同context，以为GenieX等于libGenie | 两套host输入/采样/状态调度实现分别对齐 | workflow、validation |
| 1002即权限/内存 | 先找失败阶段和完整下层日志；fullgraph曾是hidden_size检查失败 | graph-contract、fullgraph demo |
| 新context加载旧SDK | 匹配context buildId与host/stub/skel版本 | inspect_bundle、build-deploy |
| W4A16就认为KV/recurrent都16bit | 按tensor列encoding，KV8与recurrent FP16/A16可共存 | state demo |
| 两边16bit就memcpy | UF16与FP16不同；scale不同也需转换 | quant demo |
| recurrent/conv memset(0) | 量化零码可能=-offset，未必0 | quant/state demo |
| conv取最后3行 | ARpadding下取valid_tokens偏移，而非固定AR末尾 | conv demo |
| KV名相同就统一重排 | AR128 HMX、AR1 flat、scatter/index/stride单独判断 | layout demo |
| head_dim当rope_dim | partial rotary与concat形状要按导出核对 | rope demo |
| cos/sin用通用nearest | 按参考路径舍入/scale，当前官方concat用截断 | rope demo |
| 默认temperature=0是贪心 | 本案例GenieX0沿配置，官方0贪心 | greedy demo |
| 无论有无惩罚都直接argmax | grammar/penalties需要完整sampler；轴量化也需校验 | numerics |
| 异步任务取消后不等待 | buffer/TLS/计数器可悬空，barrier/drain再退出 | schedule demo |
| 129token仍从AR128采logits | 官方1tail可能AR1，选最后实际图 | tail demo |
| 文本吞吐误用128补齐长度 | 记录真实长度，区分有效与padding吞吐 | metrics demo |
| 短答案显示70tok/s就当decode极限 | EOS计数和少步骤偏高，测固定长输出 | validation |
| 只过滤应用日志 | QNN/DSP内部详细日志仍开；WARN单独控制 | performance |
| affinity成功是假设 | 检查每个TID的Cpus_allowed_list，EINVAL检查可运行核 | performance |
| qnn cycles证明带宽瓶颈 | 缺schematic没有有效optrace内存证据 | performance |
| fp单步正确便认为状态无误 | 多窗口/AR1连续反馈与reset另验 | validation |
| 输出与官方一致便认为精度好 | 两套引擎会一起答错；本案例已实测 | evidence |
| 只push GenieX主仓库 | 实际core在插件子模块；发布插件fork并更新gitlink | build-deploy |
| deliverables与测试目录同名就同库 | 校验hash、maps、配置、软链接和命令口径 | inspect_bundle、build-deploy |

## 早期部署与图改写补充

| 现象/误判 | 已核实原因与处理 |
|---|---|
| 16 MiB VTCM context 不能运行，想仅改 JSON | 当前验证采用 8 MiB 编译 context；VTCM 设置固化在 context，需按目标重新生成，不能只改运行配置 |
| 14001 / 1008 或 V73 库缺失 | 曾混用 QAIRT 2.45 / 2.50 与 host/stub/skel；统一版本和 V73 文件后跑通 |
| 另一种 1002 是整机 RAM 不够 | 早期加载中单 PD 空间不足触发新增 PD，ADB shell 被权限/SELinux 拒绝，root 可加载；与后期 fullgraph hidden_size 检查失败是不同原因 |
| W4 包没有按预期缩小 | 初期 AR1 / AR128 权重共享很少；核对实际编译存储格式和共享权重，不能只看位宽标签 |
| KV8 换包后速度掉到 7 tok/s | 初版 18 个 recurrent V 输入输出编码不同，约 9 MiB 状态逐 token 去量化再量化；r2 对齐后恢复，不能全算作 KV8 提速 |
| 跨图 hidden dtype/shape 相同就直拷 | 边界编码仍可能不同；优先导出时对齐，实验转换不能隐藏不兼容 |
| AR128 短输入 padding 修了源码就已修模型 | padding 方向曾与状态构造不一致；已有 context 不会随源码自动改变，需要重新导出并验证连续反馈 |
| embedding 文件看起来在目录里 | 曾遇到复用软链接失效；交付需包含实际目标并验证哈希 |
| all-Conv 应该让 Transformer 全部加速 | 实测 head 大幅提速、Transformer 当阶段反而变慢；看分段 profile，不能仅按总速度归因 |

对应速度与分段证据见 [历史模型优化](model-history.md)。
