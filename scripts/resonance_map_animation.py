from __future__ import annotations

from collections.abc import Sequence

import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.animation import FuncAnimation

from ls.cognition.motivation_engine import AgentNeed, MotivationEngine, NeedCategory


def animate_resonance_map_with_goal_color(
    engine: MotivationEngine,
    needs: Sequence[AgentNeed],
    cycles: int = 5,
    interval_ms: int = 1_000,
    animate_size: bool = True,
) -> FuncAnimation:
    """Animate category→goal resonance where goal nodes intensify from pale to deep blue.

    Goal color and optional node size are driven by cumulative resonance of all categories
    linked to each goal. Category nodes remain green.
    """

    fig, ax = plt.subplots(figsize=(8, 6))
    graph = nx.DiGraph()

    goals = engine.generate_goals(list(needs), max_goals=len(needs))[0]
    goal_ids = {goal.id for goal in goals}
    categories = {category.value for category in NeedCategory}

    for goal_id in goal_ids:
        graph.add_node(goal_id, type="goal")
    for category in categories:
        graph.add_node(category, type="category")

    pos = nx.spring_layout(graph, seed=42)

    def update(frame: int) -> None:
        ax.clear()
        engine.run_cycle(list(needs), max_goals=len(needs))

        edges: list[tuple[str, str]] = []
        edge_widths: list[float] = []
        edge_colors: list[float] = []

        goal_strength: dict[str, float] = {goal_id: 0.0 for goal_id in goal_ids}
        for (goal_id, category_value), weight in engine.resonance_map.items():
            if goal_id not in goal_strength or category_value not in categories:
                continue
            edges.append((category_value, goal_id))
            edge_widths.append(max(0.2, abs(weight) * 5.0))
            edge_colors.append(weight)
            goal_strength[goal_id] += weight

        max_strength = max((abs(strength) for strength in goal_strength.values()), default=1.0)
        if max_strength == 0.0:
            max_strength = 1.0

        node_colors: list[tuple[float, float, float]] = []
        node_sizes: list[int] = []
        for node in graph.nodes():
            if graph.nodes[node]["type"] == "goal":
                normalized = max(0.0, min(1.0, goal_strength[node] / max_strength))
                red = 0.5 * (1.0 - normalized)
                green = 0.8 * (1.0 - normalized)
                blue = 1.0
                node_colors.append((red, green, blue))
                node_sizes.append(int(1400 + (600 * normalized)) if animate_size else 1_500)
            else:
                node_colors.append((0.5, 1.0, 0.5))
                node_sizes.append(1_400)

        nx.draw(
            graph,
            pos,
            with_labels=True,
            node_size=node_sizes,
            node_color=node_colors,
            edgelist=edges,
            width=edge_widths,
            edge_color=edge_colors,
            edge_cmap=plt.cm.viridis,
            arrowsize=20,
            ax=ax,
        )
        ax.set_title(f"Resonance Map with Goal Color — Cycle {frame + 1}")

    animation = FuncAnimation(fig, update, frames=cycles, interval=interval_ms, repeat=False)
    plt.show()
    return animation
