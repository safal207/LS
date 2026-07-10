import sys
from unittest.mock import MagicMock

# Mock websockets before importing anything that uses it
sys.modules["websockets"] = MagicMock()
sys.modules["websockets.asyncio"] = MagicMock()
sys.modules["websockets.asyncio.client"] = MagicMock()
sys.modules["websockets.asyncio.server"] = MagicMock()
sys.modules["websockets.exceptions"] = MagicMock()
sys.modules["websockets.protocol"] = MagicMock()

import asyncio
import json
import unittest
from python.modules.web4_mesh.transport_ws import WebSocketTransport

class TestWebSocketSizeLimitComprehensive(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.node = MagicMock()
        self.node.peer_id = "test-node"
        self.transport = WebSocketTransport(node=self.node)
        self.limit = self.transport._MAX_MESSAGE_BYTES

    def test_str_at_limit(self):
        raw = "a" * self.limit
        with self.assertLogs("python.modules.web4_mesh.transport_ws", level="WARNING") as cm:
            result = self.transport._deserialize_envelope(raw)
            self.assertIsNone(result)
            self.assertFalse(any("Dropped oversized message" in output for output in cm.output))
            self.assertTrue(any("Invalid envelope JSON" in output for output in cm.output))

    def test_str_over_limit_bytes_but_not_chars(self):
        # Using a multibyte character (e.g., emoji or specialized symbol)
        # '⚡' is 3 bytes in UTF-8
        # We want to create a string that is over the byte limit but under the char limit.
        num_chars = self.limit // 2
        # If each char is 3 bytes, then total bytes = (self.limit // 2) * 3 = 1.5 * self.limit
        raw = "⚡" * num_chars

        expected_bytes = num_chars * 3
        self.assertGreater(expected_bytes, self.limit)
        self.assertLess(len(raw), self.limit)

        with self.assertLogs("python.modules.web4_mesh.transport_ws", level="WARNING") as cm:
            result = self.transport._deserialize_envelope(raw)
            self.assertIsNone(result)
            self.assertTrue(any(f"Dropped oversized message ({expected_bytes} bytes)" in output for output in cm.output))

    def test_str_over_limit_simple(self):
        raw = "a" * (self.limit + 1)
        with self.assertLogs("python.modules.web4_mesh.transport_ws", level="WARNING") as cm:
            result = self.transport._deserialize_envelope(raw)
            self.assertIsNone(result)
            self.assertTrue(any(f"Dropped oversized message ({self.limit + 1} bytes)" in output for output in cm.output))

    def test_bytes_at_limit(self):
        raw = b"a" * self.limit
        with self.assertLogs("python.modules.web4_mesh.transport_ws", level="WARNING") as cm:
            result = self.transport._deserialize_envelope(raw)
            self.assertIsNone(result)
            self.assertFalse(any("Dropped oversized message" in output for output in cm.output))

    def test_bytes_over_limit(self):
        raw = b"a" * (self.limit + 1)
        with self.assertLogs("python.modules.web4_mesh.transport_ws", level="WARNING") as cm:
            result = self.transport._deserialize_envelope(raw)
            self.assertIsNone(result)
            self.assertTrue(any(f"Dropped oversized message ({self.limit + 1} bytes)" in output for output in cm.output))

    def test_bytearray_over_limit(self):
        raw = bytearray(b"a" * (self.limit + 1))
        with self.assertLogs("python.modules.web4_mesh.transport_ws", level="WARNING") as cm:
            result = self.transport._deserialize_envelope(raw)
            self.assertIsNone(result)
            self.assertTrue(any(f"Dropped oversized message ({self.limit + 1} bytes)" in output for output in cm.output))

if __name__ == "__main__":
    unittest.main()
