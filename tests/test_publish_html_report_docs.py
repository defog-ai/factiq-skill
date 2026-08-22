import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublishHtmlReportDocsTests(unittest.TestCase):
    def test_reuses_exact_result_without_rows_in_arguments(self):
        prior_result = {
            "columns": ["period", "value"],
            "results": [["2026-01", "UNIQUE_ROW_11428031"]],
            "_factiq_data_ref": {
                "id": "ref-exact-result",
                "expires_at": "2026-08-23T12:00:00+00:00",
            },
        }
        exact_bytes = json.dumps(
            prior_result, ensure_ascii=False, separators=(",", ":")
        ).encode()
        with tempfile.TemporaryDirectory() as directory:
            saved = Path(directory) / "result.json"
            saved.write_bytes(exact_bytes)
            self.assertEqual(saved.read_bytes(), exact_bytes)

        html = "<html><script>factiqData('jobs')</script></html>"
        publish_arguments = {
            "question": "Labor report",
            "html": html,
            "data_assets": [{"key": "jobs", "ref_id": "ref-exact-result"}],
        }
        encoded_arguments = json.dumps(publish_arguments)
        self.assertNotIn("UNIQUE_ROW_11428031", encoded_arguments)
        self.assertNotIn("results", publish_arguments)
        self.assertEqual(
            publish_arguments["data_assets"],
            [{"key": "jobs", "ref_id": prior_result["_factiq_data_ref"]["id"]}],
        )

    def test_documents_complete_publish_contract(self):
        skill = (ROOT / "skills/factiq/SKILL.md").read_text(encoding="utf-8")
        guide = (ROOT / "references/output/publish-html-report.md").read_text(
            encoding="utf-8"
        )
        shell = (ROOT / "assets/viz-shell.html").read_text(encoding="utf-8")
        combined = skill + guide
        for phrase in (
            "publish_html_report",
            "_factiq_data_ref",
            "build_viz.py\" save",
            "unassembled template",
            "share_url",
            "./data/",
        ):
            self.assertIn(phrase, combined)
        self.assertIn("async function factiqData(key)", shell)
        self.assertIn("sandboxed iframe", guide)
