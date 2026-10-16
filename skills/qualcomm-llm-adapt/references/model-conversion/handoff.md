# 第一部分：模型转换与运行时交付接口

当前文件是转换部分的交接契约；模型改写、AIMET PrepareModel/QuantSim、ONNX 导出、DLC/context 生成的具体教程与脚本由转换负责人补充。这里不提供一条对未知模型声称可用的转换命令。

## 转换人应交付什么

| 类别 | 必要信息 |
|---|---|
| 原模型 | checkpoint/tokenizer 身份、revision、vocab、EOS/PAD/BOS、聊天模板、是否启用思考 |
| 图改写 | MHA→SHA、Linear→Conv、head是否只算末位置；每步 FP 等价验证与 encodings 迁移方法 |
| 量化 | 实际每类 tensor bitwidth；权重/activation/KV/conv/recurrent/head/embedding 分别列出，含敏感浮点路径 |
| 图接口 | 每个 AR/CL/shard 的 name、shape、dtype、scale/offset、axis encoding、layout、有效输入长度、padding约定 |
| 状态 | KV与recurrent/conv配对、初始实数值、零编码、输出到下一输入转换、AR之间共享或独立缓冲区 |
| 工具链 | QAIRT完整版本、context buildId、HTP架构、VTCM编译预算、O级别、共享权重方式 |
| 运行文件 | context、DLC（若做DLC对照）、配置、tokenizer、模板、LUT及其manifest（若CPU embedding）、SHA256SUMS |
| 精度 | 固定评测token IDs/哈希、参考logits/state、AR128与AR1结果、PPL数据与有效目标数 |
| profiling | context生成时的optrace schematic，必须与该context匹配；framework trace有条件提供 |

不要仅给“W4A16”标签；KV8不表示recurrent也是8bit。Qwen3.5线性注意力的recurrent矩阵不同于full-attention KV。

## 与 GenieX 的分工

转换决定图内计算和接口；GenieX负责模板/tokenizer、输入准备、跨图连接、状态反馈、采样、调度。CPU LUT也是部署选择，要确认量化表如何生成与解码，不能删除embedding context后假定运行时自动接好。

只有最后token的logits用于prefill时，若要省lm_head矩阵计算，应在head之前选hidden；在全部logits算完后切片不省该矩阵乘。PPL需要全部位置logits，应保留相应评测图/路径。

MHA→SHA或Linear→Conv后tensor名称、shape或权重轴改变，需要与新图对应的encodings。不要凭命名重映射宣称校准结果仍正确；转换端必须验证改写FP、Prepared FP、QuantSim与实际DLC/context。
