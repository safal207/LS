import asyncio
import time
import logging

# Configure minimal logging to avoid noise during benchmark
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("benchmark")

class MockNode:
    def __init__(self, peer_id):
        self.peer_id = peer_id

class MockEnvelope:
    pass

class MockTransport:
    def __init__(self, node, peers):
        self.node = node
        self._outgoing = {uri: None for uri in peers}

    async def send(self, envelope, uri):
        # Simulate network latency
        await asyncio.sleep(0.1)
        if uri == "ws://failed":
            raise Exception("Connection failed")

    async def broadcast_sequential(self, envelope):
        sent = 0
        for uri in list(self._outgoing.keys()):
            try:
                await self.send(envelope, uri)
                sent += 1
            except Exception:
                logger.warning("Broadcast failed from %s to %s", self.node.peer_id, uri)
                pass
        return sent

    async def broadcast_parallel(self, envelope):
        async def _do_send(uri):
            try:
                await self.send(envelope, uri)
                return 1
            except Exception:
                logger.warning("Broadcast failed from %s to %s", self.node.peer_id, uri)
                return 0

        results = await asyncio.gather(*[
            _do_send(uri) for uri in list(self._outgoing.keys())
        ])
        return sum(results)

async def main():
    peer_count = 10
    peers = [f"ws://peer{i}" for i in range(peer_count)]
    peers.append("ws://failed")
    node = MockNode("node1")
    transport = MockTransport(node, peers)
    envelope = MockEnvelope()

    print(f"Broadcasting to {len(peers)} peers (100ms latency each, 1 failure expected)...")

    # Baseline
    start = time.perf_counter()
    sent_seq = await transport.broadcast_sequential(envelope)
    end = time.perf_counter()
    seq_time = end - start
    print(f"Sequential: {sent_seq} sent in {seq_time:.4f}s")

    # Optimized
    start = time.perf_counter()
    sent_par = await transport.broadcast_parallel(envelope)
    end = time.perf_counter()
    par_time = end - start
    print(f"Parallel: {sent_par} sent in {par_time:.4f}s")

    print(f"Improvement: {(seq_time - par_time) / seq_time * 100:.2f}%")
    print(f"Speedup: {seq_time / par_time:.2f}x")

    assert sent_seq == sent_par == peer_count, f"Sent counts differ: seq={sent_seq}, par={sent_par}"

if __name__ == "__main__":
    asyncio.run(main())
