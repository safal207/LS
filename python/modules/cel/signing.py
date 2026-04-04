from __future__ import annotations

import json
from dataclasses import dataclass

from nacl.signing import SigningKey, VerifyKey


class SigningError(RuntimeError):
    pass


@dataclass(frozen=True)
class EventSigner:
    signing_key: SigningKey

    @classmethod
    def generate(cls) -> "EventSigner":
        return cls(signing_key=SigningKey.generate())

    @property
    def verify_key_hex(self) -> str:
        return self.signing_key.verify_key.encode().hex()

    def sign_event(self, event: dict) -> str:
        payload = dict(event)
        payload.pop("signature", None)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        sig = self.signing_key.sign(canonical).signature.hex()
        return f"ed25519:{sig}"

    def verify_event(self, event: dict) -> bool:
        signature = event.get("signature", "")
        if not isinstance(signature, str) or not signature.startswith("ed25519:"):
            return False
        raw_sig = bytes.fromhex(signature.split(":", 1)[1])
        payload = dict(event)
        payload.pop("signature", None)
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        verify_key = VerifyKey(bytes.fromhex(self.verify_key_hex))
        try:
            verify_key.verify(canonical, raw_sig)
            return True
        except Exception:
            return False
