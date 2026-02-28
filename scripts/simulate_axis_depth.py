import time
import logging
import sys
import unittest.mock
from pathlib import Path

# Setup paths
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "python"))

from modules.agent.loop import AgentLoop
from codex.causal_memory.amygdala import Amygdala

# Setup logging to capture yoga events
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("modules.agent.loop") # Adjusted logger name

class StatsHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.yoga_count = 0
        self.strengthened_total = 0
        self.reflections = 0

    def emit(self, record):
        msg = record.getMessage()
        if "Entering idle yoga mode" in msg:
            self.yoga_count += 1
        if "Strengthened" in msg and "strong links" in msg:
            parts = msg.split()
            try:
                count = int(parts[1])
                self.strengthened_total += count
            except:
                pass
        if "Silent reflection:" in msg:
            self.reflections += 1

stats = StatsHandler()
logger.addHandler(stats)

def run_simulation():
    print("--- Starting Axis of Awareness Simulation ---")

    # 1. Initialize Agent
    amygdala = Amygdala(persist_state=False)
    loop = AgentLoop(handler=lambda x: "Processing: " + x, amygdala=amygdala)

    # 2. Simulate 300 messages to build depth
    print(f"Simulating 300 interactions...")
    for i in range(300):
        loop.handle_input(f"Interation {i} about something deep and important")
        if i % 100 == 0:
            print(f"  Reached {i}...")

    initial_nodes = len(loop.temporal.nodes)
    avg_res_before = sum(n.resonance for n in loop.temporal.nodes.values()) / initial_nodes if initial_nodes else 0
    print(f"Nodes created: {initial_nodes}")
    print(f"Avg resonance before: {avg_res_before:.4f}")

    # 3. Simulate 20 minutes (1200 seconds) of idle time
    print("Simulating 20 minutes of idle time (advancing clocks)...")

    start_real_time = time.time()

    with unittest.mock.patch('time.time') as mock_time:
        mock_time.return_value = start_real_time
        loop.last_input_time = start_real_time # Just finished
        loop.last_yoga_time = 0.0

        # Advance 20 minutes, step by 10 seconds to hit cooldowns accurately
        for step in range(0, 1200 + 1, 10):
            current_fake_time = start_real_time + step
            mock_time.return_value = current_fake_time

            loop._maybe_enter_idle_yoga()

    avg_res_after = sum(n.resonance for n in loop.temporal.nodes.values()) / initial_nodes if initial_nodes else 0

    print("\n--- Simulation Results ---")
    print(f"Yoga triggers: {stats.yoga_count}")
    print(f"Total links strengthened (increments): {stats.strengthened_total}")
    print(f"Silent reflections: {stats.reflections}")
    print(f"Avg resonance after: {avg_res_after:.4f}")
    if avg_res_before > 0:
        print(f"Memory depth increase: {((avg_res_after - avg_res_before) / avg_res_before * 100):.2f}%")
    else:
        print("Memory depth increase: N/A")

if __name__ == "__main__":
    run_simulation()
