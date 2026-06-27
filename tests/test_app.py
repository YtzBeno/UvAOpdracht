import app
import data


def test_country_options_include_historical_targets():
    assert "SUN" in app.COUNTRIES
    assert "USA" in app.COUNTRIES
    assert set(app.COUNTRIES) > set(data.load_mentions()["speaker_iso"])


def _gold_locations(fig):
    """Locations of the gold (selected-country) overlay, identified by its fill color."""
    for t in fig.data:
        cs = getattr(t, "colorscale", None)
        if cs and cs[0][1] == app.AMBER:
            return list(t.locations)
    return None


def _caption_text(caption):
    """The plain text of the info-line dcc.Markdown component."""
    return caption.children if hasattr(caption, "children") else str(caption)


def test_selecting_soviet_union_draws_gold_on_sun_1960():
    fig, _info, _yr = app.update_map("SUN", 1960)
    assert _gold_locations(fig) == ["SUN"]


def test_selecting_soviet_seat_maps_gold_to_sun_pre1992():
    fig, _info, _yr = app.update_map("UKR", 1980)
    assert _gold_locations(fig) == ["SUN"]


def test_selecting_modern_country_gold_unchanged():
    fig, _info, _yr = app.update_map("USA", 1990)
    assert _gold_locations(fig) == ["USA"]


def test_update_map_returns_year_readout():
    _fig, _info, yr = app.update_map("USA", 1972)
    assert yr == "1972"


def test_update_map_with_zero_mentions_does_not_crash():
    fig, info, _yr = app.update_map("UKR", 1980)
    assert fig is not None
    assert "niemand" in _caption_text(info)
