import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "skills/factiq/SKILL.md").read_text(encoding="utf-8")
PLAYBOOK = (
    ROOT / "references/report-patterns/media-intelligence.md"
).read_text(encoding="utf-8")
PATTERN_INDEX = (
    ROOT / "references/report-patterns/README.md"
).read_text(encoding="utf-8")
SCHEMAS = (ROOT / "references/data/schemas.md").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
CLAUDE_MANIFEST = json.loads(
    (ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8")
)
CLAUDE_MARKETPLACE = json.loads(
    (ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf-8")
)
CODEX_MANIFEST = json.loads(
    (ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8")
)

SKILL_MEDIA = SKILL.split("| `search_media_appearances`", 1)[1].split(
    "| `search_news`", 1
)[0]
SKILL_MEDIA_REFERENCE = SKILL.split(
    "#### Media target/filter quick reference", 1
)[1].split("### Publishing", 1)[0]
SCHEMAS_MEDIA = next(
    line for line in SCHEMAS.splitlines() if "search_media_appearances" in line
)
PLAYBOOK_NORMALIZED = " ".join(PLAYBOOK.split())


class MediaDocumentationContractTests(unittest.TestCase):
    """Protect the deterministic media contract from semantic drift."""

    def test_skill_entry_names_every_live_parameter_and_target(self):
        for parameter in (
            "query",
            "search_target",
            "company_filter",
            "person",
            "sort",
            "appearance_type",
            "claim_family",
            "date_from",
            "date_to",
            "detail",
            "limit",
        ):
            self.assertIn(f"`{parameter}", SKILL_MEDIA)

        for target in (
            "search",
            "claims",
            "passages",
            "pressure_points",
            "appearances",
            "coverage",
        ):
            self.assertIn(f"`{target}`", SKILL_MEDIA)
        for retired_alias in ("`all`", "`videos`", "`companies`"):
            self.assertNotIn(retired_alias, SKILL_MEDIA)

    def test_retrieval_is_deterministic_strict_loose_then_trigram(self):
        for text in (SKILL_MEDIA, PLAYBOOK, SCHEMAS_MEDIA):
            normalized = " ".join(text.casefold().split())
            self.assertIn("deterministic", normalized)
            self.assertIn("strict", normalized)
            self.assertIn("loose", normalized)
            self.assertIn("trigram", normalized)
            self.assertIn("no serving-time model", normalized)

        all_media_docs = "\n".join((SKILL_MEDIA, PLAYBOOK, SCHEMAS_MEDIA, README))
        for stale_claim in (
            "question-driven, not keyword-driven",
            "search agent on FactIQ's side",
            "10–30 s",
            "search compute",
            "off-script",
            "newest-first",
            "9,000+ videos",
            "900+ listed companies",
        ):
            self.assertNotIn(stale_claim.casefold(), all_media_docs.casefold())

    def test_sort_dates_filters_and_result_shapes_are_explicit(self):
        for exact in (
            'sort="relevance"',
            'sort="newest"',
            "publication/upload date",
            "case-insensitive",
            "comma-separated",
            "claim-only fields remain null",
            "company-level structured corpus",
            "timestamped YouTube URL",
        ):
            self.assertIn(exact.casefold(), SKILL_MEDIA.casefold())

        for result_term in (
            "result_kind",
            "canonical_paraphrase",
            "matching-claim count",
            "date/channel inventory",
            "attribution",
            "relevance",
        ):
            self.assertIn(result_term, SKILL_MEDIA)

        self.assertIn('incompatible with `search_target="passages"`', PLAYBOOK)
        self.assertIn("does not change catalog rows", PLAYBOOK)
        self.assertIn("does not expose source text", PLAYBOOK_NORMALIZED)
        self.assertNotIn("channel count", PLAYBOOK.casefold())

    def test_empty_query_and_row_cap_are_target_specific(self):
        for target in (
            "search",
            "claims",
            "passages",
            "pressure_points",
            "appearances",
            "coverage",
        ):
            self.assertRegex(
                SKILL_MEDIA_REFERENCE,
                rf"\| `{target}` \|.*(?:Empty query|inventory)",
            )
        self.assertIn("reaches 50 rows", SKILL_MEDIA_REFERENCE)
        self.assertIn("never query the gated", SKILL_MEDIA_REFERENCE.casefold())
        self.assertNotIn("aggregate or compute in SQL", SKILL_MEDIA_REFERENCE)

    def test_evidence_and_workflows_prevent_false_quotes(self):
        self.assertIn(
            "`canonical_paraphrase` must stay outside quotation marks",
            SKILL_MEDIA_REFERENCE,
        )
        self.assertIn("not a transcript quotation", PLAYBOOK_NORMALIZED)
        self.assertIn("independently verify", PLAYBOOK)
        for heading in (
            "### 1. Coverage and date-window selection",
            "### 2. Broad theme sweep and drill-down",
            "### 3. Person or company timeline",
            "### 4. Cross-company theme comparison",
            "### 5. Media versus earnings",
        ):
            self.assertIn(heading, PLAYBOOK)
        for term in (
            "verbatim_quote",
            "publication date is not automatically an earnings-call period",
            "venue, audience, question, and date",
            "tone shift",
        ):
            self.assertIn(term, PLAYBOOK)

    def test_all_plugin_surfaces_advertise_media(self):
        self.assertIn("media-intelligence.md", PATTERN_INDEX)
        self.assertIn("search_media_appearances", README)
        self.assertIn("media appearances", README.casefold())
        self.assertIn("media appearances", CLAUDE_MANIFEST["description"].casefold())
        self.assertIn(
            "media appearances",
            CLAUDE_MARKETPLACE["plugins"][0]["description"].casefold(),
        )
        self.assertIn(
            "executive media appearances",
            CODEX_MANIFEST["interface"]["longDescription"],
        )


if __name__ == "__main__":
    unittest.main()
