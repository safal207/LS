#!/usr/bin/env python3
"""Unit tests for the LS external issue watcher."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHER_PATH = ROOT / "tools" / "watch_external_issue.py"

_spec = importlib.util.spec_from_file_location("watch_external_issue", WATCHER_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot import watcher from {WATCHER_PATH}")
watcher = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = watcher
_spec.loader.exec_module(watcher)


class ExternalIssueWatcherTests(unittest.TestCase):
    def comment(
        self,
        comment_id: int,
        login: str,
        body: object = "Meaningful response",
        user_type: str = "User",
    ) -> dict:
        return {
            "id": comment_id,
            "body": body,
            "html_url": f"https://github.com/openai/codex/issues/29627#issuecomment-{comment_id}",
            "created_at": "2026-07-07T06:00:00Z",
            "user": {"login": login, "type": user_type},
        }

    def test_parse_and_replace_cursor(self) -> None:
        body = "Tracker\n\n<!-- external-watch:last-comment-id=4900562872 -->"
        self.assertEqual(4900562872, watcher.parse_cursor(body))
        updated = watcher.replace_cursor(body, 4900563000)
        self.assertEqual(4900563000, watcher.parse_cursor(updated))
        self.assertEqual(1, updated.count("external-watch:last-comment-id="))

    def test_missing_cursor_is_rejected(self) -> None:
        with self.assertRaises(watcher.WatchError):
            watcher.parse_cursor("no marker")
        with self.assertRaises(watcher.WatchError):
            watcher.replace_cursor("no marker", 1)

    def test_new_human_comments_are_selected(self) -> None:
        comments = [
            self.comment(10, "safal207", "our follow-up"),
            self.comment(11, "maintainer", "Could you share the adapter contract?"),
            self.comment(12, "review-bot[bot]", "automated", user_type="Bot"),
        ]
        result = watcher.select_new_comments(comments, 9, {"safal207"})
        self.assertEqual(12, result.next_cursor)
        self.assertEqual(1, len(result.meaningful_comments))
        self.assertEqual("maintainer", result.meaningful_comments[0]["user"]["login"])

    def test_cursor_advances_when_only_ignored_comments_appear(self) -> None:
        comments = [
            self.comment(21, "safal207", "our own comment"),
            self.comment(22, "coderabbitai[bot]", "bot output", user_type="Bot"),
        ]
        result = watcher.select_new_comments(comments, 20, {"safal207"})
        self.assertTrue(result.changed)
        self.assertEqual(22, result.next_cursor)
        self.assertEqual((), result.meaningful_comments)

    def test_old_and_malformed_comment_ids_are_ignored(self) -> None:
        comments = [
            self.comment(4, "human"),
            {"id": True, "body": "bad", "user": {"login": "human", "type": "User"}},
            {"id": "6", "body": "bad", "user": {"login": "human", "type": "User"}},
        ]
        result = watcher.select_new_comments(comments, 5, set())
        self.assertFalse(result.changed)
        self.assertEqual(5, result.next_cursor)

    def test_sanitize_excerpt_blocks_mentions_and_html(self) -> None:
        excerpt = watcher.sanitize_excerpt("Hello @team <details>secret</details>")
        self.assertIn("@\u200bteam", excerpt)
        self.assertIn("&lt;details&gt;", excerpt)
        self.assertNotIn("<details>", excerpt)

    def test_sanitize_excerpt_truncates(self) -> None:
        excerpt = watcher.sanitize_excerpt("x" * 20, limit=10)
        self.assertEqual(10, len(excerpt))
        self.assertTrue(excerpt.endswith("…"))

    def test_tracker_comment_contains_safe_links_and_excerpt(self) -> None:
        body = watcher.build_tracker_comment(
            "openai/codex",
            29627,
            [self.comment(31, "maintainer", "Please review @safal207 <script>x</script>")],
        )
        self.assertIn("https://github.com/openai/codex/issues/29627", body)
        self.assertIn("issuecomment-31", body)
        self.assertIn("@\u200bsafal207", body)
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn("<script>", body)

    def test_non_github_comment_url_is_not_linked(self) -> None:
        comment = self.comment(41, "human")
        comment["html_url"] = "https://example.com/phishing"
        body = watcher.build_tracker_comment("openai/codex", 29627, [comment])
        self.assertNotIn("example.com", body)

    def test_bot_and_empty_comments_are_not_meaningful(self) -> None:
        self.assertFalse(
            watcher.is_meaningful(
                self.comment(51, "some-bot[bot]", "hello", user_type="Bot"),
                set(),
            )
        )
        self.assertFalse(watcher.is_meaningful(self.comment(52, "human", "   "), set()))


if __name__ == "__main__":
    unittest.main()
