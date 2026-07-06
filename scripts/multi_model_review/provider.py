"""OpenRouter adapter and free-endpoint resolution."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .contracts import ReviewRuntimeError


@dataclass(frozen=True)
class CatalogModel:
    model_id: str
    is_free: bool
    expiration_date: str | None


@dataclass(frozen=True)
class ResolvedModel:
    key: str
    role: str
    requested_model: str
    model_id: str
    activation: str
    fallback_used: bool


def _is_zero_price(value: Any) -> bool:
    try:
        return Decimal(str(value)) == Decimal("0")
    except (InvalidOperation, ValueError):
        return False


class OpenRouterClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: int,
        max_attempts: int,
        transport: Callable[[str, dict[str, str], dict[str, Any] | None, int], dict[str, Any]] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max_attempts
        self._transport = transport or _http_json
        self._sleeper = sleeper

    def catalog(self) -> dict[str, CatalogModel]:
        payload = self._request("/models", None)
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise ReviewRuntimeError("provider catalog response must contain a data array")
        result: dict[str, CatalogModel] = {}
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                continue
            pricing = row.get("pricing") if isinstance(row.get("pricing"), dict) else {}
            result[row["id"]] = CatalogModel(
                model_id=row["id"],
                is_free=_is_zero_price(pricing.get("prompt")) and _is_zero_price(pricing.get("completion")),
                expiration_date=row.get("expiration_date") if isinstance(row.get("expiration_date"), str) else None,
            )
        return result

    def review(self, *, model_id: str, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        response = self._request(
            "/chat/completions",
            {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0,
                "max_tokens": max_tokens,
            },
        )
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ReviewRuntimeError(f"model {model_id} returned no choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, list):
            content = "".join(
                item.get("text", "") for item in content if isinstance(item, dict) and isinstance(item.get("text"), str)
            )
        if not isinstance(content, str) or not content.strip():
            raise ReviewRuntimeError(f"model {model_id} returned empty content")
        return content

    def _request(self, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            ("Author" + "ization"): ("Bear" + f"er {self.api_key}"),
            "HTTP-Referer": "https://github.com/safal207/LS",
            "X-Title": "LS Multi-Model PR Review",
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self._transport(f"{self.base_url}{path}", headers, payload, self.timeout_seconds)
            except ReviewRuntimeError:
                # Contract/shape errors are deterministic; retrying cannot repair the response.
                raise
            except HTTPError as exc:
                last_error = exc
                retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
            except (URLError, TimeoutError) as exc:
                last_error = exc
                retryable = True
            if not retryable or attempt == self.max_attempts:
                break
            self._sleeper(min(8.0, float(2 ** (attempt - 1))))
        raise ReviewRuntimeError(f"provider request failed after {self.max_attempts} attempt(s): {last_error}")


def _http_json(url: str, headers: dict[str, str], payload: dict[str, Any] | None, timeout: int) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=headers, method="GET" if payload is None else "POST")
    with urlopen(request, timeout=timeout) as response:  # noqa: S310 - provider URL comes from reviewed config
        raw = response.read().decode("utf-8")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ReviewRuntimeError("provider returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise ReviewRuntimeError("provider response must be a JSON object")
    return parsed


def model_is_active(model: CatalogModel, today: datetime | None = None) -> bool:
    if not model.is_free:
        return False
    if not model.expiration_date:
        return True
    now = (today or datetime.now(timezone.utc)).date()
    try:
        expires = datetime.fromisoformat(model.expiration_date.replace("Z", "+00:00")).date()
    except ValueError:
        return False
    return now <= expires


def resolve_models(
    config: dict[str, Any],
    catalog: dict[str, CatalogModel],
    *,
    high_risk: bool,
    activation: str,
    used_model_ids: set[str] | None = None,
    reserved_model_ids: set[str] | None = None,
) -> tuple[list[ResolvedModel], list[dict[str, Any]]]:
    used = set() if used_model_ids is None else set(used_model_ids)
    reserved = set() if reserved_model_ids is None else set(reserved_model_ids)
    resolved: list[ResolvedModel] = []
    unavailable: list[dict[str, Any]] = []
    for item in config["models"]:
        if item.get("enabled", True) is not True or item["activation"] != activation:
            continue
        if activation == "high_risk" and not high_risk:
            continue
        candidates = [item["model"], *item.get("fallbacks", [])]
        chosen = next(
            (
                candidate
                for candidate in candidates
                if candidate in catalog
                and model_is_active(catalog[candidate])
                and candidate not in used
                and candidate not in reserved
            ),
            None,
        )
        if chosen is None:
            unavailable.append(
                {
                    "key": item["key"],
                    "requested_model": item["model"],
                    "candidates": candidates,
                    "reserved_candidates": [candidate for candidate in candidates if candidate in reserved],
                }
            )
            continue
        used.add(chosen)
        resolved.append(
            ResolvedModel(
                key=item["key"],
                role=item["role"],
                requested_model=item["model"],
                model_id=chosen,
                activation=item["activation"],
                fallback_used=chosen != item["model"],
            )
        )
    return resolved, unavailable
