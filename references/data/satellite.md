# Satellite data — `get_geo_data`

Satellite-derived indicators, fetched live from the provider and aggregated
over a region server-side. Use them when official statistics are too slow for
the question or don't cover it: crop burning as it happens, industrial
activity from emissions, smoke and haze episodes, monsoon rainfall by state,
heatwaves, agricultural drought.

Read this before the first `get_geo_data` call in a session.

## The tool

```
get_geo_data(dataset, region, start_date, end_date, aggregation="monthly",
             resolution=None, include_flares=False)
```

Returns `{columns, results, units, region, organization, attribution,
caveats, notes?}` — a small time series, at most 50 rows (the spatial modes
below return up to 500, and `fires_viirs` time series up to 200). Results are
cached server-side, so repeating a call is cheap; the first call to an external
provider can take 5–30 s (rainfall occasionally longer). `fires_viirs` is the
exception: FactIQ holds every detection since 2012 in its own database, so
those calls answer in well under a second and no provider quota applies.

`resolution` and `include_flares` apply to `fires_viirs` only — see the fires
sections below. Passing either for another dataset is an error.

## Datasets

| dataset | measures | economic reading | history | lag |
|---|---|---|---|---|
| `fires_viirs` | Active-fire detections + fire radiative power (NASA FIRMS, VIIRS 375 m) | Crop-residue burning (Punjab/Haryana Oct–Nov, Indonesian burning season), deforestation fires, wildfires, flaring | 2012→ | 1 day (yesterday is the newest complete day) |
| `no2_tropomi` | Tropospheric NO₂ column, quality-filtered area mean (Sentinel-5P) | Industrial + power + traffic activity; recessions and lockdowns show up in weeks, not quarters | 2018→ | ~3 days |
| `so2_tropomi` | SO₂ column, area mean (Sentinel-5P) | Coal power generation, smelting, refining; also volcanic eruptions. Noisy away from strong sources — read it as a trend near known source regions, never as absolute background levels (single values can even be negative) | 2018→ | ~3 days |
| `co_tropomi` | CO column, area mean (Sentinel-5P) | Biomass and crop-residue burning, wildfire smoke, industrial combustion — pairs with `fires_viirs` (detections say where, CO says how much is going into the air). CO lingers for weeks and drifts across borders; compare the same season across years | 2018→ | ~3 days |
| `aerosol_index_tropomi` | UV aerosol index, area mean (Sentinel-5P) | Smoke plumes, dust storms, severe haze — the air-quality-disruption signal. Works over clouds, unlike the gas columns. A dimensionless index (sustained values above ~1 mean heavy smoke or dust), not a PM2.5 concentration | 2018→ | ~3 days |
| `ndvi_s2` | Vegetation index NDVI, cloud-masked area mean (Sentinel-2) | Crop condition ahead of harvest statistics — compare the same season across years (sowing → peak canopy → harvest is a normal arc, not a trend) | 2017→ | ~2–5 days |
| `precip_chirps` | Rainfall, gauge-calibrated satellite (CHIRPS 0.05°) | Monsoon adequacy, drought/flood risk → food prices, rural demand, hydro | 1981→ | ~2 days prelim |
| `precip_imerg` | Rainfall (NASA IMERG V07 Late, 0.1°) | Global drought, flood, and water-supply context where CHIRPS has no coverage | 2000→ | ~1–2 days |
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

## Windows and the row budget

At most 50 intervals per call (~4 years monthly, ~7 weeks daily) — except
`fires_viirs`, which allows 200 (~16 years monthly, ~6 months daily). Patterns:

- **Seasonal YoY** (the common ask — "Punjab stubble burning this year vs
  last 5"): for `fires_viirs` use `aggregation="seasons"` — **one call** gives
  you every year (see below). For the other datasets, one call per season, e.g.
  `2021-10-01→2021-11-30`, `2022-10-01→2022-11-30`, … in parallel. Don't fetch
  whole years to compare two months.
- **Long trends**: split at the 50-month boundary (e.g. 2018–2021, 2022–2025)
  and stitch. `fires_viirs` needs no splitting — the whole 2012→ history fits
  in one monthly call.
- Daily grain is for event windows (a flood week, a heatwave fortnight), not
  long ranges.

## Comparing a season across every year — `aggregation="seasons"` (fires_viirs only)

Ask for one calendar window and get one row per year since 2012:
`year`, `fire_detections`, `total_frp_mw`. The window's month and day are
repeated in each year, so it answers "is this burning season worse than the
ones before it" in a single call.

```
get_geo_data("fires_viirs", "India/Punjab", "2025-10-15", "2025-11-15",
             aggregation="seasons")
```

- The year you pass doesn't matter — the same list of seasons comes back
  either way. Only the month and day are used.
- A window crossing new year (20 Dec → 10 Feb) keeps its length and is
  labelled by the year it starts in, so a season isn't split in two.
- Seasons whose start date hasn't arrived yet are left out.
- Window capped at 366 days: it has to be a season, not several years.

## Mapping where the signal is — `aggregation="grid"`

`fires_viirs`, `ndvi_s2`, and the four `*_tropomi` datasets accept a third
aggregation, `"grid"`, that answers *where* the signal is instead of *how
much over time*: no time series — one row per lat/lon grid cell (cell-centre
latitude and longitude plus the cell's values) aggregating the whole
requested window.

- `fires_viirs` cells carry `fire_detections` and `total_frp_mw`. These are
  **detection clusters, not fire perimeters** — say "detected fire activity",
  not "burned area". If more than 500 cells had fires, the least-active are
  dropped and a `notes` entry says how many and what share of detections the
  kept cells still cover.
- `ndvi_s2` and the `*_tropomi` cells carry the window-mean value (`ndvi`,
  `no2_mol_m2`, `so2_mol_m2`, `co_mol_m2`, `uv_aerosol_index`) plus
  `valid_obs_share`. The same cloud/quality rule as the time series applies
  per cell — a cell with a low share rests on few clear-sky views.
- Window is capped at **92 days** — one season or one event per call — except
  `fires_viirs`, which allows **366 days**.
- Cell size: for the Sentinel datasets it is picked automatically from the
  region's size and never goes finer than the dataset's native resolution.
  For `fires_viirs` you can pick it yourself with `resolution` (see below).
  At most 500 cells come back either way.
- Use it to feed a map (see the Maps section of
  `references/output/chart-spec.md`): a bubble map of a fire event or burning
  season, NO₂ across an industrial belt, NDVI across a growing region. Use
  `monthly`/`daily` for trends and comparisons.

### Choosing the fire map's cell size — `resolution` (fires_viirs only)

`resolution` is the cell size in degrees, one of `0.005, 0.01, 0.02, 0.05,
0.1, 0.2, 0.5, 1, 2, 5`. Anything else is an error listing these.

Leave it out and the finest cell that still maps the whole region in one call
is chosen, never finer than 0.1° — 0.1° for a small area, 0.2° for a state like
Punjab, coarser for a country. Set it when the automatic choice is wrong for
the map you want:

```
# Where in Punjab did it burn, street-block detail
get_geo_data("fires_viirs", "bbox:74,29.5,77,32", "2025-11-01", "2025-11-07",
             aggregation="grid", resolution=0.01)
```

Cells at 0.1° or coarser are read from pre-computed daily totals; finer cells
are computed from the individual detections. Either way you get the 500
busiest cells, and a `notes` entry says if less busy ones were dropped.

## Exact fire locations — `aggregation="points"` (fires_viirs only)

`fires_viirs` also accepts `"points"`: the individual detections, one row per
detection — `latitude`, `longitude`, `date`, `frp_mw`, `confidence` (`l` low,
`n` nominal, `h` high) — exact satellite coordinates, no binning.

- Works only when the window has **at most 500 detections**. Above that the
  call returns an error naming the actual count — narrow the region or dates,
  or switch to `"grid"`.
- Window capped at 366 days, same as `"grid"` for fires.
- `"grid"` always bins, even when the window is small — ask for `"points"`
  explicitly when the map needs exact locations.

## Gas flares and other non-fires — `include_flares` (fires_viirs only)

NASA labels each detection: vegetation fire, volcano, gas flare or other
permanent industrial heat source, or offshore. **Flares and the rest are left
out by default**, in every fires mode, because a gas field burns every day of
the year and would otherwise read as a permanent wildfire.

Set `include_flares=True` to count every detection NASA publishes — the right
call when the question *is* about flaring (Basra, the Permian, the Niger
Delta) or volcanic activity. Say which you used; the two give very different
counts over an oil-producing region.

Detections from the last few weeks have no label yet. They are counted as
vegetation fires either way, so the newest data is never silently missing.

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
  when arguing intensity rather than frequency. One fire makes many
  detections across many overpasses, and a fire that starts and dies between
  overpasses makes none.
- `fires_viirs` `notes` says when part of the requested window is not loaded
  yet. Those days count as zero, not as days with no fires — read the note
  before calling a recent stretch quiet.
- `precip_chirps` recent days are preliminary and revised in the final
  monthly product (~3rd week of the following month).
- `precip_chirps` ends at 50°N and 50°S. Use `precip_imerg` outside
  that range. Within CHIRPS coverage, prefer its finer, gauge-calibrated data.
- `precip_imerg` returns IMERG V07 Late satellite rainfall on a global 0.1°
  grid. It returns daily totals in millimetres and adds
  them for monthly output. A final month can be incomplete; read the response
  notes before using it. It does not show rainfall differences inside one cell.
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

- Not a raster or tile service: results are regional aggregates (plus the
  grid snapshots and fire detection points above) — never imagery.
- Not the only way to reach the fire data. Every detection since 2012 is also
  queryable with `run_sql` as the `nasa_fires` schema, for shapes this tool
  doesn't cover (ranking countries, joining fires to something else, night
  passes versus day passes). See `references/data/schemas.md`. Use the tool
  first — it answers the common questions with no SQL.
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
