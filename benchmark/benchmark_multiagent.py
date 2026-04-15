import time
import sys
from pathlib import Path

# Add python directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))

from modules.nca.multiagent import MultiAgentSystem
from modules.nca.agent import NCAAgent
from modules.nca.culture_engine import CultureEngine
from modules.nca.world import GridWorld
from modules.nca.orientation import OrientationCenter

def setup_system(num_agents=500):
    system = MultiAgentSystem()
    for i in range(num_agents):
        world = GridWorld(size=10, start_position=0, goal_position=9)
        orientation = OrientationCenter(identity=f"agent-{i}")
        agent = NCAAgent(world=world, orientation=orientation)

        # Populate culture engine with some data
        agent.culture = CultureEngine()
        agent.culture.norms = {f"norm_{j}": 0.5 for j in range(10)}
        agent.culture.traditions = {f"tradition_{j}": 0.8 for j in range(10)}
        agent.culture.norm_conflicts = [{"norm": "norm_0", "severity": 0.4}]
        agent.culture.culturalalignmentscore = 0.9

        system.add_agent(agent)
    return system

def run_benchmark(system, iterations=100):
    start_time = time.perf_counter()
    for _ in range(iterations):
        system.collective_state()
    end_time = time.perf_counter()
    return end_time - start_time

if __name__ == "__main__":
    num_agents = 500
    iterations = 50
    print(f"Setting up system with {num_agents} agents...")
    system = setup_system(num_agents)
    print(f"Running benchmark with {iterations} iterations...")
    total_time = run_benchmark(system, iterations)
    print(f"Total time for {iterations} calls to collective_state: {total_time:.4f} seconds")
    print(f"Average time per call: {total_time/iterations:.6f} seconds")
