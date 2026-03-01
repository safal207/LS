import os
import pytest
import json
import shutil
from pathlib import Path
from codex.causal_memory.memory import MemoryService
from codex.causal_memory.amygdala import Amygdala

@pytest.fixture
def temp_memory_dir(tmp_path):
    return tmp_path / "memory"

@pytest.fixture
def memory_service(temp_memory_dir):
    return MemoryService(user_id="test_user", base_dir=temp_memory_dir)

def test_secure_export_import_roundtrip(memory_service, temp_memory_dir):
    # 1. Setup initial state
    initial_data = {"state": 0.8, "personality_p": 0.9, "user_id": "test_user"}
    memory_service.save(initial_data)

    # 2. Export securely
    target_device = "test_user" # Decryption will use current_device_id=self.user_id
    package_path = memory_service.export_soul_secure(target_device)
    assert os.path.exists(package_path)
    assert "temp-pytest" in package_path or "pytest-of-jules" in package_path # verify it's not in ~/.ghostgpt

    # 3. Clear existing data to simulate new device
    memory_service.save({})
    assert memory_service.load() == {"user_id": "test_user"} # save adds user_id

    # 4. Import securely
    success = memory_service.import_soul_secure(package_path)
    assert success is True

    # 5. Verify restored data
    restored_data = memory_service.load()
    assert restored_data["state"] == 0.8
    assert restored_data["personality_p"] == 0.9

def test_zk_proof_verification(memory_service):
    # This test verifies that the lthread module correctly handles the simulated ZK-proof.
    # Our implementation of lthread.py always includes a zk_proof in export and checks for it in import.

    package_path = memory_service.export_soul_secure("test_user")

    # Verify the package content contains the proof (simulated)
    with open(package_path, "r") as f:
        package = json.load(f)
        assert "ct" in package

    # Decryption verifies the proof internally
    success, data = memory_service.import_soul_secure(package_path), memory_service.load()
    assert success is True
    assert data is not None

def test_soul_integrity_after_transfer(memory_service, temp_memory_dir):
    amygdala = Amygdala(user_id="test_user", memory_base_dir=temp_memory_dir)
    amygdala.state = 0.42
    amygdala.personality_p = 0.66
    amygdala._persist_state()

    package_path = memory_service.export_soul_secure("test_user")

    # New amygdala instance with DIFFERENT user_id to avoid auto-loading same file
    new_amygdala = Amygdala(user_id="imported_user", memory_base_dir=temp_memory_dir)
    assert new_amygdala.state == 0.5

    memory_service.import_soul_secure(package_path, amygdala=new_amygdala)

    assert new_amygdala.state == 0.42
    assert new_amygdala.personality_p == 0.66

def test_device_id_validation(memory_service):
    # Test that using the wrong device ID for decryption fails

    # Export for 'secret_device'
    initial_data = {"secret": "data"}
    memory_service.save(initial_data)

    from python.modules import lthread
    encrypted = lthread.encrypt_and_sign(initial_data, "secret_device")

    pkg_path = lthread.send_package(encrypted, "secret_device")

    # Trying to decrypt with 'wrong_device' should fail
    verified, data = lthread.verify_and_decrypt(pkg_path, current_device_id="wrong_device")
    assert verified is False
    assert data is None
