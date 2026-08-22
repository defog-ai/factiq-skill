---
description: Answer a data question with FactIQ — a quick chart, terminal chart, or full report
argument-hint: "<question, e.g. How has US unemployment changed since 2019?>"
disable-model-invocation: true
allowed-tools: >
  mcp__plugin_factiq_factiq__*,
  mcp__factiq__*,
  mcp__claude_ai_FactIQ__*,
  Bash(python3:*), Bash(python:*), Read, Write, AskUserQuestion, Agent
---

Answer this question with real data from FactIQ:

> $ARGUMENTS

Read `${CLAUDE_PLUGIN_ROOT}/skills/factiq/SKILL.md` first. If no question was
provided above, ask the user what they want to know.

Discovery and fetching run through the FactIQ MCP tools. Final output is local.
If the tools are unavailable or return an auth error, the MCP is not
connected — tell the user to authorize it (Claude Code: `/mcp` → factiq;
Codex: `codex mcp login factiq`), then retry.

**Pick the output mode before doing any data work:**

- **Quick chart** — one focused local chart, terminal preview, and short
  narrative. Use for one metric, trend, or comparison.
- **Detailed report** — a local multi-section report with summary, charts,
  methodology notes, and terminal previews. Use for broad analytical requests.
- **Published bespoke report** — custom HTML rendered locally against exact
  transcript-saved tool results, then published with `publish_html_report`
  using only `_factiq_data_ref` mappings. Use when the user asks for a hosted
  FactIQ report or share URL; follow `references/output/publish-html-report.md`.

If the question clearly fits one mode, proceed without asking. Only when it
is genuinely ambiguous — broad enough that a report would add value, but a
single chart could plausibly satisfy it — use the AskUserQuestion tool to
offer the two modes, noting that the report takes noticeably longer and uses
more of their tokens and FactIQ tool quota.

If the ambiguity is not chart-versus-report but scope, audience, decision
criteria, or report/dashboard depth, run the explorer-agent interview in
`references/report-patterns/interview-step.md` before data work. Use the
resulting brief as downstream context; the selected report pattern still
controls the thesis, antithesis, synthesis, and required data checks.

Then follow the skill's orchestration workflow (catalog → discover → fetch →
compute, all via the MCP tools) and finish per the mode:

- **Quick chart** → build a ChartSpec (`references/output/chart-spec.md`),
  save it to JSON, run
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/term_chart.py" render --spec <file> --charset ascii --color auto`,
  and return the JSON path, terminal preview, and short narrative.
- **Detailed report** → follow the skill's **Detailed reports** section and
  `references/output/report-spec.md`, save the report object to JSON, run
  `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/term_chart.py" report --report <file> --charset ascii --color auto`,
  and return the JSON path, terminal previews, and key findings.

For report-mode questions that span multiple topics, companies, or data sources,
decompose the research into parallel subagents after initial discovery — one
agent per research thread. Then synthesize and hand off to a report-assembler
subagent. See the skill's **Subagent orchestration** section for the pattern.
