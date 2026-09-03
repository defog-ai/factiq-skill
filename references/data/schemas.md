# FactIQ Data Schemas

Static overview. The `get_data_catalog` tool returns the live, authoritative
catalog with full per-dataset descriptions — run it before relying on this
file. Admin-only schemas do not appear in the catalog, and requests to them
return 403. The `filings` schema is open to every account but is not in the
catalog either: it has no `series`/`data_points` tables. Its row under United
States lists the tables to use.

## United States

| Schema | Source | Coverage |
|---|---|---|
| `bls` | Bureau of Labor Statistics | Employment (CES), unemployment (CPS, e.g. `LNS14000000`), CPI, PPI, JOLTS job openings, wages, productivity |
| `oews` | BLS Occupational Employment & Wage Statistics | Wages and employment by occupation and metro area |
| `census` | Census Bureau | International trade (incl. `us_census_hs` — monthly imports/exports by HS commodity and partner country; quantity `_qty` series exist only at the 10-digit level, 6-digit lines are value-only), retail, housing, demographics, business formation applications (BFS; industry detail may be incomplete) |
| `bea` | Bureau of Economic Analysis | GDP and components, personal income/spending, regional accounts |
| `eia` | Energy Information Administration | Petroleum, natural gas, electricity, renewables — production, consumption, prices |
| `ers` | USDA Economic Research Service | Agricultural and food economics |
| `bts` | Bureau of Transportation Statistics | Transportation and freight |
| `filings` | Company filings: US SEC filers (10-K, 10-Q, 8-K, 20-F, 40-F, 6-K) and companies listed in Germany (`issuers.source_schema = 'german_filings'`) | The archive behind `search_company_filings`. Use the tool for one company; use `run_sql` on `filings` for joins and aggregations across companies. Start from `securities` (`ticker`, `issuer_id`, `is_primary`) and `issuers` (`id`, `canonical_name`). `source_filings` is one row per filing (`issuer_id`, `form_type`, `fiscal_year`, `fiscal_period`, `period_end`, `published_at`, `source_url`). `facts` is one row per extracted value (`filing_id`, `source_series_id`, `source_label`, `metric_class`, `period_start`, `period_end`, `period_basis`, `value`, `unit`, `segment_axis`, `segment_member`): always filter `is_serving AND is_active` (the other rows are superseded or never promoted) and by filing, series, or issuer, because the table holds more than 150 million rows. `source_series` (`source_series_id`, `issuer_id`, `dataset_code`, `title`, `measurement_units`, `frequency`, `is_serving`) and `serving_observations` (`source_series_id`, `time`, `value`, `unit`, `filing_id`) are the series and their points; `dataset_code` separates XBRL statements (`sec_10k`, `sec_10q`, `sec_20f`, `sec_40f`, `sec_6k_interim`), management's forward guidance (`sec_guidance`), and company-specific operating KPIs like ARR/RevPAR/subscribers (`sec_kpi`). `filing_claims` holds MD&A and earnings-release commentary and year-over-year risk-factor changes (`claim_kind`, `ticker`, `fiscal_year`, `fiscal_period`, `section`, `claim_family`, `topic`, `canonical_statement`, `verbatim_quote`, `source_url`; quote only `verbatim_quote`). `filing_risks` is one row per risk-factor heading in an annual report (`cik`, `fiscal_year`, `heading`, `summary`). The remaining tables are pipeline bookkeeping. `get_series(schema="filings", series_id=...)` and `describe_dataset("filings", "<dataset_code>")` also work: they return the same result as with `schema="sec"`, and the dataset codes are the `sec_*` codes listed above. Put a row's `source_url` beside any figure you use; `search_company_filings(format="json")` returns the same links as `source_link` on filing and fact nodes. |
| *(not a SQL schema)* | Earnings-call transcripts, decomposed into a claim graph | `search_earnings_transcripts` targets (selected with `search_target`): management statements (`claims`: `query`, `ticker` for tickers or `company_name` for company names (one or the other, both case-insensitive; `company_filter` is the old name of `ticker` and still works), `quarter_filter`, `claim_family`, claims-only `section`, `detail`, `limit`); Q&A pressure (`pressure_points`: query/company/quarter/linked `claim_family`/detail/limit; section ignored); company-level habits (`disclosure_profile`: direct lookup by the first ticker, not text or quarter search; other filters/detail/limit ignored); and corpus inventory (`coverage`: company/limit, not theme or quarter search; returns `calls_covered`, `earliest_period`, and `latest_period`). Text retrieval ranks strict matches above loose partial-term matches and uses trigram only when FTS is empty. For one-call notes, use coverage → exact quarter → bounded empty-query claims + pressure calls. Claim/pressure rows expose `transcript_id`, `source_block_index`, `qa_turn_id`, and `source_link`; `source_link.source_label` names the company or ticker, fiscal period, and earnings call transcript rather than the ingestion vendor. Quote only `verbatim_quote`, preserving any `[…]` omission marker (it stands for skipped transcript sentences between non-adjacent evidence spans); `canonical_statement` is normalized; neither `analyst_hypothesized` nor `mgmt_declined_to_confirm` is management speech. Put a provided source URL beside any used quote using the provided source label as link text; if it is null, report that the link is unavailable rather than searching for or inventing one. Never use `run_sql` on the gated `transcripts` schema or promise full-transcript/paginated access. See `references/report-patterns/earnings-intelligence.md` |
| *(not a SQL schema)* | Executive podcasts, TV interviews, and conference appearances | `search_media_appearances` performs deterministic strict lexical → loose any-term → trigram retrieval over precomputed claims and passage cards; no serving-time model. Use `search`, `claims`, `passages`, or `pressure_points` for timestamped paraphrase findings, `appearances` for video rows, and `coverage` for company-level structured-corpus inventory. Dates are publication/upload dates. Never quote `canonical_paraphrase`, query `transcripts` with SQL, or infer absence before checking coverage and bounded synonym searches. See `references/report-patterns/media-intelligence.md` |

## China

| Schema | Source | Coverage |
|---|---|---|
| `china` | National Bureau of Statistics | Macro indicators: GDP, industrial production, fixed-asset investment, prices |
| `china_customs` | General Administration of Customs (GACC) | Monthly imports/exports by HS commodity and partner (6- and 8-digit levels — never sum across levels; value in US$, quantities as separate `_qty` series). A separate `china_customs_prelim` dataset carries GACC's headline preliminary totals in different units (mostly CNY 100 million) — never mix it with the per-HS US$ data |

## India

| Schema | Source | Coverage |
|---|---|---|
| `mospi` | Ministry of Statistics (MOSPI) | CPI (national key: `State: All India`; note the 2012→2024 base change — two separate series families), WPI, IIP, GDP |
| `rbi` | Reserve Bank of India | Banking, credit, money supply, rates, forex reserves |
| `india_trade` | DGCI&S | Monthly imports/exports by HS commodity and partner (6- and 8-digit levels — never sum across levels) |
| `traffic` | Live road-traffic API | Bengaluru, India only — no other city, and no city dimension. 28 fixed road points x 3 metrics (84 series): `current_speed` (km/h), `travel_time` (seconds to cross the segment), `congestion_index` (current travel time / free-flow travel time; 1.0 = free-flowing). Dimensions are `metric`, `location` (point name, e.g. "Silk Board Junction"), `area` (central/east/north/south/west) and `road_type` (junction/ring_road/highway/arterial); `traffic.road_segments` lists each point with its area, road type and coordinates. History starts 2026-02-10 and can never start earlier — the source reports present conditions only, so nothing before that date exists or can be backfilled. Readings are irregular sub-daily snapshots (about every 30 minutes during the 07:00-10:00 and 17:00-21:00 local peaks, roughly hourly otherwise), so gaps between points vary — aggregate rather than assuming a fixed interval. `data_points.time` is UTC; Bengaluru local time is UTC+05:30 |

## South Korea

| Schema | Source | Coverage |
|---|---|---|
| `korea_trade` | Korea Customs Service (KCS) | Monthly imports/exports by HS commodity and partner (6-digit international and 10-digit national levels — never sum across levels; values are in US$ thousand and weight is stored as separate kg series) |

## Japan

| Schema | Source | Coverage |
|---|---|---|
| `japan_trade` | Japan Customs / Ministry of Finance | Monthly imports/exports by 9-digit HS line and partner country (no 6-digit level — group by the first 6 digits for international comparison; value in ¥ thousand, quantities as separate `_qty`/`_qty2` series with product-specific units) |

## Taiwan

| Schema | Source | Coverage |
|---|---|---|
| `taiwan_trade` | International Trade Administration (ITA), Ministry of Economic Affairs | Monthly imports/exports by commodity (6-digit international HS and 11-digit national CCC lines — never sum across levels; value in US$, no quantity series) |

## European Union

| Schema | Source | Coverage |
|---|---|---|
| `eu_comext_<iso2>` | Eurostat Comext | One schema per EU member-state reporter; monthly imports and exports by partner and detailed CN8 product, with trade value in euros and separate weight or supplementary-quantity series |

Use the reporter's lowercase ISO2 code: `eu_comext_de` for Germany,
`eu_comext_fr` for France, and `eu_comext_nl` for the Netherlands. All 27
reporters are available: `at`, `be`, `bg`, `hr`, `cy`, `cz`, `dk`, `ee`, `fi`,
`fr`, `de`, `gr`, `hu`, `ie`, `it`, `lv`, `lt`, `lu`, `mt`, `nl`, `pl`, `pt`,
`ro`, `sk`, `si`, `es`, and `se`. There is no `eu_comext` data schema. See the
Comext section of `sql-guide.md` before querying; its large country tables need
exact series IDs rather than dimension searches.

## United Kingdom

| Schema | Source | Coverage |
|---|---|---|
| `uk` | ONS, Bank of England, HMRC, DEFRA, DBT, DfT | Six datasets in one schema — see below |

The `uk` schema holds six datasets (filter on `dataset_code`):

- `ons_macro` — ~50 curated Office for National Statistics headline series:
  GDP and components (from 1955, plus the monthly GDP index), CPI/CPIH/RPI and
  core inflation, producer prices, the labour market and earnings, retail
  sales, public-sector borrowing and debt, trade balances, production,
  services, population, productivity. Series ids are `ons_macro.<cdid>`.
- `boe_macro_finance` — Bank of England: Bank Rate and SONIA (daily, from
  1975/1997), gilt par yields at 5/10/20 years, sterling FX rates and the
  effective index, M4 money and credit aggregates, quoted household mortgage
  and deposit rates. Series ids are `boe_macro_finance.<code>`.
- `hmrc_trade` — monthly UK goods trade from 2000 at three grains: totals per
  partner country (GBP value and net mass), UK-to-world per 2-digit HS
  chapter, and partner x chapter (value only). No product detail below the
  2-digit chapter. Product levels `TOTAL` and `HS2` restate the same trade —
  filter to exactly one product level and never sum across them. Chapter 99
  (miscellaneous/confidential goods) follows a slightly different suppression
  convention before and after 2016; avoid trend claims that hinge on it
  around that boundary.
- `dft_road_traffic` — Department for Transport road traffic for Great
  Britain (England, Scotland, and Wales only — not Northern Ireland): annual
  average daily flow per count point, total and by direction; sampled hourly
  roadside counts; regional and local-authority vehicle miles. AADF is an
  average flow at one road link — never sum it across count points; vehicle
  totals overlap their component classes.
- `defra_environment` — annual UK air pollutant emissions (from 1970) and
  cereal/oilseed yields by crop (tonnes per hectare, wheat from 1885).
- `dbt_trade` — annual inward-investment results (FDI projects and jobs);
  fiscal years are dated at January of their start year.

## Global / other

| Schema | Source | Coverage |
|---|---|---|
| `imf` | International Monetary Fund | Cross-country macro indicators, plus the earlier releases of the forecast publications (World Economic Outlook, Fiscal Monitor, the Regional Economic Outlooks, COFER) — see "IMF past releases" below |
| `worldbank` | World Bank | Development and macro indicators by country |
| `singstat` | Singapore Department of Statistics | Singapore national statistics |
| `portwatch` | IMF PortWatch (satellite-AIS) | Daily shipping: transit calls + trade capacity for 28 chokepoints (Suez, Hormuz, Malacca…), port calls + import/export volume estimates for 196 countries and 2,065 ports, 2019→, refreshed weekly (data runs a few days to a week behind) |
| `nasa_fires` | NASA FIRMS (VIIRS 375 m) | Every active-fire detection worldwide since 2012-01-20, one row per satellite pixel, plus pre-computed daily totals per country, per state, and per 0.1° cell. Refreshed daily. **Shaped unlike every other schema — read "The nasa_fires schema" below before writing SQL.** Most fire questions need no SQL at all: use `get_geo_data` (see `references/data/satellite.md`) |
| `satellite` | NASA / CNES satellite-derived | Monthly nighttime lights by country + state (economic-activity proxy, Asia focus, 2019→); lake & reservoir water levels from radar altimetry (650 water bodies incl. 88 Chinese, 15 major Indian reservoirs, 1990s→, per-overpass). Water-level stations come in two grades (`grade` dimension): `operational` updates ~weekly; `research` stations are frozen scientific archives (many end 2020-22) — always check the series `end_time` before presenting a level as current, and filter to operational for live readings |

## IMF past releases

The IMF publishes a forecast, then replaces it in place at the next release: once
the April 2026 World Economic Outlook is out, the October 2025 numbers are gone
from the IMF's site. The `imf` schema keeps both, so you can show how a forecast
moved between releases.

- The plain series id is always the **newest** release. `WEO_IND.NGDPD.A` is
  India's nominal GDP in US dollars from the current WEO.
- An earlier release is the same id with the release appended:
  `WEO_IND.NGDPD.A_2025OCT`, `WEO_IND.NGDPD.A_2025APR`. The suffix is the year
  and the three-letter month of publication.
- Earlier-release series sit in their own datasets — `dataset_code` is
  `weo_vintages`, `fm_vintages`, `afrreo_vintages`, `apdreo_vintages`,
  `whdreo_vintages` or `cofer_vintages` — and each one carries a `release`
  dimension (`dimension_code` `2025OCT`, `dimension_name` "October 2025")
  alongside the usual `country`, `indicator` and `frequency` dimensions.
- Example of what this answers: India's projected 2030 nominal GDP was
  6.77 trillion US dollars in the April 2025 WEO, 6.63 trillion in the October
  2025 WEO, and 6.17 trillion in the April 2026 WEO.
- The African and Western Hemisphere Regional Economic Outlooks (`afrreo`,
  `whdreo`) changed their indicator codes between releases, so for those two
  match an earlier release to the current one on the indicator's
  `dimension_name`, not on the code. WEO, Fiscal Monitor, APDREO and COFER codes
  are stable.
- How far back this goes depends on the publication: the IMF only makes its
  recent releases retrievable, so expect two or three per publication rather than
  a long history. Query `dimension_type = 'release'` to see which ones are
  actually there before promising a comparison.

## The nasa_fires schema

A fire detection is one satellite pixel that was burning at one moment. It
belongs to no series, so **this schema has no `series` table and no
`data_points` table** — the usual discovery method does not apply. Five tables:

- **`detections`** — one row per detection since 2012-01-20: `acq_ts` (UTC
  timestamp of the overpass), `latitude`, `longitude`, `frp` (fire radiative
  power in megawatts — the heat), `bright_ti4`, `bright_ti5`, `country_id`,
  `admin1_id`, `type`, `confidence` (`l`/`n`/`h`), `daynight` (`D`/`N`),
  `quality` (`S` final, `N` provisional).
- **`region_daily`** — daily `detections` and `frp_sum` per country and state.
  `admin1_id = 0` is the country total, stored as a row **alongside** the state
  rows — so filter to `admin1_id = 0` for countries or `admin1_id > 0` for
  states. Summing both double-counts.
- **`grid_daily`** — the same daily totals per 0.1° cell. `cell_lat` and
  `cell_lon` are `floor(degrees * 10)`, so cell 302 covers 30.2 to 30.3.
- **`countries`** and **`admin1`** — id-to-name lookups, joined on
  `country_id` / `admin1_id`.

**Read `type` before counting anything**: `0` vegetation fire, `1` volcano,
`2` gas flare or other industrial heat, `3` offshore, `-1` NASA has not
classified it yet — which is every detection from the last few weeks.
`type IN (0, -1)` is wildfire and crop burning; `type = 2` is flaring. A bare
`type = 0` silently drops the newest data.

A detection is not a fire: one fire produces many detections across many
overpasses, and a fire that burns out between overpasses produces none. Count
rows for extent, sum `frp` for intensity.

`run_sql` accepts a `page` argument **on this schema only** — 50 rows at a
time, with `has_more` telling you whether to ask for the next one. Give the
query an `ORDER BY` or the pages won't line up. Totals still belong in SQL;
never page through thousands of detections to add them up yourself.

Prefer `get_geo_data` (`references/data/satellite.md`) — it answers monthly or
daily counts for a region, one window compared across every year since 2012, a
map grid, and the raw points in a small box, with no SQL at all. Come here for
the shapes it doesn't cover: ranking many countries at once, joining fires to
another dataset, or splitting day passes from night passes.

## Picking schemas

- US labor/inflation → `bls` (plus `oews` for occupation-level wages)
- US GDP/income → `bea`; US trade → `census`
- Energy anything → `eia`
- India macro → check BOTH `mospi` and `rbi`
- Trade-war / commodity-flow stories → `census` + `china_customs` +
  `india_trade` + `korea_trade` + the relevant `eu_comext_<iso2>` schemas cover
  the same flows from each country's own records when those reporters are in scope
- UK anything → `uk` (macro, rates, trade, environment, road traffic in one schema)
- Cross-country comparisons → `imf` / `worldbank`
- How an IMF forecast has been revised between releases → the `*_vintages`
  datasets in `imf` (see "IMF past releases" above)
- Shipping disruptions, chokepoint transits (Suez/Hormuz/Malacca), real-time
  trade activity → `portwatch` (daily grain, satellite-AIS based, refreshed
  weekly; cite IMF PortWatch)
- Nighttime lights (activity proxy), reservoir/lake water levels (hydropower,
  irrigation, drought) → `satellite` schema; for on-demand fires/NO2/SO2/CO/
  aerosol/rainfall/NDVI over arbitrary regions → the `get_geo_data` tool
  instead (see `references/data/satellite.md`)
- Crop burning, wildfires, gas flaring → `get_geo_data` first; drop to the
  `nasa_fires` schema only for shapes the tool doesn't cover (see "The
  nasa_fires schema" above)
- Company-specific: quotes, price history, and company/ETF profiles →
  `get_market_data`; filed financials, segment/product/geography detail,
  forward guidance, or operating KPIs (ARR, RevPAR, ...) →
  `search_company_filings`; joins or aggregations across companies over the
  same filed data → `run_sql` on `filings`; what management said live on a
  call →
  `search_earnings_transcripts` (not SQL)
- What executives said in podcasts, television interviews, and conferences
  outside earnings calls → `search_media_appearances` (not SQL); follow `references/report-patterns/media-intelligence.md`

HS trade schemas (`us_census_hs` in census, `china_customs`, `india_trade`,
`korea_trade`) carry the same trade at multiple HS digit levels — filter to one
level and never sum across levels. Some reporters also store value and physical
quantity/weight as separate series; filter value series explicitly for value
reports.

Comext is the exception to the normal HS discovery method: do not filter its
`dimensions` table by value. Search `eu_comext_lookup.product_codes`, construct
exact series IDs, and query one reporter schema at a time.
