from __future__ import annotations

# LSSValidationHistoryStore — stores ValidationHistoryRecords in an LPI
# Liminal Session Store (LSS), gaining coherence tracking and drift detection
# across validation rounds at no extra cost.
#
# Each governance engine instance maps to one LSS thread_id.
# Each ValidationHistoryRecord becomes one LSSMessage whose LCE payload
# carries the serialised record.
#
# Falls back to InMemoryValidationHistoryStore when lri is not installed so
# the rest of the stack never breaks.

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_LRI_AVAILABLE: bool | None = None  # cached after first check


def _lri_available() -> bool:
    global _LRI_AVAILABLE  # noqa: PLW0603
    if _LRI_AVAILABLE is None:
        try:
            import lri  # noqa: F401
            _LRI_AVAILABLE = True
        except ImportError:
            _LRI_AVAILABLE = False
    return _LRI_AVAILABLE


# ── LCE serialisation helpers ─────────────────────────────────────────────────


def _record_to_lce_dict(record: Any) -> dict[str, Any]:
    """Convert a ValidationHistoryRecord to a minimal LCE-shaped dict."""
    return {
        "intent": {
            "audience": ["ls:governance"],
            "type": "validation_history_record",
        },
        "payload": record.to_dict(),
        "policy": {
            "consent": "internal",
        },
    }


def _lce_dict_to_record(lce: dict[str, Any]) -> Any | None:
    """Reconstruct a ValidationHistoryRecord from an LCE dict, or None on error."""
    from ls.cognition.validation_governance import ValidationHistoryRecord  # noqa: PLC0415

    try:
        payload = lce.get("payload")
        if not isinstance(payload, dict):
            return None
        return ValidationHistoryRecord.from_dict(payload)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to decode ValidationHistoryRecord from LCE: %s", exc)
        return None


# ── LSS-backed store ──────────────────────────────────────────────────────────


class LSSValidationHistoryStore:
    """Stores validation history in an LPI Liminal Session Store.

    Parameters
    ----------
    thread_id:
        Identifies the governance session within LSS.  Use a stable,
        unique string per governance engine instance (e.g. a service
        name + hash).
    lss:
        A pre-configured LSS instance.  When None the class tries to
        create one from ``lri.lss``.  Falls back to in-memory storage
        if lri is unavailable.
    """

    def __init__(
        self,
        thread_id: str = "ls:governance:default",
        lss: Any | None = None,
    ) -> None:
        self._thread_id = thread_id
        self._lss = lss or self._build_lss()
        self._fallback: Any | None = None  # populated when lri unavailable

        if self._lss is None:
            from ls.cognition.validation_governance import InMemoryValidationHistoryStore  # noqa: PLC0415

            self._fallback = InMemoryValidationHistoryStore()
            logger.debug(
                "lri not available — LSSValidationHistoryStore using in-memory fallback"
            )

    @staticmethod
    def _build_lss() -> Any | None:
        if not _lri_available():
            return None
        try:
            from lri.lss import LSS  # type: ignore[import]  # noqa: PLC0415

            return LSS()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to initialise LSS: %s", exc)
            return None

    def load_records(self) -> list[Any]:
        if self._fallback is not None:
            return self._fallback.load_records()
        try:
            return self._load_from_lss()
        except Exception as exc:  # noqa: BLE001
            logger.warning("LSS load_records failed, returning empty: %s", exc)
            return []

    def append_record(self, record: Any) -> None:
        if self._fallback is not None:
            self._fallback.append_record(record)
            return
        try:
            self._append_to_lss(record)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LSS append_record failed, record not persisted: %s", exc)

    def coherence(self) -> float | None:
        """Return the current LSS session coherence score, or None if unavailable."""
        if self._lss is None:
            return None
        try:
            session = self._lss.get_session(self._thread_id)
            if session is None:
                return None
            return float(session.coherence)
        except Exception as exc:  # noqa: BLE001
            logger.debug("LSS coherence fetch failed: %s", exc)
            return None

    def drift_events(self) -> list[Any]:
        """Return drift events from the current LSS session."""
        if self._lss is None:
            return []
        try:
            session = self._lss.get_session(self._thread_id)
            if session is None:
                return []
            return list(session.metrics.drift_events)
        except Exception as exc:  # noqa: BLE001
            logger.debug("LSS drift_events fetch failed: %s", exc)
            return []

    # ── private ──────────────────────────────────────────────────────────────

    def _load_from_lss(self) -> list[Any]:
        session = self._lss.get_session(self._thread_id)
        if session is None:
            return []
        records = []
        for msg in session.messages:
            lce_dict = self._lss_message_to_lce_dict(msg)
            record = _lce_dict_to_record(lce_dict)
            if record is not None:
                records.append(record)
        return records

    def _append_to_lss(self, record: Any) -> None:
        from lri.lss import LSSMessage  # type: ignore[import]  # noqa: PLC0415

        lce_dict = _record_to_lce_dict(record)
        lss_msg = LSSMessage(
            lce=lce_dict,
            timestamp=datetime.now(tz=timezone.utc),
        )
        self._lss.store(self._thread_id, lss_msg)

    @staticmethod
    def _lss_message_to_lce_dict(msg: Any) -> dict[str, Any]:
        lce = msg.lce
        if isinstance(lce, dict):
            return lce
        # LCE may be a Pydantic model
        if hasattr(lce, "model_dump"):
            return lce.model_dump()
        if hasattr(lce, "__dict__"):
            return dict(lce.__dict__)
        return {}
