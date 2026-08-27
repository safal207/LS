from __future__ import annotations

import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_python_metadata_matches_resolved_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]

    # Dependabot derives its interpreter from this field before consulting the
    # pip-compile header. The committed lock includes packages whose supported
    # floor is Python 3.11, so advertising an older interpreter is not valid.
    assert project["requires-python"] == ">=3.11"
    assert "Programming Language :: Python :: 3.11" in project["classifiers"]
    assert "Programming Language :: Python :: 3.9" not in project["classifiers"]
    assert "Programming Language :: Python :: 3.10" not in project["classifiers"]

    locked_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for dependency in (
        "numpy",
        "pywavelets",
        "scikit-image",
        "scikit-learn",
        "scipy",
        "tifffile",
    ):
        assert re.search(rf"(?m)^{re.escape(dependency)}==", locked_requirements)


def test_legacy_readme_uses_the_root_python_floor() -> None:
    readme = (ROOT / "README_LEGACY.md").read_text(encoding="utf-8")

    assert "Python 3.11+" in readme
    assert "Python-3.11%2B" in readme
    assert "Python 3.9+" not in readme
    assert "Python-3.9%2B" not in readme
