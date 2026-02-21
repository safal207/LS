from modules.llm import qwen_handler


def test_replay_thread_ui_renders_lri_fields(monkeypatch):
    monkeypatch.setattr(
        qwen_handler,
        "replay_thread",
        lambda thread_id: [
            {
                "ts": "2026-02-21T10:00:00Z",
                "cause": "borrow checker conflict in replay path",
                "solution": "use owned buffer to stabilize lifetime",
                "ltp_trace": {"drift": 0.08},
                "lce": {"qos": {"coherence": 0.92}},
                "lri_core": {
                    "emotional_drift": 0.12,
                    "stabilizer": "active",
                    "resonance_map": {"focus": 0.88},
                    "invariants": ["non_reductive", "consent_first"],
                },
            }
        ],
    )

    rendered = qwen_handler.replay_thread_ui("thread-123")
    assert "Replay тред **thread-123**" in rendered
    assert "emo_drift:0.12" in rendered
    assert "stabilizer=active" in rendered
    assert "resonance.focus=0.88" in rendered
    assert "non_reductive, consent_first" in rendered


def test_handle_replay_command_returns_none_for_regular_text():
    handler = qwen_handler.QwenHandler.__new__(qwen_handler.QwenHandler)
    assert handler.handle_replay_command("just answer normally") is None


def test_handle_replay_command_requires_thread_token(monkeypatch):
    handler = qwen_handler.QwenHandler.__new__(qwen_handler.QwenHandler)
    monkeypatch.setattr(qwen_handler, "replay_thread_ui", lambda tid: f"replay:{tid}")

    assert handler.handle_replay_command("replay please now") is None
    assert handler.handle_replay_command("replay thread-123") == "replay:thread-123"
