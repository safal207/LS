from modules.llm.query_rewriter import REWRITE_PROMPT, rewrite_query


def test_rewrite_query_expands_short_queries():
    original = "502 error"

    def _mock_handler(prompt: str) -> str:
        assert original in prompt
        assert REWRITE_PROMPT.splitlines()[0] in prompt
        return "HTTP 502 Bad Gateway error from reverse proxy when upstream service is unavailable"

    rewritten = rewrite_query(original, llm_handler=_mock_handler)

    assert len(rewritten) > len(original)
    assert len(rewritten.split()) >= len(original.split()) + 2
    assert "bad gateway" in rewritten.lower()
    assert "upstream" in rewritten.lower()
    assert "error" in rewritten.lower()


def test_rewrite_query_fallback_on_llm_error():
    original = "database timeout"

    def _broken_handler(prompt: str) -> str:
        raise RuntimeError("llm unavailable")

    assert rewrite_query(original, llm_handler=_broken_handler) == original


def test_rewrite_query_empty_or_whitespace():
    assert rewrite_query("") == ""
    assert rewrite_query("   ") == "   "


def test_rewrite_query_truncates_too_long():
    long_input = "a" * 500

    def _mock_long(prompt: str) -> str:
        _ = prompt
        return "very " + "long " * 100 + "query"

    result = rewrite_query(long_input, _mock_long)

    assert result == long_input
