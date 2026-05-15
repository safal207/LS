import json

import pytest

from ls.agent_shell.cli import (
    _council_quality_path,
    load_council_quality_artifact,
    save_council_quality_artifact,
)


@pytest.mark.parametrize(
    "cycle_id",
    [
        "",
        ".",
        "..",
        "../secret",
        "nested/secret",
        "nested\\secret",
        "/tmp/secret",
        "cycle id with spaces",
        "cycle:id",
        "cycle%2Fid",
    ],
)
def test_council_quality_path_rejects_unsafe_cycle_ids(tmp_path, cycle_id):
    with pytest.raises(ValueError):
        _council_quality_path(tmp_path, cycle_id)


def test_council_quality_path_keeps_artifact_inside_quality_dir(tmp_path):
    path = _council_quality_path(tmp_path, "cycle-001_ok.v1")

    assert path == tmp_path.resolve() / "cycle-001_ok.v1.json"
    assert path.parent == tmp_path.resolve()


def test_council_quality_save_and_load_strips_internal_path(tmp_path):
    path = save_council_quality_artifact(
        tmp_path,
        "cycle-001",
        {
            "cycle_id": "cycle-001",
            "_path": "/tmp/should-not-persist",
            "operator_guidance": {"risk_state": "watch"},
        },
    )

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert "_path" not in raw

    loaded = load_council_quality_artifact(tmp_path, "cycle-001")
    assert loaded["cycle_id"] == "cycle-001"
    assert loaded["_path"] == str(path)
