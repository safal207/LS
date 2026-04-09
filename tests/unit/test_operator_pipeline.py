# -*- coding: utf-8 -*-
"""Neutral entrypoint for the historical multimodal pipeline test suite."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from test_interview_pipeline import *  # noqa: F401,F403
