from __future__ import annotations

import logging
import json
import hashlib
import hmac
import base64
import secrets
import time
import os
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPLAY_CACHE: "OrderedDict[tuple[str, str], int]" = OrderedDict()
_REPLAY_CACHE_LOCK = threading.Lock()
_REPLAY_CACHE_MAX = 4096

_DERIVED_KEY_CACHE: "OrderedDict[tuple[str, str], bytes]" = OrderedDict()
_DERIVED_KEY_CACHE_LOCK = threading.Lock()
_DERIVED_KEY_CACHE_MAX = 1024

logger = logging.getLogger(__name__)

def load_invariants() -> List[Dict[str, Any]]:
    """Loads orientation invariants from orientation_invariants.json."""
    try:
        # Try relative to script and relative to CWD
        paths = [
            Path("orientation_invariants.json"),
            Path(__file__).resolve().parents[2] / "orientation_invariants.json"
        ]
        for inv_path in paths:
            if inv_path.exists():
                data = json.loads(inv_path.read_text(encoding="utf-8"))
                return data.get("core_rules", [])
    except Exception as e:
        logger.warning(f"Failed to load orientation invariants: {e}")
    return []

def check_rule(snapshot: Dict[str, Any], rule: Dict[str, Any]) -> bool:
    """Checks a single rule against a snapshot."""
    name = rule.get("invariant")
    if name == "axis_resonance_min":
        threshold = rule.get("value", 0.6)
        # Amygdala uses 'state' as a proxy for resonance/pressure
        current_val = snapshot.get("resonance", 1.0 - snapshot.get("state", 0.5))
        try:
            return float(current_val) >= float(threshold)
        except (ValueError, TypeError):
            return True
    elif name == "phantom_pain_max":
        limit = rule.get("max", 0.8)
        current_val = snapshot.get("phantom_pain", 0.0)
        try:
            return float(current_val) <= float(limit)
        except (ValueError, TypeError):
            return True
    return True

def detect_anomaly(snapshot: Dict[str, Any]) -> List[str]:
    """Returns a list of violated invariant names."""
    violations = []
    rules = load_invariants()
    for rule in rules:
        if not check_rule(snapshot, rule):
            violations.append(rule.get("invariant", "unknown"))
    return violations

def get_last_valid_snapshot(user_id: str) -> Dict[str, Any]:
    """Fetches the last persisted valid state via MemoryService."""
    try:
        from codex.causal_memory.memory import MemoryService
        service = MemoryService(user_id=user_id)
        return service.load()
    except Exception as e:
        logger.error(f"Failed to load last valid snapshot: {e}")
        return {}

def auto_rollback(snapshot: Dict[str, Any], violations: List[str]) -> Dict[str, Any]:
    """Returns the last valid state."""
    user_id = snapshot.get("user_id", "default")
    return get_last_valid_snapshot(user_id)

def check_invariants(snapshot: Dict[str, Any], rules: Optional[Dict[str, Any]] = None) -> bool:
    """
    Checks if the provided snapshot violates any orientation invariants.
    Returns True if valid, False if a violation is detected.
    """
    if not rules:
        return len(detect_anomaly(snapshot)) == 0

    core_rules = rules.get("core_rules", [])
    for rule in core_rules:
        if not check_rule(snapshot, rule):
            logger.warning(f"Invariant violation: {rule.get('invariant')} (snapshot: {snapshot})")
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
    if isinstance(package, bytes):
        try:
            package = json.loads(package.decode())
        except Exception:
            return False

    payload = package.get("payload")
    signature = package.get("signature")
    if not payload or not signature:
        return False

    expected_signature = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return signature == expected_signature

def _load_agent_keys_from_env() -> Dict[str, str]:
    """Load agent shared keys from env (`LS_AGENT_KEYS_JSON`)."""
    raw = os.getenv("LS_AGENT_KEYS_JSON", "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception as e:
        logger.warning(f"Failed to parse LS_AGENT_KEYS_JSON: {e}")
    return {}


def _get_keyring(override: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    if override is not None:
        return {str(k): str(v) for k, v in override.items()}
    return _load_agent_keys_from_env()


def _derive_key(key_material: Any, sender: Optional[str], keyring: Optional[Dict[str, Any]]) -> bytes:
    """Derive a stable shared key for encryption/authentication (with LRU cache)."""
    resolved_keyring = _get_keyring(keyring)

    if key_material is None and sender and sender in resolved_keyring:
        key_material = resolved_keyring[sender]

    if key_material is None:
        key_material = "local-dev-key"

    if isinstance(key_material, bytes):
        base_secret = key_material
    else:
        base_secret = str(key_material).encode("utf-8")

    sender_key = sender or ""
    key_fingerprint = hashlib.sha256(base_secret).hexdigest()
    cache_key = (sender_key, key_fingerprint)

    with _DERIVED_KEY_CACHE_LOCK:
        cached = _DERIVED_KEY_CACHE.get(cache_key)
        if cached is not None:
            _DERIVED_KEY_CACHE.move_to_end(cache_key)
            return cached

    derived = hashlib.pbkdf2_hmac("sha256", base_secret, b"lthread-v2-master", 600_000, dklen=32)

    with _DERIVED_KEY_CACHE_LOCK:
        _DERIVED_KEY_CACHE[cache_key] = derived
        _DERIVED_KEY_CACHE.move_to_end(cache_key)
        if len(_DERIVED_KEY_CACHE) > _DERIVED_KEY_CACHE_MAX:
            _DERIVED_KEY_CACHE.popitem(last=False)

    return derived


def _derive_subkeys(master_key: bytes) -> tuple[bytes, bytes]:
    """Derive independent keys for stream generation and MAC."""
    enc_key = hmac.digest(master_key, b"lthread-v2/subkey/encryption", "sha256")
    mac_key = hmac.digest(master_key, b"lthread-v2/subkey/authentication", "sha256")
    return enc_key, mac_key


def _build_aad(target_device: Any, sender: str, ts: int) -> bytes:
    return f"{target_device or ''}|{sender}|{ts}".encode("utf-8")


def encrypt_and_sign(data: Any, key: Any = None, **kwargs) -> bytes:
    """
    Create a signed encrypted envelope as JSON bytes.

    NOTE: This uses a Blake2s-derived stream construction for dev/sandbox mode.
    TODO: Replace with standard AEAD (ChaCha20-Poly1305 or AES-GCM) for production.
    """
    target_device = kwargs.get("target_device", key)
    sender = str(kwargs.get("sender", "unknown_agent"))
    ts = int(kwargs.get("ts", time.time()))

    keyring = kwargs.get("agent_keys")
    master_key = _derive_key(kwargs.get("shared_key", key), sender, keyring)
    enc_key, mac_key = _derive_subkeys(master_key)

    if isinstance(data, (dict, list)):
        payload_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
    elif isinstance(data, bytes):
        payload_bytes = data
    else:
        payload_bytes = str(data).encode("utf-8")

    nonce = secrets.token_bytes(16)
    ciphertext = bytearray(len(payload_bytes))

    block_size = 32
    for offset in range(0, len(payload_bytes), block_size):
        counter = (offset // block_size).to_bytes(4, "big")
        stream_block = hashlib.blake2s(enc_key + nonce + counter).digest()
        chunk = payload_bytes[offset:offset + block_size]
        for i, b in enumerate(chunk):
            ciphertext[offset + i] = b ^ stream_block[i]

    aad = _build_aad(target_device, sender, ts)
    mac = hmac.digest(mac_key, nonce + aad + bytes(ciphertext), "sha256")

    return json.dumps({
        "v": 2,
        "alg": "blake2s-xor+hmac-sha256",
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ct": base64.b64encode(bytes(ciphertext)).decode("ascii"),
        "tag": base64.b64encode(mac).decode("ascii"),
        "ts": ts,
        "sender": sender,
        "_synthetic_target": target_device,
    }).encode("utf-8")


def send_package(package: Any, destination: str, **kwargs) -> str:
    """
    Placeholder for sending a package over LTP.
    Returns the path to the 'sent' package.
    """
    logger.info(f"Sending package to {destination}")
    base_dir = kwargs.get("base_dir", "/tmp")
    path = Path(base_dir) / f"soul_package_{destination}.bin"

    if isinstance(package, dict):
        data = json.dumps(package).encode()
    elif isinstance(package, str):
        data = package.encode()
    else:
        data = package

    path.write_bytes(data)
    return str(path)


def get_current_snapshot(user_id: str) -> Dict[str, Any]:
    """Возвращает текущий снимок Amygdala для синхронизации."""
    from codex.causal_memory.memory import MemoryService

    service = MemoryService(user_id=user_id)
    return service.load() or {}


def receive_from_peer(peer_id: str) -> Optional[Dict[str, Any]]:
    """Placeholder для приема данных от пира."""
    # В реальности тут был бы LTP/L-THREAD сокет
    path = Path("/tmp") / f"soul_package_{peer_id}.bin"
    if path.exists():
        try:
            data = json.loads(path.read_bytes().decode())
            if verify_audit_trail(data):
                return data.get("payload")
        except Exception:
            pass
    return None


def send_toxins(toxins: int, peers: List[str]):
    """Транспорт для вывода токсинов (лимфа)."""
    for peer in peers:
        logger.info(f"Sending {toxins} toxins (lymph) to {peer}")


def start_bloodstream_sync(user_id: str, peers: List[str]):
    """Запускает фоновый цикл обмена кровью с пирами."""
    logger.info(f"Starting bloodstream sync for {user_id} with {peers}")


def _register_nonce(sender: str, nonce_b64: str, now_ts: int, max_skew_seconds: int) -> bool:
    """Register nonce in replay cache, returns False if already seen in the active time window."""
    with _REPLAY_CACHE_LOCK:
        min_valid_ts = now_ts - max_skew_seconds
        # OrderedDict preserves insertion order; we intentionally keep replay entries
        # ordered by insertion time (and move updated keys to end) so we can evict
        # only expired oldest entries until the first fresh record.
        while _REPLAY_CACHE:
            oldest_key, seen_ts = next(iter(_REPLAY_CACHE.items()))
            if seen_ts >= min_valid_ts:
                break
            _REPLAY_CACHE.popitem(last=False)

        replay_key = (sender, nonce_b64)
        if replay_key in _REPLAY_CACHE:
            return False

        _REPLAY_CACHE[replay_key] = now_ts
        _REPLAY_CACHE.move_to_end(replay_key)
        while len(_REPLAY_CACHE) > _REPLAY_CACHE_MAX:
            _REPLAY_CACHE.popitem(last=False)

        return True


def verify_and_decrypt(package_path: str, **kwargs) -> tuple[bool, Any]:
    """
    Verify package integrity and decrypt payload.
    """
    current_device_id = kwargs.get("current_device_id")
    now_ts = int(kwargs.get("now_ts", time.time()))
    max_skew_seconds = int(kwargs.get("max_skew_seconds", 30))
    enforce_replay_protection = kwargs.get("enforce_replay_protection", True)
    allow_legacy_v1 = kwargs.get("allow_legacy_v1", False)

    try:
        data = Path(package_path).read_bytes()
        package = json.loads(data.decode())

        if current_device_id and "_synthetic_target" in package:
            if package["_synthetic_target"] != current_device_id:
                logger.warning(
                    f"Synthetic device ID mismatch: {package['_synthetic_target']} != {current_device_id}"
                )
                return False, None

        ct = package.get("ct", "")
        if isinstance(ct, str) and ct.startswith("enc:"):
            if not allow_legacy_v1:
                logger.warning("Legacy v1 package rejected: allow_legacy_v1=False")
                return False, None
            payload_str = ct[4:]
            try:
                return True, json.loads(payload_str)
            except json.JSONDecodeError:
                return True, payload_str

        if package.get("v") != 2:
            return False, None

        sender = package.get("sender")
        ts = package.get("ts")
        if sender is None or ts is None:
            logger.warning("Missing sender/ts in package")
            return False, None
        sender = str(sender)
        ts = int(ts)

        if abs(now_ts - ts) > max_skew_seconds:
            logger.warning("Package timestamp outside allowed skew")
            return False, None

        keyring = kwargs.get("agent_keys")
        key_material = kwargs.get("shared_key")
        if key_material is None and current_device_id and not _get_keyring(keyring).get(sender):
            key_material = current_device_id

        master_key = _derive_key(key_material, sender, keyring)
        enc_key, mac_key = _derive_subkeys(master_key)

        nonce_b64 = package["nonce"]
        if enforce_replay_protection and not _register_nonce(sender, nonce_b64, now_ts, max_skew_seconds):
            logger.warning("Replay attack detected: duplicate nonce")
            return False, None

        nonce = base64.b64decode(nonce_b64)
        ciphertext = base64.b64decode(package["ct"])
        tag = base64.b64decode(package["tag"])

        aad = _build_aad(package.get("_synthetic_target"), sender, ts)
        expected_tag = hmac.digest(mac_key, nonce + aad + ciphertext, "sha256")
        if not hmac.compare_digest(tag, expected_tag):
            logger.warning("Package signature verification failed")
            return False, None

        plaintext = bytearray(len(ciphertext))
        block_size = 32
        for offset in range(0, len(ciphertext), block_size):
            counter = (offset // block_size).to_bytes(4, "big")
            stream_block = hashlib.blake2s(enc_key + nonce + counter).digest()
            chunk = ciphertext[offset : offset + block_size]
            for i, b in enumerate(chunk):
                plaintext[offset + i] = b ^ stream_block[i]

        payload_str = bytes(plaintext).decode("utf-8", errors="replace")
        try:
            return True, json.loads(payload_str)
        except json.JSONDecodeError:
            return True, payload_str
    except Exception as e:
        logger.error(f"Decryption failed: {e}")

    return False, None
