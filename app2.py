import os
import re
import json
import pandas as pd
import geopandas as gpd
from dash import Dash, dcc, html, Input, Output, State, ctx
import plotly.express as px

SPEECHES_ROOT = "TXT"

def load_speeches(root: str) -> dict:
    """
    Geeft een dict terug: {(iso3, year): tekst}
    """
    speeches = {}
    session_pattern = re.compile(r"Session \d+ - (\d{4})", re.IGNORECASE)

    if not os.path.isdir(root):
        print(f"[WAARSCHUWING] Speeches-map '{root}' niet gevonden. Klikfunctionaliteit uitgeschakeld.")
        return speeches

    for folder in os.listdir(root):
        folder_path = os.path.join(root, folder)
        if not os.path.isdir(folder_path):
            continue
        m = session_pattern.search(folder)
        if not m:
            continue
        year = int(m.group(1))

        for fname in os.listdir(folder_path):
            if not fname.endswith(".txt"):
                continue
            iso3 = fname[:3].upper()
            fpath = os.path.join(folder_path, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    speeches[(iso3, year)] = f.read()
            except Exception:
                pass
    return speeches

speeches = load_speeches(SPEECHES_ROOT)

df = pd.read_csv("country_mentions_raw_good.csv")

mentions = (
    df.groupby(["speaker_iso", "target_iso", "year"], as_index=False)["count"]
      .sum()
      .rename(columns={"count": "mentions"})
)

code_map = {
    "URS": "SUN",
    "GIN": "PNG",
}
mentions["target_iso_mapped"] = mentions["target_iso"].replace(code_map)

shp_path = "cshapes.shp"
gdf = gpd.read_file(shp_path)

iso_col  = "ISO1AL3"
to_col   = "GWEYEAR"
from_col = "GWSYEAR" if "GWSYEAR" in gdf.columns else "COWSYEAR"

MIN_YEAR = 1945
MAX_YEAR = 2019

records = []
for _, row in gdf.iterrows():
    start = max(int(row[from_col]), MIN_YEAR)
    end   = min(int(row[to_col]),   MAX_YEAR)
    for y in range(start, end + 1):
        new_row = row.copy()
        new_row["year"] = y
        records.append(new_row)

gdf_yearly = gpd.GeoDataFrame(records, crs=gdf.crs)
gdf_yearly = gdf_yearly.to_crs(epsg=4326)

app = Dash(__name__)

app.layout = html.Div([
    html.H2("VN-speeches: wie noemt wie?"),

    html.Div([
        html.Div([
            html.Label("Spreker (speaker_iso):"),
            dcc.Dropdown(
                id="speaker-dropdown",
                options=[{"label": s, "value": s}
                         for s in sorted(mentions["speaker_iso"].unique())],
                value="ARG",
                clearable=False
            ),
        ], style={"width": "30%", "display": "inline-block"}),

        html.Div([
            html.Label("Jaar:"),
            dcc.Slider(
                id="year-slider",
                min=int(mentions["year"].min()),
                max=int(mentions["year"].max()),
                value=int(mentions["year"].min()),
                marks={int(y): str(y) for y in range(
                    int(mentions["year"].min()),
                    int(mentions["year"].max()) + 1, 5)},
                step=1,
                tooltip={"placement": "bottom", "always_visible": True},
            ),
        ], style={"width": "60%", "display": "inline-block", "padding": "0 20px"}),
    ]),

    dcc.Graph(id="world-map", style={"height": "600px"}),

    html.Div(
        id="speech-modal",
        children=[
            html.Div([
                html.Div([
                    html.H3(id="speech-title",
                            style={"display": "inline-block", "marginRight": "20px"}),
                    html.Button("✕ Sluiten", id="close-modal", n_clicks=0,
                                style={"float": "right", "cursor": "pointer",
                                       "fontSize": "14px", "padding": "4px 10px"}),
                ]),
                html.Hr(),
                html.Pre(
                    id="speech-text",
                    style={
                        "whiteSpace": "pre-wrap",
                        "maxHeight": "400px",
                        "overflowY": "auto",
                        "fontFamily": "Georgia, serif",
                        "fontSize": "13px",
                        "lineHeight": "1.6",
                    }
                ),
            ], style={
                "background": "white",
                "padding": "20px",
                "borderRadius": "8px",
                "maxWidth": "700px",
                "margin": "40px auto",
                "boxShadow": "0 4px 20px rgba(0,0,0,0.3)",
                "position": "relative",
            }),
        ],
        style={
            "display": "none",
            "position": "fixed",
            "top": 0, "left": 0,
            "width": "100%", "height": "100%",
            "background": "rgba(0,0,0,0.5)",
            "zIndex": 9999,
            "overflowY": "auto",
        },
    ),
])


@app.callback(
    Output("world-map", "figure"),
    Input("speaker-dropdown", "value"),
    Input("year-slider", "value"),
)
def update_map(selected_speaker, selected_year):
    m_year = mentions[
        (mentions["speaker_iso"] == selected_speaker) &
        (mentions["year"] == selected_year)
    ].copy()
    m_year["target_iso_mapped"] = m_year["target_iso_mapped"].fillna(m_year["target_iso"])

    g_year = gdf_yearly[gdf_yearly["year"] == selected_year].copy()

    merged = g_year.merge(
        m_year,
        left_on=iso_col,
        right_on="target_iso_mapped",
        how="left"
    )
    merged["mentions"] = merged["mentions"].fillna(0)
    merged["id"] = merged[iso_col]

    merged["heeft_speech"] = merged[iso_col].apply(
        lambda iso: "📄 Ja" if (iso, selected_year) in speeches else "Nee"
    )

    geo = json.loads(merged[["id", "geometry"]].to_json())

    max_mentions = merged["mentions"].max()
    if max_mentions == 0:
        max_mentions = 1

    fig = px.choropleth(
        merged,
        geojson=geo,
        locations="id",
        featureidkey="properties.id",
        color="mentions",
        color_continuous_scale="Reds",
        range_color=(0, max_mentions),
        hover_data={"id": True, "mentions": True, "heeft_speech": True},
        labels={
            "mentions": "Aantal mentions",
            "id": "Land (ISO3)",
            "heeft_speech": "Speech beschikbaar",
        },
        title=f"{selected_speaker} → andere landen, jaar {selected_year}",
    )

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        coloraxis_colorbar_title="Mentions",
        clickmode="event+select",
    )
    return fig


@app.callback(
    Output("speech-modal", "style"),
    Output("speech-title", "children"),
    Output("speech-text", "children"),
    Input("world-map", "clickData"),
    Input("close-modal", "n_clicks"),
    State("year-slider", "value"),
    prevent_initial_call=True,
)
def toggle_speech(click_data, close_clicks, selected_year):
    """Opent de popup bij klik op een land; sluit bij ✕."""
    modal_hidden = {"display": "none"}
    modal_visible = {
        "display": "block",
        "position": "fixed",
        "top": 0, "left": 0,
        "width": "100%", "height": "100%",
        "background": "rgba(0,0,0,0.5)",
        "zIndex": 9999,
        "overflowY": "auto",
    }

    if ctx.triggered_id == "close-modal":
        return modal_hidden, "", ""

    if click_data is None:
        return modal_hidden, "", ""

    try:
        iso3 = click_data["points"][0]["location"]
    except (KeyError, IndexError):
        return modal_hidden, "", ""

    key = (iso3, selected_year)
    if key in speeches:
        title = f"🗣️ Speech: {iso3} — {selected_year}"
        text  = speeches[key]
    else:
        title = f"{iso3} — {selected_year}"
        text  = "Geen speechbestand gevonden voor dit land en jaar."

    return modal_visible, title, text


if __name__ == "__main__":
    app.run(debug=True)
