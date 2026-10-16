# 从 main 开始适配与维护 feat

团队工作入口为 [AGENTS.md](../AGENTS.md) 和 [qualcomm-llm-adapt skill](../skills/qualcomm-llm-adapt/SKILL.md)。别人拿到 main 后，可以直接阅读这些材料并创建自己的适配分支；不需要先取得现有 feat 的实现。

## 分支职责

| 分支 | 内容 |
| --- | --- |
| main | 官方 GenieX 实现基线，加团队可复用的 skill、AGENTS.md 和工作说明 |
| feat/... | 基于 main 的具体模型适配、构建修改、插件指针和验证记录 |

已有 Qwen3.5 适配在 `feat/qwen35-runtime-speed-20261014`，它是可参考的已实现案例。main 不通过合并该 feat 来获得文档，也不因此获得它的运行时修改。模型、proprietary QAIRT 库和交付二进制不放进 skill。

## 新同事从 main 开始

```sh
git switch main
git pull --ff-only
git switch -c feat/my-model-adaptation
```

1. 阅读 AGENTS.md，再按 SKILL.md 选择图接口、数值、状态反馈、部署或验证参考。
2. 按模型转换交付契约清点现有模型包，确定目标板和需要修改的层次。
3. 初始化所需子模块。参考补丁的基线与用法见 [构建部署](../skills/qualcomm-llm-adapt/references/geniex/build-deploy.md)。先 `git apply --check`，检查当前上游是否已包含相同实现，再决定应用或按语义移植；不盲目覆盖当前源码。
4. 插件改动在 `third-party/geniex-qairt` 的独立 feat 分支提交并推送；再由主仓库记录可获取的子模块指针。不要只提交主仓库而遗漏插件实现。
5. 按 skill 做对应验证，报告实际执行范围，提交自己的 feat。Skill 是过程与案例参考，不保证所有新模型自动获得相同速度或精度。

Skill 可直接按仓库路径加载，也可以把完整 `skills/qualcomm-llm-adapt/` 复制到代码助手的 skills 目录。模型转换部分目前只定义交付契约，不是完整转换教程。

## 持续同步上游

建议官方远端名为 upstream、团队可写远端名为 fork；已有远端名不必强制更改。先检查 `git remote -v`；缺少官方远端时添加一次：

```sh
git remote add upstream https://github.com/qualcomm/GenieX.git
git fetch upstream main --recurse-submodules=no
git switch main
git merge upstream/main
# 检查和解决冲突后推送团队 main。
git push fork main

git switch feat/my-model-adaptation
git merge main
```

用普通 merge 保留团队 skill 和指南。不要用 `reset --hard upstream/main`、整目录覆盖或强推来同步。上游未改同路径时会自然保留这些文件；若未来产生同名目录或文件，仍需人工解决冲突。

插件的官方远端为 `https://github.com/qualcomm/geniex-qairt-plugin.git`。main 跟随官方插件指针；feat 按其需求维护适配插件指针。发生 gitlink 冲突时，先在插件仓库检查双方 commit 的祖先关系，必要时先合并插件上游、推送并验证，再记录主仓库指针，不能直接选 main 的指针而丢掉 feat 适配。

通用文档或 skill 的改进尽量作为独立提交进入 main，再从 main 合入 feat；若改动先发生在 feat，可仅挑选相关文档提交到 main。**不需要把整个 feat 合回 main。** 特定模型的二进制、性能结论和实现保持独立，不混入通用指导。
