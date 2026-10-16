// Semantic demonstration: uint16 logits with one common positive scale.
// Not valid for raw FP16, per-axis encodings or constrained sampling.
#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <random>
#include <stdexcept>
#include <vector>
#if defined(__aarch64__)
#include <arm_neon.h>
#endif

size_t encoded_argmax(const uint16_t* p, size_t n) {
    if (!n) throw std::invalid_argument("argmax requires a nonempty vector");
#if defined(__aarch64__)
    uint16x8_t maximums = vdupq_n_u16(0);
    size_t i = 0;
    for (; i + 8 <= n; i += 8) maximums = vmaxq_u16(maximums, vld1q_u16(p + i));
    uint16_t maximum = vmaxvq_u16(maximums);
    for (; i < n; ++i) maximum = std::max(maximum, p[i]);
    for (i = 0; i + 8 <= n; i += 8) {
        if (vmaxvq_u16(vceqq_u16(vld1q_u16(p + i), vdupq_n_u16(maximum)))) {
            for (size_t j = i; j < i + 8; ++j) if (p[j] == maximum) return j;
        }
    }
    for (; i < n; ++i) if (p[i] == maximum) return i;
    throw std::logic_error("maximum not found");
#else
    return static_cast<size_t>(std::max_element(p, p + n) - p);
#endif
}

int main() {
    std::mt19937 generator(43);
    for (size_t n : {size_t(1), size_t(7), size_t(8), size_t(9), size_t(248320)}) {
        std::vector<uint16_t> values(n);
        for (auto& v : values) v = static_cast<uint16_t>(generator());
        values[0] = 65535;
        values[n - 1] = 65535;
        const auto reference = static_cast<size_t>(std::max_element(values.begin(), values.end()) - values.begin());
        if (encoded_argmax(values.data(), values.size()) != reference) return 1;
        std::fill(values.begin(), values.end(), 0);
        if (encoded_argmax(values.data(), values.size()) != 0) return 1;
        for (auto& v : values) v = static_cast<uint16_t>(generator());
        const auto random_reference = static_cast<size_t>(std::max_element(values.begin(), values.end()) - values.begin());
        if (encoded_argmax(values.data(), values.size()) != random_reference) return 1;
    }
    bool rejected_empty = false;
    try { encoded_argmax(nullptr, 0); } catch (const std::invalid_argument&) { rejected_empty = true; }
    if (!rejected_empty) return 1;
#if defined(__aarch64__)
    std::puts("PASS: NEON argmax, first tie, tails, zeros, empty rejection and full vocabulary");
#else
    std::puts("PASS: scalar fallback; ARM NEON requires an aarch64 run");
#endif
}
