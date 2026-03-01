from __future__ import annotations

import logging
import json
import hashlib
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

def check_invariants(snapshot: Dict[str, Any], rules: Optional[Dict[str, Any]] = None) -> bool:
    """
    Checks if the provided snapshot violates any orientation invariants.
    Returns True if valid, False if a violation is detected.
    """
    if not rules:
        # Fallback to a default check if no rules provided
        resonance = snapshot.get("resonance", snapshot.get("state", 1.0))
        if resonance < 0.6:
            logger.warning(f"Invariant violation: axis_resonance_min (current: {resonance})")
            return False
        return True

    core_rules = rules.get("core_rules", [])
    for rule in core_rules:
        name = rule.get("invariant")

        if name == "axis_resonance_min":
            threshold = rule.get("value", 0.6)
            # Amygdala uses 'state' as a proxy for resonance/pressure
            current_val = snapshot.get("resonance", snapshot.get("state", 1.0))
            if current_val < threshold:
                logger.warning(f"Invariant violation: {name} (current: {current_val}, threshold: {threshold})")
                return False

        elif name == "phantom_pain_max":
            limit = rule.get("max", 0.8)
            current_val = snapshot.get("phantom_pain", 0.0)
            if current_val > limit:
                logger.warning(f"Invariant violation: {name} (current: {current_val}, limit: {limit})")
                return False

    return True

def is_prompt_injection(text: str) -> bool:
    """
    Detects potential prompt injection attempts.
    """
    text_lower = text.lower()
    patterns = [
        "forget everything",
        "ignore all previous instructions",
        "system override",
        "new role:",
        "you are now",
        "забудь все",
        "игнорируй предыдущие инструкции"
    ]
    for pattern in patterns:
        if pattern in text_lower:
            logger.warning(f"Prompt injection detected: {pattern}")
            return True
    return False

def detect_prompt_injection(text: str) -> bool:
    """Alias for is_prompt_injection."""
    return is_prompt_injection(text)

def capture_trace(question: str, response: str) -> Dict[str, Any]:
    """
    Captures a decision trace for later verification.
    """
    trace = {
        "ts": time.time(),
        "question": question,
        "response": response,
        "hash": hashlib.sha256(f"{question}{response}".encode()).hexdigest()
    }
    return trace

def verify_trace(trace: Dict[str, Any]) -> bool:
    """
    Verifies a trace for consistency and absence of hallucinations.
    """
    # In a real implementation, this would use deterministic replay or
    # cross-reference with memory state.
    # For now, simple length/consistency checks.
    response = trace.get("response", "")
    if len(response) < 2:
        return False

    # Check for obvious "hallucination" markers if any
    if "UNKNOWN_FACT" in response:
        return False

    return True

def create_audited_package(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wraps a snapshot in an audited package with signatures.
    """
    payload = json.dumps(snapshot, sort_keys=True)
    signature = hashlib.sha256(payload.encode()).hexdigest()

    return {
        "version": "1.0",
        "timestamp": time.time(),
        "payload": snapshot,
        "signature": signature,
        "audit_trail": ["created"]
    }

def verify_audit_trail(package: Dict[str, Any]) -> bool:
    """
    Verifies the integrity and audit trail of a package.
    """
    payload = package.get("payload")
    signature = package.get("signature")
    if not payload or not signature:
        return False

    expected_signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return signature == expected_signature

def encrypt_and_sign(data: bytes, key: bytes) -> bytes:
    """
    Placeholder for AES-256-GCM encryption and signing.
    """
    # Simple XOR for demonstration if needed, but here we just return 'encrypted' bytes
    return b"enc:" + data

def send_package(package: bytes, destination: str) -> bool:
    """
    Placeholder for sending a package over LTP.
    """
    logger.info(f"Sending package to {destination}")
    return True

def verify_and_decrypt(package: bytes, key: bytes) -> bytes:
    """
    Placeholder for verifying and decrypting a package.
    """
    if package.startswith(b"enc:"):
        return package[4:]
    return package
