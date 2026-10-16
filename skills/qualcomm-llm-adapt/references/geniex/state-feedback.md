# KV、recurrent 与 conv 反馈

## 三种状态分别处理

- full-attention KV：每步append新key/value到历史缓存，mask/cache_index描述同一位置。
- recurrent state：线性注意力累积矩阵，是`下一状态=f(上一状态,当前token)`，并非追加token数组。
- conv state：最近K−1个位置的特征窗口，当前案例保留3位置。

W4A16只描述部分权重/activation；KV8、recurrent K A16、V FP16可以同时存在。读各tensor真实dtype/encoding，禁止拿统一“KV bit数”描述所有状态。

## 初始化与编码

每个新问题reset KV、recurrent、conv、位置与模板会话状态。TFN零值编码为`clamp(-offset)`，UF16 offset=-32309的零码是32309，不能memset(0)。FP16零才是位模式0。axis quant按对应轴初始化。

Demo：`detail_demos.py quant`、`state`。输入输出encoding不同，走实数转换；记录饱和。AR128/AR1的输入状态shape、编码需要核对，跨CL/AR变体不能假设完全相同。

## Conv 输出尾部必须按有效token数取

例如输出shape `[B,H,3+AR,D]`，输入`[B,H,3,D]`。AR128只有37个有效token时，每plane应该从输出第37行取3行；不能取最后3行（里面可能是padding结果）。AR1从第1行取3行。

旧路径每plane先copy到vector，再写目标；编码完全匹配时现在直接从`plane_base + valid_tokens*row_bytes`复制3行，保持每plane输出stride。shape不符或编码不符回到转换路径/明确报错。

Demo：`detail_demos.py conv`，同时演示padding误取和AR1。

## KV layout与游标

本例AR128输出HMX、AR1输出flat，但输入可以均为HMX；有SCATTER(full CL + cache_index)和历史prefix布局两类。输入mask、cache_index、updateKV的写位置必须一致。tiled布局使用原core/QNN定义，不能编造一个reshape代替；`detail_demos.py layout`只是小型逻辑布局的反例，非QNN HMX实现。

## 并行与延后副本

图execute返回后提交KV任务，再提交recurrent各状态对分片。任务只能写互不重叠缓冲区；下一次读状态、重排stride、升级CL、evict、reset或destroy前barrier。复制时间与NPU/主线程重叠，不能相加得到墙钟耗时。

当前decode每步更新AR1；闲置AR128镜像可推迟至decode结束。prefill期间只连续维护AR128，结束后再同步AR1。涉及AR1 tail或切图时先同步目标图。不是跳过实际状态。

worker使用正确`valid_tokens=1`及线程局部slice；RAII恢复TLS，异常退出drain任务，防止捕获的计时器和缓冲区提前销毁。回调取消也要完成清理。Demo：`detail_demos.py schedule`。

## Tail与多轮

129-token输入可能是AR128处理128、AR1处理剩1；样本中官方如此。同步状态、切stride，并从最终实际执行图采logits。不能从旧AR128 logits取首token。PPL需要全部位置logits，不能盲目套末位置或尾AR1优化。

Demo：`detail_demos.py tail`。测短于128、128、129、255、256及接近CL上限；包含EOS、取消、reset、多轮。固定128策略与AR1 tail是模型/runtime策略选择，不是所有模型必需。
