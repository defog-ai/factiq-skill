import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SKILL = (ROOT / "skills/factiq/SKILL.md").read_text(encoding="utf-8")
SQL_GUIDE = (ROOT / "references/data/sql-guide.md").read_text(encoding="utf-8")
CHART_SPEC = (ROOT / "references/output/chart-spec.md").read_text(encoding="utf-8")
REPORT_RULES = (ROOT / "references/report-patterns/README.md").read_text(
    encoding="utf-8"
)
JOIN = "date_trunc('month', prior.time) = date_trunc('month', cur.time) - interval '1 year'"
YOY_TRAP = SQL_GUIDE.split("## Year-over-year on monthly data", 1)[1].split(
    "## HS trade datasets", 1
)[0]


def normalized(text: str) -> str:
    return " ".join(text.lower().split())


class PeriodAlignmentDocumentationTests(unittest.TestCase):
    """A row offset is not a period offset once a month is missing; the docs
    must steer every year-over-year calculation to a date match."""

    def test_sql_guide_states_time_is_the_period_start(self):
        conventions = SQL_GUIDE.split("## Always-true conventions", 1)[1].split(
            "\n## ", 1
        )[0]
        self.assertIn(
            "**Match periods on the calendar month, never on the exact date.**",
            conventions,
        )
        self.assertIn(JOIN, conventions)

    def test_sql_guide_trap_shows_lag_as_bad_and_date_join_as_good(self):
        bad, good = YOY_TRAP.split("Good", 1)
        self.assertIn("Bad", bad)
        self.assertIn("LAG(value, 12) OVER (ORDER BY time)", bad)
        self.assertIn(JOIN, good)
        self.assertNotIn("prior.time = cur.time - interval", good)
        self.assertIn("date_trunc('quarter', ...)", good)
        self.assertIn("generate_series(", good)
        self.assertIn("ON date_trunc('month', d.time) = s.time", good)
        self.assertIn('transform="yoy_pct"', good)
        self.assertIn("series_math.py yoy", good)

    def test_sql_guide_trap_tells_the_model_to_disclose_gaps(self):
        text = normalized(YOY_TRAP)
        self.assertIn("coverage_note", text)
        self.assertIn("missing_periods", text)
        self.assertIn("partial", text)
        self.assertIn("blank", text)

    def test_sql_guide_pivot_says_a_missing_period_is_absent_not_null(self):
        pivot = SQL_GUIDE.split("## Pivoting to wide format", 1)[1].split(
            "\n## ", 1
        )[0]
        self.assertIn("absent from the pivot, not a null", pivot)

    def test_skill_get_series_row_documents_transform(self):
        row = next(line for line in SKILL.splitlines() if line.startswith("| `get_series`"))
        self.assertIn("`transform?`", row)
        self.assertIn('transform="yoy_pct"', row)
        self.assertIn('"yoy_diff"', row)
        self.assertIn("matched by calendar date", row)
        self.assertIn("`coverage_note`", row)

    def test_skill_workflow_and_subagent_template_forbid_row_offsets(self):
        compute_step = SKILL.split("**Compute deterministically.**", 1)[1].split(
            "\n5. ", 1
        )[0]
        self.assertIn("matched by date", compute_step)
        self.assertIn(JOIN, compute_step)
        self.assertIn("never compare exact", compute_step)
        self.assertIn("never `LAG(value, 12)`", compute_step)
        self.assertIn("`missing_periods`", compute_step)
        template = SKILL.split("You are a FactIQ research agent", 1)[1].split(
            "FINDINGS:", 1
        )[0]
        self.assertIn("never a 12-row offset", template)
        self.assertIn("coverage_note", template)

    def test_skill_errors_section_explains_coverage_note(self):
        errors = SKILL.split("## Errors and limits", 1)[1].split("\n## ", 1)[0]
        self.assertIn("**`coverage_note` on a result**", errors)
        self.assertIn("not an error", errors)
        self.assertIn("matching dates", errors)

    def test_report_rules_disclose_missing_periods(self):
        rules = REPORT_RULES.split("## Rules the method implies", 1)[1]
        self.assertIn("**A missing period is disclosed, not bridged.**", rules)
        self.assertIn("`coverage_note`", rules)

    def test_no_doc_endorses_a_row_offset_yoy(self):
        # `shift(12)` / a bare LAG-by-12 may appear only inside the "Bad" example
        # or in text that names it as the wrong pattern.
        for name, text in (
            ("SKILL.md", SKILL),
            ("chart-spec.md", CHART_SPEC),
            ("README.md", REPORT_RULES),
        ):
            with self.subTest(doc=name):
                self.assertNotIn(".shift(12)", text)
        self.assertNotIn("shift(12)", CHART_SPEC)
        for match in re.finditer(r"LAG\(value, 12\)", SQL_GUIDE):
            window = SQL_GUIDE[max(0, match.start() - 600) : match.start()]
            self.assertTrue(
                "Bad" in window or "spine" in window or "never" in window,
                msg=SQL_GUIDE[match.start() - 120 : match.end() + 40],
            )

    def test_chart_spec_lineage_uses_a_date_matched_calculation(self):
        calc = CHART_SPEC.split('"id": "calc"', 1)[1].split("}", 1)[0]
        self.assertIn("series_math.py yoy", calc)
        self.assertNotIn("12-month difference", calc)


def monthly_payload(start_year: int, end_year: int, missing: str) -> dict:
    rows = []
    level = 100.0
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            time = f"{year}-{month:02d}-01"
            level = round(level * 1.005, 4)
            if time != missing:
                rows.append([time, level])
    return {"columns": ["time", "value"], "results": rows}


def run_yoy(payload: dict, *extra: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "series.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "series_math.py"), "yoy", "--file", str(path), *extra],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )


class SeriesMathYoyGapTests(unittest.TestCase):
    """`yoy` matches on the calendar period, so a hole never shifts the
    comparison, and the periods with no prior-year value are named on stderr."""

    def parse(self, stdout: str) -> dict[str, str]:
        lines = stdout.strip().splitlines()
        self.assertEqual(lines[0].split("\t"), ["time", "value", "yoy_pct"])
        return {parts[0]: parts[2] for parts in (line.split("\t") for line in lines[1:])}

    def test_month_after_a_hole_still_compares_with_the_same_month_prior_year(self):
        for missing in ("2025-10-01", "2025-03-01"):
            with self.subTest(missing=missing):
                payload = monthly_payload(2024, 2026, missing)
                result = run_yoy(payload)
                self.assertEqual(result.returncode, 0, result.stderr)
                yoy = self.parse(result.stdout)
                # Every month after the hole must still be +6.17% on the
                # compounding fixture (1.005**12 - 1), which is only true when
                # the comparison is date-keyed; a 12-row offset gives 1.005**13.
                after_hole = [
                    time for time in yoy if time > missing and time < "2026-01-01"
                ]
                self.assertTrue(after_hole)
                for time in after_hole:
                    self.assertAlmostEqual(float(yoy[time]), 6.1678, places=3, msg=time)
                # The month one year after the hole has no prior value.
                year, rest = missing.split("-", 1)
                blank = f"{int(year) + 1}-{rest}"
                self.assertEqual(yoy[blank], "")
                self.assertNotIn(missing, yoy)
                self.assertIn("no prior-year observation for " + blank, result.stderr)
                self.assertIn("say so in the answer", result.stderr)

    def test_complete_series_prints_no_gap_note(self):
        result = run_yoy(monthly_payload(2024, 2026, missing=""))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        yoy = self.parse(result.stdout)
        self.assertEqual(yoy["2024-06-01"], "")  # first year: no prior by design
        self.assertNotEqual(yoy["2025-06-01"], "")

    def test_gap_note_names_the_group_when_grouped(self):
        payload = monthly_payload(2024, 2025, "2024-05-01")
        payload["columns"] = ["series_id", "time", "value"]
        payload["results"] = [["CPI", *row] for row in payload["results"]]
        result = run_yoy(payload, "--group-col", "series_id")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("CPI: 2025-05-01", result.stderr)


if __name__ == "__main__":
    unittest.main()
