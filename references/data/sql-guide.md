# FactIQ SQL Guide

SQL runs read-only with one default schema per call — the `run_sql` MCP tool,
with `schema="bls"` and `sql="..."`. The server sets `search_path` to that
schema, so reference its tables bare (`series`, not `bls.series`); other
schemas stay reachable by qualified name (`korea_trade.series`,
`eu_comext_lookup.product_codes`). Statements are capped at 30 seconds, and
**every result is capped at 50 rows** — aggregate in SQL to the granularity
you actually need rather than pulling raw rows (see "Pivoting" and
"Efficiency" below).

## Table structure (identical in every schema)

- **`series`** — the catalog. Key columns: `series_id`, `series_title`,
  `human_friendly_title`, `human_friendly_description`, `dataset_code`,
  `frequency`, `measurement_units`, `adjusted_for_seasonality`, `state`,
  `county_or_metro_area`, `begin_time`, `end_time`, `data_type`
  (`timeseries` or `tabular`), `tabular_columns`.
- **`data_points`** — `series_id`, `time` (date), `value` (numeric).
- **`dimensions`** — `series_id`, `dimension_type`, `dimension_code`,
  `dimension_name`. Useful for discovery when titles are uninformative.
- **`tabular_data`** — JSONB `row_data` per row, for `data_type = 'tabular'`
  series only.
- **`compound_series`** — curated derived series with ids like
  `COMPOUND::...`. Fetch them with the `get_series` tool, not raw SQL.

The `get_data_catalog` tool returns the full DDL.

## Always-true conventions

- **`frequency` values are lowercase**: `'monthly'`, `'quarterly'`,
  `'annual'`, `'weekly'`, `'semiannual'`. `frequency = 'Monthly'` matches
  nothing.
- **`dataset_code` is lowercase** — use ILIKE or lowercase literals.
- **Match periods on the calendar month, never on the exact date.** The day
  stored inside `data_points.time` varies by source: most store the first day
  of the period, but `frb`, `rbi`, `fhfa` and `treasury` store monthly values
  on the last day of the month (`2025-02-28`, `2025-03-31`), and `frb`, `rbi`,
  `fhfa` and `cbo` store quarters on quarter-end dates. An exact-date join
  such as `prior.time = cur.time - interval '1 year'` finds nothing for those
  (February 29 minus one year is February 28). Join and compare on
  `date_trunc('month', time)` (or `date_trunc('quarter', time)` for quarterly
  series):
  `date_trunc('month', prior.time) = date_trunc('month', cur.time) - interval '1 year'`.
- The server rewrites `series_title` to
  `COALESCE(human_friendly_title, series_title)` automatically, normalizes
  frequency filters, and turns `data_points.series_id` pattern filters into
  semi-joins on `series`; the response's `transformed_query` shows what
  actually ran.
- Results come back enriched with `constituent_series` metadata
  (titles, units, source) for every series_id touched — use it for chart
  source attribution.

## Exploratory queries first

Before fetching from a dataset you haven't touched, look at 5 rows of its
catalog to learn naming conventions and units:

```sql
SELECT series_id, series_title, dataset_code, frequency,
       adjusted_for_seasonality, measurement_units
FROM series WHERE dataset_code ILIKE '<dataset>' LIMIT 5
```

Run these with `explore=true` so the server treats them as exploration.

## Keep SQL simple and broad

Don't stack ILIKE conditions — you'll miss valid rows and get zero results.
A broad query returning 50 rows beats a narrow one returning 0 (results are
capped at 50 rows either way).

```sql
-- Bad: over-filtered, likely 0 rows
SELECT series_id, series_title FROM series
WHERE dataset_code ILIKE 'jt' AND series_title ILIKE '%job openings%total nonfarm%'
  AND series_title ILIKE '%level%' AND measurement_units ILIKE '%level%'

-- Good: broad, let the results guide you
SELECT series_id, series_title, measurement_units FROM series
WHERE dataset_code ILIKE 'jt' AND series_title ILIKE '%job openings%'
  AND adjusted_for_seasonality = true
LIMIT 20
```

Prefer filtering on indexed columns (`series_id`, `dataset_code`) over text
scans. For text searches use two steps: find series_ids first, then fetch
their data.

## Pattern-matching `series_id` on `data_points`

`data_points` is enormous and its index does not serve LIKE/ILIKE; an
unindexed pattern scan of it dies at the 30s timeout. The server covers one
case for you: a LIKE/ILIKE on `data_points.series_id` in a WHERE clause is
rewritten into `series_id IN (SELECT series_id FROM series WHERE ...)` (the
response's `transformed_query` shows it), so it runs through the index. The
rewrite covers WHERE clauses only — a pattern inside a projection
(`SUM(CASE WHEN series_id LIKE '%\_5700' THEN value END)`) is untouched, and
is fine *only if* the WHERE clause already narrows the rows. The same pattern
against the small `series` catalog is always fast. (Exception: the Eurostat
Comext country catalogs are not small — millions of series each — and their
text collation defeats prefix-index use entirely; never pattern-scan
`series_id` there. See the Comext section below.) When in doubt, resolve ids
explicitly first:

```sql
-- Step 1 (fast): resolve the id list on the catalog
SELECT series_id FROM series WHERE series_id LIKE 'us\_census\_hs\_M\_10d\_280530%'

-- Step 2 (fast): fetch with an explicit IN list — uses the index
SELECT series_id, time, value FROM data_points
WHERE series_id IN ('...', '...')
```

## National vs. sub-national series — the classic trap

Geographically decomposed datasets are dominated by state/region rows; the
single national aggregate is a needle. For a national question you must
filter for the national key, not just the metric.

Caveat: server-side dataset descriptions sometimes quote *raw* title
conventions (pipe-delimited keys like `State: All India` or prefixes like
`CPI 2024`). Because your filters run against the COALESCEd friendly titles,
those exact patterns often match nothing. Filter on the natural-language
fragment instead:

- MOSPI CPI national aggregate → `series_title ILIKE '%All India%'` (add
  `'%Combined%'` for the combined rural+urban sector), NOT
  `'%State: All India%'`.
- MOSPI WPI is national-only — no state key at all. Confirm a dataset is
  geographically split before forcing a geography filter.
- To identify a CPI base-year family when titles don't say: read the
  series description from a `series` fetch, or check the base-year
  calendar average ≈ 100 in the data itself.

Never chart a single state/region as if it were the national figure. If you
can't find the national aggregate, say so rather than substituting.

## Year-over-year on monthly data — never use LAG(value, 12)

A row offset equals a period offset only when every period is present. Series
have holes: a month the source never published, a quarter outside the
requested window, a period a WHERE clause removed. After a hole,
`LAG(value, 12)` compares each month with the month **thirteen** periods back,
the numbers stay plausible, and nothing errors.

Bad — silently wrong after any gap:

```sql
SELECT time, 100 * (value / LAG(value, 12) OVER (ORDER BY time) - 1) AS yoy_pct
FROM data_points
WHERE series_id = 'CUUR0000SA0' AND time >= '2019-01-01'
ORDER BY time
```

Good — join on the calendar month, so a missing prior period gives no row (or
a null with a LEFT JOIN) instead of a wrong number. Compare
`date_trunc('month', time)`, not `time` itself: the stored day of the month
differs between sources (first of the month for most, last day of the period
for some), and an exact-date join silently finds nothing for those.

```sql
SELECT cur.time,
       100 * (cur.value / prior.value - 1) AS yoy_pct
FROM data_points cur
JOIN data_points prior
  ON prior.series_id = cur.series_id
 AND date_trunc('month', prior.time) = date_trunc('month', cur.time) - interval '1 year'
WHERE cur.series_id = 'CUUR0000SA0' AND cur.time >= '2020-01-01'
ORDER BY cur.time
```

For quarterly series use `date_trunc('quarter', ...)` on both sides; for
month-over-month subtract `interval '1 month'`.

Also good — build a complete date spine first; on a spine every period has a
row, so a row offset is a period offset and LAG is correct:

```sql
WITH spine AS (
  SELECT generate_series('2019-01-01'::timestamp, '2026-06-01', interval '1 month') AS time
),
cpi AS (
  SELECT s.time, d.value
  FROM spine s
  LEFT JOIN data_points d
    ON date_trunc('month', d.time) = s.time AND d.series_id = 'CUUR0000SA0'
)
SELECT time, value, 100 * (value / LAG(value, 12) OVER (ORDER BY time) - 1) AS yoy_pct
FROM cpi WHERE time >= '2020-01-01' ORDER BY time
```

For one series, `get_series` with `transform="yoy_pct"` (or `"yoy_diff"` for a
rate) does the date-matched calculation on the server. For several series or
a merged table, `scripts/series_math.py yoy` matches on the calendar period
too.

The result's `coverage_note` and `missing_periods` name the holes in the rows
you received, and `run_sql` says so when the statement itself uses a fixed
LAG/LEAD offset over time. Act on them: state the missing period(s) in the
answer, leave the month blank in a chart rather than interpolating, and label
an aggregate that spans a hole as partial ("Q4 2025 average of two months").

## HS trade datasets

**Don't hand-write bilateral-trade SQL — generate it.** The plugin bundles
stdlib-only generators that encode every schema's ID grammar, partner codes,
units, and HS-level rules (run `--help` for subcommands):
`{plugin_root}/scripts/trade_sql.py` covers the six national customs schemas (census
`us_census_hs`, `china_customs`, `india_trade`, `korea_trade`, `japan_trade`,
`taiwan_trade`), `{plugin_root}/scripts/comext_sql.py` covers the 27 Eurostat
Comext schemas, and `{plugin_root}/scripts/hs_codes.py` resolves HS codes <->
names offline. Resolve `{plugin_root}` as described in `SKILL.md` before
invoking them; never assume the shell is at the plugin root.

For broad bilateral merchandise-trade questions, use
`references/report-patterns/bilateral-trade.md`; it has the report trigger and ready SQL
templates for monthly totals, latest-month YoY, YTD YoY, annual totals, and top
HS product drivers.

The core guardrails:

- For trade schemas other than Comext, filter with `dimensions` (`partner`,
  `flow`, `commodity`, `hs_level`) instead of parsing series IDs. Comext uses
  the indexed workflow below.
- Use exactly one HS level in an aggregation. HS-6 is the default for
  cross-country comparison; national 8/10-digit lines are finer detail and must
  not be summed with HS-6 rows.
- Keep value and quantity/weight series separate. For example, Korea KCS has
  value in `US$ Thousand` and weight in `kg`; a value report should filter
  `measurement_units = 'US$ Thousand'`.
- Normalize units before comparing reporters. For example, India DGCI&S values
  are `US$ Million`, while Korea KCS values are `US$ Thousand`.
- Query each reporter schema separately by default and compare in local
  computation — mirror statistics differ on units, timing, valuation,
  re-exports, and revisions, so state the reporter view explicitly. The
  one-schema scope is only a default search path, not a wall: qualified
  cross-schema references do execute, so a `UNION ALL` of per-reporter
  aggregations in one call is fine when every branch converts to a common
  unit.

### Eurostat Comext country schemas

Comext uses one physical schema per EU reporter, named
`eu_comext_<lowercase ISO2>`: for example, `eu_comext_de`, `eu_comext_fr`,
and `eu_comext_nl`. There is no `eu_comext` data schema. Each country catalog
is large enough that title searches and dimension-value scans can reach the
30-second SQL limit.

Exact series IDs are mandatory here, not just faster. Each country catalog
holds millions of series, and the text collation is not byte-ordered, so
`series_id LIKE 'prefix%'` cannot run on the index (it scans the table and
hits the 30-second timeout) and `>=`/`<` string ranges over `series_id`
return wrong or empty results. Equality joins on constructed IDs are index
probes and stay fast at any scale.

Use these rules:

- Never search or filter Comext's `dimensions` table by dimension values.
- Search the shared `eu_comext_lookup.product_codes` table by `product_code`,
  `product_name`, `hs2_code`, `hs4_code`, or `hs6_code`.
  It is a complete product-code lookup, including historical codes and their
  first and last observed dates.
- Build exact series IDs and join them to `data_points`, whose `series_id`
  index makes the fetch fast. The detailed ID shape is
  `eu_comext_{M|X}_{reporter}_{partner}_{te|ti|tl}_p1_cn8_{product_code}_{eur|kg|su}`.
  `M` means imports and `X` exports. Reporter and partner are lowercase ISO2
  codes, except that `xi` is Eurostat's code for Northern Ireland. The stored
  trade token follows the partner's status in each month: `te` outside the EU,
  `ti` inside the EU, and `tl` for Northern Ireland from 2021. A range that
  crosses an EU accession or Great Britain's February 2020 exit must query both
  exact series with non-overlapping date bounds. Use `comext_sql.py` so these
  changes are handled automatically. Its `uk` input combines `gb` with the
  separately stored `xi` series from 2021; `gb` alone excludes Northern Ireland
  from that point.
- Use `_eur` for trade value, `_kg` for weight, and `_su` for supplementary
  quantity. Never sum these metrics together. Supplementary units are
  product-specific, so return `series.measurement_units` with an exact CN8
  supplementary trend and group by that unit before summing reporters.
- For all-goods totals, use the exact `cn6_total` series instead of summing
  every CN8 product.
- For several reporters, either run one already-aggregated query per reporter
  schema and combine the small results locally, or `UNION ALL` the
  per-reporter aggregations in a single call — a union of exact-ID joins
  across all 27 member schemas completes well within the 30-second limit.
  What times out is pattern scanning, not combining: every branch must use
  the exact-ID join, never a `series_id` pattern.

To inspect product mappings, qualify the shared table from any country query:

```sql
SELECT product_code, product_name, hs2_code, hs4_code, hs6_code,
       first_observed, last_observed
FROM eu_comext_lookup.product_codes
WHERE product_name ILIKE '%textile%'
ORDER BY product_code
LIMIT 50;
```

For a broad category, keep the lookup and aggregation in the same SQL call so
the 50-row tool limit does not truncate the CN8 code list. This tested example
returns monthly German-reported textile imports from China in 2025. Run it
with `schema="eu_comext_de"`:

```sql
SELECT dp.time::date AS month,
       SUM(dp.value) AS value_eur
FROM eu_comext_lookup.product_codes p
JOIN data_points dp
  ON dp.series_id =
     'eu_comext_M_de_cn_te_p1_cn8_' || lower(p.product_code) || '_eur'
WHERE p.hs2_code BETWEEN '50' AND '63'
  AND p.is_numeric_cn8
  AND p.first_observed <= DATE '2025-12-01'
  AND p.last_observed >= DATE '2025-01-01'
  AND dp.time >= DATE '2025-01-01'
  AND dp.time < DATE '2026-01-01'
GROUP BY dp.time
ORDER BY dp.time;
```

Replace the reporter, partner, flow, trade token, dates, and HS grouping for
the question. For one named CN8 product, construct its exact ID directly. For
all goods, query the total series:

```sql
SELECT time::date AS month, value AS value_eur
FROM data_points
WHERE series_id = 'eu_comext_M_de_cn_te_p1_cn6_total_eur'
  AND time >= DATE '2025-01-01'
  AND time < DATE '2026-01-01'
ORDER BY time;
```

For several reporters in one call, `UNION ALL` the same exact-ID aggregation
per country schema. This tested example returns 2025 German- and
French-reported electronics (HS chapter 85) imports from China; run it with
`schema="eu_comext_de"` (any Comext schema works as the default):

```sql
SELECT cc, SUM(v) AS value_eur
FROM (
  SELECT 'de' AS cc, dp.value AS v
  FROM eu_comext_lookup.product_codes p
  JOIN eu_comext_de.data_points dp
    ON dp.series_id =
       'eu_comext_M_de_cn_te_p1_cn8_' || lower(p.product_code) || '_eur'
  WHERE p.hs2_code = '85'
    AND dp.time >= DATE '2025-01-01' AND dp.time < DATE '2026-01-01'
  UNION ALL
  SELECT 'fr', dp.value
  FROM eu_comext_lookup.product_codes p
  JOIN eu_comext_fr.data_points dp
    ON dp.series_id =
       'eu_comext_M_fr_cn_te_p1_cn8_' || lower(p.product_code) || '_eur'
  WHERE p.hs2_code = '85'
    AND dp.time >= DATE '2025-01-01' AND dp.time < DATE '2026-01-01'
) t
GROUP BY cc
ORDER BY cc;
```

## Pivoting to wide format

Chart data wants one row per time period with one column per series. Use
CASE WHEN with **GROUP BY on time** (omitting GROUP BY fails or duplicates
rows):

```sql
SELECT time,
       MAX(CASE WHEN series_id = 'LNS14000000' THEN value END) AS unemployment_rate,
       MAX(CASE WHEN series_id = 'LNS11300000' THEN value END) AS participation_rate
FROM data_points
WHERE series_id IN ('LNS14000000', 'LNS11300000')
  AND time >= '2019-01-01'
GROUP BY time
ORDER BY time
```

A period with no row in `data_points` is absent from the pivot, not a null
cell: the time axis skips it. Read the result's `coverage_note` before
computing changes across rows.

## Tabular data

Series with `data_type = 'tabular'` store rows in `tabular_data.row_data`
(JSONB), described by `series.tabular_columns`. The `get_series` tool handles
them transparently (returns columns + results like a timeseries) — prefer it.
For direct SQL: `row_data->>'column_name'` extracts text; cast with `::numeric`
for math.

## Efficiency

- Most questions need 2–4 data calls. Batch independent fetches in one turn.
- Don't re-fetch via `get_series` what a `run_sql` call already returned — both
  are equally chartable.
- Use `get_series` for 1–2 known ids; `run_sql` for 3+ series, joins,
  aggregations.
- Results cap at 50 rows. If a fetch comes back `"truncated": true`, aggregate
  in SQL (`GROUP BY date_trunc(...)`, a SUM/AVG/rank) rather than trying to
  pull the rest — a chart needs the aggregated result anyway.
- Zero rows means your filter missed — broaden the term or drop a condition
  and rerun. You revise faster and cheaper than the server's `auto_retry`
  LLM reviser.
