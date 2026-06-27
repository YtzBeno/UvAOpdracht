"""Read-only accessors over the preprocessed build/ artifacts and speech files."""
import os
import json
import ast
import glob
import functools
import pandas as pd

BUILD_DIR = "build"
SPEECH_ROOT = "UNGDC_1946-2025/TXT"
RAW_CSV = "country_mentions_raw_good.csv"

_mentions = pd.read_parquet(os.path.join(BUILD_DIR, "mentions_clean.parquet"))


def load_mentions():
    return _mentions


_SOVIET_SEATS = {"RUS": "SUN", "UKR": "SUN", "BLR": "SUN"}
_SOVIET_UNTIL = 1991


def _geo_speaker(iso: str, year: int) -> str:
    """Map a speaker ISO to the polygon id that represents it in `year`."""
    if year <= _SOVIET_UNTIL:
        return _SOVIET_SEATS.get(iso, iso)
    return iso


_GEO_TO_SPEECH = {"SUN": "RUS"}


def speech_iso(geo_id: str, year: int) -> str:
    """The speaker code whose speech/highlights back a clicked geo polygon."""
    if year <= _SOVIET_UNTIL:
        return _GEO_TO_SPEECH.get(geo_id, geo_id)
    return geo_id


_CODE_MAP = {"URS": "SUN", "ZAR": "COD"}


def std_target(target_iso: str) -> str:
    """Standardize a raw mention target code to the dropdown/`target_std` space."""
    return _CODE_MAP.get(target_iso, target_iso)


def mentions_for_target(target: str, year: int) -> dict:
    """{geo_id: mentions} for everyone who mentioned `target` in `year`, with the
    Soviet UN seats aggregated onto the SUN polygon for years <= 1991."""
    m = _mentions[(_mentions["target_std"] == target) & (_mentions["year"] == year)]
    out = {}
    for row in m.itertuples():
        gid = _geo_speaker(row.speaker_iso, year)
        if gid == target:
            continue
        out[gid] = out.get(gid, 0) + int(row.mentions)
    return out


@functools.lru_cache(maxsize=1)
def _targets_by_year() -> dict:
    """{year: [(target_iso, total_mentions), ...]} — every target ranked desc by
    total mentions (ties broken by code) for each year."""
    g = (_mentions.groupby(["year", "target_std"])["mentions"].sum().reset_index())
    out = {}
    for year, sub in g.groupby("year"):
        sub = sub.sort_values(["mentions", "target_std"], ascending=[False, True])
        out[int(year)] = [(r.target_std, int(r.mentions)) for r in sub.itertuples()]
    return out


def most_mentioned_by_year() -> dict:
    """{year: (target_iso, total_mentions)} — most-mentioned target each year."""
    return {y: lst[0] for y, lst in _targets_by_year().items() if lst}


def top_targets(year: int, n: int = 5):
    """The `n` most-mentioned countries in `year` as [(target_iso, total), ...]."""
    return _targets_by_year().get(year, [])[:n]


def top_mentioner(target: str, year: int):
    """(speaker_iso, mentions) who mentioned `target` most in `year`, or None."""
    d = mentions_for_target(target, year)
    if not d:
        return None
    speaker = max(sorted(d), key=lambda s: d[s])
    return (speaker, d[speaker])


with open(os.path.join(BUILD_DIR, "country_names.json"), encoding="utf-8") as _f:
    _names = json.load(_f)


def name(iso: str) -> str:
    """Friendly English country name for an ISO3 code (falls back to the code)."""
    return _names.get(iso, iso)


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
    out, last_end = [], -1
    for s in spans:
        if s["start"] >= last_end:
            out.append(s)
            last_end = s["end"]
    return out


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
