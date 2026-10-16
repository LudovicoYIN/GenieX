# Qwen3.5 团队分支与上游同步

本分支在官方 GenieX 之上维护 Qwen3.5 QAIRT 适配，技能入口为 [qualcomm-llm-adapt](../skills/qualcomm-llm-adapt/SKILL.md)，团队约定见 [AGENTS.md](../AGENTS.md)。技能随 feat 分支获取，无需另行下载；在支持本地 skill 的代码助手中可按目录加载，或复制该完整目录到助手的 skills 目录。

## 仓库分工

| 内容 | 位置 | 提交方式 |
| --- | --- | --- |
| 公共 API、插件 bridge、benchmark | GenieX 主仓库 sdk/ | 主仓库提交 |
| Qwen3.5 图执行、状态反馈及数值适配 | third-party/geniex-qairt 子模块 | 先提交插件，再更新主仓库 gitlink |
| 可复用适配 skill | skills/qualcomm-llm-adapt/ | 独立主仓库提交 |
| 团队工作约定 | AGENTS.md、本文件 | 主仓库提交 |

子模块 URL 跟随团队 fork；不要将其替换为不包含适配提交的上游地址。Skill 中的历史基线 patch 是独立迁移参考，在此分支无需再次应用。

## 后续合并官方代码

当前长期维护分支名为 `feat/qwen35-runtime-speed-20261014`。名字中的日期不表示需要每天新建分支。保留 merge 历史，避免多人使用时重写远端 feat。

建议把官方远端命名为 upstream，团队可写远端命名为 fork（实际已有名字可以保留）。先用 `git remote -v` 检查；以下 upstream 只在缺失时添加一次：

```sh
git remote add upstream https://github.com/qualcomm/GenieX.git
git fetch upstream main --recurse-submodules=no
git switch feat/qwen35-runtime-speed-20261014
git status --short
git merge upstream/main
```

合并前处理或隔离未提交改动。第一次克隆此 feat 时按通常方式初始化子模块，插件内配置独立的官方 upstream：`https://github.com/qualcomm/geniex-qairt-plugin.git`。子模块默认可能处于 detached HEAD，先切到团队的插件 feat 分支，再 fetch/merge 官方 main。使用普通 fast-forward push，不强推。

若发生 gitlink 冲突：在插件仓库确认主仓库两侧指针分别是什么、是否为祖先关系。插件 feat 已包含新的官方指针时保留该 feat；否则先合并插件的新上游并验证。插件推送成功后，再在主仓库 `git add third-party/geniex-qairt`，完成 merge。避免对未初始化子模块直接执行会暂存删除目录的命令。

```sh
# 以下在主仓库完成冲突处理和验证后执行；fork 是团队可写远端。
git push fork HEAD:feat/qwen35-runtime-speed-20261014
```

`skills/` 单独占用目录，不修改自动生成或 vendored 文件来存放 skill。普通 merge 会保留上游没有更改的 skill；若上游未来加入同名路径，则需要人工合并。不要使用同步镜像、整目录替换或 reset upstream/main 来更新 feat。

## 2026-10-16 同步记录

- 官方主仓库基线更新到 `1f359cb7`，通过 merge 保留原有三个 Qwen3.5 分支提交。
- 官方插件 main 仍为 `f3a3104`；适配插件 `bb28c86` 已包含该上游，因此无需制造新的插件 merge 提交。
- Skill 及团队指南独立提交，不嵌入模型、运行库、个人工作区路径或测试设备信息。
- 验证：skill 结构校验、全部 12 个纯 CPU 语义 demo、图清点示例与 Markdown 引用检查通过。NDK r29 / Android arm64 API28 下公共 SDK 和 benchmark 编译通过；此次关闭插件构建并复用既有 Rust model-manager 静态库，未宣称插件全量重编译。
- 本次为源码同步。已有交付版二进制与历史速度属于原验证版本；未替换模型/交付运行库，未重跑完整模型 PPL 或吞吐。
