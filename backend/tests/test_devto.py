import os
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from devto import PublisherError, normalize_platforms, post_to_platform, publish_to_platforms


class PublishingProviderTests(unittest.TestCase):
    def test_normalize_platforms_defaults_to_devto_and_deduplicates(self):
        self.assertEqual(normalize_platforms(None), ["devto"])
        self.assertEqual(
            normalize_platforms(["dev.to", "hashnode", "devto", "custom"]),
            ["devto", "hashnode", "webhook"],
        )

    def test_normalize_platforms_rejects_unknown_provider(self):
        with self.assertRaises(PublisherError):
            normalize_platforms(["wordpress"])

    @patch.dict(os.environ, {"DEVTO_API_KEY": "devto-token"}, clear=True)
    @patch("devto.time.sleep", return_value=None)
    @patch("devto.requests.post")
    def test_devto_payload_preserves_existing_default_publish_flow(self, post_mock, _sleep_mock):
        post_mock.return_value = Mock(
            status_code=201,
            json=lambda: {"url": "https://dev.to/example/leetcode-two-sum"},
        )

        result = post_to_platform("Two Sum", "## Solution")

        self.assertEqual(result["url"], "https://dev.to/example/leetcode-two-sum")
        post_mock.assert_called_once()
        _, kwargs = post_mock.call_args
        self.assertEqual(kwargs["headers"]["api-key"], "devto-token")
        self.assertEqual(kwargs["json"]["article"]["title"], "LeetCode Solution: Two Sum")
        self.assertEqual(kwargs["json"]["article"]["body_markdown"], "## Solution")
        self.assertTrue(kwargs["json"]["article"]["published"])
        self.assertEqual(kwargs["json"]["article"]["tags"], ["leetcode", "dsa", "programming", "tutorial"])

    @patch.dict(os.environ, {"DEVTO_API_KEY": "devto-token"}, clear=True)
    @patch("devto.time.sleep", return_value=None)
    @patch("devto.requests.post")
    def test_publish_to_platforms_returns_per_platform_errors(self, post_mock, _sleep_mock):
        post_mock.return_value = Mock(
            status_code=201,
            json=lambda: {"url": "https://dev.to/example/leetcode-two-sum"},
        )

        results = publish_to_platforms(
            "Two Sum",
            "## Solution",
            platforms=["devto", "hashnode"],
            published=False,
            tags=["LeetCode", "Dynamic Programming"],
        )

        self.assertEqual(results[0]["platform"], "devto")
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(results[1]["platform"], "hashnode")
        self.assertEqual(results[1]["status"], "error")
        self.assertIn("HASHNODE_TOKEN", results[1]["message"])

        _, kwargs = post_mock.call_args
        self.assertFalse(kwargs["json"]["article"]["published"])
        self.assertEqual(kwargs["json"]["article"]["tags"], ["leetcode", "dynamic-programming"])


if __name__ == "__main__":
    unittest.main()
