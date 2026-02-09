from python.modules.web4bio.models import EpigenesisModel, MorphogenesisModel, TeleogenesisModel


def test_bio_models_import() -> None:
    assert "role_shift" in MorphogenesisModel().signals
    assert "observability" in EpigenesisModel().signals
    assert "human_support" in TeleogenesisModel().goals
