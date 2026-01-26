import pytest
import time
import json
import os
import shutil
from unittest.mock import MagicMock, patch
import sys

# Ensure python modules can be imported
sys.path.append(os.getcwd())

from python.modules.self_improving_v2 import SelfImprovingBrainV2, LocalEmbedder

# Mock RustOptimizer
class MockRustOptimizer:
    def __init__(self, db_path=None):
        self.available = True
        self.storage = {}
        self.patterns = []

    def save_to_storage(self, key, data):
        self.storage[key] = data

    def load_from_storage(self, key):
        return self.storage.get(key)

    def add_patterns(self, patterns):
        self.patterns.extend(patterns)

    def find_similar(self, query, k):
        # Mock similar search: return first k patterns if available
        # Returning list of (id, score)
        return [(p[0], 0.9) for p in self.patterns[:k]]

    def reindex(self):
        pass

    def optimize_memory(self):
        return 100

@pytest.fixture
def clean_env():
    if os.path.exists("data/test_patterns.db"):
        if os.path.isdir("data/test_patterns.db"):
             shutil.rmtree("data/test_patterns.db", ignore_errors=True)
        else:
             os.remove("data/test_patterns.db")
    if os.path.exists("config/test_config.yaml"):
        os.remove("config/test_config.yaml")
    if os.path.exists("data/learning_fallback.jsonl"):
        os.remove("data/learning_fallback.jsonl")
    yield
    # Cleanup
    if os.path.exists("data/test_patterns.db"):
        if os.path.isdir("data/test_patterns.db"):
             shutil.rmtree("data/test_patterns.db", ignore_errors=True)
        else:
             os.remove("data/test_patterns.db")
    if os.path.exists("config/test_config.yaml"):
        os.remove("config/test_config.yaml")
    if os.path.exists("data/learning_fallback.jsonl"):
        os.remove("data/learning_fallback.jsonl")

def test_local_embedder():
    embedder = LocalEmbedder(dim=10)
    texts = ["hello", "world"]
    embeddings = embedder.embed(texts)
    assert len(embeddings) == 2
    assert len(embeddings[0]) == 10
    assert isinstance(embeddings[0][0], float)

def test_brain_initialization(clean_env):
    # Create temp config
    with open("config/test_config.yaml", "w") as f:
        f.write("batch_size: 2\ncluster_interval: 1\nembedding_provider: local\n")

    rust_mock = MockRustOptimizer()
    brain = SelfImprovingBrainV2(config_path="config/test_config.yaml", rust_instance=rust_mock)

    assert brain.config["batch_size"] == 2
    brain.stop()

def test_learning_flow(clean_env):
    # Create temp config
    with open("config/test_config.yaml", "w") as f:
        f.write("batch_size: 2\ncluster_interval: 10\nembedding_provider: local\n")

    rust_mock = MockRustOptimizer()
    brain = SelfImprovingBrainV2(config_path="config/test_config.yaml", rust_instance=rust_mock)

    session_data = [
        {"question": "q1", "answer": "a1", "timestamp": 100},
        {"question": "q2", "answer": "a2", "timestamp": 101},
        {"question": "q3", "answer": "a3", "timestamp": 102}
    ]

    brain.learn_from_session(session_data)

    # Wait for processing (flush)
    brain.flush()

    # Check if processed
    # Batch size is 2, so first 2 should be processed immediately, last 1 might wait or be processed if we wait enough
    # With flush logic, it waits until queue empty. Worker might pick up last item after timeout.
    time.sleep(1.5) # Allow worker timeout cycle (1.0s) to pick up remaining item

    assert brain.processed_count == 3
    assert len(rust_mock.patterns) == 3
    assert len(rust_mock.storage) == 3

    brain.stop()

def test_fallback_save(clean_env):
    # Rust unavailable
    rust_mock = MockRustOptimizer()
    rust_mock.available = False

    with open("config/test_config.yaml", "w") as f:
        f.write("batch_size: 1\n")

    brain = SelfImprovingBrainV2(config_path="config/test_config.yaml", rust_instance=rust_mock)

    data = [{"question": "fq", "answer": "fa", "timestamp": 200}]
    brain.learn_from_session(data)
    brain.flush()
    time.sleep(1.5)

    assert brain.processed_count == 1
    # Check fallback file
    fallback_path = "data/learning_fallback.jsonl"
    assert os.path.exists(fallback_path)
    with open(fallback_path, 'r') as f:
        lines = f.readlines()
        # It's append mode, so we check last line
        last_line = json.loads(lines[-1])
        assert last_line["question"] == "fq"

    brain.stop()

def test_search_similar(clean_env):
    rust_mock = MockRustOptimizer()
    rust_mock.patterns = [("pattern_1", [0.1]*10)]
    rust_mock.storage["pattern_1"] = json.dumps({"question": "sq", "answer": "sa"}).encode('utf-8')

    brain = SelfImprovingBrainV2(rust_instance=rust_mock)
    results = brain.search_similar("test", k=1)

    assert len(results) == 1
    assert results[0]["question"] == "sq"
    assert results[0]["score"] == 0.9

    brain.stop()
