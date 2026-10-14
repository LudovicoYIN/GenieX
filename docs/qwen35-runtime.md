# Qwen3.5 optimized QAIRT runtime

This branch pins the matching Qwen3.5 stateful QAIRT plugin in the LudovicoYIN fork. Clone recursively to include the implementation:

```sh
git clone --branch feat/qwen35-runtime-speed-20261014 --recurse-submodules https://github.com/LudovicoYIN/GenieX.git
```

See [plugin runtime notes](../third-party/geniex-qairt/docs/qwen35-runtime.md) for numerical policies, scheduling switches, affinity, benchmark conditions and validation limits. Model binaries and proprietary QAIRT runtime libraries must be supplied separately.

The SDK can optionally reuse a compatible unchanged Rust model-manager static library with `-DGENIEX_PREBUILT_MODEL_MANAGER=/path/to/libgeniex_model.a`; leave unset for normal Cargo source builds. The speed measurements used unchanged text processor and model-manager code; only the text runtime was validated.

## Older text-reference fullgraph benchmark

On the same optimized runtime and CPU affinity, using2048 input / actual512 output tokens, explicit greedy, seed43, no warmup and three runs per mode:

| Model | Ordinary decode tok/s | Deferred decode tok/s | Ordinary input / TTFT tok/s | Deferred input / TTFT tok/s |
|---|---:|---:|---:|---:|
| Older text-reference fullgraph | 30.81 | 31.17 | 879 | 882 |
| Direct-stock fullgraph, previous final-runtime runs | 37.26 (one run) | 37.57 (three runs) | 1761 (one run) | 1742 (three runs) |

The older graph execution path takes31.54ms/token versus32.08ms total in deferred mode; encoded greedy sampling takes0.030ms/token. Model graph execution now dominates. This random-token throughput benchmark does not revalidate the older model PPL or question-answer accuracy. Each model retains its own positional-encoding configuration. Per-run data and artifact hashes are in [older fullgraph results](qwen35-old-fullgraph-results.json).
