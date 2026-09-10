from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RETIRED_NAMES = {"share_chart", "share_report", "list_my_artifacts"}


def test_public_plugin_does_not_reference_retired_publishing_tools():
    paths = [
        ROOT / "README.md",
        ROOT / ".codex-plugin/plugin.json",
        ROOT / ".claude-plugin/plugin.json",
        ROOT / ".claude-plugin/marketplace.json",
    ]
    for folder in ("commands", "skills", "references", "scripts"):
        paths.extend((ROOT / folder).rglob("*.md"))
        paths.extend((ROOT / folder).rglob("*.py"))

    offenders = {}
    for path in paths:
        text = path.read_text(encoding="utf-8")
        found = sorted(name for name in RETIRED_NAMES if name in text)
        if found:
            offenders[str(path.relative_to(ROOT))] = found

    assert not offenders, (
        "Public plugin files still reference retired FactIQ publishing tools: "
        f"{offenders}"
    )


def test_skill_stops_at_the_publishing_boundary_without_a_website_workaround():
    skill = " ".join((ROOT / "skills/factiq/SKILL.md").read_text().split())
    assert "FactIQ cannot host charts or reports publicly" in skill
    assert "Do not inspect or direct the user" in skill
    assert "legacy authenticated web interface" in skill
    assert "probe HTTP endpoints" in skill
    assert "Never call `send_feedback`" in skill
    assert "Normal OAuth connection is still supported" in skill


def test_report_sources_do_not_construct_links_to_the_legacy_ui():
    report = (ROOT / "references/output/report-spec.md").read_text()
    assert "/series/" not in report
    assert "only when the fetched result supplies" in report
