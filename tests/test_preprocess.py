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
    rows = {(r.speaker_iso, r.target_std, r.year): r.mentions for r in out.itertuples()}
    assert rows == {("ARG", "BRA", 1960): 5, ("ARG", "SUN", 1960): 1}
