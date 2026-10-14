# Qwen3.5 optimized QAIRT runtime

This branch pins the matching Qwen3.5 stateful QAIRT plugin in the LudovicoYIN fork. Clone recursively to include the implementation:

```sh
git clone --branch feat/qwen35-runtime-speed-20261014 --recurse-submodules https://github.com/LudovicoYIN/GenieX.git
```

See [plugin runtime notes](../third-party/geniex-qairt/docs/qwen35-runtime.md) for numerical policies, scheduling switches, affinity, benchmark conditions and validation limits. Model binaries and proprietary QAIRT runtime libraries must be supplied separately.

The SDK can optionally reuse a compatible unchanged Rust model-manager static library with `-DGENIEX_PREBUILT_MODEL_MANAGER=/path/to/libgeniex_model.a`; leave unset for normal Cargo source builds. The speed measurements used unchanged text processor and model-manager code; only the text runtime was validated.
