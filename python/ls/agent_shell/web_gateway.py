from __future__ import annotations

from pathlib import Path
from typing import Any
import os
import sys

from fastapi import Depends, FastAPI, Header, HTTPException
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
    artifacts: dict[str, str | None] = Field(default_factory=dict)


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

    @app.post("/v1/chat", response_model=WebChatResponse)
    def chat(payload: WebChatRequest, _: None = Depends(_verify_token)) -> dict[str, Any]:
        kit = _build_kit(
            artifact_dir=ledger_dir,
            orientation=payload.orientation or "web-agent-gateway",
        )
        raw_output = payload.raw_output or _default_raw_output(payload.prompt)
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
                    **dict(payload.metadata or {}),
                },
                thread_context=payload.thread_context,
            ),
            raw_output,
        )
        return response.to_public_dict()

    @app.post("/v1/agent-gateway", response_model=WebChatResponse)
    def agent_gateway(payload: WebChatRequest, _: None = Depends(_verify_token)) -> dict[str, Any]:
        return chat(payload)

    return app


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>LS Web Agent Gateway</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4efe6;
      --ink: #1f2823;
      --muted: #68746d;
      --card: rgba(255, 252, 245, 0.92);
      --line: #ded3c1;
      --accent: #0f766e;
      --danger: #9f3a2f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at 20% 10%, rgba(15, 118, 110, .16), transparent 34rem),
        linear-gradient(135deg, #f8f1e5, var(--bg));
      color: var(--ink);
    }
    main {
      width: min(880px, calc(100% - 28px));
      margin: 0 auto;
      padding: 28px 0 42px;
    }
    .hero {
      padding: 28px 0 18px;
    }
    h1 {
      margin: 0;
      font-size: clamp(2rem, 10vw, 4.8rem);
      line-height: .92;
      letter-spacing: -.06em;
    }
    p {
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.55;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 24px;
      box-shadow: 0 24px 70px rgba(56, 45, 30, .13);
      padding: 18px;
      backdrop-filter: blur(12px);
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
    button {
      width: 100%;
      margin-top: 16px;
      border: 0;
      border-radius: 18px;
      padding: 15px 18px;
      background: var(--accent);
      color: white;
      font-weight: 800;
      font-size: 1rem;
      cursor: pointer;
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #16231f;
      color: #f5f0e8;
      padding: 16px;
      border-radius: 18px;
      overflow: auto;
    }
    .status { font-family: ui-monospace, SFMono-Regular, Consolas, monospace; }
    .bad { color: var(--danger); }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>LS Web Agent Gateway</h1>
      <p>Send Claude, Kimi, Codex, local models, or phone chat output through your personal LS layer before it reaches you as an answer, memory, profile change, or action.</p>
    </section>
    <section class="card">
      <label for="prompt">Your message</label>
      <textarea id="prompt">Explain what LS does as a personal layer for agents.</textarea>
      <label for="raw">Raw agent output</label>
      <textarea id="raw">LS checks an agent answer before showing it.</textarea>
      <label for="agent">Agent id</label>
      <input id="agent" value="claude-or-kimi" />
      <button id="send">Route Through LS</button>
      <p class="status" id="status">Ready.</p>
      <pre id="result"></pre>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    $("send").onclick = async () => {
      $("status").textContent = "Routing...";
      $("status").className = "status";
      $("result").textContent = "";
      try {
        const res = await fetch("/v1/chat", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({
            prompt: $("prompt").value,
            raw_output: $("raw").value,
            agent_id: $("agent").value || "external-web-agent",
            agent_type: "external"
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(JSON.stringify(data));
        $("status").textContent = `${data.gateway_mode} · ${data.action_evidence_gate?.decision}/${data.action_evidence_gate?.stop_reason}`;
        $("result").textContent = data.final_output + "\\n\\n--- full contract ---\\n" + JSON.stringify(data, null, 2);
      } catch (err) {
        $("status").textContent = "Error: " + err.message;
        $("status").className = "status bad";
      }
    };
  </script>
</body>
</html>"""


app = create_app(
    artifact_dir=os.environ.get("LS_WEB_ARTIFACT_DIR", "artifacts/web-gateway/council-ledger")
)
