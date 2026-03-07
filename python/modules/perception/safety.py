from __future__ import annotations
import logging
import threading
import time
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class PrivacyRedactor:
    """Masks PII from text before it's sent to the models."""
    def __init__(self):
        # Basic patterns for v0.1: Email, Phone, 2FA codes, Passwords
        self.patterns = [
            (r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[REDACTED_EMAIL]'),
            (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED_PHONE]'),
            (r'\b\d{6}\b', '[REDACTED_2FA]'),
            (r'(?i)(password|passwd|secret)[:= ]+[^\s]+', r'\1: [REDACTED_PASSWORD]')
        ]

    def redact(self, text: str) -> str:
        """Applies redaction patterns to the given text."""
        redacted_text = text
        for pattern, replacement in self.patterns:
            redacted_text = re.sub(pattern, replacement, redacted_text)
        return redacted_text

class ConsentManager:
    """Manages user consent and perception toggles."""
    def __init__(self):
        self._global_toggle = True
        self._allowlist: List[str] = [] # Allowlist for window titles or process names
        self._denylist: List[str] = ["password", "keychain", "2fa"] # Denylist
        self._lock = threading.Lock()

    def set_global_toggle(self, enabled: bool):
        with self._lock:
            self._global_toggle = enabled

    def is_capture_allowed(self, window_context: Dict[str, Any]) -> bool:
        """Checks if screen capture is allowed for the given context."""
        # Use lock to ensure thread-safety when reading denylist/allowlist
        with self._lock:
            if not self._global_toggle:
                return False

            title = window_context.get("title", "").lower()
            process_name = window_context.get("process_name", "").lower()

            # Check denylist
            for entry in self._denylist:
                if entry in title or entry in process_name:
                    return False

            # If allowlist is empty, we allow everything not in the denylist
            if not self._allowlist:
                return True

            # Check allowlist
            for entry in self._allowlist:
                if entry in title or entry in process_name:
                    return True

            return False

class AuditLog:
    """Logs perception activity for user review."""
    def __init__(self):
        self._log: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self.max_entries = 100

    def log_event(self, event_type: str, details: Dict[str, Any]):
        # Use lock to ensure thread-safety when appending to shared log
        with self._lock:
            entry = {
                "timestamp": time.time(),
                "event_type": event_type,
                "details": details
            }
            self._log.append(entry)
            if len(self._log) > self.max_entries:
                self._log.pop(0)

    def get_entries(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._log)
