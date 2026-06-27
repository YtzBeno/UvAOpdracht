# UN Speeches Map — Improvement Design

**Date:** 2026-06-14
**Project:** Interactive map of UN General Debate speeches — per year, see which country a speaker mentions, click a country to read its speech.

## Goal

Fix the issues raised in the TA check-in and the team's open questions, without changing the core concept (speaker → who they mention, click to read speech).

## Current state

- `app2.py` — single 296-line Dash app: choropleth (speaker + year → mention counts), click a country → modal popup with speech text.
- Data on disk:
  - **Speeches:** `UNGDC_1946-2025/TXT/Session NN - YYYY/ISO_NN_YYYY.txt` (1946–2025).
  - **Mentions:** `country_mentions_raw_good.csv` (135,546 rows, includes `positions` with char offsets + surface forms), plus two thinner variants.
  - **Borders:** `cshapes.shp` (cShapes 2.0 historical boundaries, coverage **up to 2019 only**).
  - **Index:** `speakers_with_txt_path.xlsx` maps each (year, ISO) speech to its `txt_path`.

## Root-cause diagnosis

| Symptom (TA / team) | Root cause |
|---|---|
| Parts of Africa render as **water** at some years | Pre-independence countries have **no cShapes polygon** for that year; the app hides the base earth (`visible=False`), so gaps look like ocean. |
| Map / speeches load **slowly** | `gdf_yearly` duplicates every country into one row **per year**; every callback re-serializes GeoJSON via `to_json()`; all speeches would load into RAM at startup. |
| **Mentions** are wrong | Target codes are historical/non-standard (`URS`=USSR, `YUG`, `DDR`, `GIN`="New Guinea" = actually Guinea's code) and don't match cShapes → silently disappear. Self-mentions and some false positives inflate counts. |
| **Slider** wrong max | Mentions run to 2025 but borders stop at 2019. |

## Decisions

- **Canonical mentions source:** `country_mentions_raw_good.csv` (only file with `positions`, needed for highlighting).
- **Speech display:** restyled **modal popup** (kept, not a side panel).
- **Direction:** **outgoing only** (selected speaker → countries they mention). No reverse toggle.
- **Year range:** hard-cap **1946–2019**.

## Design

### 1. Data correction (`preprocess.py`, run once)

- Load `country_mentions_raw_good.csv`.
- Apply a **code-standardization map** so target codes match cShapes ISO (`ISO1AL3`) for the relevant year. At minimum: `URS`→`SUN` (USSR), `GIN`→`PNG` (New Guinea fix), plus historical entities present in the data (`YUG`, `CSK`, `DDR`, `DEU`/`FRG`, `SUN`, `YMD`/`YEM`, etc.). The exact list is derived by diffing distinct `target_iso` against cShapes codes during implementation and logging unmatched codes.
- Drop **self-mentions** (`speaker_iso == target_iso`).
- Drop rows with `year > 2019`.
- Aggregate to `(speaker_iso, target_iso_std, year) → mentions`.
- Write `mentions_clean.parquet`.
- Keep a separate lazy path for `positions` (parsed on demand per clicked speech, not preprocessed for all rows).

### 2. Geometry cache (`preprocess.py`, run once)

- Load `cshapes.shp`, reproject to EPSG:4326.
- **Simplify** geometries (tolerance tuned so the world still looks right but GeoJSON is much smaller).
- For each year 1946–2019, build the set of polygons valid that year and write a cached **GeoJSON per year** (e.g. `geo_cache/YYYY.json`) keyed by ISO code.
- This replaces the per-callback `gdf_yearly` expansion + `to_json()`.

### 3. App (`data.py` + `app.py`)

**`data.py`**
- `load_geo(year)` → cached GeoJSON for that year (read once, memoized).
- `load_mentions()` → `mentions_clean.parquet`.
- `get_speech(iso, year)` → lazily read the `.txt` via the xlsx path index (cached with `functools.lru_cache`).
- `get_highlight_spans(iso, year)` → parse `positions` for that speaker/year on demand → list of (start, end, target_iso, surface).

**`app.py`**
- Layout: speaker dropdown, year slider (1946–2019, marks every 5 yrs), choropleth, restyled modal.
- **Map callback:** merge cached GeoJSON for the year with cleaned mentions for the speaker; color by mention count.
  - **Border fix:** `update_geos(visible=True, showland=True, landcolor="#e9e9e9", showocean=True, oceancolor="#d6e8f5", showcountries=False)` so non-existent countries fall back to grey land, not water.
- **Speech modal callback:** on click, load speech text and render with mentioned-country **surface forms highlighted** (colored/bold `<span>`s built from `get_highlight_spans`). Hover shows the target country. Restyled modal (lighter, readable typography, clear close button).

### 4. Performance expectations

- Startup: load parquet + lazy speech access (no 11k-file preload).
- Per slider move: read one small cached GeoJSON + a parquet filter + recolor. Target: sub-second.

## Components & boundaries

- `preprocess.py` — pure batch job; inputs = raw CSV + shapefile, outputs = `mentions_clean.parquet` + `geo_cache/*.json`. Re-runnable, no app dependency.
- `data.py` — read-only accessors over the preprocessed artifacts + speech files. No Dash imports.
- `app.py` — Dash layout + callbacks only; depends on `data.py`.

## Out of scope (YAGNI)

- Reverse/incoming-mention view.
- Years after 2019.
- Side-panel layout.
- Re-running the NLP mention detection (we correct codes, not re-detect).

## Testing / verification

- `preprocess.py` logs: # rows dropped (self-mentions, post-2019), # target codes still unmatched after standardization (should be near zero for major historical states).
- Spot-check: USSR (`SUN`) colors in 1946–1991; Yugoslavia visible in its years; no African "water" gaps at 1960/1990/2019.
- Manual run: slider stops at 2019; clicking a country shows speech with highlighted mentions; slider response feels instant.
