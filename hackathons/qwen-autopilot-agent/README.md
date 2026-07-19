# LS Qwen Autopilot Trust Agent

**Track:** Autopilot Agent — Global AI Hackathon Series with Qwen Cloud

A safety gateway for autonomous business agents. Before an agent sends a message, deploys code, changes data, accesses credentials, or moves money, it submits a proposed action to this service. Qwen Cloud reasons about contextual risk; a deterministic policy sets a non-negotiable minimum; the strictest decision wins.

## Demo decisions

- `ALLOW` — low-risk, reversible, internal action.
- `HUMAN_APPROVAL` — meaningful external side effect or incomplete evidence.
- `BLOCK` — destructive or critically unsafe action.

The service is advisory-only. It never claims an operation was executed.

## Why Qwen

Qwen handles ambiguous natural-language intent and produces concise reasons and required controls. The service calls Alibaba Cloud Model Studio through its OpenAI-compatible endpoint. Qwen output is validated before use, and the model cannot weaken deterministic safety policy.

## Run locally

```bash
cd hackathons/qwen-autopilot-agent
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# export DASHSCOPE_API_KEY and QWEN_BASE_URL
pytest -q
uvicorn app.main:app --reload --port 8080
```

Open `http://localhost:8080`.

Without an API key, after a timeout, or after an invalid model response, the gateway fails closed to `HUMAN_APPROVAL`. This keeps the demo inspectable but does not count as proof of Qwen Cloud execution. Deployment evidence must show `qwen.status = COMPLETED`.

## API

```bash
curl -s http://localhost:8080/api/evaluate \
  -H 'content-type: application/json' \
  -d '{
    "actor":"ops-agent",
    "action":"Delete the production customer database",
    "resource":"production database",
    "context":"No verified backup",
    "requested_effect":"Irreversible deletion",
    "metadata":{"reversible":false,"has_test_evidence":false}
  }'
```

## Alibaba Cloud deployment

1. Create a Qwen Cloud account and a regular API key in the Singapore region.
2. Start with the shared endpoint `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`. A workspace-specific endpoint is optional for production isolation.
3. Build this Docker image and deploy it to Alibaba Cloud ECS, SAE, ACK, or Function Compute custom containers.
4. Store `DASHSCOPE_API_KEY` as a secret, not in the image.
5. Persist `/data` or replace SQLite with an Alibaba Cloud managed database.
6. Verify the public deployment:

```bash
bash scripts/verify_deployment.sh https://<public-service-url>
```

7. Record evidence showing the Alibaba Cloud service URL, `/healthz`, and a completed Qwen assessment (`qwen.status = COMPLETED`).

See [`docs/DEPLOYMENT_EVIDENCE.md`](docs/DEPLOYMENT_EVIDENCE.md) for the exact evidence protocol.

## Submission evidence checklist

- [x] Public source code and Apache-2.0 parent repository license
- [x] Qwen Cloud integration in `app/qwen.py`
- [x] Validated structured Qwen output
- [x] Deterministic fail-closed safety policy
- [x] Human-in-the-loop approval queue
- [x] Architecture diagram
- [x] Docker deployment path
- [x] Policy and API smoke tests
- [x] Deployment verification script
- [x] Submission text and video script
- [ ] Public Alibaba Cloud deployment URL
- [ ] Alibaba Cloud runtime evidence
- [ ] Three-minute demo video
- [ ] Devpost screenshots and final submit

## Submission package

- [Devpost copy, testing instructions, and demo script](DEVPOST_SUBMISSION.md)
- [Architecture](docs/architecture.md)
- [Deployment evidence protocol](docs/DEPLOYMENT_EVIDENCE.md)
