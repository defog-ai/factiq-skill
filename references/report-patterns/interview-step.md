# Interview Step

Use this reference before detailed report generation when the user's request
is vague, high stakes, or contains a major unresolved choice. The interview
is a short clarification pass, run in the main conversation before data
fetching and report construction. Ask the user directly; a background
subagent cannot.

The interview resolves intent, audience, scope, and decision criteria before
the workflow commits to a dataset, chart structure, or argument. It reduces
wasted data work and makes the eventual synthesis answer the user's real
decision, not merely the easiest interpretation of the prompt.

This step does not replace the report-pattern dialectical method. After the
interview, the selected playbook still runs thesis, antithesis, and synthesis:
the interview clarifies the question being tested; the dialectic remains the
method for testing it.

## Activate When

- The request is broad or underspecified: "analyze", "what is happening",
  "make a report", "compare", or "evaluate".
- Multiple materially different scopes are plausible: geography, sector,
  time window, measure, audience, policy frame, or company universe.
- A report structure depends on a major product choice: KPI set,
  refresh cadence, drilldown depth, chart density, or share/report format.
- The answer may drive a business, policy, investment, or public-facing
  decision and the success criterion is not stated.
- The user asks for a comprehensive report but has not named the decision,
  audience, or time horizon.

## Skip When

- The user asks for a single series, lookup, or quick chart with clear
  variables and date range.
- The prompt already defines audience, scope, time window, comparison set,
  output format, and decision criterion.
- The user explicitly says not to ask clarifying questions or requests a fast
  best-effort answer.
- The task is only formatting, publishing, or validating an already specified
  report object.

## Default Interview

Ask only the questions needed to unblock the work. Prefer 2-4 questions; do
not turn the interview into a survey.

1. Decision: "What decision or judgment should this report support?"
2. Audience: "Who is the primary reader, and what do they already know?"
3. Scope: "Which geography, entities, sectors, and time window should be in
   bounds?"
4. Success metric: "What would make the output useful: a recommendation, risk
   map, trend explanation, KPI monitor, or evidence pack?"
5. Constraints: "Are there required sources, excluded sources, publication
   deadlines, or formatting limits?"

If the user does not answer and the workflow must continue, record explicit
assumptions and proceed with the narrowest reasonable scope.

## Passing Answers Downstream

Convert the interview result into a compact brief before fetching data:

- `decision`: the decision or judgment the output must support.
- `audience`: reader type and required level of explanation.
- `scope`: geography, entities, sector, metric family, and time window.
- `output`: quick chart or detailed report constraints.
- `success_criteria`: what the synthesis must resolve or recommend.
- `assumptions`: unanswered items and defaults used.

Use the brief to choose the report pattern, data sources, chart set, and
section structure. Then run the existing dialectical method unchanged:

- Thesis: strongest surface reading for the clarified scope.
- Antithesis: fetched contradictions and counter-checks required by the
  selected playbook.
- Synthesis: one claim that explains both sides and directly answers the
  clarified decision.

If interview answers conflict with a playbook's required coverage, keep the
playbook coverage unless the user explicitly narrows the task. Disclose any
omitted antithesis fetches as scope limits, not as silent simplifications.
