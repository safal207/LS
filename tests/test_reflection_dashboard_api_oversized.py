import json
import io
from unittest.mock import MagicMock, patch
import pytest
from agent.reflection_dashboard_api import ReflectionDashboardApiHandler, ContentTooLargeError

class MockRequest:
    def __init__(self, rfile, headers):
        self.rfile = rfile
        self.headers = headers

    def makefile(self, *args, **kwargs):
        return self.rfile

def test_read_json_body_oversized():
    # Setup
    headers = {"Content-Length": "1048577"}
    rfile = io.BytesIO(b'{"test": 1}')

    # We need to mock more than just rfile/headers because __init__ calls super().__init__
    # which does a lot of network stuff.
    # Instead of full instantiation, let's mock the necessary attributes on a dummy object
    # or use a more surgical approach.

    handler = MagicMock(spec=ReflectionDashboardApiHandler)
    handler.headers = headers
    handler._MAX_BODY = 1048576

    # We want to test the actual method logic
    with pytest.raises(ContentTooLargeError) as excinfo:
        ReflectionDashboardApiHandler._read_json_body(handler)

    assert "request body too large" in str(excinfo.value)

def test_read_json_body_valid():
    headers = {"Content-Length": "13"}
    rfile = io.BytesIO(b'{"test": 1}')

    handler = MagicMock(spec=ReflectionDashboardApiHandler)
    handler.headers = headers
    handler.rfile = rfile
    handler._MAX_BODY = 1048576

    result = ReflectionDashboardApiHandler._read_json_body(handler)
    assert result == {"test": 1}

def test_read_json_body_invalid_json():
    headers = {"Content-Length": "5"}
    rfile = io.BytesIO(b'{not}')

    handler = MagicMock(spec=ReflectionDashboardApiHandler)
    handler.headers = headers
    handler.rfile = rfile
    handler._MAX_BODY = 1048576

    with pytest.raises(ValueError) as excinfo:
        ReflectionDashboardApiHandler._read_json_body(handler)
    assert "invalid JSON" in str(excinfo.value)
