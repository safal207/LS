from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import time
from pathlib import Path

from modules.web4_mesh import DeliveryEvent, Web4MeshNode, WebSocketTransport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_mesh_ws")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Web4 Mesh websocket demo")
    parser.add_argument("--collect-metrics", action="store_true", help="Collect delivery latency into CSV")
    parser.add_argument("--metrics-path", default="artifacts/mesh_delivery_metrics.csv", help="CSV output path")
    return parser.parse_args()


async def start_node(
    peer_id: str,
    host: str,
    port: int,
    on_delivery,
    run_id: str,
) -> tuple[Web4MeshNode, WebSocketTransport]:
    node = Web4MeshNode(peer_id=peer_id, address=f"ws://{host}:{port}")
    transport = WebSocketTransport(node=node, host=host, port=port, on_delivery=on_delivery, run_id=run_id)
    await transport.start()
    return node, transport


async def demo(args: argparse.Namespace) -> list[DeliveryEvent]:
    host = "127.0.0.1"
    run_id = f"mesh-{int(time.time())}"
    delivery_events: list[DeliveryEvent] = []

    def on_delivery(event: DeliveryEvent) -> None:
        if args.collect_metrics:
            delivery_events.append(event)

    node_a, t_a = await start_node("node-a", host, 9001, on_delivery, run_id)
    node_b, t_b = await start_node("node-b", host, 9002, on_delivery, run_id)
    node_c, t_c = await start_node("node-c", host, 9003, on_delivery, run_id)

    node_a.add_peer("node-b", t_b.listen_uri)
    node_a.add_peer("node-c", t_c.listen_uri)
    node_b.add_peer("node-a", t_a.listen_uri)
    node_b.add_peer("node-c", t_c.listen_uri)
    node_c.add_peer("node-a", t_a.listen_uri)
    node_c.add_peer("node-b", t_b.listen_uri)

    await t_a.connect_to_peer(t_b.listen_uri)
    await t_a.connect_to_peer(t_c.listen_uri)
    await t_b.connect_to_peer(t_a.listen_uri)
    await t_c.connect_to_peer(t_a.listen_uri)

    await t_a.send_many_routed(node_a.announce())
    await t_a.send_many_routed(node_a.push_reflection("hello mesh", "r1"))
    await asyncio.sleep(0.3)

    logger.info("node-b graph: %s", list(node_b.memory_graph.keys()))
    logger.info("node-c graph: %s", list(node_c.memory_graph.keys()))

    node_d, t_d = await start_node("node-d", host, 9004, on_delivery, run_id)
    node_d.add_peer("node-a", t_a.listen_uri)
    node_a.add_peer("node-d", t_d.listen_uri)
    await t_d.connect_to_peer(t_a.listen_uri)

    request = node_d.request_graph_chunk("node-a")
    if request is not None:
        await t_d.send(request, t_a.listen_uri)

    await asyncio.sleep(0.5)
    logger.info("node-d graph after sync: %s", list(node_d.memory_graph.keys()))

    await asyncio.gather(t_a.stop(), t_b.stop(), t_c.stop(), t_d.stop())
    return delivery_events


def write_metrics_csv(path: str, events: list[DeliveryEvent]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["run", "envelope_id", "origin", "destination", "latency_s", "delivered_bool"],
        )
        writer.writeheader()
        for event in events:
            writer.writerow(
                {
                    "run": event.run,
                    "envelope_id": event.envelope_id,
                    "origin": event.origin,
                    "destination": event.destination,
                    "latency_s": f"{event.latency_s:.6f}",
                    "delivered_bool": str(event.delivered_bool).lower(),
                }
            )


if __name__ == "__main__":
    args = parse_args()
    events = asyncio.run(demo(args))
    if args.collect_metrics:
        write_metrics_csv(args.metrics_path, events)
        logger.info("Saved metrics to %s with %d rows", args.metrics_path, len(events))
