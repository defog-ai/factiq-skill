from pathlib import Path
import re


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
        found = sorted(
            name
            for name in RETIRED_NAMES
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", text)
        )
        if found:
            offenders[str(path.relative_to(ROOT))] = found

    assert not offenders, (
        "Public plugin files still reference retired FactIQ publishing tools: "
        f"{offenders}"
    )
