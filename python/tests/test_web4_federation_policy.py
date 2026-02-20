from modules.protocols.cip import CipIdentity, build_envelope
from modules.web4_runtime.federation_policy import (
    AllowAllFederationPolicy,
    DenylistFederationPolicy,
)


def _envelope(sender_id: str = "sender-a", receiver_id: str = "receiver-b", message_type: str = "HELLO") -> dict:
    sender = CipIdentity(sender_id, f"fp-{sender_id}")
    receiver = CipIdentity(receiver_id, f"fp-{receiver_id}")
    return build_envelope(message_type, sender, receiver, {"k": "v"})


def test_allow_all_federation_policy_allows_any_envelope() -> None:
    policy = AllowAllFederationPolicy()
    decision = policy.evaluate(_envelope())

    assert decision.allowed is True
    assert decision.reason == "allowed"
    assert decision.policy == "allow_all"


def test_denylist_policy_blocks_message_type_before_peer_checks() -> None:
    policy = DenylistFederationPolicy.from_iterables(
        blocked_senders=["sender-a"],
        blocked_receivers=["receiver-b"],
        blocked_message_types=["HELLO"],
    )
    decision = policy.evaluate(_envelope(message_type="HELLO"))

    assert decision.allowed is False
    assert decision.reason == "blocked_message_type:HELLO"
    assert decision.policy == "denylist"


def test_denylist_policy_blocks_sender_and_receiver() -> None:
    sender_policy = DenylistFederationPolicy.from_iterables(blocked_senders=["sender-a"])
    sender_decision = sender_policy.evaluate(_envelope(sender_id="sender-a"))
    assert sender_decision.allowed is False
    assert sender_decision.reason == "blocked_sender:sender-a"

    receiver_policy = DenylistFederationPolicy.from_iterables(blocked_receivers=["receiver-b"])
    receiver_decision = receiver_policy.evaluate(_envelope(receiver_id="receiver-b"))
    assert receiver_decision.allowed is False
    assert receiver_decision.reason == "blocked_receiver:receiver-b"


def test_denylist_policy_allows_non_matching_envelope() -> None:
    policy = DenylistFederationPolicy.from_iterables(
        blocked_senders=["other-sender"],
        blocked_receivers=["other-receiver"],
        blocked_message_types=["FACT_CHALLENGE"],
    )
    decision = policy.evaluate(_envelope(sender_id="sender-a", receiver_id="receiver-b", message_type="HELLO"))

    assert decision.allowed is True
    assert decision.reason == "allowed"
    assert decision.policy == "denylist"
