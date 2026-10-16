# 构建、部署与C++接入

## 官方上游与源码补丁

GenieX主仓库负责公共API、plugin bridge和benchmark；QAIRT plugin子模块负责图执行与状态适配。此skill提供纯源码diff，不包含个人仓库地址、发布分支、作者邮箱或定制子模块指针。

复现补丁的官方上游基线：GenieX `c487efa83b106bb10a4ab844fe2fb32e29a53601`，QAIRT plugin `f3a310431874367e4d75433cd2915d45d50fa7b0`。它们是官方上游版本标识；适配改动以skill中的补丁内容为准。

```sh
git clone https://github.com/qualcomm/GenieX.git GenieX-qwen35
git -C GenieX-qwen35 checkout c487efa83b106bb10a4ab844fe2fb32e29a53601
git -C GenieX-qwen35 submodule update --init --recursive
git -C GenieX-qwen35/third-party/geniex-qairt fetch origin
git -C GenieX-qwen35/third-party/geniex-qairt checkout f3a310431874367e4d75433cd2915d45d50fa7b0
```

设置此skill所在目录，再检查与应用补丁：

```sh
SKILL_DIR=/absolute/path/to/qualcomm-llm-adapt
git -C GenieX-qwen35 apply --check "$SKILL_DIR/assets/patches/geniex-sdk.patch"
git -C GenieX-qwen35/third-party/geniex-qairt apply --check "$SKILL_DIR/assets/patches/qwen35-plugin.patch"
git -C GenieX-qwen35 apply "$SKILL_DIR/assets/patches/geniex-sdk.patch"
git -C GenieX-qwen35/third-party/geniex-qairt apply "$SKILL_DIR/assets/patches/qwen35-plugin.patch"
```

应用后子模块会有本地修改。需要交付源码时，在团队自己的共享代码位置保存插件改动，再记录主仓库与子模块对应版本。不要只提交主仓库CMake而遗漏插件源代码。补丁是已测文本模型适配参考，采用较新上游时先检查是否已经包含对应实现，按语义移植；不要重复应用。使用其中快速路径前仍需验证模型的encoding和状态接口，不能把该补丁视为所有模型的通用正确性保证。

## 构建模式

Android arm64，Release，NDK toolchain。源码正常全量构建要初始化proc/tokenizers子模块及Rust依赖；QAIRT bridge的某些版本会强制VLM/OpenCV，请读当前CMake，不把“text-only”当开关已生效。

```sh
cmake -S GenieX-qwen35/sdk -B build-sdk \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_ROOT/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-28 \
  -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release \
  -DGENIEX_PLUGIN_QAIRT=ON -DGENIEX_PLUGIN_LLAMA_CPP=OFF -DGENIEX_BENCHMARK=ON
cmake --build build-sdk --parallel 4
```

这是标准构建示例，不是说当前工作区已执行过这条全量构建。已测实验是SDK/core/bridge隔离构建：SDK关闭插件、单独core关闭VLM、bridge链接已有proc及VLM stub依赖；文本proc和Rust manager代码未变所以复用二进制，仅验证文本。可用可选`GENIEX_PREBUILT_PROC`与`GENIEX_PREBUILT_MODEL_MANAGER`，复用前核对ABI/接口/源码，不把旧lib与最新core任意混搭。不要提交测试环境中的绝对路径symlink、被移走的第三方.so或proprietary SDK。

## 部署目录

```text
bundle/
  model/                 context、genie_config、tokenizer、模板、LUT（如需要）
  runtime/bin/           geniex-bench / 用户应用
  runtime/lib/           libgeniex.so、插件与依赖
  runtime/lib/qairt/     libgeniex_core.so、proc等
  qairt/                 matching host libs、V73 stub/skel、扩展
  logs/                  运行证据
  SHA256SUMS
```

实际库布局取决于安装输出，设置`GENIEX_PLUGIN_PATH`为包含qairt插件目录的根。`LD_LIBRARY_PATH`包含应用/bridge/core/QAIRT共享库目录，`ADSP_LIBRARY_PATH`包含正确skel路径。这些应在初始化前设置。路径迁移后检查配置中的绝对context/tokenizer路径及软链接是否仍有效。

`run_android.sh`是Android端最小运行wrapper，要求显式传 MODEL_DIR/RUNTIME_DIR/QAIRT_LIB_DIR，不写thermal/sysfs、不中断其他进程、不默认绑CPU。按[demo索引](demos.md)运行。

## C++公共API

`assets/cpp/chat.cpp`是独立问题示例：init→create→reset→template→generate→free→destroy。显式贪心，no-think；每行reset，因此不是保留缓存的多轮聊天。错误/取消时生命周期要收尾；同一handle调用串行，回调不再次调用handle。UI/网络发送放其他队列，先复制UTF8数据，不保留SDK临时指针。

```sh
cmake -S assets/cpp -B build-chat \
  -DCMAKE_TOOLCHAIN_FILE="$ANDROID_NDK_ROOT/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-28 \
  -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release \
  -DGENIEX_SDK_DIR=/absolute/path/to/sdk
cmake --build build-chat --parallel 4
```

SDK目录需有`include/geniex.h`与`lib/libgeniex.so`。示例能编译不证明某个模型能正确答题。程序输入长度加max输出不得超过context有效上限。APK/JNI的FastRPC权限和库打包需另验，adb shell成功不表示APK成功。

交付前比较主机与板端SHA256，用`readelf -d`看NEEDED，用`/proc/PID/maps`看真实加载库；不要只看文件名。运行时库未附在此skill中。
