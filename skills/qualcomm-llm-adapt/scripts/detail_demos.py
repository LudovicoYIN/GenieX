#!/usr/bin/env python3
"""Small executable semantic examples, not QNN kernels or a model evaluator."""
import argparse
import math
import struct
from concurrent.futures import ThreadPoolExecutor


def encode(x, scale, offset, bits=16, nearest=True):
    if scale <= 0:
        raise ValueError('scale must be positive')
    v = min((1 << bits) - 1, max(0.0, x / scale - offset))
    return math.floor(v + 0.5) if nearest else int(v)


def decode(q, scale, offset):
    return scale * (q + offset)


def quant():
    q, source_scale, source_offset = 32031, 1e-5, -32021
    value = decode(q, source_scale, source_offset)
    target = encode(value, 2e-5, -100)
    assert target == 105
    assert abs(decode(target, 2e-5, -100) - value) < 1e-12
    half_bits = struct.unpack('<H', struct.pack('<e', value))[0]
    assert half_bits != q
    exact_zero = min(65535, max(0, -(-32309)))
    assert exact_zero == 32309 and decode(exact_zero, 0.01, -32309) == 0
    assert decode(0, 0.01, -32309) != 0
    # A constructed floating intermediate illustrates truncation, not an actual QNN scale.
    perturbed = math.nextafter(float(exact_zero), 0)
    assert int(perturbed) == 32308
    print(f'quant: UF16 {q} -> real {value:.7f} -> new UF16 {target}; FP16 bits {half_bits}; zero={exact_zero}')


def embedding():
    table = struct.pack('<6H', 101, 102, 103, 104, 105, 106)
    vocab, hidden, scale, offset = 2, 3, 0.1, -100
    def lookup(token):
        if not 0 <= token < vocab:
            raise ValueError('token ID out of range')
        codes = struct.unpack_from('<3H', table, token * hidden * 2)
        return [decode(q, scale, offset) for q in codes]
    assert all(math.isclose(a, b) for a, b in zip(lookup(1), [0.4, 0.5, 0.6]))
    try:
        lookup(2)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid token accepted')
    print('embedding: token1 row restored as', lookup(1), '; explicit pad-token selects its own row')


def state():
    # Scalar recurrence only illustrates a persistent state, not GatedDeltaNet math.
    kv, recurrent = [], 0.0
    for token in [1.0, 2.0, 3.0]:
        kv.append(token)
        recurrent = 0.5 * recurrent + token
    assert kv == [1, 2, 3] and recurrent == 4.25
    kv.clear()
    recurrent = 0.0
    assert kv == [] and recurrent == 0
    print('state: toy KV appends history; recurrent accumulates into one state; reset clears both')


def conv():
    history, ar, valid, width, planes = 3, 128, 37, 2, 2
    output = []
    for plane in range(planes):
        rows = [[plane * 1000 + i * width + j for j in range(width)] for i in range(history + ar)]
        output.extend(x for row in rows for x in row)
    stride = (history + ar) * width
    direct = []
    for plane in range(planes):
        start = plane * stride + valid * width
        direct.extend(output[start:start + history * width])
    gathered = []
    for plane in range(planes):
        for row in range(valid, valid + history):
            for col in range(width):
                gathered.append(output[plane * stride + row * width + col])
    assert direct == gathered
    assert direct[:6] == [74, 75, 76, 77, 78, 79]
    assert output[stride - history * width:stride] != direct[:6]
    ar1 = [[10], [20], [30], [40]]
    assert ar1[1:4] == [[20], [30], [40]]
    print('conv: valid37/AR128 copies rows37..39 in every plane; final padded rows are different; AR1 copies rows1..3')


def layout():
    # An illustrative row-major / column-major permutation, NOT QNN HMX layout.
    logical = [[10, 11, 12], [20, 21, 22]]
    flat = [x for row in logical for x in row]
    columns = [logical[row][col] for col in range(3) for row in range(2)]
    assert flat != columns
    recovered = [[columns[col * 2 + row] for col in range(3)] for row in range(2)]
    assert recovered == logical
    print('layout: same logical shape, different storage:', flat, columns, '; QNN HMX needs its real layout contract')


def rope():
    dim, theta, position = 64, 1e7, 5
    half_freq = [theta ** (-2 * i / dim) for i in range(dim // 2)]
    cos_half = [math.cos(position * f) for f in half_freq]
    concat = cos_half + cos_half
    assert len(concat) == dim and concat[:32] == concat[32:]
    wrong = [math.cos(position * theta ** (-i / dim)) for i in range(dim)]
    assert concat != wrong
    scale, offset, value = 0.01, -100, 0.006
    nearest = encode(value, scale, offset, nearest=True)
    truncate = encode(value, scale, offset, nearest=False)
    assert (nearest, truncate) == (101, 100)
    print('rope: 32 frequencies repeated twice; example nearest=101 vs official-style truncate=100; policy is model-specific')


def mask():
    rows, valid, past, width, new_base = 4, 3, 2, 8, 4
    scale, offset = 0.01, -100
    hidden, visible = encode(-1e9, scale, offset), encode(0, scale, offset)
    floats = [[-1e9] * width for _ in range(rows)]
    direct = [[hidden] * width for _ in range(rows)]
    for row in range(valid):
        for col in range(past):
            floats[row][col] = 0
            direct[row][col] = visible
        for col in range(new_base, new_base + row + 1):
            floats[row][col] = 0
            direct[row][col] = visible
    reference = [[encode(x, scale, offset) for x in row] for row in floats]
    assert direct == reference
    assert all(x == hidden for x in direct[-1])
    assert direct[0][new_base] == visible and direct[0][new_base + 1] == hidden
    print('mask: direct encoded input exactly equals float->quant example; padding row remains masked:', direct)


def greedy():
    codes = [7, 300, 9, 300, 2]
    values = [decode(q, 0.01, -100) for q in codes]
    index = lambda xs: max(range(len(xs)), key=xs.__getitem__)
    assert index(codes) == index(values) == 1
    # Per-axis scales break global encoded order.
    assert index([100, 50]) != index([100 * 0.01, 50 * 1.0])
    half_codes = [struct.unpack('<H', struct.pack('<e', x))[0] for x in [-1.0, 0.5]]
    assert index(half_codes) != index([-1.0, 0.5])
    print('greedy: shared positive scale preserves argmax and earliest tie; axis scales and raw FP16 do not')


def schedule():
    kv, recurrent = [None] * 2, [None] * 6
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = [pool.submit(kv.__setitem__, i, i + 10) for i in range(2)]
        def copy_slice(start):
            for i in range(start, len(recurrent), 3):
                recurrent[i] = i + 100
        jobs += [pool.submit(copy_slice, slice_index) for slice_index in range(3)]
        # Independent sampling may run here; every next state read waits first.
        token = max(range(3), key=[1, 9, 2].__getitem__)
        for job in jobs:
            job.result()
        assert kv == [10, 11] and recurrent == list(range(100, 106)) and token == 1
    drained = []
    def fail():
        raise RuntimeError('demo execute failure')
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(drained.append, 'finished')
            pool.submit(fail).result()
    except RuntimeError:
        assert drained == ['finished'] and pending.done()
    print('schedule: disjoint writes + barrier before reuse; executor exit drains jobs even on error')


def tail():
    def route(length, ar1_tail=True, all_logits=False):
        full, remainder = divmod(length, 128)
        widths = [128] * full
        if remainder:
            widths += [1 if remainder == 1 and ar1_tail and not all_logits else 128]
        return widths
    assert route(128) == [128]
    assert route(129) == [128, 1]
    assert route(256) == [128, 128]
    assert route(129, all_logits=True) == [128, 128]
    print('tail: 129 normal path uses AR128+AR1 and samples AR1 logits; all-logits path keeps AR128')


def metrics():
    actual, padded, ttft, generated, decode_seconds = 37, 128, 0.1, 512, 16.4
    effective, padded_rate = actual / ttft, padded / ttft
    assert effective == 370 and padded_rate == 1280
    targets = 10 * (4096 - 1)
    assert targets == 40950
    print(f'metrics: actual input {effective:.0f} tok/s vs padded {padded_rate:.0f}; decode {generated/decode_seconds:.2f}; PPL targets={targets}')


def fullgraph():
    def accepted(shards, integer_input, logits_output, hidden, vocab):
        integrated = shards == 1 and integer_input and logits_output
        return vocab > 0 and (hidden > 0 or integrated)
    assert accepted(1, True, True, 0, 248320)
    assert not accepted(2, True, True, 0, 248320)
    assert not accepted(1, True, True, 0, 0)
    print('fullgraph: integer token->logits one shard may omit hidden boundary; multi-shard and unknown vocab still fail')


DEMOS = {f.__name__: f for f in [quant, embedding, state, conv, layout, rope, mask, greedy, schedule, tail, metrics, fullgraph]}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('demo', choices=['all', *DEMOS])
    args = parser.parse_args()
    for function in DEMOS.values() if args.demo == 'all' else [DEMOS[args.demo]]:
        function()
