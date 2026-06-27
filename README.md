# UN Speeches Map

Interactive map of UN General Debate speeches: pick a speaker country and a year to
see which countries it mentioned (color = number of mentions), then click a country
to read its speech with the mentioned countries highlighted.

## Setup

```
pip install pandas geopandas shapely pyarrow openpyxl dash plotly
```

## Build (run once — regenerates the `build/` folder)

```
python preprocess.py
```

Produces `build/mentions_clean.parquet` and `build/geo_cache/<year>.json`.

## Run

```
python app.py
```

Open http://127.0.0.1:8050

## Notes

- **Mentions source:** `country_mentions_raw_good.csv`. Cleaning: `URS`→`SUN` (USSR),
  `ZAR`→`COD` (DR Congo), self-mentions removed, years capped at 2019.
- **Borders:** `cshapes.shp` (coverage 1946–2016). Years 2017–2019 reuse the 2016
  border set so the slider can reach 2019.
- **"Water" fix:** countries that did not exist in a given year (e.g. African
  colonies pre-independence) fall back to a grey land base instead of looking like ocean.
- **Speeches:** `UNGDC_1946-2025/TXT/`, loaded lazily on click; mentioned countries
  are highlighted in yellow (hover a highlight to see the country ISO code).
- **Performance:** geometry is simplified and cached per year at build time, so slider
  moves only recolor a small cached map.

## Tests

```
python -m pytest -v
```
