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


def test_product_lens_keeps_the_seven_product_obligations() -> None:
    text = PRODUCT_LENS.read_text(encoding="utf-8")
    english, russian = text.split("# Продуктовая линза Лотоса", maxsplit=1)

    english_obligations = (
        "State the user goal and the business goal separately",
        "Preserve context, progress, selected items, language, price, and recovery state",
        "relevant, clearly optional, separately priced, and easy to decline",
        "show the exact item, amount, currency, recurring terms, and next state",
        "bounded frequency, honest wording, opt-out, privacy, and a stop condition",
        "refunds, churn, complaints, completion, retention, repeat value, and harm signals",
        "a visible no, a comprehensible total, a route back",
    )
    russian_obligations = (
        "Отдельно фиксируй цель пользователя и цель бизнеса",
        "Сохраняй контекст, прогресс, выбранные позиции, язык, цену и состояние восстановления",
        "релевантными, явно необязательными, отдельно оценёнными и простыми для отказа",
        "точный товар, сумму, валюту, условия регулярных списаний или продления и следующий шаг",
        "ограниченной частотой, честным текстом, opt-out, приватностью и условием остановки",
        "возвратами, churn, жалобами, завершением, retention, повторной ценностью и сигналами вреда",
        "видимый отказ, понятный total, путь назад",
    )

    for phrase in english_obligations:
        assert phrase in english
    for phrase in russian_obligations:
        assert phrase in russian


def test_product_lens_preserves_choice_and_evidence() -> None:
    text = PRODUCT_LENS.read_text(encoding="utf-8")

    assert "Paid extras must not be preselected" in text
    assert "Vendor case studies and platform-wide percentages are context, not proof" in text
    assert "causal, correlational, simulated, or anecdotal" in text
    assert "- refund path;" in text
    assert "- recovery path;" in text
    assert "for subscription stages, a separate cancellation or stop-renewal path" in text
    assert "missing cancellation or stop-renewal paths" in text
    assert "do not authorize a launch, price, payment, experiment, deployment, or merge" in text
    assert "Платные дополнения нельзя выбирать заранее" in text
    assert "не доказательством для этого продукта" in text
    assert "основанный на единичных историях, отзывах либо свидетельствах" in text
    assert "отдельный путь возврата средств" in text
    assert "отдельный путь восстановления" in text
    assert "Для этапов с подпиской отдельно фиксируй путь отмены или остановки автопродления" in text
    assert "отсутствие пути отмены или остановки автопродления" in text
    assert "не дают права запускать продукт" in text


def test_product_pr_checklist_requires_counter_metrics_and_cancellation() -> None:
    template = PR_TEMPLATE.read_text(encoding="utf-8")

    assert "user goal and business goal are both explicit" in template
    assert "Price, recurring terms, decline path, cancellation or stop-renewal path" in template
    assert "refund path, and recovery path are visible before commitment" in template
    assert "relevant, optional, and not preselected" in template
    assert "refunds, churn, complaints, completion, retention, repeat value, and harm signals" in template
    assert "No false urgency, obstructed decline, surprise payment" in template
