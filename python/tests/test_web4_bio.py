from modules.web4_bio.agent_roles import AgentRoles
from modules.web4_bio.epigenesis import EpigenesisPrinciples
from modules.web4_bio.models import BioAdaptiveEdge, BioAdaptiveNode, EpigenesisModel, MorphogenesisModel, TeleogenesisModel
from modules.web4_bio.morphogenesis import MorphogenesisPrinciples
from modules.web4_bio.teleogenesis import TeleogenesisPrinciples


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


def test_bio_models() -> None:
    morph = MorphogenesisModel()
    epi = EpigenesisModel()
    telo = TeleogenesisModel()
    assert "edge_strength" in morph.signals
    assert "observability" in epi.signals
    assert "human_support" in telo.goals


def test_bio_adaptive_entities() -> None:
    node = BioAdaptiveNode("node-a")
    edge = BioAdaptiveEdge("edge-a-b")
    assert node.node_id == "node-a"
    assert edge.edge_id == "edge-a-b"
