from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..contracts import RouteDecision
from ..routing import (
    MalformedRouteResponseError,
    NoRouteError,
    RoutingDisabledError,
    RoutingTimeoutError,
    RoutingUnavailableError,
    _required_string,
    _sanitize,
)


JsonObject = Mapping[str, Any]
Transport = Callable[[JsonObject, "DAOlimConfig"], Mapping[str, Any]]


@dataclass(frozen=True)
class DAOlimConfig:
    enabled: bool = False
    mode: str = "cli"
    timeout_seconds: float = 2.0
    endpoint: str = "http://127.0.0.1:9103/v1/explain"
    command: tuple[str, ...] = ("daoctl", "explain")
    host: str = "ls.local"
    path: str = "/v1/route"
    actor: str = "adapter:dao_lim"

    def __post_init__(self) -> None:
        if self.mode not in {"cli", "http"}:
            raise ValueError("DAO_lim mode must be 'cli' or 'http'")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not self.endpoint:
            raise ValueError("endpoint must not be empty")
        if not self.command:
            raise ValueError("command must not be empty")
        if not self.host or not self.path or not self.actor:
            raise ValueError("host, path, and actor must not be empty")


class DAOlimRoutingAdapter:
    """Feature-flagged DAO_lim routing boundary.

    Only route metadata is sent to DAO_lim. Task content and provider secrets are
    deliberately excluded from the transport payload.
    """

    def __init__(
        self,
        config: Optional[DAOlimConfig] = None,
        transport: Optional[Transport] = None,
    ) -> None:
        self.config = config or DAOlimConfig()
        self._transport = transport

    @property
    def adapter_name(self) -> str:
        return "dao_lim"

    def route(self, request: JsonObject) -> RouteDecision:
        if not self.config.enabled:
            raise RoutingDisabledError(
                "DAO_lim routing is disabled; enable it explicitly in configuration"
            )

        payload = self._transport_payload(request)
        try:
            response = (
                self._transport(payload, self.config)
                if self._transport is not None
                else self._default_transport(payload)
            )
        except RoutingTimeoutError:
            raise
        except TimeoutError as error:
            raise RoutingTimeoutError("DAO_lim routing timed out") from error
        except subprocess.TimeoutExpired as error:
            raise RoutingTimeoutError("DAO_lim CLI routing timed out") from error
        except (HTTPError, URLError, OSError) as error:
            raise RoutingUnavailableError("DAO_lim transport is unavailable") from error

        if not isinstance(response, Mapping):
            raise MalformedRouteResponseError("DAO_lim response must be an object")
        return self._decision_from_response(request, response)

    def _transport_payload(self, request: JsonObject) -> dict[str, Any]:
        constraints = request.get("constraints", {})
        if not isinstance(constraints, Mapping):
            raise TypeError("routing constraints must be a mapping")
        routing_intent = request.get("routing_intent", request.get("capability"))
        if not isinstance(routing_intent, str) or not routing_intent.strip():
            raise ValueError("routing_intent must be a non-empty string")
        return {
            "capability": _required_string(request, "capability"),
            "role_id": _required_string(request, "role_id"),
            "routing_intent": routing_intent.strip(),
            "constraints": _sanitize(constraints),
            "host": str(request.get("host", self.config.host)),
            "path": str(request.get("path", self.config.path)),
        }

    def _default_transport(self, payload: JsonObject) -> Mapping[str, Any]:
        if self.config.mode == "http":
            return self._http_transport(payload)
        return self._cli_transport(payload)

    def _http_transport(self, payload: JsonObject) -> Mapping[str, Any]:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        request = Request(
            self.config.endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                content = response.read().decode("utf-8")
        except TimeoutError as error:
            raise RoutingTimeoutError("DAO_lim HTTP routing timed out") from error
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as error:
            raise MalformedRouteResponseError(
                "DAO_lim HTTP response is not valid JSON"
            ) from error
        if not isinstance(decoded, Mapping):
            raise MalformedRouteResponseError("DAO_lim HTTP response must be an object")
        return decoded

    def _cli_transport(self, payload: JsonObject) -> Mapping[str, Any]:
        command = list(self.config.command)
        command.extend(
            [
                "--host",
                str(payload["host"]),
                "--path",
                str(payload["path"]),
                "--intent",
                str(payload["routing_intent"]),
                "--json",
            ]
        )
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=self.config.timeout_seconds,
        )
        if completed.returncode != 0:
            raise RoutingUnavailableError(
                f"DAO_lim CLI exited with code {completed.returncode}"
            )
        try:
            decoded = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            raise MalformedRouteResponseError(
                "DAO_lim CLI output is not valid JSON"
            ) from error
        if not isinstance(decoded, Mapping):
            raise MalformedRouteResponseError("DAO_lim CLI output must be an object")
        return decoded

    def _decision_from_response(
        self,
        request: JsonObject,
        response: Mapping[str, Any],
    ) -> RouteDecision:
        status = str(response.get("status", "ok")).lower()
        if status in {"no_route", "unavailable", "blocked"}:
            raise NoRouteError(str(response.get("reason", "DAO_lim found no route")))

        selected = response.get("selected_backend", response.get("selected"))
        if not isinstance(selected, str) or not selected:
            raise MalformedRouteResponseError(
                "DAO_lim response requires selected_backend"
            )

        considered_value = response.get("considered_backends")
        if considered_value is None:
            considered_value = self._candidate_names(response.get("candidates", ()))
        if isinstance(considered_value, (str, bytes)) or not isinstance(
            considered_value,
            (list, tuple),
        ):
            raise MalformedRouteResponseError(
                "DAO_lim response requires considered_backends"
            )
        considered = tuple(str(item) for item in considered_value if str(item))
        if not considered or selected not in considered:
            raise MalformedRouteResponseError(
                "selected backend must appear in considered_backends"
            )

        approved = request.get("approved_backends", ())
        if isinstance(approved, (str, bytes)) or not isinstance(
            approved,
            (list, tuple),
        ):
            raise TypeError("approved_backends must be a sequence")
        if not approved:
            raise NoRouteError(
                "DAO_lim routing requires an explicit approved_backends allowlist"
            )
        if selected not in approved:
            raise NoRouteError(
                f"DAO_lim selected unapproved backend {selected!r}; route rejected"
            )

        reason = response.get("reason", response.get("explanation"))
        if not isinstance(reason, str) or not reason.strip():
            raise MalformedRouteResponseError("DAO_lim response requires a reason")

        metadata = {
            "explainability_version": "trusted_runtime.dao_lim.explain.v0.1",
            "transport_mode": self.config.mode,
            "fallback_used": bool(response.get("fallback_used", False)),
            "scores": _sanitize(response.get("scores", {})),
            "metrics": _sanitize(response.get("metrics", {})),
            "alternatives": _sanitize(response.get("alternatives", [])),
            "dao_explain": _sanitize(response.get("explainability", {})),
        }
        return RouteDecision(
            route_id=str(
                request.get(
                    "route_id",
                    f"route-{_required_string(request, 'role_id')}-{selected}",
                )
            ),
            task_id=_required_string(request, "task_id"),
            trail_id=_required_string(request, "trail_id"),
            role_id=_required_string(request, "role_id"),
            capability=_required_string(request, "capability"),
            adapter=self.adapter_name,
            actor=str(request.get("actor", self.config.actor)),
            selected_backend=selected,
            considered_backends=considered,
            reason=reason.strip(),
            created_at=_required_string(request, "created_at"),
            parent_cause=_required_string(request, "parent_cause"),
            metadata=metadata,
        )

    @staticmethod
    def _candidate_names(value: Any) -> tuple[str, ...]:
        if isinstance(value, (str, bytes)) or not isinstance(value, (list, tuple)):
            return ()
        names = []
        for item in value:
            if isinstance(item, str):
                names.append(item)
            elif isinstance(item, Mapping):
                name = item.get("backend", item.get("name"))
                if name:
                    names.append(str(name))
        return tuple(names)
