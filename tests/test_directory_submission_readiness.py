import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DirectorySubmissionReadinessTests(unittest.TestCase):
    def test_manifests_have_complete_factiq_publisher_metadata(self):
        plugin = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        codex = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        marketplace = json.loads(
            (ROOT / ".claude-plugin" / "marketplace.json").read_text(
                encoding="utf-8"
            )
        )

        expected_publisher = {
            "name": "FactIQ",
            "url": "https://www.factiq.com",
        }
        self.assertEqual(plugin["author"], expected_publisher)
        self.assertEqual(codex["author"], expected_publisher)
        self.assertEqual(codex["interface"]["developerName"], "FactIQ")
        self.assertEqual(
            plugin["repository"], "https://github.com/defog-ai/factiq-plugin"
        )
        self.assertEqual(plugin["license"], "MIT")
        self.assertTrue(plugin["keywords"])
        self.assertTrue(marketplace["description"])
        self.assertEqual(marketplace["owner"], expected_publisher)

    def test_claude_and_codex_versions_stay_in_sync(self):
        claude = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        codex = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertEqual(claude["version"], codex["version"])

    def test_setup_covers_terminal_and_terminal_free_auth(self):
        setup = (ROOT / "SETUP.md").read_text(encoding="utf-8")
        for expected in (
            "Claude Code",
            "/mcp",
            "Cowork has no terminal",
            "Customize → Plugins",
            "get_data_catalog",
            "Do not ask",
        ):
            self.assertIn(expected, setup)


if __name__ == "__main__":
    unittest.main()
