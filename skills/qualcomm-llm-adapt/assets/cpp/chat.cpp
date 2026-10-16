#include "geniex.h"

#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>

static void check(int32_t code, const char* operation) {
    if (code != GENIEX_SUCCESS)
        throw std::runtime_error(std::string(operation) + " failed: " + std::to_string(code));
}

static void log_message(geniex_LogLevel level, const char* message) {
    if (level >= GENIEX_LOG_LEVEL_WARN && message) std::fprintf(stderr, "%s\n", message);
}

static bool print_token(const char* token, void*) {
    // Avoid flushing stdout on every token.
    if (token) std::fputs(token, stdout);
    return true;
}

struct Runtime {
    Runtime() {
        check(geniex_set_log(log_message), "set_log");
        check(geniex_init(), "init");
    }
    ~Runtime() { geniex_deinit(); }
};

class Session {
public:
    explicit Session(const char* tokenizer) {
        geniex_LlmCreateInput input{};
        input.model_path = tokenizer;
        input.plugin_id = "qairt";
        input.device_id = "NPU";
        input.config.power_mode = GENIEX_POWER_MODE_BURST;
        check(geniex_llm_create(&input, &handle_), "llm_create");
    }
    ~Session() { if (handle_) geniex_llm_destroy(handle_); }
    Session(const Session&) = delete;
    Session& operator=(const Session&) = delete;

    void reply(const std::string& prompt, int max_tokens) {
        // Each invocation is an independent question with a fresh KV/state cache.
        check(geniex_llm_reset(handle_), "llm_reset");
        geniex_LlmChatMessage message{};
        message.role = "user";
        message.content = prompt.c_str();
        geniex_LlmApplyChatTemplateInput template_input{};
        template_input.messages = &message;
        template_input.message_count = 1;
        template_input.enable_thinking = false;
        template_input.add_generation_prompt = true;
        geniex_LlmApplyChatTemplateOutput formatted{};
        int32_t code = geniex_llm_apply_chat_template(handle_, &template_input, &formatted);
        std::unique_ptr<char, decltype(&geniex_free)> text(formatted.formatted_text, geniex_free);
        check(code, "apply_chat_template");

        geniex_SamplerConfig sampler{};
        sampler.temperature = -1; // Explicit greedy for the tested GenieX plugin semantics.
        sampler.top_p = 1;
        sampler.repetition_penalty = 1;
        sampler.seed = 42;
        geniex_GenerationConfig config{};
        config.max_tokens = max_tokens;
        config.sampler_config = &sampler;
        geniex_LlmGenerateInput input{};
        input.prompt_utf8 = text.get();
        input.config = &config;
        input.on_token = print_token;
        geniex_LlmGenerateOutput output{};
        code = geniex_llm_generate(handle_, &input, &output);
        std::unique_ptr<char, decltype(&geniex_free)> full_text(output.full_text, geniex_free);
        check(code, "llm_generate");
        std::puts("");
        std::fflush(stdout);
        const auto& p = output.profile_data;
        std::fprintf(stderr, "prompt=%lld generated=%lld TTFT=%.1f ms decode=%.3f tok/s stop=%s\n",
            static_cast<long long>(p.prompt_tokens), static_cast<long long>(p.generated_tokens),
            p.ttft / 1000.0, p.decoding_speed, p.stop_reason ? p.stop_reason : "unknown");
    }

private:
    geniex_LLM* handle_ = nullptr;
};

int main(int argc, char** argv) {
    try {
        if (argc < 2 || argc > 4) {
            std::fprintf(stderr, "Usage: qwen35-chat model/tokenizer.json [prompt] [max_tokens]\n");
            return 2;
        }
        int max_tokens = 128;
        if (argc == 4) {
            size_t consumed = 0;
            const std::string value(argv[3]);
            max_tokens = std::stoi(value, &consumed);
            if (consumed != value.size() || max_tokens < 1 || max_tokens > 4096)
                throw std::runtime_error("max_tokens must be an integer in [1,4096]");
        }
        Runtime runtime;
        Session session(argv[1]);
        if (argc >= 3) session.reply(argv[2], max_tokens);
        else {
            std::string prompt;
            while (std::getline(std::cin, prompt)) {
                if (!prompt.empty()) session.reply(prompt, max_tokens);
            }
        }
        return 0;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "%s\n", error.what());
        return 1;
    }
}
