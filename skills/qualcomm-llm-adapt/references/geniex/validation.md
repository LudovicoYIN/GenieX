# 精度、状态连续性与验收

## 四类证据不同

| 证据 | 能证明 | 不能证明 |
|---|---|---|
| 单次零状态forward | 图I/O和该步数值一致性 | 连续KV/recurrent正确 |
| 固定token IDs的多步官方对照 | 已测输入上的runtime一致性 | 模型本身问答正确 |
| 正常问题与多轮 | 模板、EOS、质量及会话边界 | 整体PPL或所有场景准确率 |
| 完整PPL | 指定数据/执行路径的next-token损失 | AR1生成、多轮取消及聊天体验 |

## 固定问题与模板

`assets/qa-prompts.txt`包含8个独立问题，期望`323、北京、甲、10、香蕉、是、十月十二日、东区`。raw user文本传`--accuracy --no-think --prompt-file`，bench会套模板；已经套模板的文本不要再进入该模式。每题reset；最多128输出，记录完整回答、EOS/length、实际token数与是否重复。

先验证tokenizer与checkpoint，BOS/PAD/EOS、system、thinking开关一致。GenieX默认可能补system `You are a helpful AI assistant.`，做官方对照时要包含它；省掉system会改变token IDs。不要因no-think输出仍含think就删除输出掩盖问题。

对照不同引擎尽量直接输入相同token IDs，不让各自模板隐式变化。比first-logits、状态tensor或完整输出IDs定位首个分歧。文本匹配不等于已比较IDs；EOS计数的不同要单独解释。

## PPL协议（当前参考案例）

WikiText-2 raw test全部文本用`\n\n`拼接，原tokenizer统一tokenize、add_special_tokens=True，不用chat template；前10个不重叠4096-token块，固定ID与哈希。校准使用train，与评测test分开。

每块reset，块内32个AR128窗口持续反馈本模型自己的KV/recurrent，位置递增。整块第t行logits预测t+1，跨AR窗口边界也计入；只丢每个4096块最后一行。总目标=10×4095=40950。先汇总NLL，PPL=exp(total_NLL/40950)，不平均各块PPL，不采样或temperature。

实际DLC/HTP评测注明embedding是在ORT、CPU LUT或HTP。不要把QuantSim PPL写成最终DLC PPL。全词表读取及CPU loss很贵，PPL总耗时不是模型prefill速度。AR128 PPL也不能代替连续AR1 teacher-forcing验证。

## 多轮与异常

先实现完整历史reset后重算，再验证增量模板+缓存。禁止保留cache却重送完整历史导致重复prefill。测会话A/B隔离、回调取消、reset后结果、CL边界、AR尾窗口、异常drain与销毁。当前案例尚未证明完整多轮可用。

问答通过标准明确：正常答案、无无意义循环、给出结论。输出中偶然出现正确词但后面大量重复单列“命中但异常”，不算正常对话通过。
