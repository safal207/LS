from __future__ import annotations

from .schemas import EfficiencyIn, EfficiencyOut


def calculate_economic_efficiency(data: EfficiencyIn) -> EfficiencyOut:
    payout_per_task = data.avg_reward_budget * data.avg_impact_score * data.avg_quality_score
    net_saving_per_task = data.baseline_human_cost_per_task - payout_per_task

    gross_monthly_saving = data.tasks_per_month * net_saving_per_task
    automation_uplift_value = gross_monthly_saving * data.automation_uplift_pct
    monthly_net_effect = gross_monthly_saving + automation_uplift_value - data.platform_opex_monthly

    if data.platform_opex_monthly == 0:
        roi_monthly = None
    else:
        roi_monthly = monthly_net_effect / data.platform_opex_monthly

    if monthly_net_effect <= 0:
        payback_months = None
    else:
        payback_months = data.platform_opex_monthly / monthly_net_effect if data.platform_opex_monthly else 0.0

    return EfficiencyOut(
        payout_per_task=payout_per_task,
        net_saving_per_task=net_saving_per_task,
        gross_monthly_saving=gross_monthly_saving,
        automation_uplift_value=automation_uplift_value,
        monthly_net_effect=monthly_net_effect,
        roi_monthly=roi_monthly,
        payback_months=payback_months,
    )
