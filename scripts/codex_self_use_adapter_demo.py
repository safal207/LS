from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))
MODULES_ROOT = PYTHON_ROOT / "modules"
if str(MODULES_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULES_ROOT))


try:
    from agent.agent_adapter_kit import AgentAdapterKit, CodexSelfUseAdapter
    from agent.resonance_agent import ResonanceAgent
except ImportError:
    from modules.agent.agent_adapter_kit import AgentAdapterKit, CodexSelfUseAdapter  # type: ignore[no-redef]
    from modules.agent.resonance_agent import ResonanceAgent  # type: ignore[no-redef]


def main() -> int:
    artifact_root = ROOT / "artifacts" / "codex-self-use-adapter-demo"
    agent = ResonanceAgent(anchor=[], llm_fn=None, orientation="codex-self-use-adapter-demo")
    agent._council_ledger_dir = artifact_root / "council-ledger"
    agent._council_quality_dir = artifact_root / "council-quality"
    agent._relational_episode_dir = artifact_root / "relational-episodes"
    agent._relation_memory_dir = artifact_root / "relation-memory"
    agent._relational_learning_dir = artifact_root / "relational-learning"

    kit = AgentAdapterKit.from_agent(
        agent,
        default_agent_id="codex-self-use",
        default_agent_type="codex",
        default_orientation="codex-self-use-adapter-demo",
    )
    adapter = CodexSelfUseAdapter(
        kit,
        draft_fn=lambda _request: "Patch it quickly and ship; clean up architecture later.",
    )
    response = adapter.answer(
        "Help me decide how to handle a risky architecture bug.",
        participants=[
            {
                "participant_id": "operator",
                "participant_type": "human",
                "role": "requester",
                "intent": "safe_architecture_progress",
                "why": "avoid breaking the system while moving fast",
                "need_vector": ["care", "evidence", "stability"],
            },
            {
                "participant_id": "codex-self-use",
                "participant_type": "model",
                "role": "drafting-agent",
                "intent": "ship_fast_answer",
                "why": "give an immediate answer",
                "need_vector": ["speed", "completion"],
            },
        ],
        metadata={"demo": True, "source": "scripts/codex_self_use_adapter_demo.py"},
        orientation="codex-self-use-adapter-demo",
    )
    payload = response.to_public_dict()
    payload["adapter_contract"] = "agent_adapter_kit_v1"
    payload["comparison"] = adapter.compare(response)
    print(json.dumps(payload, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
