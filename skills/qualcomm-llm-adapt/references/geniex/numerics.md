# 量化、Embedding、RoPE、Mask与采样

## TFN转换

`real = scale * (stored + offset)`。例如q=32031、scale=1e-5、offset=-32021，实数=0.0001；换成scale=2e-5、offset=-100的输入编码应接近105，不是直接copy32031。写回前确认舍入模式和范围；溢出饱和可能掩盖错误encoding。

Demo：`detail_demos.py quant`。零初始化使用整数-offset；浮点中间步骤可能出现32308.999…再截为32308，哪怕真实零应为32309。

## CPU Embedding LUT

旧部署是248320×2048 little-endian UF16 LUT，scale=5.8860487115453e-06、offset=-32021，约970MiB。索引先查范围、行偏移和byte order，再去量化。确认pad-token，不默认填token0；只移除embedding context不够，还要连好hidden入口。

Demo：`detail_demos.py embedding`用小表验证行查找与还原。它不包含模型LUT。FP32 LUT与UF16 LUT区别是量化误差及还原开销，先对比参考embedding，不因“CPU”就认定不准确。实际fullgraph整数入口无需该LUT。

## concat RoPE

当前direct-stock rope-dim=64、theta=1e7，先生成32个频率，再把同一半cos/sin重复两次，不是64个独立频率。head_dim=256也不代表旋转256维，要读partial rotary和导出shape。

已对官方该路径逐项核对：`value / cos_scale - cos_offset`裁剪后截断，sin/cos均用cos量化参数。`GENIEX_CONCAT_OFFICIAL_QUANT=1`只用于已确认该policy的concat模型，不能泛化所有版本，不能凭“nearest更精确”替代官方encoding。

Demo：`detail_demos.py rope`展示频率重复与nearest/truncate差异；生产实现还需要参考C++双精度计算结果逐项对照，不用纯Pythondemo宣称bitwise相等。当前证据是4096×64官方cos/sin编码逐项一致。

## 直接生成量化mask

标准mask值为屏蔽-1e9、可见0，先按同一转换函数算两个码，再填UF8/UF16输入。历史可见区域与当前窗口causal区域分别填写，padding保持屏蔽，cache_index与写游标一致。无axis编码且shape满足时才启用；其他情况保留原路径。

Demo：`detail_demos.py mask`比较先float后quant与直接填码等价。若128×4096，float临时矩阵约2MiB，UF16输入约1MiB；省掉的是CPU准备与转换，不是attention本身。

## 贪心与随机采样

GenieX CLI temperature=0可能表示沿用bundle/default；官方0为贪心。本案例显式`--temperature -1`且模型配置temp=0/top-k=0/top-p=1。不是修改所有应用随机采样偏好。

无grammar、无重复/频率惩罚、共享正scale的logits，argmax(real)=argmax(encoded)，省float数组。UF16 NEON一次8个，第二遍找最早最大值保持tie-breaking。FP16位模式不是可直接比较的有序无符号整数；有axis编码也不能未证明就直接编码argmax。

Demo：`detail_demos.py greedy`和`assets/cpp/argmax_neon.cpp`。生产入口`sampleNextToken()`与`Graph::argmaxOutput()`。有额外采样约束时保留完整sampler与历史accept逻辑。
