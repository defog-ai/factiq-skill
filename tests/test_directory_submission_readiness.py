import json
import struct
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
            codex["interface"]["websiteURL"], "https://www.factiq.com"
        )
        self.assertEqual(
            codex["interface"]["privacyPolicyURL"],
            "https://www.factiq.com/privacy",
        )
        self.assertEqual(
            codex["interface"]["termsOfServiceURL"],
            "https://www.factiq.com/legal",
        )
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

    def test_codex_listing_copy_and_assets_fit_directory_constraints(self):
        manifest = json.loads(
            (ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        interface = manifest["interface"]

        self.assertLessEqual(len(interface["shortDescription"]), 30)
        self.assertLessEqual(len(interface["defaultPrompt"]), 3)
        for prompt in interface["defaultPrompt"]:
            self.assertLessEqual(len(prompt), 128)

        for field in ("composerIcon", "logo"):
            relative_path = interface[field]
            self.assertTrue(relative_path.startswith("./assets/"))
            asset = ROOT / relative_path.removeprefix("./")
            self.assertTrue(asset.is_file())
            self.assertLessEqual(asset.stat().st_size, 5 * 1024 * 1024)
            png = asset.read_bytes()
            self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
            width, height = struct.unpack(">II", png[16:24])
            self.assertEqual(width, height)
            self.assertGreaterEqual(width, 48)
            self.assertLessEqual(width, 4096)

    def test_skill_uses_current_market_contract_without_broad_permissions(self):
        skill = (ROOT / "skills" / "factiq" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("allowed-tools:", skill)
        self.assertIn(
            "`get_market_data` (`asset`, `data_type?`, `frequency?`, `limit?`)",
            skill,
        )
        for legacy_parameter in ("`function`", "`outputsize?`"):
            self.assertNotIn(legacy_parameter, skill)

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
