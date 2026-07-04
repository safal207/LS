#!/usr/bin/env python3
"""Deterministic web-to-POS attribution reference runtime for Roby's V0."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, NamedTuple

TOKEN_RE = re.compile(r"^rv_[a-z0-9]{20}$")
RUN_ID_RE = re.compile(r"^ATTRRUN-[A-Z0-9-]{3,80}$")
EVENT_ID_RE = re.compile(r"^wev_[a-z0-9][a-z0-9_-]{2,63}$")
ORDER_ID_RE = re.compile(r"^ord_[a-z0-9][a-z0-9_-]{2,63}$")
MONEY_RE = re.compile(r"^(?:0|[1-9][0-9]*)(?:\.[0-9]{1,2})?$")
MONEY_QUANTUM = Decimal("0.01")
MEASUREMENT_PLAN_REF = "MPLAN-ROBYS-MENU-TO-VISIT-001"
ATTRIBUTION_WINDOW_HOURS = 24


class AttributionError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AttributionError(message)


def parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise AttributionError(f"{field} must be an RFC3339 date-time") from exc
    require(parsed.tzinfo is not None, f"{field} must include a timezone offset")
    return parsed


def parse_money(value: str, field: str) -> Decimal:
    require(isinstance(value, str), f"{field} must be a decimal string")
    require(
        bool(MONEY_RE.fullmatch(value)),
        f"{field} must use canonical non-negative decimal notation with at most 2 decimal places",
    )
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise AttributionError(f"{field} must be a valid decimal string") from exc
    require(amount.is_finite(), f"{field} must be finite")
    return amount


def money(value: Decimal) -> str:
    return str(value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP))


def canonical(item: dict[str, Any]) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def dedupe_by_id(
    items: Iterable[dict[str, Any]], id_field: str, label: str
) -> list[dict[str, Any]]:
    seen: dict[str, str] = {}
    unique: list[dict[str, Any]] = []
    for item in items:
        item_id = item[id_field]
        encoded = canonical(item)
        if item_id in seen:
            require(
                seen[item_id] == encoded,
                f"conflicting duplicate {label} id: {item_id}",
            )
            continue
        seen[item_id] = encoded
        unique.append(item)
    return unique


def validate_input(bundle: dict[str, Any]) -> None:
    required_top = {
        "schemaVersion",
        "runId",
        "mode",
        "productRef",
        "measurementPlanRef",
        "currency",
        "attributionWindowHours",
        "webEvents",
        "posOrders",
    }
    require(
        set(bundle) == required_top,
        "input contains missing or unknown top-level fields",
    )
    require(
        bundle["schemaVersion"] == "robys-attribution-input.v0",
        "unsupported schemaVersion",
    )
    require(
        isinstance(bundle["runId"], str)
        and bool(RUN_ID_RE.fullmatch(bundle["runId"])),
        "runId is invalid",
    )
    require(
        bundle["mode"] == "BASELINE",
        "V0 runtime only authorizes BASELINE mode",
    )
    require(
        bundle["productRef"] == "PROD-ROBYS-WEB",
        "productRef must be PROD-ROBYS-WEB",
    )
    require(
        bundle["measurementPlanRef"] == MEASUREMENT_PLAN_REF,
        "measurementPlanRef must match the approved readiness plan",
    )
    require(
        isinstance(bundle["currency"], str)
        and bool(re.fullmatch(r"[A-Z]{3}", bundle["currency"])),
        "currency must be ISO-4217 style",
    )
    require(
        isinstance(bundle["attributionWindowHours"], int),
        "attributionWindowHours must be an integer",
    )
    require(
        bundle["attributionWindowHours"] == ATTRIBUTION_WINDOW_HOURS,
        "attributionWindowHours must match the approved 24-hour readiness contract",
    )
    require(isinstance(bundle["webEvents"], list), "webEvents must be an array")
    require(isinstance(bundle["posOrders"], list), "posOrders must be an array")

    event_fields = {"eventId", "eventName", "occurredAt", "campaignToken"}
    for index, event in enumerate(bundle["webEvents"]):
        require(
            isinstance(event, dict) and set(event) == event_fields,
            f"webEvents[{index}] fields are invalid",
        )
        require(
            event["eventName"] == "visit_intent_created",
            f"webEvents[{index}].eventName is invalid",
        )
        require(
            isinstance(event["eventId"], str)
            and bool(EVENT_ID_RE.fullmatch(event["eventId"])),
            f"webEvents[{index}].eventId is invalid",
        )
        require(
            bool(TOKEN_RE.fullmatch(event["campaignToken"])),
            f"webEvents[{index}].campaignToken is invalid",
        )
        parse_datetime(event["occurredAt"], f"webEvents[{index}].occurredAt")

    order_fields = {
        "orderId",
        "orderedAt",
        "campaignToken",
        "grossRevenue",
        "currency",
        "variableCost",
    }
    for index, order in enumerate(bundle["posOrders"]):
        require(
            isinstance(order, dict) and set(order) == order_fields,
            f"posOrders[{index}] fields are invalid",
        )
        require(
            isinstance(order["orderId"], str)
            and bool(ORDER_ID_RE.fullmatch(order["orderId"])),
            f"posOrders[{index}].orderId is invalid",
        )
        require(
            bool(TOKEN_RE.fullmatch(order["campaignToken"])),
            f"posOrders[{index}].campaignToken is invalid",
        )
        parse_datetime(order["orderedAt"], f"posOrders[{index}].orderedAt")
        require(
            order["currency"] == bundle["currency"],
            f"posOrders[{index}].currency must match bundle currency",
        )
        parse_money(order["grossRevenue"], f"posOrders[{index}].grossRevenue")
        parse_money(order["variableCost"], f"posOrders[{index}].variableCost")


class EventRef(NamedTuple):
    event_id: str
    occurred_at: datetime
    campaign_token: str


def calculate_attribution(bundle: dict[str, Any]) -> dict[str, Any]:
    validate_input(bundle)
    unique_events_raw = dedupe_by_id(bundle["webEvents"], "eventId", "web event")
    unique_orders = dedupe_by_id(bundle["posOrders"], "orderId", "POS order")

    events_by_token: dict[str, list[EventRef]] = {}
    for event in unique_events_raw:
        ref = EventRef(
            event_id=event["eventId"],
            occurred_at=parse_datetime(event["occurredAt"], "occurredAt"),
            campaign_token=event["campaignToken"],
        )
        events_by_token.setdefault(ref.campaign_token, []).append(ref)
    for refs in events_by_token.values():
        refs.sort(key=lambda item: (item.occurred_at, item.event_id))

    ttl = timedelta(hours=ATTRIBUTION_WINDOW_HOURS)
    matched: list[dict[str, Any]] = []
    unmatched: list[str] = []
    expired: list[str] = []
    ambiguous: list[str] = []

    total_revenue = Decimal("0.00")
    total_variable_cost = Decimal("0.00")

    for order in sorted(unique_orders, key=lambda item: item["orderId"]):
        ordered_at = parse_datetime(order["orderedAt"], "orderedAt")
        token_events = events_by_token.get(order["campaignToken"], [])
        preceding = [event for event in token_events if event.occurred_at <= ordered_at]
        eligible = [
            event for event in preceding if ordered_at - event.occurred_at <= ttl
        ]

        if not eligible:
            if preceding:
                expired.append(order["orderId"])
            else:
                unmatched.append(order["orderId"])
            continue

        latest_time = max(event.occurred_at for event in eligible)
        latest = [event for event in eligible if event.occurred_at == latest_time]
        if len(latest) != 1:
            ambiguous.append(order["orderId"])
            continue

        event = latest[0]
        revenue = parse_money(order["grossRevenue"], "grossRevenue")
        variable_cost = parse_money(order["variableCost"], "variableCost")
        contribution = revenue - variable_cost
        total_revenue += revenue
        total_variable_cost += variable_cost
        matched.append(
            {
                "orderId": order["orderId"],
                "eventId": event.event_id,
                "campaignToken": order["campaignToken"],
                "lagSeconds": int(
                    (ordered_at - event.occurred_at).total_seconds()
                ),
                "grossRevenue": money(revenue),
                "variableCost": money(variable_cost),
                "grossContributionBeforeAcquisitionAndExperimentCosts": money(
                    contribution
                ),
            }
        )

    gross_contribution = total_revenue - total_variable_cost
    status = "AMBIGUOUS" if ambiguous else "ATTRIBUTION_CALCULATED"
    return {
        "schemaVersion": "robys-attribution-result.v0",
        "runId": bundle["runId"],
        "mode": bundle["mode"],
        "productRef": bundle["productRef"],
        "measurementPlanRef": bundle["measurementPlanRef"],
        "currency": bundle["currency"],
        "attributionWindowHours": ATTRIBUTION_WINDOW_HOURS,
        "status": status,
        "deduplication": {
            "inputWebEvents": len(bundle["webEvents"]),
            "uniqueWebEvents": len(unique_events_raw),
            "inputPosOrders": len(bundle["posOrders"]),
            "uniquePosOrders": len(unique_orders),
        },
        "matchedOrders": matched,
        "unmatchedOrderRefs": sorted(unmatched),
        "expiredOrderRefs": sorted(expired),
        "ambiguousOrderRefs": sorted(ambiguous),
        "totals": {
            "attributableOrders": len(matched),
            "attributableGrossRevenue": money(total_revenue),
            "attributableVariableCosts": money(total_variable_cost),
            "grossContributionBeforeAcquisitionAndExperimentCosts": money(
                gross_contribution
            ),
        },
        "profitDecision": {
            "ready": False,
            "reason": (
                "Acquisition and experiment costs are not part of this attribution "
                "runtime; a separate Profit Traceability decision is required."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        bundle = json.loads(args.input.read_text(encoding="utf-8"))
        result = calculate_attribution(bundle)
    except (OSError, json.JSONDecodeError, AttributionError) as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
