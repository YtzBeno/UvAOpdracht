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


def test_build_highlighted_children_marks_surfaces():
    text = "Hello Brazil and Chile."
    spans = [{"start": 6, "end": 12, "target": "BRA", "surface": "Brazil"}]
    children = data.build_highlighted_children(text, spans)
    marked = [c for c in children if isinstance(c, dict)]
    assert marked and marked[0]["text"] == "Brazil" and marked[0]["target"] == "BRA"


def test_mentions_for_target_usa_1946_aggregates_soviet_seats():
    d = data.mentions_for_target("USA", 1946)
    assert d.get("SUN") == 52
    assert "RUS" not in d and "UKR" not in d and "BLR" not in d
    assert "USA" not in d
    assert all(v > 0 for v in d.values())


def test_mentions_for_target_unknown_is_empty():
    assert data.mentions_for_target("ZZZ", 1946) == {}


def test_most_mentioned_by_year_1946_is_usa():
    mm = data.most_mentioned_by_year()
    assert mm[1946][0] == "USA"
    assert mm[1946][1] == 136


def test_top_mentioner_of_usa_1946_is_soviet_union():
    assert data.top_mentioner("USA", 1946) == ("SUN", 52)


def test_top_mentioner_unknown_is_none():
    assert data.top_mentioner("ZZZ", 1946) is None


def test_geo_speaker_maps_soviet_seats_only_through_1991():
    assert data._geo_speaker("RUS", 1980) == "SUN"
    assert data._geo_speaker("UKR", 1991) == "SUN"
    assert data._geo_speaker("RUS", 1992) == "RUS"
    assert data._geo_speaker("USA", 1946) == "USA"


def test_mentions_for_target_no_soviet_aggregation_after_1991():
    d = data.mentions_for_target("USA", 2000)
    assert "SUN" not in d


def test_speech_iso_maps_sun_to_russia_pre1992():
    assert data.speech_iso("SUN", 1960) == "RUS"
    assert data.speech_iso("SUN", 2000) == "SUN"
    assert data.speech_iso("USA", 1960) == "USA"
    assert data.get_speech("SUN", 1960) is None
    assert data.get_speech(data.speech_iso("SUN", 1960), 1960)


def test_mentions_for_target_sun_excludes_aggregated_self():
    d = data.mentions_for_target("SUN", 1960)
    assert "SUN" not in d
    tm = data.top_mentioner("SUN", 1960)
    assert tm is None or tm[0] != "SUN"
