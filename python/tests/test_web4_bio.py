from python.modules.web4_bio.agent_roles import AgentRoles
from python.modules.web4_bio.epigenesis import EpigenesisPrinciples
from python.modules.web4_bio.morphogenesis import MorphogenesisPrinciples
from python.modules.web4_bio.teleogenesis import TeleogenesisPrinciples


def test_morphogenesis_principles() -> None:
    principles = MorphogenesisPrinciples()
    assert "topology_change" in principles.signals


def test_epigenesis_principles() -> None:
    principles = EpigenesisPrinciples()
    assert "trust_transition" in principles.signals


def test_teleogenesis_principles() -> None:
    principles = TeleogenesisPrinciples()
    assert "human_support" in principles.goals


def test_agent_roles() -> None:
    roles = AgentRoles()
    assert "guardian" in roles.roles
