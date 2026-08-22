import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills/factiq/SKILL.md").read_text(encoding="utf-8")
PLAYBOOK = (
    ROOT / "references/report-patterns/earnings-intelligence.md"
).read_text(encoding="utf-8")
SCHEMAS = (ROOT / "references/data/schemas.md").read_text(encoding="utf-8")
SKILL_EARNINGS = SKILL.split("| `search_earnings_transcripts`", 1)[1].split(
    "| `search_media_appearances`", 1
)[0]
PLAYBOOK_RETRIEVAL = PLAYBOOK.split("### How lexical retrieval behaves", 1)[1].split(
    "## The Six Workflows", 1
)[0]
SCHEMAS_EARNINGS = next(
    line for line in SCHEMAS.splitlines() if "search_earnings_transcripts" in line
)


class EarningsDocumentationContractTests(unittest.TestCase):
    """Protect load-bearing earnings instructions from semantic drift."""

    def test_retrieval_describes_strict_loose_and_trigram_tiers(self):
        for text in (SKILL_EARNINGS, PLAYBOOK_RETRIEVAL, SCHEMAS_EARNINGS):
            normalized = " ".join(text.lower().split())
            self.assertIn("strict", normalized)
            self.assertIn("loose", normalized)
            self.assertIn("partial", normalized)
            self.assertIn("trigram", normalized)
        for stale_claim in (
            "all query terms must match",
            "full claim spine",
            "mostly the **latest call only**",
        ):
            self.assertNotIn(stale_claim, SKILL_EARNINGS.lower())
            self.assertNotIn(stale_claim, PLAYBOOK.lower())

    def test_single_call_workflow_is_coverage_first_and_quarter_pinned(self):
        section = PLAYBOOK.split("### 1. Single-call earnings note", 1)[1].split(
            "### 2.", 1
        )[0]
        coverage_at = section.index('search_target="coverage"')
        claims_at = section.index('search_target="claims"')
        pressure_at = section.index('search_target="pressure_points"')
        self.assertLess(coverage_at, claims_at)
        self.assertLess(claims_at, pressure_at)
        self.assertIn('quarter_filter="<exact FY...Q...>"', section)
        self.assertIn("cap", section.lower())

    def test_target_applicability_and_evidence_rules_are_explicit(self):
        matrix = PLAYBOOK.split("## Target and Filter Reference", 1)[1].split(
            "## The Six Workflows", 1
        )[0]
        for target in (
            "claims",
            "pressure_points",
            "disclosure_profile",
            "coverage",
        ):
            self.assertIn(f"`{target}`", matrix)
        self.assertIn("section` is ignored", matrix)
        self.assertIn("quarter_filter` is ignored", matrix)
        self.assertIn("do not narrow the inventory", matrix)
        for field in (
            "verbatim_quote",
            "canonical_statement",
            "analyst_hypothesized",
            "mgmt_declined_to_confirm",
            "denominator",
            "sec_guidance",
        ):
            self.assertIn(field, PLAYBOOK)

    def test_bespoke_tool_cap_never_routes_to_transcript_sql(self):
        cap_guidance = SKILL.split(
            "Every row-returning tool (`run_sql`, `get_series`,", 1
        )[1].split("### Publishing", 1)[0]
        self.assertIn("Never query the gated `transcripts` schema", cap_guidance)
        self.assertIn("bounded searches", cap_guidance)
        self.assertNotIn("aggregate or compute in SQL", cap_guidance)

    def test_multi_period_workflows_pin_and_disclose_periods(self):
        self.assertIn("### 5. Multi-quarter change", PLAYBOOK)
        cross_company = PLAYBOOK.split("### 4. Cross-company", 1)[1].split(
            "### 5.", 1
        )[0]
        self.assertIn("exact quarter", cross_company)
        self.assertIn("calendar_date", cross_company)

    def test_missing_company_coverage_is_reported_without_false_positives(self):
        feedback = SKILL.split("### Feedback", 1)[1].split(
            "### Terminal charts", 1
        )[0]
        normalized_feedback = " ".join(feedback.split())
        normalized_playbook = " ".join(PLAYBOOK.split())

        self.assertIn('category="missing_data"', normalized_feedback)
        self.assertIn(
            "supported WorldDB database, cache, and provider lookup",
            normalized_feedback,
        )
        for function in (
            "OVERVIEW",
            "INCOME_STATEMENT",
            "BALANCE_SHEET",
            "CASH_FLOW",
            "EARNINGS",
        ):
            self.assertIn(f"`{function}`", normalized_feedback)
        self.assertIn('search_target="coverage"', normalized_feedback)
        self.assertIn("exact ticker + `quarter_filter`", normalized_feedback)
        self.assertIn(
            "ticker, exact period, and observed missing coverage",
            normalized_feedback,
        )
        self.assertIn("topical or lexical query", normalized_feedback)
        self.assertIn("Slack delivery failure", normalized_feedback)
        self.assertIn(
            "personal details or conversation content", normalized_feedback
        )

        self.assertIn(
            'send_feedback` with `category="missing_data"', normalized_playbook
        )
        self.assertIn(
            "empty-query call using that ticker + exact `quarter_filter`",
            normalized_playbook,
        )
        self.assertIn("do not file `missing_data` solely", normalized_playbook)


if __name__ == "__main__":
    unittest.main()
