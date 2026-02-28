import importlib


def test_amygdala_module_import_and_constructor_signature() -> None:
    module = importlib.import_module("codex.causal_memory.amygdala")
    amygdala = module.Amygdala(user_id="regression", persist_state=False)
    assert amygdala.user_id == "regression"
