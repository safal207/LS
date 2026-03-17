#include <cctype>
#include <cstring>

namespace {
const char* find_value_start(const char* frame, const char* key_name) {
    const char* p = std::strstr(frame, key_name);
    if (!p) return nullptr;
    p += std::strlen(key_name);
    while (*p && *p != ':') ++p;
    if (*p != ':') return nullptr;
    ++p;
    while (*p && std::isspace(static_cast<unsigned char>(*p))) ++p;
    if (*p != '"') return nullptr;
    return p + 1;
}
}

extern "C" int extract_ollama_token_cpp(
    const char* frame,
    int has_messages,
    char* out,
    int out_cap,
    int* out_len
) {
    if (!frame || !out || out_cap <= 0 || !out_len) {
        return -1;
    }

    const char* value = nullptr;
    if (has_messages) {
        const char* msg = std::strstr(frame, "\"message\"");
        if (!msg) {
            *out_len = 0;
            out[0] = '\0';
            return 0;
        }
        // Fast-path limitation: this is a substring search from the `"message"` anchor
        // and not a full JSON structural parser. If ambiguous/escaped content is detected,
        // we return 0 and let Rust/Python JSON parser handle the frame safely.
        value = find_value_start(msg, "\"content\"");
    } else {
        value = find_value_start(frame, "\"response\"");
    }

    if (!value) {
        *out_len = 0;
        out[0] = '\0';
        return 0;
    }

    int i = 0;
    const char* p = value;
    while (*p) {
        if (*p == '\\' && *(p + 1) != '\0') {
            // escaped sequences (e.g. \u041f) are delegated to Python/Rust JSON parser
            return 0;
        }
        if (*p == '"') {
            break;
        }
        if (i + 1 >= out_cap) {
            return -2;
        }
        out[i++] = *p;
        ++p;
    }

    out[i] = '\0';
    *out_len = i;
    return 1;
}
