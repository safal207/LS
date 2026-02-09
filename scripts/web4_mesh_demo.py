from python.modules.protocols.cip import CipIdentity
from python.modules.protocols.lip import LipIdentity, LipSource
from python.modules.protocols.trust import TrustFSM, TrustState
from python.modules.web4_runtime.cip_runtime import CipRuntime
from python.modules.web4_runtime.lip_runtime import LipRuntime
from python.modules.web4_runtime.rtt import RttConfig, RttSession


def main() -> None:
    trust = TrustFSM()
    node_a = CipRuntime(CipIdentity("node-a", "fp-a"), trust)
    node_b = CipRuntime(CipIdentity("node-b", "fp-b"), trust)

    rtt = RttSession[str](config=RttConfig(max_queue=4))
    hello = node_a.build_hello(node_b.identity)
    rtt.send(str(hello))
    received = rtt.receive()
    print("RTT received:", received)

    lip = LipRuntime(LipIdentity("node-a", "fp-a"))
    source = LipSource("https://mesh.local/data", "tier1", "now")
    update = lip.build_source_update(LipIdentity("node-b", "fp-b"), {"mesh": "ok"}, source)
    deferred = lip.defer_if_untrusted(update, TrustState.UNTRUSTED)
    print("Deferred while untrusted:", deferred)
    released = lip.release_deferred(TrustState.TRUSTED)
    print("Released after trust:", released)


if __name__ == "__main__":
    main()
