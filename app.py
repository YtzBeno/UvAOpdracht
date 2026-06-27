import pandas as pd
from dash import Dash, dcc, html, Input, Output, State, ctx
import plotly.express as px
import plotly.graph_objects as go
import data

MIN_YEAR, MAX_YEAR = 1946, 2019
mentions = data.load_mentions()
COUNTRIES = sorted(set(mentions["speaker_iso"]) | set(mentions["target_std"]), key=data.name)

PAGE = "#eef2f7"
OCEAN = "#d6e8f5"
LAND = "#e7ebf0"
MAP_LINE = "#aeb7c2"
COAST = "#97a3b1"
TEXT = "#16202b"
MUTED = "#5d6775"
AMBER = "#f5c542"
VIOLET = "#7b2cbf"
GREENS = [[0.0, "#cdeac4"], [0.5, "#41ab5d"], [1.0, "#00441b"]]

app = Dash(__name__)
app.title = "Wie de wereld benoemt"

app.index_string = """<!DOCTYPE html>
<html>
<head>
{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=Space+Mono:wght@400;700&family=Newsreader:opsz,wght@6..72,400;6..72,500&display=swap" rel="stylesheet">
<style>
  :root{
    --page:#eef2f7; --panel:rgba(255,255,255,.9); --line:rgba(20,30,50,.12);
    --text:#16202b; --muted:#5d6775; --amber:#f5c542; --violet:#7b2cbf; --green:#1b7a3c;
  }
  *{box-sizing:border-box;}
  html,body{margin:0;height:100%;background:var(--page);overflow:hidden;
    font-family:Inter,system-ui,sans-serif;color:var(--text);
    -webkit-font-smoothing:antialiased;}
  #react-entry-point,._dash-app-content{height:100%;}

  /* full-bleed map canvas */
  .map-layer{position:fixed;inset:0;z-index:0;}
  .map-layer .js-plotly-plot,.map-layer .plot-container,.map-layer .svg-container{height:100%!important;width:100%!important;}

  /* control rail */
  .rail{position:fixed;top:0;left:0;right:0;z-index:20;display:flex;align-items:center;
    gap:28px;padding:16px 26px;background:rgba(255,255,255,.92);
    backdrop-filter:blur(10px);border-bottom:1px solid var(--line);
    box-shadow:0 6px 26px rgba(20,30,50,.13);}
  .brand{display:flex;flex-direction:column;gap:2px;min-width:200px;}
  .eyebrow{font-family:'Space Mono',monospace;font-size:10.5px;letter-spacing:.22em;
    text-transform:uppercase;color:var(--green);}
  .brand-title{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:20px;
    line-height:1.05;letter-spacing:-.01em;color:var(--text);}
  .controls{display:flex;align-items:center;gap:26px;flex:1;min-width:0;}
  .field{display:flex;flex-direction:column;gap:5px;}
  .field-label{font-family:'Space Mono',monospace;font-size:10px;letter-spacing:.16em;
    text-transform:uppercase;color:var(--muted);}
  .field-country{width:240px;}
  .field-year{flex:1;min-width:340px;}
  .year-row{display:flex;align-items:center;gap:20px;}
  .year-readout{font-family:'Space Mono',monospace;font-weight:700;font-size:44px;
    line-height:1;color:var(--text);min-width:122px;letter-spacing:.01em;}
  .year-slider{flex:1;padding-top:14px;}

  /* dropdown (react-select v1) */
  .field-country .Select-control{background:#fff!important;border:1px solid var(--line)!important;
    border-radius:9px!important;height:40px!important;}
  .field-country .Select-value,.field-country .Select-placeholder{line-height:40px!important;padding-left:12px!important;}
  .field-country .Select-value-label{color:var(--text)!important;font-weight:600;font-size:14px;}
  .field-country .Select-menu-outer{background:#fff!important;border:1px solid var(--line)!important;
    border-radius:9px!important;margin-top:6px;box-shadow:0 18px 40px rgba(20,30,50,.18);}
  .field-country .VirtualizedSelectOption{color:var(--text);font-size:13.5px;cursor:pointer;}
  .field-country .VirtualizedSelectFocusedOption{background:#eaf4ee;color:#0d4d24;}
  .field-country .is-focused:not(.is-open)>.Select-control{box-shadow:0 0 0 2px rgba(27,122,60,.35)!important;
    border-color:rgba(27,122,60,.5)!important;}

  /* slider (rc-slider) */
  .year-slider .rc-slider-rail{background:#c4cdd9!important;height:4px;}
  .year-slider .rc-slider-track{background:transparent!important;}
  .year-slider .rc-slider-handle{border:2px solid #b8860b!important;background:var(--amber)!important;
    width:17px;height:17px;margin-top:-7px;opacity:1;box-shadow:0 1px 4px rgba(20,30,50,.3)!important;}
  .year-slider .rc-slider-handle:hover,.year-slider .rc-slider-handle-active{box-shadow:0 0 0 6px rgba(245,197,66,.3)!important;}
  .year-slider .rc-slider-dot{display:none;}
  .year-slider .rc-slider-mark-text{color:#3c4a5e!important;font-family:'Space Mono',monospace;
    font-size:11px;font-weight:700;}
  .year-slider .rc-slider-mark-text-active{color:#0e1722!important;}
  .year-slider .rc-slider-tooltip-inner{background:#15202c!important;color:#fff!important;
    font-family:'Space Mono',monospace;font-weight:700;box-shadow:none!important;border-radius:5px;}
  .year-slider .rc-slider-tooltip-arrow{border-top-color:#15202c!important;}

  /* bottom caption + legend */
  .caption{position:fixed;left:26px;bottom:22px;z-index:15;max-width:min(560px,55vw);
    font-size:14px;line-height:1.5;color:#243040;
    background:rgba(255,255,255,.82);backdrop-filter:blur(5px);
    padding:9px 13px;border-radius:10px;border:1px solid var(--line);}
  .caption strong{color:#0c1320;font-weight:700;}
  .caption p{margin:0;}
  .legend{position:fixed;right:22px;bottom:22px;z-index:15;display:flex;flex-direction:column;gap:8px;
    padding:12px 14px;background:rgba(255,255,255,.92);backdrop-filter:blur(6px);
    border:1px solid var(--line);border-radius:11px;box-shadow:0 6px 20px rgba(20,30,50,.12);}
  .legend-row{display:flex;align-items:center;gap:9px;font-size:11.5px;color:#3a4658;
    font-family:'Space Mono',monospace;letter-spacing:.02em;}
  .sw{width:13px;height:13px;border-radius:3px;flex:none;}
  .sw-sel{background:var(--amber);border:1px solid #b8860b;}
  .sw-mm{background:transparent;border:2px solid var(--violet);}
  .sw-grad{background:linear-gradient(90deg,#cdeac4,#41ab5d,#00441b);}

  /* speech modal */
  .modal-overlay{position:fixed;inset:0;z-index:9999;background:rgba(20,30,45,.45);
    backdrop-filter:blur(3px);overflow-y:auto;}
  .modal-card{max-width:780px;margin:7vh auto;position:relative;background:#fff;
    border:1px solid var(--line);border-radius:16px;padding:26px 30px;
    box-shadow:0 30px 80px rgba(20,30,50,.4);}
  .modal-title{font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:22px;margin:0;color:var(--text);}
  .modal-close{position:absolute;top:18px;right:20px;border:1px solid var(--line);background:#f3f5f8;
    color:var(--muted);font-size:15px;cursor:pointer;width:32px;height:32px;border-radius:8px;line-height:1;}
  .modal-close:hover{color:var(--text);background:#e7ebf0;}
  .modal-hint{color:var(--muted);font-size:12.5px;margin:8px 0 14px;}
  .modal-rule{border:none;border-top:1px solid var(--line);margin:0 0 16px;}
  .speech{white-space:pre-wrap;max-height:62vh;overflow-y:auto;padding-right:10px;
    font-family:Newsreader,Georgia,serif;font-size:16px;line-height:1.75;color:#26303d;}
  .speech mark{background:#ffe08a;color:#3a2c00;padding:0 2px;border-radius:2px;}

  ::-webkit-scrollbar{width:10px;height:10px;}
  ::-webkit-scrollbar-thumb{background:rgba(20,30,50,.22);border-radius:6px;}
  ::-webkit-scrollbar-track{background:transparent;}

  @media (max-width:880px){
    .rail{flex-direction:column;align-items:stretch;gap:14px;}
    .controls{flex-direction:column;align-items:stretch;gap:16px;}
    .field-country{width:100%;}.field-year{min-width:0;}
    .year-readout{font-size:34px;min-width:96px;}
    .legend{display:none;}.caption{max-width:90vw;}
  }
  @media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important;}}
</style>
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>"""


app.layout = html.Div([
    dcc.Graph(id="world-map", className="map-layer",
              config={"displayModeBar": False, "scrollZoom": True, "doubleClick": "reset"},
              responsive=True),

    html.Div(className="rail", children=[
        html.Div(className="brand", children=[
            html.Div("VN algemene beschouwingen", className="eyebrow"),
            html.Div("Wie de wereld benoemt", className="brand-title"),
        ]),
        html.Div(className="controls", children=[
            html.Div(className="field field-country", children=[
                html.Label("Welk land wordt genoemd?", className="field-label"),
                dcc.Dropdown(id="speaker-dropdown", clearable=False, value="USA",
                             options=[{"label": data.name(s), "value": s} for s in COUNTRIES]),
            ]),
            html.Div(className="field field-year", children=[
                html.Label("Jaar", className="field-label"),
                html.Div(className="year-row", children=[
                    html.Div("1990", id="year-readout", className="year-readout"),
                    html.Div(className="year-slider", children=[
                        dcc.Slider(id="year-slider", min=MIN_YEAR, max=MAX_YEAR, step=1,
                                   value=1990, included=False,
                                   marks={y: str(y) for y in range(1950, MAX_YEAR + 1, 10)},
                                   tooltip={"placement": "bottom", "always_visible": False}),
                    ]),
                ]),
            ]),
        ]),
    ]),

    html.Div(id="info-line", className="caption"),

    html.Div(className="legend", children=[
        html.Div(className="legend-row", children=[html.Span(className="sw sw-sel"), "geselecteerd land"]),
        html.Div(className="legend-row", children=[html.Span(className="sw sw-mm"), "meest genoemd dit jaar"]),
        html.Div(className="legend-row", children=[html.Span(className="sw sw-grad"), "keer genoemd →"]),
    ]),

    html.Div(id="speech-modal", className="modal-overlay", style={"display": "none"}, children=[
        html.Div(className="modal-card", children=[
            html.Button("✕", id="close-modal", n_clicks=0, className="modal-close"),
            html.H3(id="speech-title", className="modal-title"),
            html.Div(id="speech-hint", className="modal-hint"),
            html.Hr(className="modal-rule"),
            html.Div(id="speech-text", className="speech"),
        ]),
    ]),
])


def _style_map(fig, cmax):
    fig.update_geos(
        visible=True, resolution=110,
        showland=True, landcolor=LAND,
        showocean=True, oceancolor=OCEAN,
        showlakes=True, lakecolor=OCEAN,
        showcountries=True, countrycolor=MAP_LINE, countrywidth=0.5,
        coastlinecolor=COAST, coastlinewidth=0.5,
        showframe=False, framecolor="rgba(0,0,0,0)", bgcolor="rgba(0,0,0,0)",
        lataxis_showgrid=False, lonaxis_showgrid=False,
        projection_type="natural earth", projection_scale=1.13,
        center=dict(lat=14, lon=8),
    )
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=MUTED),
        clickmode="event",
        coloraxis_colorbar=dict(
            title=dict(text="keer<br>genoemd", font=dict(size=10, color=MUTED)),
            tickfont=dict(size=10, color=MUTED), thickness=9, len=0.42,
            x=0.985, xanchor="right", y=0.46, outlinewidth=0,
            bgcolor="rgba(255,255,255,0.55)", ticks="",
        ),
        hoverlabel=dict(bgcolor="#ffffff", bordercolor=MAP_LINE,
                        font=dict(family="Inter, sans-serif", color=TEXT, size=13)),
    )
    fig.update_traces(marker_line_color="#ffffff", marker_line_width=0.35,
                      selector=dict(type="choropleth"))
    return fig


@app.callback(Output("world-map", "figure"), Output("info-line", "children"),
              Output("year-readout", "children"),
              Input("speaker-dropdown", "value"), Input("year-slider", "value"))
def update_map(speaker, year):
    geo = data.load_geo(year)
    lut = data.mentions_for_target(speaker, year)
    ids = [f["properties"]["id"] for f in geo["features"]]
    dfp = pd.DataFrame([{"id": i, "name": data.name(i), "mentions": lut[i]}
                        for i in ids if lut.get(i, 0) > 0],
                       columns=["id", "name", "mentions"])
    cmax = max(dfp["mentions"].max(), 1) if not dfp.empty else 1
    fig = px.choropleth(
        dfp, geojson=geo, locations="id", featureidkey="properties.id",
        color="mentions", color_continuous_scale=GREENS, range_color=(0, cmax),
        hover_name="name", hover_data={"id": False, "mentions": True},
        labels={"mentions": "Keer genoemd"})
    _style_map(fig, cmax)

    base_names = [data.name(i) for i in ids]
    base_counts = [lut.get(i, 0) for i in ids]
    fig.add_trace(go.Choropleth(
        geojson=geo, locations=ids, z=[0] * len(ids), featureidkey="properties.id",
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
        marker_line_color="rgba(0,0,0,0)", marker_line_width=0,
        customdata=list(zip(base_names, base_counts)),
        hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}× genoemd<extra></extra>"))
    fig.data = (fig.data[-1],) + tuple(fig.data[:-1])

    sel_geo = data._geo_speaker(speaker, year)
    if sel_geo in ids:
        fig.add_trace(go.Choropleth(
            geojson=geo, locations=[sel_geo], z=[0], featureidkey="properties.id",
            colorscale=[[0, AMBER], [1, AMBER]], showscale=False,
            marker_line_color="#8a6a12", marker_line_width=1.2,
            hovertemplate=f"{data.name(speaker)} (geselecteerd)<extra></extra>"))

    mm_target, mm_total = data.most_mentioned_by_year().get(year, (None, 0))
    if mm_target in ids:
        fig.add_trace(go.Choropleth(
            geojson=geo, locations=[mm_target], z=[0], featureidkey="properties.id",
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
            marker_line_color=VIOLET, marker_line_width=2.4,
            hovertemplate=f"{data.name(mm_target)} (meest genoemd {year})<extra></extra>"))

    parts = []
    top5 = data.top_targets(year, 5)
    if top5:
        items = []
        for rank, (t, tot) in enumerate(top5, 1):
            label = f"{data.name(t)} ({tot}×)"
            if t == speaker:
                label = f"**{label}**"
            items.append(f"{rank}. {label}")
        parts.append(f"**Top 5 meest genoemd wereldwijd in {year}**\n\n" + "\n".join(items))
    tm = data.top_mentioner(speaker, year)
    if tm:
        parts.append(f"{data.name(speaker)} het vaakst genoemd door "
                     f"**{data.name(tm[0])}** ({tm[1]}×).")
    else:
        parts.append(f"{data.name(speaker)} werd in {year} door niemand genoemd.")
    caption = dcc.Markdown("\n\n".join(parts))
    return fig, caption, str(year)


@app.callback(
    Output("speech-modal", "style"), Output("speech-title", "children"),
    Output("speech-hint", "children"), Output("speech-text", "children"),
    Input("world-map", "clickData"), Input("close-modal", "n_clicks"),
    State("speaker-dropdown", "value"), State("year-slider", "value"),
    prevent_initial_call=True)
def show_speech(click, _close, speaker, year):
    hidden = {"display": "none"}
    visible = {"display": "block"}
    if ctx.triggered_id == "close-modal" or not click:
        return hidden, "", "", ""
    iso = click["points"][0].get("location")
    cname = data.name(iso)
    speech_id = data.speech_iso(iso, year)
    sel_name = data.name(speaker)
    hint = f"Gemarkeerd: waar {cname} {sel_name} noemt."
    text = data.get_speech(speech_id, year)
    if not text:
        return visible, f"{cname}, {year}", hint, "Geen speech gevonden voor dit land in dit jaar."
    spans = [s for s in data.get_highlight_spans(speech_id, year)
             if data.std_target(s["target"]) == speaker]
    children = []
    for c in data.build_highlighted_children(text, spans):
        if isinstance(c, dict):
            children.append(html.Mark(c["text"], title=data.name(c["target"])))
        else:
            children.append(c)
    return visible, f"{cname}, {year}", hint, children


if __name__ == "__main__":
    app.run(debug=True)
