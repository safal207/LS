from modules.llm.query_rewriter import REWRITE_PROMPT, rewrite_query


def test_rewrite_query_expands_short_queries():
    original = "502 error"

    def _mock_handler(prompt: str) -> str:
        assert original in prompt
        assert REWRITE_PROMPT.splitlines()[0] in prompt
        return "HTTP 502 Bad Gateway error from reverse proxy when upstream service is unavailable"

    rewritten = rewrite_query(original, llm_handler=_mock_handler)

    assert len(rewritten) > len(original)
    assert len(rewritten.split()) > len(original.split())


def test_rewrite_query_fallback_on_llm_error():
    original = "database timeout"

    def _broken_handler(prompt: str) -> str:
        raise RuntimeError("llm unavailable")

    assert rewrite_query(original, llm_handler=_broken_handler) == original


def test_rewrite_query_empty_or_whitespace():
    assert rewrite_query("") == ""
    assert rewrite_query("   ") == "   "
