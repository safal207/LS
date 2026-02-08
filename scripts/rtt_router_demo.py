import json
import logging

from python.rust_bridge import RustOptimizer
from python.modules.protocols.cip import (
    CipIdentity,
    CipState,
    build_envelope,
    canonical_json,
)
from python.modules.protocols.router import ProtocolRouter


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtt_router_demo")


def main() -> None:
    optimizer = RustOptimizer()
    if not optimizer.transport_available():
        logger.error("Rust transport not available.")
        return

    session_id = optimizer.create_session("router-peer")
    if session_id is None:
        logger.error("Failed to create session.")
        return

    channel_id = optimizer.open_channel("knowledge", session_id=session_id)
    if channel_id is None:
        logger.error("Failed to open channel.")
        return

    sender = CipIdentity(agent_id="agent-alpha", fingerprint="alpha-fp")
    receiver = CipIdentity(agent_id="agent-beta", fingerprint="beta-fp")
    state = CipState(presence="focused", lri=1, intent="handshake")
    payload = {"message": "router-hello", "confidence": 0.95}
    envelope = build_envelope(
        message_type="HELLO",
        sender=sender,
        receiver=receiver,
        payload=payload,
        state=state,
    )

    router = ProtocolRouter()
    router.register_trust_signals()
    router.on("HELLO", lambda env: logger.info("Handled HELLO: %s", env["msg_id"]))

    serialized = canonical_json(envelope).encode("utf-8")
    if not optimizer.send(channel_id, serialized):
        logger.error("Send failed.")
        return

    raw = optimizer.receive(channel_id)
    if raw is None:
        logger.error("No response received.")
        return

    received = json.loads(raw.decode("utf-8"))
    result = router.dispatch(received)
    logger.info("Router handled=%s transition=%s", result.handled, result.transition)
    logger.info("Trust state=%s", router.trust.state.value)

    optimizer.close_channel(channel_id)
    optimizer.close_session(session_id)


if __name__ == "__main__":
    main()
