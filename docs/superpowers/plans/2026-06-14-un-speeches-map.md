# UN Speeches Map Improvement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the UN speeches map — correct mentions, fix the "Africa as water" borders, cap the slider at 2019, make it fast, and highlight mentioned countries inside each speech.

**Architecture:** Split the single `app2.py` into three units: a one-time `preprocess.py` (clean mentions → parquet, simplify + cache borders per year → JSON), a read-only `data.py` accessor layer (lazy speeches, highlight spans), and `app.py` (Dash UI + callbacks). The app reads only preprocessed artifacts so slider moves are fast.

**Tech Stack:** Python 3.11, pandas, geopandas, shapely, pyarrow, dash, plotly. Tests with pytest.

---

## Key data facts (verified)

- Canonical mentions: `country_mentions_raw_good.csv` (has `positions`). After filtering to year ≤ 2019, only 3 target codes don't match cShapes `ISO1AL3`: `URS`, `ZAR`, `PSE`.
- Standardization: `URS`→`SUN` (USSR polygon, 1946–1991), `ZAR`→`COD` (DR Congo). `PSE` has no polygon → remains uncolored (expected).
- cShapes columns of interest: `ISO1AL3`, `GWSYEAR`, `GWEYEAR`, `CNTRY_NAME`. Polygons exist 1946–**2016** (2017–2019 empty). For years 2017–2019 we reuse the 2016 polygon set so the slider can reach 2019.
- Some ISO codes have multiple cShapes rows in a year (e.g. USSR successor slivers); when building a year's geometry we keep, per ISO, the polygon whose `[GWSYEAR, GWEYEAR]` contains the year, dissolving duplicates by union.
- Speeches: `UNGDC_1946-2025/TXT/Session NN - YYYY/ISO_NN_YYYY.txt`. Filename → ISO = first 3 chars; year from folder.

## File Structure

- Create `preprocess.py` — batch job. Inputs: `country_mentions_raw_good.csv`, `cshapes.shp`. Outputs: `build/mentions_clean.parquet`, `build/geo_cache/<year>.json` (1946–2019).
- Create `data.py` — read-only accessors over `build/` + speech files. No dash imports.
- Create `app.py` — Dash layout + callbacks. Replaces `app2.py` (kept for reference).
- Create `tests/test_preprocess.py` — unit tests for the pure standardization/cleaning functions.
- Constant `CODE_MAP = {"URS": "SUN", "ZAR": "COD"}` lives in `preprocess.py` and is imported by tests.

---

## Task 1: Mention-cleaning pure functions

**Files:**
- Create: `preprocess.py`
- Test: `tests/test_preprocess.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_preprocess.py
import pandas as pd
from preprocess import CODE_MAP, standardize_targets, clean_mentions

def test_code_map_values():
    assert CODE_MAP["URS"] == "SUN"
    assert CODE_MAP["ZAR"] == "COD"

def test_standardize_targets_maps_known_codes():
    df = pd.DataFrame({"target_iso": ["URS", "ZAR", "USA"]})
    out = standardize_targets(df)
    assert list(out["target_std"]) == ["SUN", "COD", "USA"]

def test_clean_mentions_drops_self_and_post2019_and_aggregates():
    df = pd.DataFrame({
        "speaker_iso": ["ARG", "ARG", "ARG", "ARG", "ARG"],
        "target_iso":  ["BRA", "BRA", "ARG", "URS", "USA"],
        "year":        [1960,  1960,  1960,  1960,  2020],
        "count":       [2,     3,     9,     1,     5],
    })
    out = clean_mentions(df)
    # self-mention (ARG->ARG) dropped, 2020 dropped, BRA rows aggregated to 5, URS->SUN
    rows = {(r.speaker_iso, r.target_std, r.year): r.mentions for r in out.itertuples()}
    assert rows == {("ARG", "BRA", 1960): 5, ("ARG", "SUN", 1960): 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_preprocess.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError` (functions not defined).

- [ ] **Step 3: Write minimal implementation**

```python
# preprocess.py  (top portion)
import pandas as pd

MAX_YEAR = 2019
CODE_MAP = {"URS": "SUN", "ZAR": "COD"}

def standardize_targets(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["target_std"] = df["target_iso"].replace(CODE_MAP)
    return df

def clean_mentions(df: pd.DataFrame) -> pd.DataFrame:
    df = standardize_targets(df)
    df = df[df["year"] <= MAX_YEAR]
    df = df[df["speaker_iso"] != df["target_std"]]
    out = (df.groupby(["speaker_iso", "target_std", "year"], as_index=False)["count"]
             .sum()
             .rename(columns={"count": "mentions"}))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_preprocess.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit** (skip if not a git repo)

```bash
git add preprocess.py tests/test_preprocess.py
git commit -m "feat: mention cleaning + code standardization"
```

---

## Task 2: Write cleaned mentions parquet

**Files:**
- Modify: `preprocess.py`

- [ ] **Step 1: Add the parquet build function**

```python
# preprocess.py
import os

BUILD_DIR = "build"

def build_mentions(csv_path="country_mentions_raw_good.csv",
                   out_path=os.path.join(BUILD_DIR, "mentions_clean.parquet")):
    os.makedirs(BUILD_DIR, exist_ok=True)
    df = pd.read_csv(csv_path, usecols=["speaker_iso", "target_iso", "year", "count"])
    clean = clean_mentions(df)
    clean.to_parquet(out_path, index=False)
    print(f"[mentions] {len(df)} raw rows -> {len(clean)} clean rows -> {out_path}")
    return clean
```

- [ ] **Step 2: Run it and verify output**

Run:
```bash
python -c "import preprocess as p; d=p.build_mentions(); print(d['year'].min(), d['year'].max()); print(sorted(d['target_std'].unique())[:5])"
```
Expected: prints year range `1946 2019`, a parquet file at `build/mentions_clean.parquet`, and no `URS`/`ZAR` in target_std.

- [ ] **Step 3: Commit** (skip if not a git repo)

```bash
git add preprocess.py
git commit -m "feat: emit mentions_clean.parquet"
```

---

## Task 3: Simplify + cache per-year border GeoJSON

**Files:**
- Modify: `preprocess.py`

- [ ] **Step 1: Add geometry build function**

```python
# preprocess.py
import json
import geopandas as gpd

SHP_PATH = "cshapes.shp"
ISO_COL, FROM_COL, TO_COL = "ISO1AL3", "GWSYEAR", "GWEYEAR"
MIN_YEAR = 1946
GEO_MAX_DATA_YEAR = 2016     # cShapes has no polygons after 2016
SIMPLIFY_TOL = 0.05          # degrees; shrinks GeoJSON a lot, still looks right

def build_geo(shp_path=SHP_PATH, out_dir=os.path.join(BUILD_DIR, "geo_cache")):
    os.makedirs(out_dir, exist_ok=True)
    gdf = gpd.read_file(shp_path).to_crs(epsg=4326)
    gdf = gdf[gdf[ISO_COL].notna()].copy()
    gdf["geometry"] = gdf["geometry"].simplify(SIMPLIFY_TOL, preserve_topology=True)
    for year in range(MIN_YEAR, MAX_YEAR + 1):
        q = min(year, GEO_MAX_DATA_YEAR)   # reuse 2016 borders for 2017-2019
        sub = gdf[(gdf[FROM_COL] <= q) & (gdf[TO_COL] >= q)].copy()
        # one geometry per ISO (union duplicates), keep id = ISO
        sub = sub.dissolve(by=ISO_COL, as_index=False)
        sub["id"] = sub[ISO_COL]
        geo = json.loads(sub[["id", "geometry"]].to_json())
        with open(os.path.join(out_dir, f"{year}.json"), "w") as f:
            json.dump(geo, f)
    print(f"[geo] wrote {MAX_YEAR - MIN_YEAR + 1} year files to {out_dir}")

def build_all():
    build_mentions()
    build_geo()

if __name__ == "__main__":
    build_all()
```

- [ ] **Step 2: Run the full preprocess**

Run: `python preprocess.py`
Expected: prints mention + geo summaries; `build/geo_cache/1946.json` … `2019.json` exist.

- [ ] **Step 3: Verify no "water" gaps and 2019 has borders**

Run:
```bash
python -c "
import json
for y in [1960, 1990, 2016, 2019]:
    g = json.load(open(f'build/geo_cache/{y}.json'))
    isos = [f['properties']['id'] for f in g['features']]
    print(y, 'countries:', len(isos), 'Africa sample COD in set:', 'COD' in isos)
"
```
Expected: each year has ~100–195 countries; 2019 is non-empty (reused 2016); `COD` present.

- [ ] **Step 4: Commit** (skip if not a git repo)

```bash
git add preprocess.py
git commit -m "feat: cache simplified per-year border geojson"
```

---

## Task 4: Data accessor layer

**Files:**
- Create: `data.py`
- Test: `tests/test_data.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_data.py
import data

def test_load_geo_has_features():
    g = data.load_geo(1960)
    assert g["features"] and "id" in g["features"][0]["properties"]

def test_get_speech_returns_text():
    txt = data.get_speech("ARG", 1946)
    assert isinstance(txt, str) and len(txt) > 50

def test_get_speech_missing_returns_none():
    assert data.get_speech("ZZZ", 1946) is None

def test_highlight_spans_sorted_nonoverlapping_fields():
    spans = data.get_highlight_spans("AUS", 1946)
    assert all({"start", "end", "target", "surface"} <= set(s) for s in spans)
    starts = [s["start"] for s in spans]
    assert starts == sorted(starts)
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_data.py -v`
Expected: FAIL (module/functions missing).

- [ ] **Step 3: Implement `data.py`**

```python
# data.py
import os, json, ast, glob, functools
import pandas as pd

BUILD_DIR = "build"
SPEECH_ROOT = "UNGDC_1946-2025/TXT"
RAW_CSV = "country_mentions_raw_good.csv"

_mentions = pd.read_parquet(os.path.join(BUILD_DIR, "mentions_clean.parquet"))

def load_mentions():
    return _mentions

@functools.lru_cache(maxsize=128)
def load_geo(year: int):
    with open(os.path.join(BUILD_DIR, "geo_cache", f"{year}.json")) as f:
        return json.load(f)

@functools.lru_cache(maxsize=4096)
def _speech_path(iso: str, year: int):
    hits = glob.glob(os.path.join(SPEECH_ROOT, f"Session * - {year}", f"{iso}_*_{year}.txt"))
    return hits[0] if hits else None

@functools.lru_cache(maxsize=512)
def get_speech(iso: str, year: int):
    p = _speech_path(iso, year)
    if not p:
        return None
    with open(p, encoding="utf-8", errors="replace") as f:
        return f.read()

# positions parsed lazily only for the clicked speaker+year
_raw = None
def _raw_df():
    global _raw
    if _raw is None:
        _raw = pd.read_csv(RAW_CSV, usecols=["speaker_iso", "target_iso", "year", "positions"])
    return _raw

def get_highlight_spans(speaker: str, year: int):
    df = _raw_df()
    rows = df[(df["speaker_iso"] == speaker) & (df["year"] == year)]
    spans = []
    for _, r in rows.iterrows():
        try:
            positions = ast.literal_eval(r["positions"])
        except Exception:
            continue
        for pos in positions:
            spans.append({
                "start": int(pos["abs_start"]),
                "end": int(pos["abs_end"]),
                "target": r["target_iso"],
                "surface": pos.get("surface", ""),
            })
    spans.sort(key=lambda s: s["start"])
    # drop overlaps (keep first)
    out, last_end = [], -1
    for s in spans:
        if s["start"] >= last_end:
            out.append(s)
            last_end = s["end"]
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_data.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit** (skip if not a git repo)

```bash
git add data.py tests/test_data.py
git commit -m "feat: data accessor layer (geo cache, lazy speech, highlights)"
```

---

## Task 5: Speech highlighting renderer

**Files:**
- Modify: `data.py`
- Test: `tests/test_data.py`

- [ ] **Step 1: Add failing test**

```python
# tests/test_data.py  (append)
def test_build_highlighted_children_marks_surfaces():
    text = "Hello Brazil and Chile."
    spans = [{"start": 6, "end": 12, "target": "BRA", "surface": "Brazil"}]
    children = data.build_highlighted_children(text, spans)
    # returns a list mixing plain strings and dict-marked highlight segments
    marked = [c for c in children if isinstance(c, dict)]
    assert marked and marked[0]["text"] == "Brazil" and marked[0]["target"] == "BRA"
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_data.py::test_build_highlighted_children_marks_surfaces -v`
Expected: FAIL (function missing).

- [ ] **Step 3: Implement**

```python
# data.py  (append)
def build_highlighted_children(text: str, spans):
    """Split text into plain str chunks and {'text','target'} highlight dicts."""
    children, cursor = [], 0
    for s in spans:
        if s["start"] > cursor:
            children.append(text[cursor:s["start"]])
        children.append({"text": text[s["start"]:s["end"]], "target": s["target"]})
        cursor = s["end"]
    if cursor < len(text):
        children.append(text[cursor:])
    return children
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_data.py -v`
Expected: PASS (all data tests).

- [ ] **Step 5: Commit** (skip if not a git repo)

```bash
git add data.py tests/test_data.py
git commit -m "feat: speech highlight renderer"
```

---

## Task 6: Dash app (UI + callbacks)

**Files:**
- Create: `app.py`

- [ ] **Step 1: Implement the app**

```python
# app.py
import json
from dash import Dash, dcc, html, Input, Output, State, ctx
import plotly.express as px
import data

MIN_YEAR, MAX_YEAR = 1946, 2019
mentions = data.load_mentions()
SPEAKERS = sorted(mentions["speaker_iso"].unique())

app = Dash(__name__)
app.title = "UN Speeches — who mentions whom?"

CARD = {"background": "#fff", "borderRadius": "10px",
        "boxShadow": "0 1px 4px rgba(0,0,0,.12)", "padding": "16px"}

app.layout = html.Div([
    html.H2("🌍 UN General Debate — who mentions whom?",
            style={"fontFamily": "Inter, Arial, sans-serif", "margin": "8px 0 16px"}),
    html.Div([
        html.Div([
            html.Label("Speaker"),
            dcc.Dropdown(id="speaker-dropdown",
                         options=[{"label": s, "value": s} for s in SPEAKERS],
                         value="USA", clearable=False),
        ], style={"width": "26%", "display": "inline-block", "verticalAlign": "top"}),
        html.Div([
            html.Label("Year"),
            dcc.Slider(id="year-slider", min=MIN_YEAR, max=MAX_YEAR, step=1, value=1990,
                       marks={y: str(y) for y in range(MIN_YEAR, MAX_YEAR + 1, 5)},
                       tooltip={"placement": "bottom", "always_visible": True}),
        ], style={"width": "70%", "display": "inline-block", "padding": "0 16px"}),
    ], style={**CARD, "marginBottom": "12px"}),

    dcc.Loading(dcc.Graph(id="world-map", style={"height": "62vh"}), type="default"),

    # modal
    html.Div(id="speech-modal", children=[
        html.Div([
            html.Div([
                html.H3(id="speech-title", style={"display": "inline-block", "margin": 0}),
                html.Button("✕", id="close-modal", n_clicks=0,
                            style={"float": "right", "border": "none", "background": "none",
                                   "fontSize": "20px", "cursor": "pointer"}),
            ]),
            html.Div("Highlighted words are countries this speaker mentioned.",
                     style={"color": "#666", "fontSize": "12px", "margin": "4px 0 8px"}),
            html.Hr(),
            html.Div(id="speech-text", style={
                "whiteSpace": "pre-wrap", "maxHeight": "55vh", "overflowY": "auto",
                "fontFamily": "Georgia, serif", "fontSize": "14px", "lineHeight": "1.7"}),
        ], style={**CARD, "maxWidth": "760px", "margin": "5vh auto", "position": "relative"}),
    ], style={"display": "none", "position": "fixed", "inset": 0,
              "background": "rgba(0,0,0,.45)", "zIndex": 9999, "overflowY": "auto"}),
], style={"maxWidth": "1200px", "margin": "0 auto", "padding": "12px",
          "background": "#f5f6f8", "minHeight": "100vh"})


@app.callback(Output("world-map", "figure"),
              Input("speaker-dropdown", "value"), Input("year-slider", "value"))
def update_map(speaker, year):
    geo = data.load_geo(year)
    m = mentions[(mentions["speaker_iso"] == speaker) & (mentions["year"] == year)]
    ids = [f["properties"]["id"] for f in geo["features"]]
    lut = dict(zip(m["target_std"], m["mentions"]))
    rows = [{"id": i, "mentions": float(lut.get(i, 0))} for i in ids]
    import pandas as pd
    dfp = pd.DataFrame(rows)
    cmax = max(dfp["mentions"].max(), 1)
    fig = px.choropleth(
        dfp, geojson=geo, locations="id", featureidkey="properties.id",
        color="mentions", color_continuous_scale="YlOrRd", range_color=(0, cmax),
        labels={"mentions": "Mentions"})
    fig.update_geos(visible=True, showland=True, landcolor="#e9e9e9",
                    showocean=True, oceancolor="#d6e8f5",
                    showcountries=False, showframe=False, projection_type="natural earth")
    fig.update_layout(margin={"r": 0, "t": 10, "l": 0, "b": 0},
                      coloraxis_colorbar_title="Mentions", clickmode="event+select")
    return fig


@app.callback(
    Output("speech-modal", "style"), Output("speech-title", "children"),
    Output("speech-text", "children"),
    Input("world-map", "clickData"), Input("close-modal", "n_clicks"),
    State("speaker-dropdown", "value"), State("year-slider", "value"),
    prevent_initial_call=True)
def show_speech(click, _close, speaker, year):
    hidden = {"display": "none"}
    visible = {"display": "block", "position": "fixed", "inset": 0,
               "background": "rgba(0,0,0,.45)", "zIndex": 9999, "overflowY": "auto"}
    if ctx.triggered_id == "close-modal" or not click:
        return hidden, "", ""
    iso = click["points"][0].get("location")
    text = data.get_speech(iso, year)
    if not text:
        return visible, f"{iso} — {year}", "No speech file found for this country/year."
    spans = data.get_highlight_spans(iso, year)
    children = []
    for c in data.build_highlighted_children(text, spans):
        if isinstance(c, dict):
            children.append(html.Mark(c["text"], title=c["target"],
                                      style={"background": "#ffe08a", "padding": "0 2px"}))
        else:
            children.append(c)
    return visible, f"🗣 {iso} — {year}", children


if __name__ == "__main__":
    app.run(debug=True)
```

- [ ] **Step 2: Smoke-test imports + map callback without a browser**

Run:
```bash
python -c "
import app
fig = app.update_map('USA', 1990)
print('traces:', len(fig.data), 'has geojson:', fig.data[0].geojson is not None)
"
```
Expected: prints a trace count ≥ 1 and `has geojson: True`, no exceptions.

- [ ] **Step 3: Run the app and verify in browser**

Run: `python app.py`
Open http://127.0.0.1:8050 and confirm: no African "water" gaps; slider stops at 2019; pick USA/1990, click a colored country, modal shows the speech with yellow-highlighted country names; slider feels instant.

- [ ] **Step 4: Commit** (skip if not a git repo)

```bash
git add app.py
git commit -m "feat: rebuilt dash app (fast map, fixed borders, highlighted speeches)"
```

---

## Task 7: Cleanup + README note

**Files:**
- Create: `README.md`

- [ ] **Step 1: Document run steps**

```markdown
# UN Speeches Map

## Setup
pip install pandas geopandas shapely pyarrow openpyxl dash plotly

## Build (run once, regenerates build/)
python preprocess.py

## Run
python app.py   # http://127.0.0.1:8050

Notes:
- Mentions source: country_mentions_raw_good.csv (URS->SUN, ZAR->COD, self-mentions removed, year<=2019).
- Borders: cshapes.shp (coverage 1946-2016; 2017-2019 reuse 2016 borders).
- Speeches: UNGDC_1946-2025/TXT/, loaded lazily on click; mentioned countries highlighted.
```

- [ ] **Step 2: Final full test run**

Run: `python -m pytest -v`
Expected: all tests PASS.

- [ ] **Step 3: Commit** (skip if not a git repo)

```bash
git add README.md
git commit -m "docs: add README run instructions"
```

---

## Self-review notes

- **Spec coverage:** mentions correction (T1–T2), borders/water fix (T3, T6 step1 geos), slider cap 2019 (T2, T6), performance via cache + lazy load (T3–T4, T6), highlighting (T4–T6), restyled modal + design (T6). All spec points mapped.
- **Type consistency:** `target_std` used throughout mentions; `id` is the GeoJSON property key everywhere; `build_highlighted_children` returns str|dict consumed in T6.
- **Out of scope held:** no reverse view, no side panel, no post-2019, no NLP re-detection.
