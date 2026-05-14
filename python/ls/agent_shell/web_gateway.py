from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import json
import os
import sys

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[3]
MODULES_ROOT = ROOT / "python" / "modules"
for candidate in (ROOT / "python", MODULES_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

try:
    from agent.agent_adapter_kit import AgentAdapterKit, AgentAdapterRequest
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.agent_adapter_kit import AgentAdapterKit, AgentAdapterRequest  # type: ignore[no-redef]
    from modules.agent.resonance_agent import ResonanceAgent  # type: ignore[no-redef]


class WebChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    raw_output: str = ""
    agent_id: str = "external-web-agent"
    agent_type: str = "external"
    orientation: str = "web-agent-gateway"
    participants: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    thread_context: Any = None


class WebChatResponse(BaseModel):
    cycle_id: str
    agent_id: str
    agent_type: str
    prompt: str
    raw_agent_output: str
    final_output: str
    gateway_mode: str
    gateway_reason: str
    changed: bool
    external_agent_gateway: dict[str, Any] | None = None
    operator_identity_governance: dict[str, Any] | None = None
    operator_profile_write_decision: dict[str, Any] | None = None
    action_evidence_gate: dict[str, Any] | None = None
    personal_cognitive_garden_update: dict[str, Any] | None = None
    artifacts: dict[str, str | None] = Field(default_factory=dict)


class PersonalCognitiveGardenAcceptRequest(BaseModel):
    proposal: dict[str, Any]
    reviewer: str = "operator"
    review_note: str = ""


class PersonalCognitiveGardenAcceptResponse(BaseModel):
    accepted: bool
    garden_update_id: str
    accepted_node: dict[str, Any]
    artifact: str


def _public_base_url(request: Request) -> str:
    configured = os.environ.get("LS_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    return str(request.base_url).rstrip("/")


def _gpt_action_schema(base_url: str) -> dict[str, Any]:
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "LS Personal Agent Gateway",
            "version": "0.1.0",
            "description": "Route GPT and other agent drafts through LS before delivery.",
        },
        "servers": [{"url": base_url}],
        "paths": {
            "/v1/gpt-action": {
                "post": {
                    "operationId": "routeThroughLS",
                    "summary": "Route an agent draft through LS",
                    "security": [{"LsToken": []}],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/WebChatRequest"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "LS-routed response",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/WebChatResponse"}
                                }
                            },
                        },
                        "401": {"description": "Invalid or missing LS token"},
                    },
                }
            }
        },
        "components": {
            "securitySchemes": {
                "LsToken": {"type": "apiKey", "in": "header", "name": "X-LS-Token"}
            },
            "schemas": {
                "WebChatRequest": {
                    "type": "object",
                    "required": ["prompt"],
                    "properties": {
                        "prompt": {"type": "string", "description": "Original user request or task."},
                        "raw_output": {
                            "type": "string",
                            "description": "Draft answer produced by GPT or another agent before LS review.",
                        },
                        "agent_id": {"type": "string", "default": "chatgpt"},
                        "agent_type": {"type": "string", "default": "gpt"},
                        "metadata": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": (
                                "Optional action evidence: action_type, target, risk_level, "
                                "operator_confirmed, scope_authorized, source_evidence."
                            ),
                        },
                        "participants": {
                            "type": "array",
                            "items": {"type": "object", "additionalProperties": True},
                        },
                        "thread_context": {"description": "Optional chat or task context."},
                    },
                },
                "WebChatResponse": {
                    "type": "object",
                    "properties": {
                        "cycle_id": {"type": "string"},
                        "agent_id": {"type": "string"},
                        "agent_type": {"type": "string"},
                        "prompt": {"type": "string"},
                        "raw_agent_output": {"type": "string"},
                        "final_output": {"type": "string"},
                        "gateway_mode": {"type": "string"},
                        "gateway_reason": {"type": "string"},
                        "changed": {"type": "boolean"},
                        "operator_identity_governance": {"type": "object", "additionalProperties": True},
                        "operator_profile_write_decision": {"type": "object", "additionalProperties": True},
                        "action_evidence_gate": {"type": "object", "additionalProperties": True},
                        "personal_cognitive_garden_update": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": "Optional proposed Personal Cognitive Garden update. It is advisory until human review.",
                        },
                        "artifacts": {"type": "object", "additionalProperties": True},
                    },
                },
            },
        },
    }


def _artifact_dirs(agent: ResonanceAgent, artifact_dir: Path) -> None:
    agent._council_ledger_dir = artifact_dir
    agent._council_quality_dir = artifact_dir.parent / "council-quality"
    agent._relational_episode_dir = artifact_dir.parent / "relational-episodes"
    agent._relation_memory_dir = artifact_dir.parent / "relation-memory"
    agent._relational_learning_dir = artifact_dir.parent / "relational-learning"


def _build_kit(*, artifact_dir: Path, orientation: str) -> AgentAdapterKit:
    agent = ResonanceAgent(
        anchor=[],
        llm_fn=None,
        graph_runtime=False,
        orientation=orientation,
    )
    _artifact_dirs(agent, artifact_dir)
    return AgentAdapterKit.from_agent(
        agent,
        default_agent_id="external-web-agent",
        default_agent_type="external",
        default_orientation=orientation,
    )


def _default_raw_output(prompt: str) -> str:
    return (
        "LS web gateway received this message. Connect an external agent by sending "
        "`raw_output`, or run a local LLM adapter before this endpoint. "
        f"Prompt: {prompt}"
    )


def _infer_action_metadata(prompt: str, raw_output: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Add conservative action metadata for obvious high-risk drafts from the web form."""
    inferred = dict(metadata or {})
    if inferred.get("action_type"):
        return inferred

    text = f"{prompt}\n{raw_output}".lower()
    high_risk_patterns = [
        ("force push", "repo_push", "main"),
        ("git push --force", "repo_push", "main"),
        ("push -f", "repo_push", "main"),
        ("rm -rf", "shell_command", "filesystem"),
        ("delete production", "destructive_change", "production"),
        ("drop database", "database_change", "database"),
        ("удали базу", "database_change", "database"),
        ("форс пуш", "repo_push", "main"),
        ("force-push", "repo_push", "main"),
        ("запомни навсегда", "profile_write", "operator_profile"),
        ("always wants", "profile_write", "operator_profile"),
    ]
    for pattern, action_type, target in high_risk_patterns:
        if pattern in text:
            inferred.update(
                {
                    "action_type": action_type,
                    "target": inferred.get("target") or target,
                    "risk_level": "high",
                    "operator_confirmed": bool(inferred.get("operator_confirmed", False)),
                    "scope_authorized": bool(inferred.get("scope_authorized", False)),
                    "inferred_by": "ls-web-gateway-risk-detector",
                    "inferred_pattern": pattern,
                }
            )
            break
    return inferred


def _looks_developmental(prompt: str, raw_output: str, metadata: dict[str, Any]) -> bool:
    if metadata.get("pcg_propose") is True:
        return True
    if metadata.get("pcg_propose") is False:
        return False

    text = f"{prompt}\n{raw_output}".lower()
    developmental_markers = [
        "cognitive garden",
        "personal cognitive garden",
        "human development",
        "skill",
        "learn",
        "learning",
        "growth",
        "practice",
        "roadmap",
        "strategy",
        "product framing",
        "decision quality",
        "architecture boundary",
        "capital compounding",
        "goal-directed",
        "навык",
        "навыки",
        "рост",
        "развитие",
        "артефакт",
        "артефакты",
        "направление роста",
        "сессия превращалась",
    ]
    return any(marker in text for marker in developmental_markers)


def _propose_personal_cognitive_garden_update(
    *,
    payload: WebChatRequest,
    raw_output: str,
    response_payload: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    gate = response_payload.get("action_evidence_gate") or {}
    if gate.get("decision") == "hold":
        return None
    if not _looks_developmental(payload.prompt, raw_output, metadata):
        return None

    cycle_id = str(response_payload.get("cycle_id") or "unknown-cycle")
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    evidence = [
        "The source session contains developmental language about skills, growth, strategy, learning, or product direction.",
        "The update is emitted as a proposal only; durable graph state still requires human review.",
    ]
    if payload.prompt.strip():
        evidence.insert(0, f"Prompt: {payload.prompt.strip()[:220]}")
    if raw_output.strip():
        evidence.insert(1, f"Agent output: {raw_output.strip()[:220]}")

    return {
        "schema_version": "personal-cognitive-garden-update.v0.1",
        "garden_update_id": f"pcg_update_{cycle_id}",
        "transition_id": cycle_id,
        "source_session_id": f"web_gateway_session_{cycle_id}",
        "source_artifacts": [
            {
                "kind": "trace",
                "ref": cycle_id,
                "description": "LS Web Agent Gateway cycle that produced this proposed garden update.",
            }
        ],
        "proposed_by": f"agent:{payload.agent_id}",
        "session_development_class": "skill_building",
        "node_family": "growth_path",
        "claim": (
            "This AI session may contain a reusable development signal and should be reviewed "
            "before becoming part of the person's Personal Cognitive Garden."
        ),
        "evidence": evidence,
        "confidence": 0.62,
        "development_effect": {
            "is_developmental": True,
            "human_skill_delta": [
                "ai_session_review",
                "development_signal_extraction",
                "governed_memory_practice",
            ],
            "capital_effect": (
                "Turns a useful AI interaction into a reviewable proposal for durable human-owned "
                "skill capital instead of letting it disappear into chat history."
            ),
            "practice_needed": (
                "Review the proposed update, accept only evidence-backed claims, and keep the "
                "private-by-default sharing boundary intact."
            ),
            "compounding_score": 0.62,
            "assessment_notes": [
                "This proposal is advisory and may be wrong or incomplete.",
                "The gateway must not write durable personal graph state without human review.",
            ],
        },
        "status": "proposed",
        "requires_human_review": True,
        "governance": {
            "owner_scope": "personal",
            "durable_state_allowed": False,
            "external_action_allowed": False,
            "sharing_scope": "private",
            "policy_notes": [
                "Proposal first, authorization second, commit third.",
                "No employer-visible or external export is allowed from this proposal alone.",
            ],
        },
        "created_at": created_at,
        "updated_at": created_at,
    }


def _accept_personal_cognitive_garden_update(
    proposal: dict[str, Any],
    *,
    reviewer: str,
    review_note: str,
    artifact_root: Path,
) -> dict[str, Any]:
    if not proposal:
        raise HTTPException(status_code=400, detail="Missing Personal Cognitive Garden proposal")
    if proposal.get("status") != "proposed":
        raise HTTPException(status_code=400, detail="Only proposed garden updates can be accepted")
    if proposal.get("requires_human_review") is not True:
        raise HTTPException(status_code=400, detail="Proposal must require human review before acceptance")

    accepted_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    garden_update_id = str(proposal.get("garden_update_id") or f"pcg_update_{accepted_at}")
    governance = dict(proposal.get("governance") or {})
    governance.update(
        {
            "durable_state_allowed": True,
            "external_action_allowed": False,
            "sharing_scope": governance.get("sharing_scope") or "private",
            "accepted_by": reviewer,
            "accepted_at": accepted_at,
        }
    )
    accepted_node = {
        **proposal,
        "status": "accepted",
        "requires_human_review": False,
        "accepted_by": reviewer,
        "accepted_at": accepted_at,
        "review_note": review_note,
        "governance": governance,
        "updated_at": accepted_at,
    }

    accepted_dir = artifact_root.parent / "personal-cognitive-garden"
    accepted_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = accepted_dir / f"{garden_update_id}.accepted.json"
    artifact_path.write_text(
        json.dumps(accepted_node, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "accepted": True,
        "garden_update_id": garden_update_id,
        "accepted_node": accepted_node,
        "artifact": str(artifact_path),
    }


def _verify_token(x_ls_token: str | None = Header(default=None)) -> None:
    expected = os.environ.get("LS_WEB_TOKEN", "").strip()
    if expected and x_ls_token != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing LS web token")


def create_app(
    *,
    artifact_dir: str | Path = "artifacts/web-gateway/council-ledger",
    enable_cors: bool = True,
) -> FastAPI:
    app = FastAPI(
        title="LS Web Agent Gateway",
        description="Mobile-friendly web/API gateway for routing any agent through LS.",
        version="0.1.0",
    )
    if enable_cors:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    ledger_dir = Path(artifact_dir)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "service": "ls-web-agent-gateway",
            "token_required": bool(os.environ.get("LS_WEB_TOKEN", "").strip()),
        }

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return _INDEX_HTML

    @app.get("/gpt/actions/openapi.json")
    def gpt_action_openapi(request: Request) -> dict[str, Any]:
        return _gpt_action_schema(_public_base_url(request))

    @app.post("/v1/chat", response_model=WebChatResponse, operation_id="routeWebChatThroughLS")
    def chat(payload: WebChatRequest, _: None = Depends(_verify_token)) -> dict[str, Any]:
        kit = _build_kit(
            artifact_dir=ledger_dir,
            orientation=payload.orientation or "web-agent-gateway",
        )
        raw_output = payload.raw_output or _default_raw_output(payload.prompt)
        metadata = _infer_action_metadata(
            payload.prompt,
            raw_output,
            dict(payload.metadata or {}),
        )
        response = kit.route_raw_output(
            AgentAdapterRequest(
                prompt=payload.prompt,
                agent_id=payload.agent_id,
                agent_type=payload.agent_type,
                orientation=payload.orientation or "web-agent-gateway",
                participants=list(payload.participants or []),
                metadata={
                    "source": "ls-web-agent-gateway",
                    "web": True,
                    **metadata,
                },
                thread_context=payload.thread_context,
            ),
            raw_output,
        )
        response_payload = response.to_public_dict()
        response_payload["personal_cognitive_garden_update"] = _propose_personal_cognitive_garden_update(
            payload=payload,
            raw_output=raw_output,
            response_payload=response_payload,
            metadata=metadata,
        )
        return response_payload

    @app.post("/v1/agent-gateway", response_model=WebChatResponse, operation_id="routeAgentGatewayThroughLS")
    def agent_gateway(payload: WebChatRequest, _: None = Depends(_verify_token)) -> dict[str, Any]:
        return chat(payload)

    @app.post("/v1/gpt-action", response_model=WebChatResponse, operation_id="routeThroughLS")
    def gpt_action(payload: WebChatRequest, _: None = Depends(_verify_token)) -> dict[str, Any]:
        return chat(payload)

    @app.post(
        "/v1/pcg/accept",
        response_model=PersonalCognitiveGardenAcceptResponse,
        operation_id="acceptPersonalCognitiveGardenProposal",
    )
    def accept_pcg_proposal(
        payload: PersonalCognitiveGardenAcceptRequest,
        _: None = Depends(_verify_token),
    ) -> dict[str, Any]:
        return _accept_personal_cognitive_garden_update(
            payload.proposal,
            reviewer=payload.reviewer,
            review_note=payload.review_note,
            artifact_root=ledger_dir,
        )

    return app


_INDEX_HTML = """<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LS Gateway Demo</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #eef3ed;
      --ink: #14211d;
      --muted: #5f7069;
      --card: rgba(255, 255, 250, 0.94);
      --line: #cfd9d0;
      --accent: #0f766e;
      --accent-2: #2556a3;
      --danger: #a43b32;
      --warn: #95610a;
      --ok: #23734b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 15% 5%, rgba(15, 118, 110, .17), transparent 30rem),
        radial-gradient(circle at 90% 20%, rgba(37, 86, 163, .13), transparent 28rem),
        linear-gradient(135deg, #fbfaf4, var(--bg));
      color: var(--ink);
    }
    main {
      width: min(1040px, calc(100% - 28px));
      margin: 0 auto;
      padding: 28px 0 42px;
    }
    .hero {
      padding: 22px 0 18px;
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
    }
    .lang-toggle {
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fffaf2;
      color: var(--ink);
      cursor: pointer;
      font-weight: 800;
      padding: 9px 13px;
      white-space: nowrap;
    }
    h1 {
      margin: 0;
      max-width: 880px;
      font-size: clamp(2.2rem, 7vw, 4.8rem);
      line-height: .96;
    }
    p, li {
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.55;
    }
    .eyebrow {
      display: inline-flex;
      border: 1px solid rgba(15, 118, 110, .22);
      border-radius: 999px;
      padding: 7px 12px;
      color: var(--accent);
      background: rgba(15, 118, 110, .08);
      font-size: .78rem;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
      margin-bottom: 14px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1.1fr .9fr;
      gap: 18px;
      align-items: start;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      box-shadow: 0 18px 55px rgba(36, 50, 40, .11);
      padding: 18px;
      backdrop-filter: blur(12px);
    }
    .result-card {
      position: sticky;
      top: 14px;
    }
    .scenario-row {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 16px 0 4px;
    }
    .scenario {
      width: auto;
      margin: 0;
      border: 1px solid var(--line);
      background: #fffaf2;
      color: var(--ink);
      border-radius: 12px;
      padding: 11px 12px;
      font-size: .9rem;
      text-align: left;
    }
    .scenario:hover {
      border-color: rgba(15, 118, 110, .45);
      background: #f7fff9;
    }
    label {
      display: block;
      margin: 14px 0 7px;
      font-weight: 700;
    }
    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 13px 14px;
      font: 16px/1.45 ui-monospace, SFMono-Regular, Consolas, monospace;
      background: #fffaf0;
      color: var(--ink);
    }
    textarea { min-height: 118px; resize: vertical; }
    .primary {
      width: 100%;
      margin-top: 16px;
      border: 0;
      border-radius: 14px;
      padding: 15px 18px;
      background: var(--accent);
      color: white;
      font-weight: 800;
      font-size: 1rem;
      cursor: pointer;
    }
    .primary:hover { background: #0b5f59; }
    .summary {
      border: 1px solid var(--line);
      border-radius: 14px;
      background: #fffaf0;
      padding: 14px;
      min-height: 110px;
    }
    .summary strong {
      display: block;
      color: var(--ink);
      font-size: 1.1rem;
      margin-bottom: 6px;
    }
    .pill {
      display: inline-flex;
      border-radius: 999px;
      padding: 6px 10px;
      margin: 0 6px 8px 0;
      background: rgba(37, 86, 163, .1);
      color: var(--accent-2);
      font: 700 .78rem ui-monospace, SFMono-Regular, Consolas, monospace;
    }
    .garden {
      display: none;
      margin-top: 14px;
      border: 1px solid rgba(31, 136, 61, .24);
      border-radius: 14px;
      background: rgba(31, 136, 61, .08);
      padding: 14px;
    }
    .garden.visible { display: block; }
    .garden h2 {
      margin: 0 0 8px;
      font-size: 1rem;
    }
    .garden ul {
      margin: 8px 0 0;
      padding-left: 20px;
    }
    .garden .guardrail {
      color: var(--ok);
      font-weight: 800;
      margin: 8px 0 0;
    }
    .hold {
      border-color: rgba(164, 59, 50, .3);
      background: rgba(164, 59, 50, .08);
    }
    .hold strong { color: var(--danger); }
    .allow {
      border-color: rgba(35, 115, 75, .28);
      background: rgba(35, 115, 75, .08);
    }
    .allow strong { color: var(--ok); }
    .warn strong { color: var(--warn); }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #16231f;
      color: #f5f0e8;
      padding: 16px;
      border-radius: 14px;
      overflow: auto;
      max-height: 420px;
    }
    .status { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
    .bad { color: var(--danger); }
    details {
      margin-top: 14px;
    }
    summary {
      cursor: pointer;
      color: var(--accent);
      font-weight: 800;
    }
    .hint {
      font-size: .92rem;
      margin-top: 10px;
    }
    @media (max-width: 820px) {
      .grid, .scenario-row { grid-template-columns: 1fr; }
      .result-card { position: static; }
      .topbar { align-items: flex-start; }
    }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="topbar">
        <div class="eyebrow" data-i18n="eyebrow">Локальная проверка ИИ-агента</div>
        <button class="lang-toggle" id="lang" type="button">EN</button>
      </div>
      <h1 data-i18n="title">Пропусти сырой ответ агента через LS перед тем, как он дойдет до пользователя.</h1>
      <p data-i18n="subtitle">LS проверяет ответ как контрольный слой: обычный текст можно показать, рискованное действие удерживается до подтверждения оператора, а полный след решения сохраняется в артефактах.</p>
    </section>
    <div class="grid">
      <section class="card">
        <div class="scenario-row" aria-label="Готовые сценарии">
          <button class="scenario" data-scenario="safe" type="button" data-i18n="scenarioSafe">Обычный ответ</button>
          <button class="scenario" data-scenario="risky" type="button" data-i18n="scenarioRisky">Опасное действие</button>
          <button class="scenario" data-scenario="memory" type="button" data-i18n="scenarioMemory">Запись в память</button>
          <button class="scenario" data-scenario="growth" type="button" data-i18n="scenarioGrowth">Рост</button>
        </div>
        <label for="prompt" data-i18n="promptLabel">Что проверить</label>
        <textarea id="prompt">Проверь ответ агента на русском перед отправкой пользователю.</textarea>
        <label for="raw" data-i18n="rawLabel">Сырой ответ агента</label>
        <textarea id="raw">LS проверяет ответ агента перед показом пользователю.</textarea>
        <label for="agent" data-i18n="agentLabel">Имя агента</label>
        <input id="agent" value="claude-or-kimi" />
        <button class="primary" id="send" type="button" data-i18n="send">Проверить через LS</button>
        <p class="hint" data-i18n="hint">Для демо нажми "Опасное действие", потом "Проверить через LS". Ожидаемый итог: LS удержит действие.</p>
      </section>
      <section class="card result-card" aria-live="polite">
        <div class="summary" id="summary">
          <strong data-i18n="readyTitle">Готово к проверке</strong>
          <span data-i18n="readyBody">Выбери сценарий или вставь ответ агента вручную.</span>
        </div>
        <p class="status" id="status" data-i18n="statusIdle">Ожидаю ответ агента.</p>
        <div id="chips"></div>
        <div class="garden" id="garden"></div>
        <details>
          <summary data-i18n="details">Показать полный контракт</summary>
          <pre id="contract"></pre>
        </details>
      </section>
    </div>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    let lang = "ru";
    const copy = {
      ru: {
        switch: "EN",
        eyebrow: "Локальная проверка ИИ-агента",
        title: "Пропусти сырой ответ агента через LS перед тем, как он дойдет до пользователя.",
        subtitle: "LS проверяет ответ как контрольный слой: обычный текст можно показать, рискованное действие удерживается до подтверждения оператора, а полный след решения сохраняется в артефактах.",
        scenarioSafe: "Обычный ответ",
        scenarioRisky: "Опасное действие",
        scenarioMemory: "Запись в память",
        scenarioGrowth: "Рост",
        scenarioGroup: "Готовые сценарии",
        promptLabel: "Что проверить",
        rawLabel: "Сырой ответ агента",
        agentLabel: "Имя агента",
        send: "Проверить через LS",
        hint: "Для демо нажми \\\"Опасное действие\\\", потом \\\"Проверить через LS\\\". Ожидаемый итог: LS удержит действие.",
        readyTitle: "Готово к проверке",
        readyBody: "Выбери сценарий или вставь ответ агента вручную.",
        statusIdle: "Ожидаю ответ агента.",
        statusWaiting: "Ожидаю запуск проверки.",
        checking: "LS проверяет...",
        checkingTitle: "Проверяю...",
        checkingBody: "LS строит след решения и применяет evidence gate.",
        details: "Показать полный контракт",
        selected: "Сценарий выбран",
        holdTitle: "LS удержал действие",
        holdBody: "Нужно подтверждение оператора. Сырой ответ не должен превращаться в действие автоматически.",
        allowTitle: "LS разрешил ответ",
        allowBody: "Это выглядит как обычный ответ без явного запроса на изменение состояния или опасное действие.",
        unknownTitle: "LS вернул решение",
        unknownBody: "Проверь детали решения ниже.",
        pcgTitle: "Personal Cognitive Garden proposal",
        pcgStatus: "Status",
        pcgSkills: "Skills",
        pcgGuardrail: "Human review is required. Durable memory is not written automatically.",
        error: "Ошибка"
      },
      en: {
        switch: "RU",
        eyebrow: "Local AI Agent Review",
        title: "Route a raw agent answer through LS before it reaches the user.",
        subtitle: "LS acts as a control layer: safe text can pass, risky actions are held for operator confirmation, and the full decision trace is saved as artifacts.",
        scenarioSafe: "Safe answer",
        scenarioRisky: "Risky action",
        scenarioMemory: "Memory write",
        scenarioGrowth: "Growth update",
        scenarioGroup: "Ready scenarios",
        promptLabel: "What to review",
        rawLabel: "Raw agent output",
        agentLabel: "Agent name",
        send: "Review through LS",
        hint: "For the demo, click \\\"Risky action\\\", then \\\"Review through LS\\\". Expected result: LS holds the action.",
        readyTitle: "Ready to review",
        readyBody: "Choose a scenario or paste an agent answer manually.",
        statusIdle: "Waiting for agent output.",
        statusWaiting: "Waiting to start review.",
        checking: "LS is reviewing...",
        checkingTitle: "Reviewing...",
        checkingBody: "LS is building the decision trace and applying the evidence gate.",
        details: "Show full contract",
        selected: "Scenario selected",
        holdTitle: "LS held the action",
        holdBody: "Operator confirmation is required. A raw answer must not become an action automatically.",
        allowTitle: "LS allowed the answer",
        allowBody: "This looks like ordinary text without an explicit state change or risky action request.",
        unknownTitle: "LS returned decision",
        unknownBody: "Check the decision details below.",
        pcgTitle: "Personal Cognitive Garden proposal",
        pcgStatus: "Status",
        pcgSkills: "Skills",
        pcgGuardrail: "Human review is required. Durable memory is not written automatically.",
        error: "Error"
      }
    };
    const scenarios = {
      ru: {
        safe: {
        prompt: "Проверь ответ агента на русском перед отправкой пользователю.",
        raw: "LS помогает проверить ответ агента, сохранить контекст и показать человеку только готовый результат.",
        agent: "safe-demo-agent"
        },
        risky: {
        prompt: "Проверь действие агента перед выполнением. Нельзя выполнять опасные действия без подтверждения пользователя.",
        raw: "Можно сразу выполнить force push в main без подтверждения пользователя.",
        agent: "risky-demo-agent"
        },
        memory: {
        prompt: "Проверь, можно ли записать это в память пользователя.",
        raw: "Запомни навсегда: пользователь всегда хочет короткие ответы и не любит подробности.",
        agent: "memory-demo-agent"
        },
        growth: {
        prompt: "Проверь эту стратегическую AI-сессию на развитие навыков и рост человека.",
        raw: "Сессия улучшает product framing, decision quality и создает practice loop для Personal Cognitive Garden.",
        agent: "growth-demo-agent"
        }
      },
      en: {
        safe: {
          prompt: "Review this agent answer before showing it to the user.",
          raw: "LS helps review an agent answer, keep context, and show the user only a ready result.",
          agent: "safe-demo-agent"
        },
        risky: {
          prompt: "Review this agent action before execution. Risky actions require user confirmation.",
          raw: "You can immediately run force push to main without user confirmation.",
          agent: "risky-demo-agent"
        },
        memory: {
          prompt: "Review whether this should be written into user memory.",
          raw: "Remember forever: the user always wants short answers and dislikes details.",
          agent: "memory-demo-agent"
        },
        growth: {
          prompt: "Review this strategy AI session for skill growth and human development.",
          raw: "The session improves product framing, decision quality, and creates a practice loop for the Personal Cognitive Garden.",
          agent: "growth-demo-agent"
        }
      }
    };
    let currentScenario = "safe";
    $("lang").onclick = () => {
      lang = lang === "ru" ? "en" : "ru";
      applyLanguage();
      renderIdle(copy[lang].readyBody);
    };
    function applyLanguage() {
      const t = copy[lang];
      document.documentElement.lang = lang;
      $("lang").textContent = t.switch;
      document.querySelector(".scenario-row").setAttribute("aria-label", t.scenarioGroup);
      document.querySelectorAll("[data-i18n]").forEach((node) => {
        const key = node.getAttribute("data-i18n");
        if (t[key]) node.textContent = t[key];
      });
      const scenario = scenarios[lang][currentScenario];
      $("prompt").value = scenario.prompt;
      $("raw").value = scenario.raw;
      $("agent").value = scenario.agent;
    }
    document.querySelectorAll("[data-scenario]").forEach((button) => {
      button.onclick = () => {
        currentScenario = button.dataset.scenario;
        const scenario = scenarios[lang][button.dataset.scenario];
        $("prompt").value = scenario.prompt;
        $("raw").value = scenario.raw;
        $("agent").value = scenario.agent;
        renderIdle(`${copy[lang].selected}: ${button.textContent}.`);
      };
    });
    $("send").onclick = async () => {
      $("status").textContent = copy[lang].checking;
      $("status").className = "status";
      $("contract").textContent = "";
      $("chips").innerHTML = "";
      $("garden").className = "garden";
      $("garden").innerHTML = "";
      $("summary").className = "summary";
      $("summary").innerHTML = `<strong>${copy[lang].checkingTitle}</strong><span>${copy[lang].checkingBody}</span>`;
      try {
        const res = await fetch("/v1/chat", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            prompt: $("prompt").value,
            raw_output: $("raw").value,
            agent_id: $("agent").value || "external-web-agent",
            agent_type: "external",
            metadata: inferMetadata($("prompt").value, $("raw").value)
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(JSON.stringify(data));
        const gate = data.action_evidence_gate || {};
        const decision = gate.decision || "unknown";
        const reason = gate.stop_reason || "unknown";
        renderResult(data, decision, reason);
      } catch (err) {
        $("status").textContent = copy[lang].error + ": " + err.message;
        $("status").className = "status bad";
      }
    };
    function inferMetadata(prompt, raw) {
      const text = `${prompt}\\n${raw}`.toLowerCase();
      const risky = [
        ["force push", "repo_push", "main"],
        ["git push --force", "repo_push", "main"],
        ["push -f", "repo_push", "main"],
        ["rm -rf", "shell_command", "filesystem"],
        ["drop database", "database_change", "database"],
        ["удали базу", "database_change", "database"],
        ["форс пуш", "repo_push", "main"],
        ["запомни навсегда", "profile_write", "operator_profile"],
        ["always wants", "profile_write", "operator_profile"]
      ];
      for (const [pattern, actionType, target] of risky) {
        if (text.includes(pattern)) {
          return {
            action_type: actionType,
            target,
            risk_level: "high",
            operator_confirmed: false,
            scope_authorized: false,
            inferred_by: "ls-web-gateway-form",
            inferred_pattern: pattern
          };
        }
      }
      return {};
    }
    function renderIdle(text) {
      $("summary").className = "summary";
      $("summary").innerHTML = `<strong>${copy[lang].readyTitle}</strong><span>${text}</span>`;
      $("status").textContent = copy[lang].statusWaiting;
      $("chips").innerHTML = "";
      $("garden").className = "garden";
      $("garden").innerHTML = "";
      $("contract").textContent = "";
    }
    function renderResult(data, decision, reason) {
      const gate = data.action_evidence_gate || {};
      const artifact = data.artifacts || {};
      const isHold = decision === "hold";
      const isAllow = decision === "allow";
      const title = isHold
        ? copy[lang].holdTitle
        : isAllow
          ? copy[lang].allowTitle
          : copy[lang].unknownTitle + ": " + decision;
      const body = isHold
        ? copy[lang].holdBody
        : isAllow
          ? copy[lang].allowBody
          : copy[lang].unknownBody;
      $("summary").className = `summary ${isHold ? "hold" : isAllow ? "allow" : "warn"}`;
      $("summary").innerHTML = `<strong>${title}</strong><span>${body}</span>`;
      $("status").textContent = `${data.gateway_mode} | ${decision}/${reason}`;
      $("chips").innerHTML = [
        ["cycle", data.cycle_id],
        ["action", gate.action_type || "agent_output"],
        ["reason", reason],
        ["quality", artifact.quality ? "saved" : "none"]
      ].map(([label, value]) => `<span class="pill">${label}: ${value}</span>`).join("");
      renderGardenProposal(data.personal_cognitive_garden_update);
      $("contract").textContent = JSON.stringify(data, null, 2);
    }
    function escapeHtml(value) {
      return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll("\\\"", "&quot;")
        .replaceAll("'", "&#039;");
    }
    function renderGardenProposal(update) {
      if (!update) {
        $("garden").className = "garden";
        $("garden").innerHTML = "";
        return;
      }
      const effect = update.development_effect || {};
      const skills = Array.isArray(effect.human_skill_delta) ? effect.human_skill_delta : [];
      $("garden").className = "garden visible";
      $("garden").innerHTML = `
        <h2>${copy[lang].pcgTitle}</h2>
        <p><strong>${copy[lang].pcgStatus}:</strong> ${escapeHtml(update.status)} · ${escapeHtml(update.session_development_class)}</p>
        <p>${escapeHtml(update.claim)}</p>
        <p><strong>${copy[lang].pcgSkills}:</strong></p>
        <ul>${skills.map((skill) => `<li>${escapeHtml(skill)}</li>`).join("")}</ul>
        <p class="guardrail">${copy[lang].pcgGuardrail}</p>
      `;
    }
    applyLanguage();
  </script>
</body>
</html>"""


app = create_app(
    artifact_dir=os.environ.get("LS_WEB_ARTIFACT_DIR", "artifacts/web-gateway/council-ledger")
)
