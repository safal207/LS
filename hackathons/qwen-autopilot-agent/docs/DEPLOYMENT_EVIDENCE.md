# Alibaba Cloud deployment evidence

Status: **PENDING LIVE DEPLOYMENT**

This file is intentionally honest: the application code and deployment assets are ready, but the final public Alibaba Cloud URL and captured runtime evidence must be added after deployment.

## Alibaba Cloud / Qwen integration evidence

The backend calls Qwen through Alibaba Cloud Model Studio's OpenAI-compatible API:

- implementation: [`../app/qwen.py`](../app/qwen.py)
- model: `qwen3.7-plus` by default
- secret: `DASHSCOPE_API_KEY`
- recommended Singapore base URL: `https://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1`
- Docker deployment asset: [`../Dockerfile`](../Dockerfile)

The API key must be injected as a runtime secret. It must never be committed to this repository or displayed in a demo recording.

## Values to add after deployment

Replace the placeholders below after the public service is running:

- Alibaba Cloud service: `<ECS | SAE | ACK | Function Compute>`
- Region: `<region>`
- Public service URL: `https://<public-service-url>`
- Deployment date in UTC: `<YYYY-MM-DDTHH:MM:SSZ>`
- Verified commit SHA: `<full-commit-sha>`
- Container image digest: `<sha256:...>`

## Runtime verification

Run from the project directory:

```bash
bash scripts/verify_deployment.sh https://<public-service-url> | tee deployment-proof.json
```

The verifier fails unless all of these conditions are true:

1. `/healthz` returns `status = ok`.
2. `/api/evaluate` returns a successful response.
3. `qwen.status = COMPLETED`, proving that the deployed backend reached Qwen Cloud.
4. `execution.status = NOT_EXECUTED` and `execution.authority = advisory_only`, proving that the gateway does not misrepresent judgment as execution.

## Evidence to preserve

Before submitting, preserve all of the following:

- the public URL opened in an incognito browser window;
- the output of `scripts/verify_deployment.sh` with no secrets;
- a screenshot of the Alibaba Cloud service page showing region and running status;
- the deployed container image digest or exact commit SHA;
- a demo recording showing one real `qwen.status = COMPLETED` response;
- the final public repository links pinned to the verified commit SHA.

## Sanitization gate

Do not publish evidence until you have checked that it contains none of the following:

- API keys or authorization headers;
- Alibaba Cloud account IDs, phone numbers, billing details, or private endpoints;
- unredacted workspace secrets;
- customer data or real credentials;
- terminal history containing exported secrets.

## Final verified result

Replace this section after deployment.

```json
{
  "deployment_verified": false,
  "public_url": null,
  "commit_sha": null,
  "container_image_digest": null,
  "health_status": null,
  "qwen_status": null,
  "verified_at": null
}
```
