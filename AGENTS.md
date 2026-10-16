# Team guide for Qualcomm LLM adaptation

本文件服务于从 main 开发适配、或维护已有 feat 的工程师和代码助手。先读取当前工作区状态；保留其他人的未提交改动。根据任务范围工作，不默认重做模型转换或更换已交付运行库。

## 从哪里开始

- `skills/qualcomm-llm-adapt/SKILL.md`：QAIRT/QNN 模型到 GenieX 的适配入口。按任务选择参考文件，不必一次读取全部资源。
- Skill 中的 `references/geniex/evidence.md`：历史案例及限制。历史数字不是新版本的性能保证；feat 中若有额外运行报告，再按任务阅读。
- `docs/qwen35-development.md`：分支、子模块与上游同步约定。
- `sdk/include/geniex.h`：公共 C ABI，C++ / JNI 接入应与实际运行库匹配。
- `third-party/geniex-qairt/`：QAIRT 插件子模块；模型图执行、状态反馈和数值路径主要在这里。

Skill 的模型转换部分目前只定义交付契约，不能宣称已有完整自动转换流程。main 保留官方实现基线，只增加 skill 和团队指南；不要假定 main 已有 Qwen3.5 定制适配。开始适配时从 main 创建新的 feat，再按 skill 检查并移植补丁。已有适配 feat 不要重复应用旧基线补丁。

## 工作区与代码边界

- 先核对当前分支、commit、子模块指针和 dirty 状态。主仓库干净不代表插件及其嵌套子模块干净。
- 插件变更先在插件仓库提交、推送，再在主仓库记录可获取的子模块 commit；不要只提交 gitlink 而遗漏实现。
- Skill 独立放在 `skills/qualcomm-llm-adapt/`。保持其引用相对、自包含，不加入个人绝对路径、个人仓库地址、设备序列号或访问凭据。
- 模型、proprietary QAIRT 库、构建输出、绝对路径软链接和板端原始大日志不作为本分支源码提交。遵循已有许可与忽略规则。
- 提交只包含本次任务的文件。部署、源码分支和已验收二进制是不同的交付物；合并源码不代表已发布新推理库。

## 同步官方上游

保留 feat 历史，用普通 merge 合入官方 main，不用 reset --hard 或强推覆盖团队分支。若需要改用其他策略，先根据团队明确约定处理。

`skills/` 和本指南作为自己的独立提交维护。上游未改这些路径时通常可自动保留；同路径改动仍可能冲突，逐项解决，不用整目录覆盖消除冲突。

子模块冲突需要在插件仓库检查双方 ancestry，必要时先合并插件上游，再选择包含所需适配的新 commit。不要机械选择 upstream gitlink。同步后验证主仓库和插件的版本组合。适配实现保留在 feat；通用 skill/指南可独立提交到 main，再从 main 合入 feat，不必把整个 feat 合回 main。

## 适配与验证

- 新包先清点 graph、AR/CL、I/O shape、dtype、encoding、KV layout、recurrent/conv state 和 tokenizer/template；不要凭文件名推断接口兼容。
- reset 清理的不只是 KV，还包含 recurrent/conv 的逻辑状态。FP16 状态不能按量化 UF16 反解，量化零也不一定是整数 0。
- 改状态/布局/数值路径后，验证单步和连续反馈、多轮、reset、尾窗口与异常退出；不要仅凭随机输入吞吐或文字通顺验收精度。
- 保留已测 runtime 基线，候选使用独立构建/部署目录。不要为了验证源码合并而覆盖同事正在使用的交付包。
- 速度记录实际输入/输出 token、stop_reason、采样、预热、重复次数、反馈配置和设备条件；TTFT 用 ms，Prefill/Decode 用 tok/s。
- 不把非 EOS 停止当作完整对话成功。EdgeLLM 适配还需验证 EOT/末 token、KV 闭合、长度截断后的拒绝续接和 reset 恢复。
- 功能测试、PPL、算子 profile 各自说明范围。未执行的检查写为未执行；未经重测，不沿用历史速度宣称合并版相同表现。
- 不因为电量显示低就修改电源或温控。先读取电量、真实温度、cooling 状态和 CPU 可用掩码；设备配置变更须在用户授权范围内进行。

## 检查与交付

只运行与变更有关的检查。Skill 变更运行可用的 skill validator、纯 CPU demo 和引用检查；C++/构建变更运行相应目标编译；运行时行为变更再做必要板端验证。构建所需 QAIRT/NDK 路径通过配置传入，不硬编码开发者目录。

结束时报告：改动目的、主/子仓库 commit、实际执行的检查、未覆盖的风险、是否推送。不要在用户只要求源码同步时暗中替换模型或发布新的运行库。
