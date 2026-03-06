from dataclasses import dataclass

@dataclass
class SleepConfig:
    idle_timeout: int = 1800
    prune_threshold: float = 0.2
    active_window: int = 200
    reflection_energy: float = 0.05
    compost_boost_per_node: float = 0.01
    immune_threshold: float = 0.7
    immune_decay: float = 0.9
