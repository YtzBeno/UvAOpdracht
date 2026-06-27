# UN Speeches Map — Direction Reversal & UX Fixes Design

**Date:** 2026-06-18
**Project:** Interactive map of UN General Debate speeches.
**Builds on:** `2026-06-14-un-speeches-map-design.md` (initial build).

## Goal

Fix the issues found during review and add two interactive highlights, **without**
changing the core concept (pick a country + year, read speeches by clicking the map).
The headline change is **reversing the mention direction**: the map now answers
*"who mentions the selected country?"* instead of *"who does the selected country mention?"*.

## Current state (what exists)

- `app.py` — Dash app. Dropdown picks a country; slider picks a year; choropleth colors
  the map; click a country → modal with its speech, mentions highlighted.
- `data.py` — read-only accessors over `build/` artifacts.
- `preprocess.py` — builds `build/mentions_clean.parquet`, `build/geo_cache/<year>.json`,
  `build/country_names.json`.
- Mentions parquet columns: `speaker_iso`, `target_std`, `year`, `mentions`.

## Issues & decisions

| # | Issue (from review) | Decision |
|---|---|---|
| 1 | **Direction is reversed.** Selecting USA shows who USA mentions, not who mentions USA. | Flip it: color speakers by how often they mention the selected (target) country. This **overrides** the original "outgoing only" decision. |
| 2 | **Two colors for "0".** Countries with 0 mentions get the lightest scale color; countries with no polygon show grey land → two appearances of "nothing". | Countries with 0 mentions render as the **same grey** as the land base (excluded from the colored layer). One grey = "nothing". |
| 3 | **Red color scale reads oddly.** | Switch `YlOrRd` → **Greens** (light = few, dark = many). |
| 4 | **Slider looks like a range** (filled purple track from start to handle). | `included=False` so only the single-year handle/dot shows. |
| 5 | **Africa is one grey blob** with no internal borders in early years (colonies have no cShapes polygon). | Enable Plotly `showcountries=True` → real (Natural Earth) country borders drawn over the land base, so every country incl. African ones is individually visible at every year. Modern borders; the historical cShapes polygons still drive the choropleth fill. |
| 6 | **Selected country not highlighted.** | Render the selected country with a distinct **gold fill + bold outline** (it is otherwise grey since self-mentions are excluded). |
| 7 | **No "most mentioned" insight.** | Show **both**: (a) the globally most-mentioned country that year, with a **purple outline** on the map + an info line; (b) the top mentioner of the selected country, named in the info line. |
| — | Compare-across-periods feature | **Out of scope** (user dropped it). |

## Addendum (2026-06-18, after implementation review): the speaker↔geo join

Reversing the direction exposed a join bug the original verification missed. Speaker codes in
the mentions data are **modern ISO3** (`RUS`/`UKR`/`BLR` for the USSR's three UN seats), but the
historical cShapes polygons use **`SUN`** for 1946–1991. So early-year mentions land on codes with
no polygon and silently disappear — **52% of all 1946 mentions** were lost. Two compounding causes,
two fixes (user chose **historical borders + Soviet aggregation**):

1. **cShapes ISO backfill (`preprocess.py`).** cShapes splits each country into border-period rows;
   early periods have `ISO1AL3 = None` (e.g. Egypt 1946–1967, China 1946–1949), and the old
   `dropna(ISO1AL3)` deleted them, so those countries were absent for years they clearly existed.
   Fix: backfill `ISO1AL3` from the stable `GWCODE` (only when a `GWCODE` maps to exactly one ISO,
   to avoid the `GWCODE 365 → {SUN, RUS}` ambiguity). Recovers Egypt, China, etc. (1946: 68 → 74
   polygons). Requires rebuilding `geo_cache/` and `country_names.json` (mentions parquet unchanged).
   India stays absent in 1946 — correct, it gained statehood Aug 1947.

2. **Soviet-seat aggregation (`data.py`).** In `mentions_for_target`, map `RUS`/`UKR`/`BLR` → `SUN`
   for `year ≤ 1991` and **sum** their counts onto the Soviet Union polygon. Result: 1946 top
   mentioner of the USA is `SUN` = 23+19+10 = **52**, shown on the real Soviet Union polygon, labeled
   "Soviet Union" — matching the user's original expectation. (This supersedes the earlier
   verification target of `RUS`/23; Task 1's two exact-value tests are updated accordingly.)

## Design

### Data (`preprocess.py`, `data.py`)

No new build artifacts required — the existing `mentions_clean.parquet` already has every
`(speaker_iso, target_std, year, mentions)` row, which supports both directions and the
"most mentioned globally" aggregate.

- Add `data.most_mentioned_by_year()` → dict `{year: (target_iso, total_mentions)}`,
  computed once from the parquet by `groupby(["year","target_std"]).mentions.sum()` then
  per-year argmax. Cheap; cache at module load.

### Map callback (`app.py update_map`)

For selected target `S` and year `Y`:

1. **Direction:** filter `mentions[(target_std == S) & (year == Y)]`; build
   `lut = {speaker_iso: mentions}`. (Was keyed on `target_std`.)
2. **Fill data:** for each polygon id, `value = lut.get(id, 0)`. Build the choropleth from
   only the rows where `value > 0` so 0-mention countries fall through to the grey land base.
3. **Color:** `color_continuous_scale="Greens"`, `range_color=(0, max(values, 1))`.
4. **Selected country layer:** a separate single-feature trace (or `go` scatter/choropleth
   overlay) drawing `S` in gold with a bold outline.
5. **Most-mentioned-globally layer:** outline the year's top target (`data.most_mentioned_by_year`)
   in purple. Border channel only, so it never hides a green fill.
6. **Base map:** keep grey land (`showland=True, landcolor=#e9e9e9`) + ocean; add
   `showcountries=True`, `countrycolor` a light grey line.
7. **Info line** (above or as a figure annotation):
   *"Meest genoemd wereldwijd in {Y}: {name} ({n}×) — {S} het vaakst genoemd door: {top} ({m}×)."*
   If `S` got 0 mentions that year, say so gracefully.

### Slider (`app.py layout`)

Add `included=False` to the existing `dcc.Slider`. Keep min/max/marks/tooltip.

### Speech modal (`app.py show_speech`)

Unchanged behavior (click any country → its speech, that speaker's mentions highlighted).
Update the helper caption to match the new framing. Clicking a colored (speaker) country
opens the speech of a country that mentioned `S`, which is the natural read with the new
direction.

## Implementation notes / risks

- Drawing the selected + purple overlays: simplest is to add extra `graph_objects` traces to
  the figure returned by `px.choropleth`. Need to confirm a clean way to draw a single
  polygon outline (likely a second `go.Choropleth` with that one id and a transparent fill +
  colored marker line, or two overlay choropleths). Verify visually.
- `showcountries=True` lines are drawn by the base map and are independent of the choropleth;
  confirm they render under the historical fills, not on top obscuring colors.
- If gold/purple overlay traces prove fiddly in `px`, fall back to per-id `marker.line` styling
  within a single `go.Choropleth` built from a full id list with a categorical/explicit color
  array. Decide during implementation; verify by screenshot at 1946, 1950, 1990.

## Verification (targets confirmed against `mentions_clean.parquet`)

- 1946 + United States → **Russia darkest green (23)**, then Ukraine (19), Belarus (10) —
  i.e. who mentioned the USA. (Data quirk: the USSR's UN seats appear as speaker codes
  `RUS`/`UKR`/`BLR`; `SUN` only appears as a *target*, so the top mentioner is labeled
  "Russia," not "Soviet Union".)
- Globally most-mentioned country in 1946 = **USA (136)** → that is the purple-outlined
  country and the one named in the info line. ("Palestine 1946" from the request was an
  illustrative example, not the actual value — nothing is hardcoded.)
- 1950 → African countries individually visible with borders (not one grey blob).
- 0-mention countries and no-polygon countries are the **same** grey.
- Slider shows a single dot, no filled track.
- Selected country gold; year's top global target purple; info line correct.
