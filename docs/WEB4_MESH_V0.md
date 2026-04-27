# Web4 Mesh v0 (plan alignment)

## What ships in this repo

- **Stack:** Python `modules.web4_mesh` + `websockets` (not js-libp2p in-tree; that remains an optional future transport).
- **Message types (envelope `message_type`):** `ANNOUNCE`, `SYNC_GRAPH_REQUEST` / `SYNC_GRAPH_CHUNK`, `PUSH_REFLECTION` — see `python/modules/web4_mesh/node.py`.
- **Cross-process demo:** `python tools/run_mesh_ws.py` (multi-node, reflection + graph sync).
- **Automated v0 / W3 check:** `python/tests/test_web4_mesh_v0_two_peers_announce.py` — two local WebSocket peers; **A** broadcasts `ANNOUNCE`, **B** learns **A** in `PeerRegistry`.

## Run

```bash
# Full websocket demo (ports 9001–9004)
PYTHONPATH=python python tools/run_mesh_ws.py
```

## CI

`mesh-tests` workflow runs mesh unit tests including transport WS; add `test_web4_mesh_v0_two_peers_announce` to the same lane (paths updated in workflow).
