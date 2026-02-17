from modules.web4_runtime.flow import BackpressureStrategy, GlobalFlowController
from modules.web4_runtime.rtt import RttConfig, RttSession


def test_global_flow_proportional_strategy() -> None:
    controller = GlobalFlowController[str](
        max_total_pending=100,
        per_session_limit=50,
        strategy=BackpressureStrategy.PROPORTIONAL,
    )

    session1 = RttSession[str](config=RttConfig(max_queue=50))
    session2 = RttSession[str](config=RttConfig(max_queue=50))

    controller.register_session(session1)
    controller.register_session(session2)

    for _ in range(50):
        assert controller.can_enqueue(session1)
        controller.on_enqueue(session1)

    assert controller.can_enqueue(session2)

    for _ in range(50):
        assert controller.can_enqueue(session2)
        controller.on_enqueue(session2)

    assert not controller.can_enqueue(session1)
    assert not controller.can_enqueue(session2)


def test_dynamic_strategy_switching() -> None:
    controller = GlobalFlowController[str](
        max_total_pending=10,
        per_session_limit=10,
        strategy=BackpressureStrategy.FAIR,
    )
    session = RttSession[str](config=RttConfig(max_queue=10))
    controller.register_session(session)

    assert controller.can_enqueue(session)
    controller.set_strategy(BackpressureStrategy.PRIORITY)
    assert controller.can_enqueue(session)
