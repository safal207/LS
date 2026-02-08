import logging

from python.rust_bridge import RustOptimizer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtt_demo")


def main() -> None:
    optimizer = RustOptimizer()
    if not optimizer.transport_available():
        logger.error("Rust transport not available.")
        return

    session_id = optimizer.create_session("local-peer")
    if session_id is None:
        logger.error("Failed to create session.")
        return

    challenge = b"handshake-challenge"
    response = optimizer.handshake(session_id, challenge)
    if response != challenge:
        logger.error("Handshake failed.")
        return

    channel_id = optimizer.open_channel("control", session_id=session_id)
    if channel_id is None:
        logger.error("Failed to open channel.")
        return

    payload = b"hello-web4"
    if not optimizer.send(channel_id, payload):
        logger.error("Send failed.")
        return

    received = optimizer.receive(channel_id)
    logger.info("Received payload: %s", received)

    stats = optimizer.channel_stats(channel_id)
    logger.info("Channel stats: %s", stats)

    snapshot = optimizer.transport_snapshot()
    logger.info("Transport snapshot: %s", snapshot)

    optimizer.close_channel(channel_id)
    optimizer.close_session(session_id)


if __name__ == "__main__":
    main()
