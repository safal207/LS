from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOTUS = ROOT / "LOTUS.md"
PRODUCT_LENS = ROOT / "docs" / "LOTUS_PRODUCT_LENS.md"
PR_TEMPLATE = ROOT / ".github" / "pull_request_template.md"


def test_pr_evidence_is_bound_to_exact_head() -> None:
    template = PR_TEMPLATE.read_text(encoding="utf-8")

    assert "Exact PR head SHA validated" in template
    assert "Validation command" in template
    assert "Validation was run or rerun after the most recent PR head change" in template
    assert "Evidence becomes stale" in template
    assert "apply to the exact SHA above" in template


def test_lotus_preserves_human_authority_in_both_languages() -> None:
    text = LOTUS.read_text(encoding="utf-8")
    english, russian = text.split("# Слой Лотоса", maxsplit=1)

    assert "has no ownership, approval, execution, delivery, or merge authority" in english
    assert "не имеет права собственности" in russian
    assert "одобрения" in russian
    assert "исполнения" in russian
    assert "доставки или merge" in russian


def test_english_and_russian_contracts_keep_the_seven_core_petals() -> None:
    text = LOTUS.read_text(encoding="utf-8")
    english, russian = text.split("# Слой Лотоса", maxsplit=1)

    english_petals = (
        "Clarity from complexity",
        "Evidence before confidence",
        "Causes before symptoms",
        "Memory without authority",
        "Consent before durable memory",
        "Repair before judgment",
        "Human authorship at the center",
    )
    russian_petals = (
        "Ясность из сложности",
        "Доказательства до уверенности",
        "Причины до симптомов",
        "Память без власти",
        "Согласие до долговременной памяти",
        "Исправление до осуждения",
        "Человек остаётся автором",
    )

    for phrase in english_petals:
        assert phrase in english
    for phrase in russian_petals:
        assert phrase in russian


def test_lotus_remains_guidance_not_runtime_authority() -> None:
    text = LOTUS.read_text(encoding="utf-8")

    assert "not a runtime component, a permission system, or an autonomous actor" in text
    assert "not a personality cult, hidden authority, mystical proof" in text
    assert "не runtime-компонент, не система разрешений и не автономный агент" in text
    assert "не культ личности, не скрытая власть, не мистическое доказательство" in text


def test_product_lens_is_bilingual_and_vendor_neutral() -> None:
    text = PRODUCT_LENS.read_text(encoding="utf-8")
    english, russian = text.split("# Продуктовая линза Лотоса", maxsplit=1)

    assert "SamCart" in english and "ClickFunnels" in english
    assert "SamCart" in russian and "ClickFunnels" in russian
    assert "vendor-neutral" in english
    assert "не зависит от вендора" in russian
    assert "not a runtime component" in english
    assert "не является runtime-компонентом" in russian


def test_product_lens_keeps_the_seven_product_petals() -> None:
    text = PRODUCT_LENS.read_text(encoding="utf-8")
    english, russian = text.split("# Продуктовая линза Лотоса", maxsplit=1)

    english_petals = (
        "Intent before conversion",
        "Continuity before friction",
        "Complementary value before upsell",
        "One click without hidden commitment",
        "Recovery before pressure",
        "Evidence before growth claims",
        "Human freedom at every stage",
    )
    russian_petals = (
        "Намерение до конверсии",
        "Непрерывность до трения",
        "Дополнительная ценность до допродажи",
        "Один клик без скрытого обязательства",
        "Восстановление до давления",
        "Доказательства до заявлений о росте",
        "Свобода человека на каждом этапе",
    )

    for phrase in english_petals:
        assert phrase in english
    for phrase in russian_petals:
        assert phrase in russian


def test_product_lens_preserves_choice_and_evidence() -> None:
    text = PRODUCT_LENS.read_text(encoding="utf-8")

    assert "Paid extras must not be preselected" in text
    assert "Vendor case studies and platform-wide percentages are context, not proof" in text
    assert "do not authorize a launch, price, payment, experiment, deployment, or merge" in text
    assert "Платные дополнения нельзя выбирать заранее" in text
    assert "не доказательством для этого продукта" in text
    assert "не дают права запускать продукт" in text
