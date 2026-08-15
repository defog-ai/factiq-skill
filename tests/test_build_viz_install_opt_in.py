import contextlib
import importlib.util
import io
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "build_viz", ROOT / "scripts" / "build_viz.py"
)
assert SPEC and SPEC.loader
build_viz = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_viz)


class DocumentationContractTests(unittest.TestCase):
    def test_readme_names_all_supported_clients_and_canonical_guides(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for expected in (
            "Claude (web, desktop, and Cowork)",
            "ChatGPT Desktop",
            "https://www.factiq.com/claude",
            "https://www.factiq.com/chatgpt",
            "https://www.factiq.com/claude-code",
            "https://www.factiq.com/codex",
        ):
            self.assertIn(expected, readme)

    def test_public_guidance_requires_explicit_install_opt_in(self):
        for relative_path in (
            "README.md",
            "skills/factiq/SKILL.md",
            "references/output/viz-guide.md",
        ):
            text = (ROOT / relative_path).read_text(encoding="utf-8")
            self.assertIn("--install-deps", text)
            self.assertNotIn("Installs Playwright + Chromium", text)


class RenderDependencyOptInTests(unittest.TestCase):
    def test_install_deps_is_off_by_default_and_requires_a_flag(self):
        parser = build_viz.build_parser()

        default = parser.parse_args(["render", "viz.html"])
        opted_in = parser.parse_args(["render", "viz.html", "--install-deps"])

        self.assertFalse(default.install_deps)
        self.assertTrue(opted_in.install_deps)

    def test_missing_playwright_does_not_run_install_commands_without_opt_in(self):
        real_import = __import__

        def import_without_playwright(name, *args, **kwargs):
            if name == "playwright.sync_api":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        stderr = io.StringIO()
        with (
            mock.patch("builtins.__import__", side_effect=import_without_playwright),
            mock.patch.object(build_viz.os.path, "exists", return_value=False),
            mock.patch.object(build_viz.subprocess, "run") as run,
            mock.patch.object(build_viz.os, "execve") as execve,
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            build_viz._ensure_render_env(install_deps=False)

        self.assertEqual(raised.exception.code, 6)
        run.assert_not_called()
        execve.assert_not_called()
        self.assertIn("did not install anything", stderr.getvalue())
        self.assertIn("--install-deps", stderr.getvalue())

    def test_existing_factiq_render_environment_is_reused_without_opt_in(self):
        real_import = __import__

        def import_without_playwright(name, *args, **kwargs):
            if name == "playwright.sync_api":
                raise ImportError("not installed")
            return real_import(name, *args, **kwargs)

        with (
            mock.patch("builtins.__import__", side_effect=import_without_playwright),
            mock.patch.object(build_viz.os.path, "exists", return_value=True),
            mock.patch.object(build_viz, "_venv_has_playwright", return_value=True),
            mock.patch.object(build_viz.os, "execve") as execve,
        ):
            build_viz._ensure_render_env(install_deps=False)

        execve.assert_called_once()

    def test_missing_chromium_is_not_installed_without_opt_in(self):
        chromium = mock.Mock()
        chromium.launch.side_effect = RuntimeError("Executable doesn't exist")
        stderr = io.StringIO()

        with (
            mock.patch.object(build_viz, "_install_chromium") as install,
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as raised,
        ):
            build_viz._launch_chromium(chromium, install_deps=False)

        self.assertEqual(raised.exception.code, 6)
        install.assert_not_called()
        self.assertIn("terminal/table fallback", stderr.getvalue())

    def test_missing_chromium_can_be_installed_after_opt_in(self):
        browser = object()
        chromium = mock.Mock()
        chromium.launch.side_effect = [
            RuntimeError("Executable doesn't exist"),
            browser,
        ]

        with mock.patch.object(build_viz, "_install_chromium") as install:
            result = build_viz._launch_chromium(chromium, install_deps=True)

        install.assert_called_once_with()
        self.assertIs(result, browser)


if __name__ == "__main__":
    unittest.main()
