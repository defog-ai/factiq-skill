# Earnings-Intelligence Report Pattern

Company and earnings analysis from what management said live
(`search_earnings_transcripts`), what the company filed
(`search_company_filings`, or `run_sql` on the `filings` schema), what it
formally guided (`sec_guidance`), how the market priced it
(`get_market_data`), and — FactIQ's edge — whether the macro data agrees.

The dialectic here: the **thesis** is the story management tells on the call
and the consensus narrative around it. The **antithesis** is the variant
perception fetched from data management doesn't control — filed actuals,
disclosure behavior (what they stopped breaking out, what they refused to
quantify), the analyst pressure map, and the government statistics behind
every macro claim. The **synthesis** is the claim that explains both: what
the narrative gets right, where it flatters, and what would falsify it.

## Trigger Phrases

"What did <company> say", "summarize the earnings call", "earnings note on
X", "did they guide up or down", "what is the Street worried about",
"compare what <A> and <B> said about <theme>", "is management's story
consistent with the data", "who mentioned <theme> this quarter".

## Before Anything Else: Coverage

`search_earnings_transcripts(search_target="coverage")` — with
`company_filter` when the question names companies. `company_filter` takes
tickers or company names (`"NVDA"`, `"NVIDIA Corporation"`, or a
comma-separated list); a name is resolved to the stored ticker, and the
response reports the resolution in `company_filter_matched` and lists
possible matches under `company_filter_unmatched` for a value that
resolved to nothing. Treat its live
`calls_covered`, `earliest_period`, `latest_period`, and `latest_call_date` as
the authoritative coverage window; do not rely on a static assumption about
how many calls exist. If a ticker is not covered, say so and fall back to
`search_company_filings` plus `get_market_data`; never silently substitute
filed data for spoken remarks.
An uncovered period, an empty lexical result, or a partial result is never
evidence management did not discuss a topic.

## Target and Filter Reference

| `search_target` | What `query` does | Applicable filters and returned detail |
|---|---|---|
| `claims` | Ranked lexical search; `query=""` browses rows | `company_filter`, exact `quarter_filter`, `claim_family` (primary or secondary family), `section`, `detail`, and `limit`. Every row includes `transcript_id`, `source_block_index`, `qa_turn_id`, and `source_link`; `detail=true` adds `structured_fields`, secondary families, period/horizon, conviction, denominator, and the `falsifiable` flag. |
| `pressure_points` | Ranked lexical search; `query=""` browses Q&A pressure rows | `company_filter`, exact `quarter_filter`, `claim_family` (the linked family), `detail`, and `limit`. Every row includes the same transcript locator and source-link fields. `section` is ignored because every row is Q&A. `detail=true` adds `tone_note`. |
| `disclosure_profile` | No text search: direct company lookup | Uses the first `company_filter` value (ticker or company name), or `query` as the ticker. It is accumulated at company level. `quarter_filter` is ignored; `claim_family`, `section`, `detail`, and `limit` are also ignored. |
| `coverage` | No theme search: corpus inventory | `company_filter` and `limit` apply. `query`, `quarter_filter`, `claim_family`, `section`, and `detail` do not narrow the inventory. |

All targets return at most 50 rows. `coverage` counts are inventory metadata,
not proof that a quarter-pinned claim browse returned every row in that call.
Never route around the cap with `run_sql` on `transcripts`; that schema is
gated, and no raw-transcript or pagination path is promised.

### How lexical retrieval behaves

For a non-empty claims or pressure-points query, strict
`websearch_to_tsquery` matches receive a ranking boost above a loose
partial-match OR-of-tokens full-text tier. A returned row can therefore match
only part of a multi-term
query. If full-text search yields no rows, a trigram fallback catches typos and
sub-word variants. This is lexical, not semantic retrieval:

1. Start with concise, company-native terms rather than a long question.
2. Read the returned statement or pressure row; do not infer topical support
   from rank alone.
3. Sweep genuine vocabulary alternatives (for example `capex`, `capital
   expenditure`, `capacity investment`) and segment/product names.
4. Check coverage before describing an empty result. Say "no matching row in
   the covered calls" rather than "management never discussed it."

## The Six Workflows

### 1. Single-call earnings note ("what did MU say?")

1. Coverage first: `query=""`, `search_target="coverage"`,
   `company_filter="MU"`. Choose one exact returned fiscal period (usually
   `latest_period`) and record the full coverage window.
2. Browse that call's bounded claim rows: `query=""`,
   `search_target="claims"`, `company_filter="MU"`,
   `quarter_filter="<exact FY...Q...>"`, `detail=true`, `limit=50`. Never omit
   `quarter_filter`: an unpinned browse can mix calls. A pinned empty browse
   returns rows in spoken/source order. If 50 rows return, state that the cap
   may omit additional extracted claims; even a shorter result is a claim-graph
   view, not a raw or guaranteed-complete transcript.
3. Fetch the same call's Q&A dynamics: `query=""`,
   `search_target="pressure_points"`, with the same ticker and exact quarter,
   `detail=true`, `limit=50`. Disclose the same cap caveat when relevant. The
   `response_quality` distribution and any `refused_number` rows are the
   "what the Street couldn't get" section.
4. Use `search_target="disclosure_profile"` as a ticker-level, unquartered
   lookup of what this company routinely breaks out vs. withholds, so you can
   flag anything volunteered off-pattern.
5. Antithesis pass: pair the 3–5 most checkable claims with filed data —
   filed XBRL actuals, `sec_kpi` operating metrics, and `sec_guidance`
   formal targets, all through `search_company_filings` — and the
   call-window price move
   (`get_market_data` with `data_type="price_history"`,
   `frequency="daily"`, and a deliberate `limit`).
6. Report: summary (the synthesis, not a recap) → guidance table → quote
   panels for the load-bearing verbatim statements → verification charts →
   watch-list from the refusals. State the pinned fiscal period, coverage
   window, and whether either bounded browse hit 50 rows. Put each used row's
   provided `source_link.source_url` beside its quote as a Markdown link, using
   `source_link.source_label` as the link text; if it is null, state that the
   direct transcript link is unavailable. The label must identify the company
   or ticker, fiscal period, and earnings call transcript—not an ingestion
   vendor.

### 2. Claim-vs-data verification (the FactIQ edge)

Management routinely makes macro claims — "the consumer is trading down",
"freight costs have eased", "power constraints gate datacenter builds".
Every such claim names a government series FactIQ has:

| Claim family heard on calls | Verify against |
|---|---|
| Consumer health / trading down / cohort behavior (`cohort_behavior`) | `census` retail sales, `bls` CPI + real earnings, `frb` G.19 consumer credit |
| Input costs, freight, energy (`cost_margin_bridge`, `stated_risk_constraint`) | `bls` PPI, `eia` energy prices, `bts` freight, `portwatch` shipping |
| Demand magnitude / industry TAM (`demand_magnitude`) | `census` shipments/orders, trade schemas for the import/export view, sector KPIs across `sec_kpi` peers |
| Hiring, wage pressure (`labor_org`) | `bls` payrolls/JOLTS/ECI |
| Tariffs, policy, regulation (`regulatory_policy`) | customs/trade schemas, `policy` communications |

Chart the claim and the series together; title the chart with the verdict
("Gasoline demand supports WMT's consumer-stress read"). Say plainly when
the data contradicts or cannot yet test the claim.

### 3. Guidance scorecard (beat/miss/follow-through)

1. Check coverage and select each exact fiscal period first. For every period,
   fetch spoken targets with the same ticker + `quarter_filter`,
   `claim_family="forward_conviction"` and `claim_family="prior_view_revision"`
   (`vs_prior` is the revision payload). Do not combine unpinned quarters.
2. Formal targets: `sec_guidance` series
   (`{TICKER}_{metric}[_growth]_guidance_{period}_{bound}_*`) — check
   whether the spoken and filed guidance agree.
3. Actuals as they land: `search_company_filings` for filed company results.
4. Output: one table — metric, guided value/range, vs-prior, spoken vs
   formal, actual, verdict. `falsifiable=true` claims (in `detail` output)
   are the rows this table is made of.

### 4. Cross-company theme sweep ("who's saying what about <theme>?")

1. Check coverage for all named tickers. Use each company’s returned
   `latest_period`, or verify another named exact period, and retain
   `calendar_date`; the same fiscal label can map to different calendar
   windows, while the same calendar quarter can map to different fiscal labels.
2. Run the same concise theme terms, filters, and synonym sweep separately for
   each ticker + exact quarter. Do not depend on one 50-row multi-ticker result:
   a prolific company can crowd out peers. Strict matches rank above loose
   partial-term matches, so inspect each row and merge only rows that support
   the theme.
3. Group hits by `reporting_ticker` and `claim_family`; split
   `company_asserted` from `analyst_hypothesized` (the latter is the
   Street's framing, not the companies').
4. Disclosure asymmetry is its own finding: for the central tickers, pull
   `disclosure_profile` — who breaks the theme out vs. who withholds it.
5. `section` matters: a theme confined to `qa` is one analysts force;
   a theme in `prepared_remarks` is one management leads with.

### 5. Multi-quarter change ("how did management's view evolve?")

1. Use coverage to establish `calls_covered`, `earliest_period`, and
   `latest_period`; it does not enumerate every intermediate quarter. Select
   user-named periods or test candidate fiscal periods with exact
   `quarter_filter` calls, and compare only periods that return rows. Never use
   one unpinned empty browse.
2. For each quarter, issue the same bounded claims calls with ticker,
   `quarter_filter`, target, family/section filters, synonym sweep, detail, and
   limit. Fetch pressure points separately with the same ticker and quarter.
3. Compare normalized `canonical_statement` content in prose, but quote only
   each row's `verbatim_quote`. Keep period and speaker attached to every row.
4. Distinguish a changed claim from a retrieval gap: "no matching extracted
   row in FY2026Q2" is not "management stopped discussing it." Disclose the
   coverage window and any 50-row cap hit for every quarter.

### 6. Q&A pressure analysis ("what is the Street trying to find out?")

For one company/call, check coverage and pin the exact ticker + quarter before
calling `search_target="pressure_points"`; add a concise lexical `query` only
when the question names a theme. Read the rows as a map of information
asymmetry: `topic_pressed` × `response_quality`. The `declined`/`deflected`
rows with a `refused_number` are known unknowns — list them as the watch-list
for next quarter. `linked_claim_id` ties a refusal back to the claim it guards.
`tone_note` (in `detail` output) is subjective — attribute it as a reading if
used at all.

## Data Source Ladder

1. `search_earnings_transcripts` — spoken claims, Q&A, disclosure habits.
2. `search_company_filings` — filed XBRL segment/product/geo detail,
   `sec_guidance` formal targets, `sec_kpi` operating metrics. For joins or
   aggregations across companies, `run_sql` on the `filings` schema (see
   `references/data/schemas.md`).
3. `get_market_data` — quotes, company/ETF profiles, and price history for
   reaction windows.
4. Macro schemas (`bls`/`census`/`eia`/`frb`/trade/`policy`) — the
   verification layer for any macro claim.
5. Never `run_sql` on the `transcripts` schema — it is bespoke and gated;
   the tool is the only supported access.

## Default Report Shape

Summary states the synthesis with numbers. Then: (1) what management said —
guidance table + quote panels; (2) what the data says — verification charts,
filed vs. spoken; (3) what the Street pressed on — pressure points and
refusals; (4) watch-list — the falsifiers and when they print (next earnings
date, next macro release). Fetch the `earnings` style guide
(`get_style_guides(["earnings"])`) and follow it: verbatim-only quotes with
speaker/role/ticker/period, spoken-vs-filed source labels, quote panels not
quote-filled text panels.

## Guardrails

- `assertion_status` is load-bearing: `analyst_hypothesized` belongs to the
  analyst; `mgmt_declined_to_confirm` is a refusal, and often the finding.
- Only `verbatim_quote` may appear in quotation marks or quote panels. A
  `[…]` inside it marks omitted transcript sentences between non-adjacent
  evidence spans; keep the marker exactly as returned and never close the gap
  into one continuous sentence.
  `canonical_statement` is normalized content for synthesis, not a quotation.
- Put the exact row's provided source URL beside every quote or filing-backed
  figure, using its provided source label as the Markdown link text. Do not
  replace the evidence label with an ingestion vendor, make another tool call
  just to find the citation, reconstruct a URL, or substitute a related press
  release. A document-precision URL is not an exact-context link. When
  `source_url` is null, say it is unavailable.
- Retrieval is lexical. A broad/partial hit is not proof of the full theme,
  and an empty result is not proof of silence — inspect rows, sweep the
  company's own vocabulary, and report the coverage boundary.
- A % claim without its `denominator` does not go in a table.
- Spoken ≠ filed ≠ formal guidance: label each, and when two disagree, that
  disagreement is content, not noise.
- Do not turn a pressure-point refusal (`response_quality="declined"` or a
  `refused_number`) into an affirmative claim.
- Do not build a multi-period scorecard from one quarter of coverage. State
  the live coverage window and the exact fiscal periods actually compared.

## Methodology Language To Include

"Earnings-call claims are extracted from live-call transcripts into
quote-anchored structured rows; quotes are verbatim, attributed to speaker
and fiscal period. Spoken statements are distinguished from filed financials
(SEC XBRL) and formally issued guidance (sec_guidance). Coverage:
<tickers/quarters from the coverage call>."
