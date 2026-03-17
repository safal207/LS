# Web4 Mesh WS Demo Quickstart

## Run demo
```bash
PYTHONPATH=python python tools/run_mesh_ws.py
```

## Run demo with delivery metrics CSV
```bash
PYTHONPATH=python python tools/run_mesh_ws.py --collect-metrics
```

Default metrics output:
- `artifacts/mesh_delivery_metrics.csv`

## Validate tests
```bash
PYTHONPATH=python pytest -q tests/test_service_runtime.py python/tests/test_web4_mesh.py python/tests/test_web4_mesh_node.py python/tests/test_web4_mesh_transport_ws.py
```
