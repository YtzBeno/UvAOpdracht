"""One-time preprocessing for the UN speeches map.

Inputs : country_mentions_raw_good.csv, cshapes.shp
Outputs: build/mentions_clean.parquet, build/geo_cache/<year>.json (1946-2019)

Run: python preprocess.py
"""
import os
import json
import pandas as pd

BUILD_DIR = "build"
MIN_YEAR = 1946
MAX_YEAR = 2019
GEO_MAX_DATA_YEAR = 2016
CODE_MAP = {"URS": "SUN", "ZAR": "COD"}

SHP_PATH = "cshapes.shp"
ISO_COL, FROM_COL, TO_COL = "ISO1AL3", "GWSYEAR", "GWEYEAR"
SIMPLIFY_TOL = 0.05


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


def build_mentions(csv_path="country_mentions_raw_good.csv",
                   out_path=os.path.join(BUILD_DIR, "mentions_clean.parquet")):
    os.makedirs(BUILD_DIR, exist_ok=True)
    df = pd.read_csv(csv_path, usecols=["speaker_iso", "target_iso", "year", "count"])
    clean = clean_mentions(df)
    clean.to_parquet(out_path, index=False)
    print(f"[mentions] {len(df)} raw rows -> {len(clean)} clean rows -> {out_path}")
    return clean


def _backfill_iso(gdf):
    """cShapes leaves ISO1AL3 null on early border-period rows; backfill it from
    the row's GWCODE when that GWCODE maps to exactly one known ISO (avoids the
    GWCODE 365 -> {SUN, RUS} ambiguity)."""
    valid = gdf[gdf[ISO_COL].notna() & (gdf["GWCODE"] > 0)]
    nunique = valid.groupby("GWCODE")[ISO_COL].nunique()
    gw2iso = (valid[valid["GWCODE"].isin(nunique[nunique == 1].index)]
              .groupby("GWCODE")[ISO_COL].first())
    mask = gdf[ISO_COL].isna() & gdf["GWCODE"].isin(gw2iso.index)
    gdf.loc[mask, ISO_COL] = gdf.loc[mask, "GWCODE"].map(gw2iso)
    return gdf


def build_geo(shp_path=SHP_PATH, out_dir=os.path.join(BUILD_DIR, "geo_cache")):
    import geopandas as gpd
    os.makedirs(out_dir, exist_ok=True)
    gdf = gpd.read_file(shp_path).to_crs(epsg=4326)
    gdf = _backfill_iso(gdf)
    gdf = gdf[gdf[ISO_COL].notna()].copy()
    gdf["geometry"] = gdf["geometry"].simplify(SIMPLIFY_TOL, preserve_topology=True)
    for year in range(MIN_YEAR, MAX_YEAR + 1):
        q = min(year, GEO_MAX_DATA_YEAR)
        sub = gdf[(gdf[FROM_COL] <= q) & (gdf[TO_COL] >= q)].copy()
        sub = sub.dissolve(by=ISO_COL, as_index=False)
        sub["id"] = sub[ISO_COL]
        geo = json.loads(sub[["id", "geometry"]].to_json())
        with open(os.path.join(out_dir, f"{year}.json"), "w") as f:
            json.dump(geo, f)
    print(f"[geo] wrote {MAX_YEAR - MIN_YEAR + 1} year files to {out_dir}")


NAME_OVERRIDES = {
    "EU": "European Union", "PSE": "Palestine", "URS": "Soviet Union",
    "VAT": "Vatican City", "ZAR": "Zaire (DR Congo)",
    "USA": "United States", "GBR": "United Kingdom", "RUS": "Russia",
    "KOR": "South Korea", "PRK": "North Korea", "IRN": "Iran",
    "SYR": "Syria", "LAO": "Laos", "TZA": "Tanzania", "MDA": "Moldova",
    "VNM": "Vietnam", "BRN": "Brunei", "CZE": "Czechia", "MKD": "North Macedonia",
    "COD": "DR Congo", "COG": "Republic of the Congo", "BOL": "Bolivia",
    "VEN": "Venezuela", "SUN": "Soviet Union", "YUG": "Yugoslavia",
    "CSK": "Czechoslovakia", "DDR": "East Germany",
}


def build_names(shp_path=SHP_PATH, out_path=os.path.join(BUILD_DIR, "country_names.json")):
    import geopandas as gpd
    os.makedirs(BUILD_DIR, exist_ok=True)
    g = gpd.read_file(shp_path)
    cs = g.dropna(subset=[ISO_COL])[[ISO_COL, "ISONAME"]].drop_duplicates(ISO_COL)
    names = dict(zip(cs[ISO_COL], cs["ISONAME"]))
    names.update(NAME_OVERRIDES)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(names, f, ensure_ascii=False)
    print(f"[names] wrote {len(names)} country names -> {out_path}")


def build_all():
    build_mentions()
    build_geo()
    build_names()


if __name__ == "__main__":
    build_all()
