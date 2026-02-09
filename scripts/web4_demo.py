from python.modules.agent.loop import AgentLoop
from python.modules.protocols.cip import CipIdentity
from python.modules.protocols.hcp import HcpIdentity
from python.modules.protocols.lip import LipIdentity
from python.modules.protocols.trust import TrustFSM
from python.modules.web4_runtime.agent_integration import AgentLoopAdapter
from python.modules.web4_runtime.cip_runtime import CipRuntime
from python.modules.web4_runtime.hcp_runtime import HcpRuntime
from python.modules.web4_runtime.lip_runtime import LipRuntime
from python.modules.web4_runtime.protocol_router import Web4ProtocolRouter


def main() -> None:
    trust = TrustFSM()
    cip = CipRuntime(CipIdentity("demo-agent", "fp-demo"), trust)
    hcp = HcpRuntime(identity=HcpIdentity("demo-agent", "fp-demo"))
    lip = LipRuntime(identity=LipIdentity("demo-agent", "fp-demo"))
    router = Web4ProtocolRouter(cip=cip, hcp=hcp, lip=lip)
    agent = AgentLoop(handler=lambda text: f"agent_response:{text}")
    adapter = AgentLoopAdapter(agent_loop=agent, router=router)

    receiver = CipIdentity("peer", "fp-peer")
    envelope = cip.build_hello(receiver)
    result = adapter.handle_envelope(envelope)
    print("WEB4 demo result:", result)


if __name__ == "__main__":
    main()
