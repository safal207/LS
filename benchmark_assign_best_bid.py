import time
import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from market_layer_mvp.app import crud
from market_layer_mvp.app.models import Base, Project, Agent, Task, Bid

def setup_benchmark_db(num_bids=100):
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    crud.ensure_governance_defaults(db)

    project = crud.create_project(db, name="Benchmark Project", treasury_balance=10000)
    task = crud.create_task(db, project_id=project.id, title="Benchmark Task", description="...", reward=1000)

    agents = []
    for i in range(num_bids):
        agent = crud.create_agent(db, name=f"Agent {i}")
        agents.append(agent)

    for i in range(num_bids):
        crud.submit_bid(db, task_id=task.id, agent_id=agents[i].id, price=100 + i, eta_hours=24 + i)

    db.commit()
    return db, task.id

def benchmark():
    num_bids = 200
    db, task_id = setup_benchmark_db(num_bids)

    # Warm up
    # crud.assign_best_bid(db, task_id=task_id) # This actually changes state

    # We need to reset the task status and bid status to run it multiple times if we wanted to,
    # but let's just measure one execution with many bids.

    start_time = time.perf_counter()
    crud.assign_best_bid(db, task_id=task_id)
    end_time = time.perf_counter()

    print(f"Time taken for {num_bids} bids: {end_time - start_time:.4f} seconds")

if __name__ == "__main__":
    benchmark()
