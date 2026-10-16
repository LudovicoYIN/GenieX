#!/system/bin/sh
# Set paths and model-specific flags explicitly before calling. No sysfs writes.
set -eu
: "${MODEL_DIR:?Set absolute Android MODEL_DIR}"
: "${RUNTIME_DIR:?Set absolute Android RUNTIME_DIR}"
: "${QAIRT_LIB_DIR:?Set matching Android QAIRT_LIB_DIR}"
case "$MODEL_DIR:$RUNTIME_DIR:$QAIRT_LIB_DIR" in /*:/*:/*) ;; *) echo 'Paths must be absolute' >&2; exit 2 ;; esac
[ -f "$MODEL_DIR/tokenizer.json" ] || { echo 'tokenizer.json missing' >&2; exit 2; }
[ -x "$RUNTIME_DIR/bin/geniex-bench" ] || { echo 'geniex-bench missing or not executable' >&2; exit 2; }
[ -d "$QAIRT_LIB_DIR" ] || { echo 'QAIRT directory missing' >&2; exit 2; }
export LD_LIBRARY_PATH="$RUNTIME_DIR/lib:$RUNTIME_DIR/lib/qairt:$QAIRT_LIB_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export ADSP_LIBRARY_PATH="$QAIRT_LIB_DIR${ADSP_LIBRARY_PATH:+:$ADSP_LIBRARY_PATH}"
export GENIEX_QAIRT_LIB="$QAIRT_LIB_DIR"
export GENIEX_PLUGIN_PATH="$RUNTIME_DIR/lib"
export GENIEX_QNN_LOG_WARN=1
cd "$MODEL_DIR"
# Caller supplies affinity and optional feedback/numerical policies.
if [ -n "${MAIN_CPU_MASK:-}" ]; then
    exec taskset "$MAIN_CPU_MASK" "$RUNTIME_DIR/bin/geniex-bench" --plugin qairt --device npu -m ./tokenizer.json --no-warmup --temperature -1 --seed 43 "$@"
fi
exec "$RUNTIME_DIR/bin/geniex-bench" --plugin qairt --device npu -m ./tokenizer.json --no-warmup --temperature -1 --seed 43 "$@"
