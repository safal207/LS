import argparse
import logging

from python.rust_bridge import RustOptimizer


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rtt_cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="RTT transport demo CLI")
    parser.add_argument("--peer-id", default="local-peer", help="Peer identifier")
    parser.add_argument("--channel-kind", default="control", help="Channel kind")
    parser.add_argument("--payload", default="hello-web4", help="Payload to send")
    parser.add_argument("--repeat", type=int, default=1, help="Number of sends")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    optimizer = RustOptimizer()
    if not optimizer.transport_available():
        logger.error("Rust transport not available.")
        return

    session_id = optimizer.create_session(args.peer_id)
    if session_id is None:
        logger.error("Failed to create session.")
        return

    challenge = b"handshake-challenge"
    response = optimizer.handshake(session_id, challenge)
    if response != challenge:
        logger.error("Handshake failed.")
        return

    channel_id = optimizer.open_channel(args.channel_kind, session_id=session_id)
    if channel_id is None:
        logger.error("Failed to open channel.")
        return

    payload = args.payload.encode("utf-8")
    for _ in range(max(args.repeat, 1)):
        if not optimizer.send(channel_id, payload):
            logger.error("Send failed.")
            return
        _ = optimizer.receive(channel_id)

    logger.info("Channel stats: %s", optimizer.channel_stats(channel_id))
    logger.info("Transport snapshot: %s", optimizer.transport_snapshot())

    optimizer.close_channel(channel_id)
    optimizer.close_session(session_id)


if __name__ == "__main__":
    main()
