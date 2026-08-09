# Satellite data — `get_geo_data`

Satellite-derived indicators, fetched live from the provider and aggregated
over a region server-side. Use them when official statistics are too slow for
the question or don't cover it: crop burning as it happens, industrial
activity from emissions, smoke and haze episodes, monsoon rainfall by state,
heatwaves, agricultural drought.

Read this before the first `get_geo_data` call in a session.

## The tool

```
get_geo_data(dataset, region, start_date, end_date, aggregation="monthly")
```

Returns `{columns, results, units, region, organization, attribution,
caveats, notes?}` — a small time series, at most 50 rows. Results are cached
server-side, so repeating a call is cheap; the first call to an external
provider can take 5–30 s (rainfall occasionally longer).

## Datasets

| dataset | measures | economic reading | history | lag |
|---|---|---|---|---|
| `fires_viirs` | Active-fire detections + fire radiative power (NASA FIRMS, VIIRS 375 m) | Crop-residue burning (Punjab/Haryana Oct–Nov, Indonesian burning season), deforestation fires, wildfires, flaring | 2012→ | ~3 h |
| `no2_tropomi` | Tropospheric NO₂ column, quality-filtered area mean (Sentinel-5P) | Industrial + power + traffic activity; recessions and lockdowns show up in weeks, not quarters | 2018→ | ~3 days |
| `so2_tropomi` | SO₂ column, area mean (Sentinel-5P) | Coal power generation, smelting, refining; also volcanic eruptions. Noisy away from strong sources — read it as a trend near known source regions, never as absolute background levels (single values can even be negative) | 2018→ | ~3 days |
| `co_tropomi` | CO column, area mean (Sentinel-5P) | Biomass and crop-residue burning, wildfire smoke, industrial combustion — pairs with `fires_viirs` (detections say where, CO says how much is going into the air). CO lingers for weeks and drifts across borders; compare the same season across years | 2018→ | ~3 days |
| `aerosol_index_tropomi` | UV aerosol index, area mean (Sentinel-5P) | Smoke plumes, dust storms, severe haze — the air-quality-disruption signal. Works over clouds, unlike the gas columns. A dimensionless index (sustained values above ~1 mean heavy smoke or dust), not a PM2.5 concentration | 2018→ | ~3 days |
| `ndvi_s2` | Vegetation index NDVI, cloud-masked area mean (Sentinel-2) | Crop condition ahead of harvest statistics — compare the same season across years (sowing → peak canopy → harvest is a normal arc, not a trend) | 2017→ | ~2–5 days |
| `precip_chirps` | Rainfall, gauge-calibrated satellite (CHIRPS 0.05°) | Monsoon adequacy, drought/flood risk → food prices, rural demand, hydro | 1981→ | ~2 days prelim |
| `precipitation_power` | Rainfall (NASA POWER, MERRA-2 0.5°) | Global drought, flood, and water-supply context where CHIRPS has no coverage | 1981→ | ~3 days |
| `temperature_power` | 2 m air temperature mean/max/min (NASA POWER, MERRA-2 0.5°) | Heatwaves → electricity demand, labour productivity, crop stress | 1981→ | ~3 days |
| `soil_moisture_power` | Root-zone soil wetness 0–1 (NASA POWER, MERRA-2) | Sowing conditions and agricultural drought ahead of production data | 1981→ | ~3 days |

## Regions

- Any country: `"IND"`, `"China"`, `"Indonesia"` (ISO3 or plain name).
- States/provinces for: **IND, CHN, IDN, VNM, THA, MYS, PHL, PAK, BGD, LKA,
  MMR, KHM, NPL, KOR, JPN, TWN, USA** — `"India/Punjab"`, `"CHN/Guangdong"`,
  `"USA/Texas"`. Misspellings and common variants resolve (a `notes` entry
  says what matched); if a name can't resolve, the error lists valid names.
- Anywhere else: `"bbox:west,south,east,north"` in degrees.

The response's `region.resolved` echoes what was actually used — repeat it in
your narrative so the reader knows the exact geography.

## Windows and the 50-row budget

At most 50 intervals per call (~4 years monthly, ~7 weeks daily). Patterns:

- **Seasonal YoY** (the common ask — "Punjab stubble burning this year vs
  last 5"): one call per season, e.g. `2021-10-01→2021-11-30`,
  `2022-10-01→2022-11-30`, … in parallel. Don't fetch whole years to compare
  two months.
- **Long trends**: split at the 50-month boundary (e.g. 2018–2021, 2022–2025)
  and stitch.
- **`fires_viirs` is additionally capped at 3 years per call** (the provider
  serves 5-day chunks); seasonal calls sidestep this entirely.
- Daily grain is for event windows (a flood week, a heatwave fortnight), not
  long ranges.

## Mapping a fire's footprint — `aggregation="grid"` (fires_viirs only)

`fires_viirs` accepts a third aggregation, `"grid"`, that answers *where* the
burning is instead of *how much over time*: no time series — one row per
lat/lon grid cell (cell-centre latitude and longitude, detection count, total
fire radiative power) aggregating the whole requested window.

- Window is capped at **92 days**: one burning season or one fire event per
  call, not a multi-year history.
- Cell size is picked automatically from the region's size — roughly 1 km
  cells for a single fire complex, coarser for a whole large country. At most
  500 cells come back; if there were more, the least-active are dropped and a
  `notes` entry says how many and what share of detections the kept cells
  still cover.
- Cells are **detection clusters, not fire perimeters** — say "detected fire
  activity", not "burned area".
- Use it to feed a coordinate bubble map (see the Maps section of
  `references/output/chart-spec.md`) of a fire event or a burning season;
  use `monthly`/`daily` for trends and comparisons.

## Reading the results honestly

- **Sentinel datasets (`no2_tropomi`, `so2_tropomi`, `co_tropomi`,
  `aerosol_index_tropomi`, `ndvi_s2`): check `valid_obs_share` on every
  row.** It is the share of pixels with a valid, cloud-free retrieval. Below
  ~0.2 the mean rests on a handful of clear-sky views — say so if you use it.
  Fully clouded intervals (South Asian monsoon: typically Jun–Sep) are
  **omitted from results** and named in `notes`; never interpolate through
  them silently. (`aerosol_index_tropomi` retrieves through clouds, so its
  share is usually high.)
- `ndvi_s2` is strongly seasonal: month-over-month moves mix crop cycle with
  weather. The honest comparison is same-month (or same-season) across years —
  e.g. Punjab wheat peaks Jan–Feb (~0.65–0.70 NDVI); a weak peak vs prior
  years is the signal, not the Nov→Feb climb.
- `fires_viirs` counts overpass detections, not fires put out — cloud cover
  suppresses counts; compare like-for-like seasons, and prefer `total_frp_mw`
  when arguing intensity rather than frequency.
- `precip_chirps` recent days are preliminary and revised in the final
  monthly product (~3rd week of the following month).
- `precip_chirps` ends at 50°N and 50°S. Use `precipitation_power` outside
  that range. Within CHIRPS coverage, prefer its finer, gauge-calibrated data.
- `precipitation_power` returns daily rainfall totals in millimetres and adds
  them for monthly output. A final month can be incomplete; read the response
  notes before using it. It is 0.5° reanalysis and does not show local showers.
- POWER datasets are 0.5° reanalysis — honest at state/country scale, blind to
  city microclimates. Very small or very large regions sample the centroid
  cell (a `notes` entry appears for large ones).
- `notes` can also report partially failed fetches ("may undercount — retry").
  Retry once before using such a result.

## Attribution

Every response carries an `attribution` string — put it in the chart/report
`sources`, exactly as given. The Copernicus one ("Contains modified Copernicus
Sentinel-5P data…") is a licence requirement, not a courtesy.

## What this tool is not

- Not a raster or tile service: results are regional aggregates (plus, for
  fires only, the grid-cell footprint above) — never imagery.
- Several satellite signals live in the WAREHOUSE instead of this tool, as
  the `satellite` SQL schema: monthly **nighttime lights** by country/state
  (precomputed — no hosted aggregation API exists) and **lake/reservoir water
  levels** from radar altimetry (per-station series; search by reservoir
  name, e.g. "srisailam"). Shipping/trade activity is the `portwatch` schema
  (satellite-AIS chokepoint transits, port calls, import/export estimates).
  See `references/data/schemas.md`.
- For anything already in the warehouse (official rainfall indices, IMD data,
  electricity output), prefer the curated series — satellite data complements
  statistics, it doesn't replace them.
