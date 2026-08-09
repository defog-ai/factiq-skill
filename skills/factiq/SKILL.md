---
name: factiq
description: >
  Answer economic and financial data questions with real FactIQ (worlddb)
  data: US indicators (BLS employment/CPI, BEA GDP, Census trade, EIA energy,
  USDA ERS, BTS transport); international data (China NBS/customs, India
  MOSPI/RBI/trade, EU Comext, Singapore, IMF, World Bank); stocks,
  commodities/forex; earnings-call transcripts; executive media appearances
  from podcasts, TV interviews, and conferences; a curated business-news feed;
  and satellite-derived data: nighttime lights by country and state,
  lake and reservoir water levels, daily shipping and port activity
  (chokepoint transits, port calls, seaborne trade estimates), plus on-demand
  signals (fire detections/crop burning with mappable footprints, NO2/SO2/CO
  industrial and combustion activity, smoke and dust aerosol, crop-condition
  NDVI, monsoon rainfall, heatwaves, soil moisture — by country, state, or
  bounding box). Use for unemployment, inflation, GDP, trade flows, energy, wages,
  markets, earnings and executive-media intelligence, recent news context,
  stubble burning, wildfires, air quality,
  monsoon or drought conditions, nighttime lights, reservoir levels, shipping
  or chokepoint traffic, economic charts or maps, terminal previews,
  multi-section research reports, and custom HTML dashboards. Discover series, query SQL, compute, then return a sourced answer
  or render the requested output. For bilateral trade, use the bundled SQL generators instead of hand-writing schema-specific queries.
allowed-tools: >
  mcp__plugin_factiq_factiq__*,
  mcp__factiq__*,
  mcp__claude_ai_FactIQ__*,
  Bash(python3:*), Bash(python:*), Read, Write, Agent
---

# FactIQ Data Tools

You are the analyst. FactIQ provides authenticated MCP tools for discovery and
fetching: catalog, dataset and series search, read-only SQL, series lookup,
market data, transcript and media search, satellite signals, style guides, and
feedback. There is no server-side agent. You decompose the question, fetch the
data, do the math, then answer or build a local output.

Four output modes:

- **Direct answer** — a plain-text sentence with no chart. Use
  when the question asks for a single current value or a simple scalar lookup
  where a chart would add nothing: "what's the US unemployment rate right now?",
  "latest CPI print", "Apple's trailing P/E". Still fetch the value with the MCP
  tools — only the *presentation* is a sentence. State the number with its
  period and source (e.g. "US unemployment was 4.1% in May 2026, per BLS.").
  The moment the question wants a trend, a history, a comparison across
  categories or entities, a breakdown, or explicitly asks for a chart or report,
  switch to one of the modes below.
- **Quick chart** (`term_chart.py`) — one focused local ChartSpec plus an inline
  terminal preview. Default for a single trend or category comparison. Maps can
  use a ranked-table terminal fallback; see `references/output/chart-spec.md`.
- **Detailed report** — a saved report JSON object with summary, sections,
  charts, methodology, and terminal previews. Use for broad analytical
  questions. Covered domains route through `references/report-patterns/README.md`.
  If scope is unclear, use `references/report-patterns/interview-step.md` first.
- **Bespoke local viz** (`build_viz.py`) — a self-contained HTML file you
  author freely and save locally. Use when the answer
  needs something the ChartSpec can't express: a custom layout, a multi-panel
  dashboard, a force/flow/chord diagram, a novel encoding, or fine-grained
  visual control. See **Bespoke local visualizations** below.

**Data in, output out:**

- All discovery and fetching go through the FactIQ **MCP tools**. Local scripts
  build and render the final files from the fetched results.
- The local scripts never touch the API:

  ```bash
  python3 "{plugin_root}/scripts/term_chart.py" render ... # terminal ChartSpec preview
  python3 "{plugin_root}/scripts/build_viz.py"  ...   # local visualization helper
  python3 "{plugin_root}/scripts/comext_sql.py" ...   # SQL generator: Eurostat Comext (EU) trade
  python3 "{plugin_root}/scripts/trade_sql.py"  ...   # SQL generator: US/China/India/Korea/Japan/Taiwan customs
  python3 "{plugin_root}/scripts/hs_codes.py"   ...   # HS commodity code <-> name, offline
  python3 "{plugin_root}/scripts/series_math.py" ...  # YoY/YTD/share/index/merge on saved results
  ```

  Resolve `{plugin_root}` once, then reuse it. In Claude Code it is
  `${CLAUDE_PLUGIN_ROOT}`. In Codex, start from the absolute path supplied for
  this `SKILL.md`: the plugin root is two directories above the directory
  containing this file (`skills/factiq/../..`). Never resolve these scripts
  from the shell's current working directory or from a similarly named
  `scripts/` directory in the user's project. Keep the quotes around the
  absolute path so installations under a directory containing spaces still
  work.

  **For any bilateral-trade question, generate the SQL instead of writing it.**
  `comext_sql.py` and `trade_sql.py` encode each schema's series-ID grammar,
  partner-code system, units, and HS-level rules, so the query is correct by
  construction — run `--help` on either for the subcommands (total / products /
  trend). Label the HS codes a ranking returns with `hs_codes.py` (zero server
  calls), and do growth/share arithmetic with `series_math.py` on results saved
  via `build_viz.py save` rather than in your own output.

## Setup

One connection covers everything: the FactIQ **MCP server** bundled with this
plugin (`.mcp.json`), authorized over OAuth. On first use the coding agent runs
FactIQ's browser-based **Connect** flow. If the FactIQ tools are missing or
return an auth error, the connection isn't set up yet — tell the user to
authorize the MCP server:

- **Claude Code**: run **`/mcp`**, pick **factiq**, and complete the sign-in.
- **Codex**: run **`codex mcp login factiq`** and complete the sign-in.

The same FactIQ login works everywhere (email, Google, or passkey) and authorizes
the data and feedback tools.

**Local development.** The bundled MCP URL is
`https://api.factiq.com/mcp`. For a local backend, edit `.mcp.json` in your
development checkout or configure a standalone `factiq` MCP server in Codex or
Claude Code that points at the local URL.

## Tools

All FactIQ tools are MCP tools provided by the `factiq` MCP server.

### Data

| Tool | Purpose |
|---|---|
| `get_data_catalog` (`schemas?`, `full?`) | Per-schema index + the shared table DDL. **Call once per session before anything else.** `full=true` returns the heavy per-dataset dump (rarely needed — use `describe_dataset`). Schemas listed under `schemas_without_data` have no rows — skip them. |
| `search_datasets` (`query`, `schemas?`, `limit?`) | Keyword (not semantic) ranking of datasets across all schemas. **The first discovery step** — find the right `schema` + `dataset_code`. |
| `describe_dataset` (`schema`, `dataset_code`) | Full metadata for one dataset: topic, methodology, release dates, base-change notice, dimensions, example series. Call after `search_datasets`. |
| `search_series` (`schema`, `terms`, `limit?`, `include_compound?`) | Series-level title-substring search within one schema (`terms` is a list — prefer short stems). Includes `COMPOUND::` series. |
| `run_sql` (`schema`, `sql`, `question?`, `explore?`, `auto_retry?`) | Read-only SELECT against one schema. The power tool for joins, pivots, aggregation. |
| `get_series` (`schema`, `series_id`, `from_year?`, `to_year?`) | Fetch one series — timeseries, tabular, or `COMPOUND::` ids all work. |
| `get_market_data` (`function`, `symbol?`, `interval?`, `outputsize?`) | Quotes, daily/weekly/monthly series, fundamentals (OVERVIEW, INCOME_STATEMENT, EARNINGS), FX, commodities (WTI, BRENT, GOLD), SYMBOL_SEARCH. |
| `get_geo_data` (`dataset`, `region`, `start_date`, `end_date`, `aggregation?`) | Satellite-derived signals, fetched live rather than stored as series: `fires_viirs` (crop burning/wildfires, ~3h lag; `aggregation="grid"` maps the fire's footprint), `no2_tropomi` / `so2_tropomi` / `co_tropomi` (industrial, coal/smelting, and combustion activity), `aerosol_index_tropomi` (smoke/dust/haze), `ndvi_s2` (crop condition), `precip_chirps` (0.05° gauge-calibrated rainfall within 50S-50N), `precip_imerg` (0.1° global rainfall), `temperature_power`, `soil_moisture_power` — aggregated over a country, state (`"India/Punjab"`), or bbox. **Read `references/data/satellite.md` before first use** — it covers windows (max 50 intervals; grid max 92 days), the `valid_obs_share` rule, and attribution. |
| `search_earnings_transcripts` (`query`, `search_target?`, `company_filter?`, `quarter_filter?`, `claim_family?`, `section?`, `detail?`, `limit?`) | Lexical (not semantic) retrieval over atomic, quote-anchored earnings-call rows — never a raw transcript dump. For a non-empty `query`, strict websearch matches rank above an automatically broadened loose partial-match OR-of-tokens tier, so lower-ranked rows may match only some terms; trigram fallback runs only when full-text search returns no rows. Inspect every row for support and retry concise company-native vocabulary (`"capital expenditure"`, `"capex"`, segment names) before concluding lexical silence. For one-call notes, first use `search_target="coverage"`, choose its exact returned `latest_period`, then browse `claims` with `query=""`, that ticker + `quarter_filter`, `detail=true`, and a deliberate limit; fetch `pressure_points` with the same ticker and quarter. The browse is capped, not a promise of a complete call. Quote only `verbatim_quote`; `canonical_statement` is normalized, and neither `analyst_hypothesized` nor `mgmt_declined_to_confirm` is a management assertion. For filed XBRL actuals use `run_sql` on `sec`; for formal targets use `sec_guidance`. Full target/filter reference and workflows: `references/report-patterns/earnings-intelligence.md`. |
| `search_media_appearances` (`query`, `search_target?`, `company_filter?`, `person?`, `sort?`, `appearance_type?`, `claim_family?`, `date_from?`, `date_to?`, `detail?`, `limit?`) | Deterministic, lexical retrieval over precomputed public-safe paraphrases of what executives said outside earnings calls; **no serving-time model** interprets or expands the query. Strict lexical FTS runs first, loose any-term FTS only when strict finds no candidates, and trigram fallback only when both FTS stages are empty. Prefer concise topical language and retry company-native synonyms before concluding silence. Canonical targets are `search` (default claims + passages blend), `claims`, `passages`, `pressure_points`, `appearances`, and `coverage`; compatibility aliases `all`, `videos`, and `companies` map respectively to `search`, `appearances`, and `coverage` and are not recommended for new calls. `sort="relevance"` ranks lexical score before publication date; `sort="newest"` ranks publication date before lexical score. `company_filter` accepts comma-separated primary tickers; `person` is a case-insensitive speaker-name substring; `appearance_type`, `claim_family`, inclusive `date_from`/`date_to`, `detail`, and `limit` provide further narrowing. Dates are the video's publication/upload date, not necessarily its recording/event date. `claim_family` makes blended search claims-only, is invalid with `passages`, and requires matching claims for catalog targets. Structured finding rows expose `result_kind`, `canonical_paraphrase`, speaker/topic/video metadata, relevance, and a timestamped YouTube URL; `appearances` returns video-level metadata, attribution, matching-claim count, URL, and relevance; `coverage` returns company-level structured corpus counts and date/channel inventory. `detail=true` adds normalized claim/attribution fields to finding rows, but never raw transcript text or evidence spans; claim-only fields remain null on passages and detail does not change catalog rows. Never put `canonical_paraphrase` in quotation marks or claim it is verbatim; follow the timestamped source when exact wording or tone matters. Empty-query behavior and the complete workflow are in `references/report-patterns/media-intelligence.md`. |
| `search_news` (`query?`, `tickers?`, `topic?`, `sources?`, `start_date?`, `end_date?`, `sort?`, `limit?`) | Search FactIQ's curated business-news feed — public RSS headlines and summaries from Bloomberg, the Financial Times, and the Wall Street Journal, plus India-macro (Zerodha Daily Brief, ET HealthWorld) and global-health sources (WHO, ECDC, CDC, STAT News, KFF), aggregated and processed by FactIQ so each article carries the listed companies it names (`{symbol, exchange, country}`) and an `analysis` block: searchable keywords, a geography, and an `angle` — one sentence on why the story matters to an investor. Company stories get analysis too, not just macro ones; only content with no business read at all (sports, lifestyle, celebrity) comes back with `analysis: null`. Pivot from a story into data: company stories → `get_market_data` / `search_earnings_transcripts` / `run_sql` on `sec`; macro stories → `search_series` / `run_sql`. Results are headline + short publisher summary + link out, never full articles. `query` is lexical full-text over headline+summary — start with short concrete stems (`"obesity drug"`, `"rate cut"`); if a multi-word query matches nothing in full, the tool automatically retries matching ANY of the words with rare words ranked first, flagged as `meta.query_mode: "any_term"`, so one query attempt is usually enough. `tickers` matches share classes and cross-listings automatically (GOOG also finds GOOGL-tagged articles, TSM its Taiwan listing) — pass whichever symbol you know; most macro stories name no listed company, so zero ticker matches is a normal answer. `topic` is one of markets / economics / companies / technology / politics / world / energy / health / india / opinion — combined with a `query` it is a ranking preference (matching sections rank first, but strong matches from other sections still return, since stories often run outside their obvious feed); without a query it filters to the topic's feeds. `sort` is `"latest"` (default) or `"relevance"` (needs a query); `limit` 1–50 (default 20). Coverage is recent news (most feeds start late 2025), and the feed is continuously being expanded and improved — treat it as a current-events lens, not an archive. |
| `get_style_guides` (`guides`) | FactIQ house-style guides (`"chart"`, `"report"`, `"sql"`, `"earnings"`, or `"all"`). Use these for current style and sourcing rules. Fetch `"earnings"` before writing from `search_earnings_transcripts`. |

Every row-returning tool (`run_sql`, `get_series`,
`search_earnings_transcripts`, `search_media_appearances`) returns **at most 50
rows**, but the remedy is tool-specific:

- For `run_sql`, aggregate to the needed grain; for a long `get_series`
  result, use `from_year` / `to_year`. See **Context budget** below.
- For earnings, narrow by ticker, exact fiscal quarter, target, family, and
  (for claims) section. Synthesize multiple bounded calls and disclose when a
  50-row result may be incomplete. Never query the gated `transcripts` schema
  with `run_sql`, request a raw transcript, or assume pagination exists.
- For media, narrow by ticker, person, dates, target, appearance type, and
  claim family as supported by the live tool contract; use bounded searches
  rather than SQL or an assumed pagination/full-transcript path.

There is no universal "give me everything" option, by design.

#### Earnings target/filter quick reference

| Target | Use and applicable arguments |
|---|---|
| `claims` | Lexical search or empty browse; company, exact quarter, family (primary or secondary), claims-only section, detail, limit |
| `pressure_points` | Lexical search or empty browse; company, exact quarter, linked family, detail, limit. `section` is ignored because these rows are Q&A |
| `disclosure_profile` | Direct lookup by ticker from the first `company_filter` value or `query`; not text or quarter search; other filters, detail, and limit are ignored |
| `coverage` | Company inventory and limit; query, quarter, family, section, and detail do not narrow it |

Canonical call patterns:

- **Latest-call note:** `coverage` for one ticker → read `latest_period` →
  empty-query `claims` with that ticker + exact `quarter_filter`, `detail=true`,
  deliberate limit → `pressure_points` with the same ticker + quarter.
- **Cross-company theme:** check coverage, then run the same concise query and
  synonym sweep separately for each ticker + exact comparable quarter; inspect
  partial-term rows before merging them.
- **Disclosure habits:** call `disclosure_profile` with one ticker; do not add a
  quarter or treat the ticker as a theme query.

Quote only `verbatim_quote`; use `canonical_statement` unquoted. Treat
`analyst_hypothesized` as the analyst’s framing and
`mgmt_declined_to_confirm` as a refusal. Keep spoken call claims, formal
`sec_guidance` targets, and filed `sec` actuals as separate source classes.

#### Media target/filter quick reference

| Target | Use and empty-query behavior |
|---|---|
| `search` | Default blend of high-signal claims and broad passage cards. Empty query browses recent high-signal claims only, without generic passages |
| `claims` | Structured, decision-relevant executive claims. Empty query browses recent claims |
| `passages` | Broader substantive topics not promoted to claims. Empty query browses recent passage cards |
| `pressure_points` | Stored refusal / declined-to-confirm rows, not a complete interviewer-Q&A map. Empty query browses recent refusals |
| `appearances` | Video-level title, channel, publication date, type, attribution, claim-count, URL, and relevance rows. Empty query browses the catalog |
| `coverage` | Company-level structured corpus inventory: appearance/claim counts, date span, covered channels, and attribution status. Empty query returns the inventory |

Use `all`, `videos`, and `companies` only when maintaining an older client;
they are aliases for `search`, `appearances`, and `coverage`. For new work,
use the canonical targets above. All targets accept `company_filter`, `person`,
`appearance_type`, `claim_family` where compatible, publication-date
`date_from`/`date_to`, and `limit`; finding targets also support `detail`.
`claim_family` suppresses passage cards in `search` and cannot be combined
with `passages`. Catalog rows are not expanded by `detail=true`.

Start with `coverage` before absence claims. Use `search` plus
`sort="relevance"` for a theme sweep, then drill into `claims` and
`passages`. Use explicit `sort="newest"` plus date filters for a timeline.
If a bounded result reaches 50 rows, narrow by ticker, person, target,
appearance type, claim family, or date window; never query the gated
`transcripts` schema, assume pagination, or ask for a full transcript.

Media findings are sourced paraphrases. Attribute person, company/ticker when
available, publication date, title/channel, and the timestamped link.
`canonical_paraphrase` must stay outside quotation marks. Verify the linked
source independently when exact wording or tone is material. For coverage,
theme sweeps, timelines, cross-company work, and media-vs-earnings comparison,
read `references/report-patterns/media-intelligence.md` before searching.


### Feedback

| Tool | Purpose |
|---|---|
| `send_feedback` (`message`, `category?`) | Report a problem to the FactIQ team: `category` is `"data_issue"` (a value that contradicts the official source, wrong units/scale, duplicated or missing periods), `"tool_error"` (a tool that errors or returns malformed results), `"missing_data"` (advertised but empty, or coverage ends too early), or `"other"`. Returns an acknowledgment. |

Use it on your own initiative whenever something looks broken — don't wait for
the user to complain. Write one short, specific message with the concrete
identifiers (schema, `dataset_code` / `series_id`, the SQL you ran, expected
vs. observed, the official source's value or URL if you have one). Don't
include the user's personal details or your conversation. It's one-way — the
team reviews every report, but nothing comes back — so file it and continue
with the task; never block on it.

### Terminal charts — `term_chart.py`

`term_chart.py` prints local ANSI/ASCII previews from FactIQ chart objects. It
never calls FactIQ. Build the ChartSpec from fetched data, save it to JSON, and
render it:

```bash
python3 "{plugin_root}/scripts/term_chart.py" render --spec /tmp/factiq-chart.json --width 80 --charset ascii --color auto
```

For a report, save the report object or a wrapper such as
`{"question": "...", "report": {...}}` to JSON, then render its charts:

```bash
python3 "{plugin_root}/scripts/term_chart.py" report --report /tmp/factiq-report.json --width 80 --charset ascii --color auto
```

After `term_chart.py` renders, paste the preview verbatim into your reply inside
a triple-backtick code block and provide the saved JSON path.

Supported terminal renderers:

| Renderer | Use when |
|---|---|
| `bar` | Categorical comparisons and short ranked lists |
| `line` | Time-series trends (one or more series) |
| `table` | Fallback for unsupported chart types or dense data |

Useful options:

| Option | Purpose |
|---|---|
| `--type auto\|bar\|line\|table` | Pick the terminal renderer; `auto` maps from `ChartSpec.type` |
| `--width 80` / `--width auto` | Fixed width by default; `auto` reads the terminal size |
| `--height N` | Line-chart plot height |
| `--charset ascii\|unicode-block` | Strict ASCII or denser Unicode block glyphs |
| `--color auto\|always\|never` | ANSI color control; `auto` respects TTY, `NO_COLOR`, and `TERM=dumb` |
| `--max-charts N` | Report previews only: cap the number of rendered charts; `0` means all |
| `--out FILE` | Also save the rendered text |

Because agents often capture command output instead of streaming it directly to
the user's terminal, use `--charset ascii --color never` for previews you paste
into the final answer. Use ANSI color for real terminal stdout or saved `.ansi`
previews.

### Local viz — `build_viz.py`

`build_viz.py save … / assemble … / render …` saves raw tool results to disk
(no retyping), builds, and screenshots a bespoke local HTML viz (see **Bespoke
local visualizations**). Local-only; never calls the API.

## Orchestration workflow

0. **Interview before major forks.** If the request is broad, vague, or about
   to become a high-commitment workflow — especially a detailed report,
   multi-panel dashboard, bespoke visualization, or a report that could follow
   multiple scopes — use an explorer-agent interview before fetching data or
   spawning research subagents. Read
   `references/report-patterns/interview-step.md` and ask only the few choices
   that would materially change the work: detail level, audience, user context
   or hypothesis, priority lens, required/excluded entities, and time window.
   Pass the answers into all downstream research and assembler prompts as hard
   context. Skip the interview for direct answers, narrow quick charts, or when
   the user already gave clear scope, audience, and detail level. If the user
   does not answer, proceed with the defaults in the interview guide.
1. **Catalog first.** Call `get_data_catalog` once to get the compact
   per-schema index and the table DDL. It tells you what each schema covers,
   not every dataset. Skip schemas under `schemas_without_data`. (You rarely
   need `full=true`; use `describe_dataset` for detail on one dataset.)
2. **Find datasets, then drill in.** Call `search_datasets` to rank datasets
   across all schemas by keyword — the primary discovery step. Survey every
   schema that could be relevant before committing: for India check both
   `mospi` and `rbi`; for the US check `bls`, `bea`, `census`; energy means
   `eia`. Once a dataset looks right, `describe_dataset` for its dimensions and
   example series, then find the exact series with `search_series` (substring —
   prefer short stems like `rare`, not `rare earth`) or exploration SQL
   (`run_sql` with `explore=true`) on the `series` and `dimensions` tables.
   For multi-source stories, actually fetch data from 2+ schemas.
   Satellite-derived series live in two schemas: `portwatch` (daily shipping —
   chokepoints, ports, country trade estimates) and `satellite` (nighttime
   lights by state, lake/reservoir water levels) — see
   `references/data/schemas.md` for routing and
   `references/data/satellite.md` for the on-demand geo tool.

   Eurostat Comext is the exception: country schemas contain millions of
   series, so do not explore their `series` or `dimensions` tables by text or
   dimension value. Read the **Eurostat Comext country schemas** section in
   `references/data/sql-guide.md`; it uses the small product lookup table and
   exact indexed series IDs.

   The IMF replaces each forecast in place, but the `imf` schema also keeps the
   recent earlier releases of the World Economic Outlook, the Fiscal Monitor,
   the Regional Economic Outlooks and COFER. Use them for any question about how
   a forecast has been revised. The plain series id is always the newest
   release; an earlier one is the same id with the year and month appended
   (`WEO_IND.NGDPD.A_2025OCT`), lives in a dataset whose code ends in
   `_vintages`, and carries a `release` dimension. See **IMF past releases** in
   `references/data/schemas.md`.

   **Domain report patterns.** If the question is broad and analytical —
   policy, trade, revenue, investment analysis, "what's driving X" — read
   `references/report-patterns/README.md` **before fetching**. It teaches the
   dialectical method every report follows (thesis: the headline reading;
   antithesis: the strongest contradiction, fetched, not footnoted;
   synthesis: one claim that explains both) and routes covered domains
   (bilateral trade, bilateral economic policy, monetary policy,
   fiscal-policy revenue, business formation) to a playbook of that domain's
   canonical antitheses with ready SQL. For domains without a playbook, apply
   the method directly. Either way it changes what you fetch, not just how
   you write it up. The interview step does not replace this method: it sets
   the user's preferred scope and audience first, then the report-pattern
   method determines the thesis, antithesis, synthesis, and data work inside
   that scope.

   For report-mode questions covering multiple topics, companies, or data
   sources, consider decomposing the research into parallel subagents — see
   **Subagent orchestration** below.

3. **Fetch in batches.** Once you know which series you need, issue the fetch
   calls together (multiple tool calls in one turn). Use `get_series` for 1–2
   known ids; `run_sql` with a CASE-WHEN pivot for 3+ series or joins. Keep
   results inside the 50-row cap — aggregate in SQL to the granularity a chart
   actually needs. For report tables, choose row granularity by context:
   monthly rows can work for shorter multi-year windows, roughly up to 3-5
   years, when timing, seasonality, or turning points matter; for longer
   windows, especially 5+ years, usually summarize with annual totals, YTD
   comparisons, latest/prior snapshots, or selected turning points. Do not
   default categorically to monthly or yearly rows.
4. **Compute yourself.** YoY growth, rebasing to an index, per-capita, ratios —
   write your own Python locally on the fetched values. There is no server-side
   code interpreter in this loop.
5. **Recent market data.** The DB lags for very recent market/price data — use
   `get_market_data` for current quotes, commodities, and FX. For what the
   news is saying about a company, sector, or economy right now, use
   `search_news` — each business article carries keywords, a geography, and a
   one-sentence investor angle, plus the tickers it names; chase a company
   story with `get_market_data` or `search_earnings_transcripts`, and a macro
   story with `search_series`/`run_sql`.
6. **Satellite signals.** For crop burning, wildfires, air-quality-based
   activity (NO2/SO2/CO), smoke and dust plumes, crop condition (NDVI),
   monsoon rainfall, heatwaves, or agricultural drought — where satellite
   observation runs ahead of official statistics — use `get_geo_data`. Read
   `references/data/satellite.md` first: it covers the ten datasets, region
   syntax, the 50-interval window budget (seasonal comparisons = one call per
   season), the fires-only `grid` mode for mapping a fire's footprint,
   cloud-cover caveats, and required attribution. Satellite data complements
   warehouse series; prefer curated series where both exist.
7. **Answer, render, or build.** Direct-answer mode: reply with one sentence
   that states the number, period, and source. Quick-chart mode: build a
   ChartSpec from wide-format data (see `references/output/chart-spec.md`), save
   it to JSON, run `term_chart.py render`, and paste the preview into a fenced
   code block. Report mode: build and save a report object (see
   `references/output/report-spec.md`), run `term_chart.py report`, and return
   the findings, local JSON path, and terminal previews. Bespoke-viz mode: save
   each fetched result with `build_viz.py save`, author an HTML file, assemble
   it, render screenshots, inspect and fix it, then give the user the local HTML
   and PNG paths.

## Subagent orchestration

For report-mode questions that span multiple distinct topics, companies, or data
sources, decompose the work into parallel subagents. This does two things:
each research thread gets a full, focused context instead of competing for
attention in one serial pass, and the report-assembly step gets the spec
loaded directly in its prompt so it never guesses at field names.

Before spawning subagents for a broad or underspecified request, run the
explorer-agent interview described in
`references/report-patterns/interview-step.md` unless the user already gave
clear scope, detail level, audience, and priority lens. Include the interview
answers in every research-agent prompt and in the report-assembler prompt so
the final artifact reflects the user's context instead of only the generic
version of the question.

### Explorer interview subagent

Use an explorer agent for the interview step, not a research subagent. Its job
is to clarify the decision, audience, scope, output shape, and success criteria
and return a compact brief. It should not fetch data, choose final chart
schemas, or assemble the final output. Research subagents run only after the brief and
the relevant report pattern are known.

**Do NOT use subagents** for quick-chart mode or single-topic questions — the
overhead is not worth it. The decision point is right after step 2 of the
orchestration workflow: once you have done the catalog lookup and initial
dataset discovery, you know whether the question decomposes into 2+ independent
research threads. If it does, fan out.

### Research subagents

Spawn one Agent call per research thread. Each agent inherits the skill's
FactIQ MCP tools, so it can discover, fetch, and compute on its own. Give each
agent a tightly scoped prompt and tell it to return structured findings — not
prose and not a final artifact.

Agent prompt template (adapt the specifics per thread):

```
You are a FactIQ research agent. Answer one sub-question and return structured
findings only. Do not assemble the final chart or report.

Sub-question: {sub_question}

Relevant schemas/datasets (from the parent's catalog step): {hints}

Steps:
1. search_datasets / describe_dataset / search_series to find the right series.
2. Fetch data with get_series or run_sql. Aggregate in SQL to stay under the
   50-row cap.
3. Save each fetched result to its own JSON file so a later charting step can
   load the exact numbers instead of re-querying FactIQ or retyping them.
   Right after each fetch, run (no retyping — it copies the payload from the
   transcript), giving each file a thread-unique name and a --match on a
   distinctive bit of your own SQL so a sibling agent's result can't be grabbed:
   `python3 {plugin_root}/scripts/build_viz.py save --tool run_sql --match "<distinctive SQL fragment>" --out /tmp/factiq-raw/{thread_label}-<name>.json`
4. Compute derived metrics (YoY, ratios, indices) yourself.
5. Return your findings as a structured block:

FINDINGS:
- sub_question: (echo it back)
- series_used: [{schema, series_id, title}, ...]
- sql_queries: [the exact SQL you ran, formatted multi-line]
- data: [{columns: [...], rows: [...]}, ...] — the actual fetched/computed values
- raw_data_files: [/tmp/factiq-raw/{thread_label}-*.json, ...] — the files you
  saved in step 3, so a downstream viz/report step loads exact data
- key_insights: [1-3 sentences stating what the data shows, with numbers]
- chart_suggestion: {chart_type, title, x_column, y_columns, units}
```

Launch the agents in parallel — multiple Agent tool calls in one turn:

```
Agent(prompt="<research prompt for thread 1>", label="research-supply-chain")
Agent(prompt="<research prompt for thread 2>", label="research-pricing")
Agent(prompt="<research prompt for thread 3>", label="research-demand")
```

Each agent runs independently and returns its findings block. Wait for all of
them before proceeding to assembly.

### Report assembler subagent

After all research is complete, spawn a single report-assembler agent. Its
prompt must contain two things: (1) the full content of `references/output/report-spec.md`
so the spec is in context, not behind a file read that might be skipped, and
(2) all the research findings from the previous step.

Before spawning the assembler, read `references/output/report-spec.md` yourself with
the Read tool. Then embed its entire content in the assembler's prompt.

Agent prompt template:

```
You are a FactIQ report assembler. Build a complete report object, save it, and
render terminal previews for its charts. Do not do data discovery or fetching;
all data is provided below.

USER QUESTION: {original_question}

=== REPORT SPEC (from references/output/report-spec.md) ===
{paste the full content of references/output/report-spec.md here}
=== END REPORT SPEC ===

=== RESEARCH FINDINGS ===
{paste all findings blocks from the research agents, labeled by thread}
=== END RESEARCH FINDINGS ===

Instructions:
1. Design 2-5 sections. Each section makes one claim its chart(s) prove.
2. Chart titles state the finding with numbers, not the topic.
3. Narratives are plain text — no markdown formatting.
4. Every chart must have columns, data (from the findings above), x_column,
   y_columns (for line/bar), sources, and lineage.
5. Lineage code must be formatted multi-line SQL/Python with real newlines.
   series_refs must list every series the step used.
6. Save the full report object to JSON and run:
   `python3 {plugin_root}/scripts/term_chart.py report --report <json-file> --charset ascii --color never`
7. Return the JSON path and paste the terminal previews into the reply inside a
   triple-backtick code block.
```

Launch the assembler:

```
Agent(prompt="<assembler prompt with spec + findings>", label="report-assembler")
```

The assembler has the full spec in context, so it builds the report object,
saves the JSON, and returns the local path plus terminal previews.

### Example decomposition

Question: "How is the US EV market evolving — supply chain, pricing, and demand?"

After step 2 (catalog + discovery), you identify three independent threads:

| Thread | Sub-question | Schemas |
|---|---|---|
| Supply chain | What does US EV battery/component production look like? | `census`, `bea` |
| Pricing | How have EV prices and average selling prices changed? | `bls` (CPI), market data |
| Consumer demand | What are EV sales and registration trends? | `bts`, `bea`, market data |

Spawn three research agents in parallel. When all return, spawn one assembler
agent with the spec and all three findings blocks. The assembler builds a
3-section report, saves it, renders terminal previews, and returns both.

### When NOT to use subagents

- Quick-chart mode (single metric, single chart).
- Single-topic questions even in report mode ("How has US unemployment evolved
  since 2020?" — one thread, no decomposition needed).
- Bespoke local visualizations — the build_viz loop is inherently iterative and

For these cases, do the research and build the output in the main context.

## Detailed reports

A report is a structured local research output: a bulleted summary, sections
that pair narrative with charts, and methodology notes. Author every chart row
and narrative claim from data fetched in this session. The JSON format and a
worked example are in `references/output/report-spec.md`. For reliable assembly,
load that full file into a dedicated report-assembler subagent.

Ground rules:

- **2–5 sections, 1–2 charts each** is the normal size. The format allows up to 12
  sections, 16 charts). Each section should make one claim its charts prove.
- **Chart titles state the finding** ("Health care added 652k jobs in 2024 —
  triple tech's losses"), not the topic ("Jobs by sector").
- **Narratives are plain text.** Keep them short and direct.
- **Cite sources and lineage.** Every chart must identify the datasets and the
  exact SQL or computation used. Format SQL and Python with real newlines. List
  every series used in `series_refs`.
- **Do not pad.** If the data only supports one chart, build a quick chart
  instead of inflating a report.
- **Broad analytical questions get the dialectic.** Follow the
  thesis → antithesis → synthesis method in
  `references/report-patterns/README.md`: sections that only restate the
  headline reading are an unfinished report. Covered domains (bilateral
  trade, bilateral economic policy, monetary policy, fiscal-policy revenue,
  business formation) must additionally meet the required coverage in the
  playbook the README routes to — do not reduce them to the easiest single
  chart.

Check the report object against `references/output/report-spec.md`, save it to
JSON, and render it with `term_chart.py report`. Return the report findings, the
local JSON path, and visible terminal previews.

## Bespoke local visualizations

When the answer needs a custom layout, a dashboard of several panels, a
force/flow/chord diagram, an annotated narrative, a novel encoding, or fine
visual control, build a self-contained local HTML file.
There is no fixed chart-type list: author the HTML/JS with ECharts, D3, Canvas, SVG, or WebGL,
inject the data you already fetched, then render and iterate. Read
`references/output/viz-guide.md` before starting — it covers technique selection, the
data contract, and the legibility checklist.

The tool is `{plugin_root}/scripts/build_viz.py` (local-only — it never calls
the API):

| Command | Purpose |
|---|---|
| `save --out F.json [--tool run_sql] [--match STR] [--index N] [--list]` | Copy a tool result's **raw JSON from the harness transcript** to `F.json` — the shell copies the bytes, you never retype the data. Feeds `assemble --data`. Stdlib only. |
| `assemble --template T.html --data k1=f1.json k2=f2.json … --out O.html [--open]` | Inject on-disk JSON into your HTML at the `__FACTIQ_DATA__` marker; write one portable, self-contained file. Stdlib only. List **all** key=path pairs after the one `--data` flag. |
| `render O.html [--out P.png] [--width N] [--height N] [--full-page] [--selector CSS] [--wait MS]` | Screenshot the file in headless Chromium and report JS/console errors + failed asset loads. Installs Playwright + Chromium into `~/.factiq/viz-venv` on first run (uses `uv` if available, else a stdlib venv). |

The loop that makes this work — **fetch → save → author → assemble → render →
look → fix**:

1. Fetch the data with the MCP tools, then **save each result to a JSON file
   with `build_viz.py save` — do not retype it via Write**. The MCP tools return
   their payload into your context, not to disk; `save` lifts that exact payload
   back out of the harness transcript so the shell copies the bytes (never
   re-emit a ~100-row result by hand — it double-pays the tokens and one
   mistyped digit ships a wrong chart with no error). Run one `save` per fetch,
   pinning the call with `--tool`/`--match`:
   ```bash
   python3 "{plugin_root}/scripts/build_viz.py" save --match "korea_customs" --out /tmp/korea.json
   ```
   The file holds the tool's own `{columns, results, …}` payload — see
   `references/output/viz-guide.md` (**Saving data without retyping**) for `--list`,
   `--index`, and the fallback when a transcript can't be found. Because the MCP
   caps results at 50 rows, this is context-cheap; aggregate or window in SQL to
   get exactly the rows the viz needs.
2. Copy `assets/viz-shell.html`, add any CDN library you need, and author the
   viz. Keep the `__FACTIQ_DATA__` marker inside its
   `<script id="factiq-data" type="application/json">` tag — that exact element
   is where the data lands and how the page reads it back. After assembly the
   page exposes a `DATA` global; rows are at `DATA.<key>.results`.
3. `assemble` the self-contained file, then `render` it and **actually read the
   screenshot**. `render` exits **5** when the page logged a JS error or a
   failed request — that usually means a blank page; fix it before judging the
   visual. One render pass is never enough; budget two or three.
4. Hand the user the local file path; offer `--open` to open it in a browser.

If the viz will instead be published as a **claude.ai Artifact** that calls
FactIQ live from the page (`window.claude.mcp`), read
`references/output/viz-guide.md` (**Publishing as a claude.ai Artifact with
live data**) first. In short: declare the capability as `factiq` (the default
connector name) and publish without asking; when you deliver the link, tell
the user that if the page can't find their connector they should send you its
exact name from claude.ai Settings → Connectors so you can republish with it.
In the page's own JS, discover the callable server at runtime with
`listTools()` rather than hardcoding a name.

## Context budget — the 50-row cap

Every row-returning MCP tool (`run_sql`, `get_series`) returns **at most 50
rows**, and there is no "give me everything" option — by design. The cap keeps
results context-sized, so you do **not** stage data to disk to protect your
context; you take the tool result directly.

When a result comes back `"truncated": true`, there is more data and your move
is to **aggregate or compute it in SQL**, not to try to fetch the raw rows:

- Roll a long daily/monthly series up with `GROUP BY date_trunc('month', time)`
  (or quarter/year) — a chart wants a few hundred points at most, and 50
  aggregated points usually says everything.
- Return a SUM / AVG / rank / ratio instead of the underlying rows.
- For one series, window it with `get_series(..., from_year=, to_year=)`, or
  make a few windowed calls and stitch them.

Whatever you chart or report has to be the aggregated result you bring back —
which is also all it needs. For `build_viz`, persist that (already small) result
to a JSON file with `build_viz.py save` before assembling — it copies the
payload from the transcript so you never retype the rows.

## Errors and limits

- **MCP tool unavailable / auth error** — the FactIQ MCP is not connected. Tell
  the user to authorize it (Claude Code: `/mcp` → factiq; Codex:
  `codex mcp login factiq`).
- **429** — either the 1 request/second rate limit or the monthly tool-call
  quota. The error states when it resets. Do not re-fetch data you already have.
- **403** — that schema is admin-restricted for this account; drop it.
- **SQL errors** come back in the tool result as an `error` (syntax errors,
  timeouts, bad column names). Revise the query and rerun.
- **Zero rows** — your filter was too narrow. Broaden it yourself (see
  `references/data/sql-guide.md`). `auto_retry=true` opts into a server-side LLM
  reviser, but you can usually revise better and cheaper yourself.
- **SQL timeout** — statements are capped at 30s. Filter on indexed columns
  (`series_id`, `dataset_code`) instead of scanning titles, and never
  pattern-match `series_id` on `data_points` — resolve ids from `series` first
  (see the pitfall in `references/data/sql-guide.md`). For `eu_comext_*`, do
  not retry a dimension scan; use `eu_comext_lookup.product_codes` and exact
  IDs as described in the Comext section of that guide.
- **Anything that looks broken on FactIQ's side** — a value that contradicts
  the official source, wrong units, missing periods, an advertised dataset
  that returns nothing, a tool that keeps erroring — report it with
  `send_feedback` (see **Feedback** above), then work around it and continue.
  The FactIQ team reviews every report and fixes what it can.

## References

**`references/data/`** — the data layer:

- `schemas.md` — what lives in each schema. The `get_data_catalog` tool is the
  live, authoritative version; `search_datasets` / `describe_dataset` drill
  into individual datasets on demand.
- `sql-guide.md` — table structure, query idioms, pitfalls (frequency
  literals, national vs sub-national, pivots, tabular data).
- `satellite.md` — the `get_geo_data` satellite tool: datasets and their
  economic reading, region syntax and coverage, window budgeting, the
  fires-only `grid` footprint mode, cloud/quality caveats, attribution
  requirements.

**`references/output/`** — local output formats:

- `chart-spec.md` — ChartSpec format, chart-type selection, terminal rendering, and a worked example.
- `report-spec.md` — report JSON format: sections, per-chart fields,
  sources, lineage, limits, and a worked example.
- `viz-guide.md` — bespoke local HTML visualizations with `build_viz.py`: the
  assemble/render loop, the `DATA` contract, technique selection
  (ECharts/D3/Canvas/WebGL), a legibility checklist, starter recipes.

**`references/report-patterns/`** — how to think about broad analytical
questions. Start at `report-patterns/interview-step.md` when the request is
vague or high-commitment; it defines the explorer-agent interview that
clarifies scope and audience before data work. Then read
`report-patterns/README.md`: it teaches the dialectical method (thesis →
antithesis → synthesis) that every report follows and routes covered domains
(bilateral trade, bilateral economic policy, monetary policy, fiscal-policy
revenue, business formation, and any added later) to a playbook of that
domain's canonical antitheses with ready SQL. For uncovered domains —
investment analysis, general macro — the README shows how to apply the method
directly.
