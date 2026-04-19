"""
NTB Seychelles — Combined Data Pipeline + Interactive Dashboard
===============================================================
Combines all four NTB scrapers' outputs into a single master dataset,
then launches an interactive Plotly Dash dashboard in your browser.

Steps
-----
1. Run all four scrapers first to generate their CSVs:
       python ntb_seychelles_scraper.py        → ntb_tenders.csv
       python ntb_minutes_scraper.py           → ntb_minutes.csv
       python ntb_eoi_scraper.py               → ntb_eoi.csv
       python ntb_advertised_scraper.py        → ntb_advertised.csv

2. Then run this script:
       python ntb_dashboard.py

   Or point to custom CSV paths:
       python ntb_dashboard.py \\
           --awarded   path/to/ntb_tenders.csv \\
           --minutes   path/to/ntb_minutes.csv \\
           --eoi       path/to/ntb_eoi.csv \\
           --advertised path/to/ntb_advertised.csv \\
           --port 8050

Requirements
------------
    pip install pandas plotly dash dash-bootstrap-components openpyxl

Dashboard sections
------------------
  Overview          — headline KPIs across all 4 datasets
  Procurement funnel— Advertised → EOI → Minutes → Awarded flow
  Awarded spend     — SR value by org / category / period (bar + treemap)
  Bidding market    — Minutes: bid count, competition level, top bidders
  Pipeline tracker  — Advertised tenders: upcoming deadlines, category mix
  Organisation view — Per-org deep dive across all stages
  Search            — Full-text search across all 4 datasets
  Download          — Export any dataset (or all combined) as CSV / Excel / JSON
"""

import io
import json
import argparse
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State, dash_table
import dash_bootstrap_components as dbc

# ---------------------------------------------------------------------------
# 1. Data loading & normalisation
# ---------------------------------------------------------------------------

CATEGORY_COLORS = {
    "Housing":          "#185FA5",
    "Infrastructure":   "#0F6E56",
    "Utilities":        "#854F0B",
    "Roads & seawalls": "#534AB7",
    "Education":        "#993C1D",
    "Transport":        "#3B6D11",
    "Health":           "#993556",
    "Energy":           "#5F5E5A",
    "Fisheries":        "#3C3489",
    "Maritime":         "#0C447C",
    "Environment":      "#63380A",
    "ICT":              "#1D9E75",
    "Sports":           "#D85A30",
    "Security":         "#888780",
    "Consultancy":      "#7F77DD",
    "Goods & Services": "#D4537E",
    "Other":            "#B4B2A9",
}

SOURCE_COLORS = {
    "Awarded":    "#185FA5",
    "Minutes":    "#0F6E56",
    "EOI":        "#854F0B",
    "Advertised": "#534AB7",
}


def load_awarded(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["source"] = "Awarded"
    # Normalise column names
    rename = {
        "org": "org", "description": "title",
        "winner": "winner", "sr_value": "sr_value",
        "currency": "currency", "category": "category",
        "period": "period",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "title" not in df and "desc" in df.columns:
        df["title"] = df["desc"]
    df["sr_value"] = pd.to_numeric(df.get("sr_value"), errors="coerce")
    return df


def load_minutes(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["source"] = "Minutes"
    rename = {
        "org": "org", "tender_description": "title",
        "bidder_name": "winner", "bid_amount": "sr_value",
        "currency": "currency", "category": "category",
        "opening_date": "opening_date", "n_bids_declared": "n_bids",
        "bid_number": "bid_number",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df["sr_value"] = pd.to_numeric(df.get("sr_value"), errors="coerce")
    return df


def load_eoi(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["source"] = "EOI"
    rename = {
        "org": "org", "title": "title",
        "category": "category", "eoi_type": "eoi_type",
        "submission_deadline": "submission_deadline",
        "created_date": "created_date",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df["sr_value"] = float("nan")
    return df


def load_advertised(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["source"] = "Advertised"
    rename = {
        "org": "org", "title": "title",
        "category": "category",
        "submission_deadline": "submission_deadline",
        "contractor_class": "contractor_class",
        "performance_period": "performance_period",
        "dossier_fee": "dossier_fee",
        "pre_bid_meeting": "pre_bid_meeting",
        "created_date": "created_date",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    df["sr_value"] = float("nan")
    return df


def combine(awarded_path, minutes_path, eoi_path, advertised_path) -> dict[str, pd.DataFrame]:
    """Load all four CSVs and return as a dict of cleaned DataFrames."""
    dfs = {}

    if Path(awarded_path).exists():
        dfs["awarded"] = load_awarded(awarded_path)
        print(f"  Awarded:    {len(dfs['awarded']):,} rows")
    else:
        print(f"  WARNING: {awarded_path} not found — skipping Awarded dataset")
        dfs["awarded"] = pd.DataFrame()

    if Path(minutes_path).exists():
        dfs["minutes"] = load_minutes(minutes_path)
        print(f"  Minutes:    {len(dfs['minutes']):,} rows (bids)")
    else:
        print(f"  WARNING: {minutes_path} not found — skipping Minutes dataset")
        dfs["minutes"] = pd.DataFrame()

    if Path(eoi_path).exists():
        dfs["eoi"] = load_eoi(eoi_path)
        print(f"  EOI:        {len(dfs['eoi']):,} rows")
    else:
        print(f"  WARNING: {eoi_path} not found — skipping EOI dataset")
        dfs["eoi"] = pd.DataFrame()

    if Path(advertised_path).exists():
        dfs["advertised"] = load_advertised(advertised_path)
        print(f"  Advertised: {len(dfs['advertised']):,} rows")
    else:
        print(f"  WARNING: {advertised_path} not found — skipping Advertised dataset")
        dfs["advertised"] = pd.DataFrame()

    # Save combined master CSV
    common_cols = ["source", "org", "title", "category", "sr_value"]
    frames = []
    for key, df in dfs.items():
        sub = df.copy()
        for col in common_cols:
            if col not in sub.columns:
                sub[col] = None
        frames.append(sub[common_cols + [c for c in sub.columns if c not in common_cols]])
    master = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    master.to_csv("ntb_master.csv", index=False, encoding="utf-8-sig")
    print(f"\n  Master CSV saved → ntb_master.csv ({len(master):,} total rows)")

    return dfs

# ---------------------------------------------------------------------------
# 2. Pre-compute summary stats used by the dashboard
# ---------------------------------------------------------------------------

def compute_stats(dfs: dict) -> dict:
    stats = {}
    aw = dfs.get("awarded", pd.DataFrame())
    mn = dfs.get("minutes", pd.DataFrame())
    eo = dfs.get("eoi", pd.DataFrame())
    ad = dfs.get("advertised", pd.DataFrame())

    # Awarded SR totals
    aw_sr = aw[aw.get("currency", pd.Series()) == "SR"] if not aw.empty else pd.DataFrame()
    stats["total_sr"] = aw_sr["sr_value"].sum() if not aw_sr.empty else 0
    stats["n_awarded"] = len(aw_sr) if not aw_sr.empty else 0
    stats["n_minutes_tenders"] = mn["detail_url"].nunique() if not mn.empty and "detail_url" in mn.columns else (len(mn) if not mn.empty else 0)
    stats["n_eoi"] = len(eo)
    stats["n_advertised"] = len(ad)
    stats["n_unique_orgs"] = len(
        set().union(
            *(df["org"].dropna().unique().tolist() for df in dfs.values() if not df.empty and "org" in df.columns)
        )
    )
    stats["n_unique_bidders"] = mn["winner"].nunique() if not mn.empty and "winner" in mn.columns else 0

    # Awarded spend by category
    if not aw_sr.empty and "category" in aw_sr.columns:
        stats["spend_by_cat"] = (
            aw_sr.groupby("category")["sr_value"].sum()
            .sort_values(ascending=False)
            .reset_index()
        )
    else:
        stats["spend_by_cat"] = pd.DataFrame(columns=["category", "sr_value"])

    # Awarded spend by org (top 12)
    if not aw_sr.empty and "org" in aw_sr.columns:
        stats["spend_by_org"] = (
            aw_sr.groupby("org")["sr_value"].sum()
            .sort_values(ascending=False)
            .head(12)
            .reset_index()
        )
    else:
        stats["spend_by_org"] = pd.DataFrame(columns=["org", "sr_value"])

    # Minutes: competition (avg bids per tender)
    if not mn.empty and "bid_number" in mn.columns and "detail_url" in mn.columns:
        bids_per = mn.groupby("detail_url")["bid_number"].max().reset_index()
        stats["avg_bids"] = round(bids_per["bid_number"].mean(), 1)
        stats["bids_dist"] = bids_per["bid_number"].value_counts().sort_index().reset_index()
        stats["bids_dist"].columns = ["n_bids", "count"]
    else:
        stats["avg_bids"] = 0
        stats["bids_dist"] = pd.DataFrame(columns=["n_bids", "count"])

    # Top bidders by win count — proxy: lowest bid_number that appears most
    if not mn.empty and "winner" in mn.columns and "bid_number" in mn.columns:
        stats["top_bidders"] = (
            mn[mn["bid_number"] == 1]["winner"]
            .value_counts()
            .head(10)
            .reset_index()
        )
        stats["top_bidders"].columns = ["bidder", "appearances_as_lowest_bidder"]
    else:
        stats["top_bidders"] = pd.DataFrame()

    # Advertised: upcoming deadlines
    if not ad.empty and "submission_deadline" in ad.columns:
        ad_deadlines = ad.copy()
        ad_deadlines["submission_deadline"] = pd.to_datetime(
            ad_deadlines["submission_deadline"], errors="coerce"
        )
        today = pd.Timestamp.today()
        upcoming = (
            ad_deadlines[ad_deadlines["submission_deadline"] >= today]
            .sort_values("submission_deadline")
            .head(20)
        )
        stats["upcoming"] = upcoming[["title", "org", "category", "submission_deadline", "contractor_class"]].copy()
    else:
        stats["upcoming"] = pd.DataFrame()

    # Category mix across all datasets
    cat_counts = {}
    for key, df in dfs.items():
        if not df.empty and "category" in df.columns:
            for cat, cnt in df["category"].value_counts().items():
                cat_counts[cat] = cat_counts.get(cat, 0) + cnt
    stats["cat_counts"] = pd.DataFrame(
        sorted(cat_counts.items(), key=lambda x: -x[1]),
        columns=["category", "count"]
    )

    # Funnel: unique tenders at each stage (proxy)
    stats["funnel"] = pd.DataFrame({
        "stage": ["Advertised", "EOI", "Minutes\n(opened)", "Awarded"],
        "count": [
            stats["n_advertised"],
            stats["n_eoi"],
            stats["n_minutes_tenders"],
            stats["n_awarded"],
        ],
        "color": ["#534AB7", "#854F0B", "#0F6E56", "#185FA5"],
    })

    return stats

# ---------------------------------------------------------------------------
# 3. Chart builders
# ---------------------------------------------------------------------------

def fig_spend_by_cat(stats):
    df = stats["spend_by_cat"]
    if df.empty:
        return go.Figure()
    colors = [CATEGORY_COLORS.get(c, "#888") for c in df["category"]]
    fig = go.Figure(go.Bar(
        x=df["category"],
        y=(df["sr_value"] / 1e6).round(1),
        marker_color=colors,
        text=(df["sr_value"] / 1e6).round(1).astype(str) + "M",
        textposition="outside",
    ))
    fig.update_layout(
        xaxis_tickangle=-35, yaxis_title="SR (millions)",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, b=80, l=40, r=10), showlegend=False,
        font=dict(size=12),
    )
    return fig


def fig_spend_by_org(stats):
    df = stats["spend_by_org"]
    if df.empty:
        return go.Figure()
    short = df["org"].str.replace("Seychelles ", "Sey. ").str[:32]
    fig = go.Figure(go.Bar(
        y=short,
        x=(df["sr_value"] / 1e6).round(1),
        orientation="h",
        marker_color="#B5D4F4",
        marker_line_color="#185FA5",
        marker_line_width=0.5,
        text=(df["sr_value"] / 1e6).round(1).astype(str) + "M",
        textposition="outside",
    ))
    fig.update_layout(
        xaxis_title="SR (millions)",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=40, l=200, r=60),
        yaxis=dict(autorange="reversed"),
        font=dict(size=11),
    )
    return fig


def fig_treemap(stats):
    df = stats["spend_by_cat"]
    if df.empty:
        return go.Figure()
    colors = [CATEGORY_COLORS.get(c, "#888") for c in df["category"]]
    fig = go.Figure(go.Treemap(
        labels=df["category"],
        values=df["sr_value"],
        parents=[""] * len(df),
        marker_colors=colors,
        texttemplate="<b>%{label}</b><br>SR %{value:,.0f}",
        hovertemplate="<b>%{label}</b><br>SR %{value:,.0f}<extra></extra>",
    ))
    fig.update_layout(
        margin=dict(t=10, b=10, l=10, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def fig_bids_dist(stats):
    df = stats["bids_dist"]
    if df.empty:
        return go.Figure()
    fig = go.Figure(go.Bar(
        x=df["n_bids"].astype(str),
        y=df["count"],
        marker_color="#9FE1CB",
        marker_line_color="#0F6E56",
        marker_line_width=0.5,
    ))
    fig.update_layout(
        xaxis_title="Number of bids received",
        yaxis_title="Number of tenders",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=40, l=40, r=10),
        font=dict(size=12),
    )
    return fig


def fig_funnel(stats):
    df = stats["funnel"]
    fig = go.Figure(go.Funnel(
        y=df["stage"],
        x=df["count"],
        marker_color=df["color"].tolist(),
        textinfo="value+percent initial",
        connector=dict(line=dict(color="rgba(0,0,0,0.1)", width=1)),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=10, l=10, r=10),
        font=dict(size=13),
    )
    return fig


def fig_cat_all(stats):
    df = stats["cat_counts"].head(14)
    if df.empty:
        return go.Figure()
    colors = [CATEGORY_COLORS.get(c, "#888") for c in df["category"]]
    fig = go.Figure(go.Bar(
        y=df["category"],
        x=df["count"],
        orientation="h",
        marker_color=colors,
        text=df["count"],
        textposition="outside",
    ))
    fig.update_layout(
        xaxis_title="Total records across all datasets",
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=10, b=40, l=140, r=60),
        yaxis=dict(autorange="reversed"),
        font=dict(size=11),
    )
    return fig

# ---------------------------------------------------------------------------
# 4. Dash app layout
# ---------------------------------------------------------------------------

def build_app(dfs: dict, stats: dict) -> Dash:
    app = Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        title="NTB Seychelles — Procurement Dashboard",
    )

    aw = dfs.get("awarded", pd.DataFrame())
    mn = dfs.get("minutes", pd.DataFrame())
    eo = dfs.get("eoi", pd.DataFrame())
    ad = dfs.get("advertised", pd.DataFrame())

    # All orgs for dropdown
    all_orgs = sorted(set().union(
        *(df["org"].dropna().unique().tolist()
          for df in dfs.values() if not df.empty and "org" in df.columns)
    ))

    def kpi(label, value, sub=""):
        return dbc.Card(dbc.CardBody([
            html.P(label, style={"fontSize": "12px", "color": "#888", "marginBottom": "4px"}),
            html.H4(value, style={"fontWeight": "500", "marginBottom": "2px"}),
            html.P(sub, style={"fontSize": "11px", "color": "#aaa", "marginBottom": 0}),
        ]), style={"background": "#f8f8f6", "border": "none", "borderRadius": "8px"})

    def section(title, *children):
        return html.Div([
            html.H6(title, style={"fontWeight": "500", "color": "#555",
                                  "fontSize": "11px", "letterSpacing": "0.05em",
                                  "textTransform": "uppercase", "marginBottom": "12px",
                                  "marginTop": "2rem"}),
            *children,
            html.Hr(style={"borderColor": "rgba(0,0,0,0.07)", "marginTop": "1.5rem"}),
        ])

    sr_total = f"SR {stats['total_sr']/1e6:.0f}M"

    app.layout = dbc.Container([
        # Header
        dbc.Row(dbc.Col(html.Div([
            html.H4("NTB Seychelles — Procurement Intelligence Dashboard",
                    style={"fontWeight": "500", "marginBottom": "4px"}),
            html.P("Combining Awarded Tenders · Minutes of Tenders · Expressions of Interest · Advertised Tenders",
                   style={"color": "#888", "fontSize": "13px"}),
        ]), padding="1.5rem 0 0.5rem")),

        # Source filter pills
        dbc.Row(dbc.Col([
            html.Span("Show: ", style={"fontSize": "12px", "color": "#888", "marginRight": "8px"}),
            dcc.Checklist(
                id="source-filter",
                options=[{"label": s, "value": s} for s in ["Awarded", "Minutes", "EOI", "Advertised"]],
                value=["Awarded", "Minutes", "EOI", "Advertised"],
                inline=True,
                inputStyle={"marginRight": "4px"},
                labelStyle={"marginRight": "16px", "fontSize": "13px", "cursor": "pointer"},
            ),
        ])),

        html.Br(),

        # KPI row
        dbc.Row([
            dbc.Col(kpi("Total SR awarded", sr_total, f"{stats['n_awarded']:,} SR contracts"), width=3),
            dbc.Col(kpi("Tenders opened (minutes)", f"{stats['n_minutes_tenders']:,}", f"avg {stats['avg_bids']} bids each"), width=3),
            dbc.Col(kpi("EOI / limited bids", f"{stats['n_eoi']:,}", "market sounding notices"), width=3),
            dbc.Col(kpi("Advertised tenders", f"{stats['n_advertised']:,}", f"{stats['n_unique_orgs']} procuring entities"), width=3),
        ], className="g-2"),

        # ── Section 1: Procurement funnel ──────────────────────────────────
        section("Procurement funnel",
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig_funnel(stats), config={"displayModeBar": False},
                                  style={"height": "320px"}), width=5),
                dbc.Col(dcc.Graph(figure=fig_cat_all(stats), config={"displayModeBar": False},
                                  style={"height": "320px"}), width=7),
            ])
        ),

        # ── Section 2: Awarded spend ───────────────────────────────────────
        section("Awarded spend (SR contracts only)",
            dbc.Row([
                dbc.Col(dcc.Graph(id="spend-cat-chart", figure=fig_spend_by_cat(stats),
                                  config={"displayModeBar": False},
                                  style={"height": "300px"}), width=8),
                dbc.Col(dcc.Graph(id="treemap", figure=fig_treemap(stats),
                                  config={"displayModeBar": False},
                                  style={"height": "300px"}), width=4),
            ]),
            dbc.Row(dbc.Col(
                dcc.Graph(id="spend-org-chart", figure=fig_spend_by_org(stats),
                          config={"displayModeBar": False},
                          style={"height": "420px"}),
            )),
        ),

        # ── Section 3: Bidding market ──────────────────────────────────────
        section("Bidding market (minutes of tenders)",
            dbc.Row([
                dbc.Col([
                    html.P("Bid count distribution — how competitive are tenders?",
                           style={"fontSize": "12px", "color": "#888"}),
                    dcc.Graph(figure=fig_bids_dist(stats),
                              config={"displayModeBar": False},
                              style={"height": "260px"}),
                ], width=7),
                dbc.Col([
                    html.P("Top 10 most frequent first-position bidders",
                           style={"fontSize": "12px", "color": "#888"}),
                    dash_table.DataTable(
                        data=stats["top_bidders"].to_dict("records") if not stats["top_bidders"].empty else [],
                        columns=[
                            {"name": "Bidder", "id": "bidder"},
                            {"name": "Times lowest bid", "id": "appearances_as_lowest_bidder"},
                        ],
                        style_table={"overflowX": "auto"},
                        style_cell={"fontSize": "12px", "padding": "6px 8px",
                                    "fontFamily": "inherit", "border": "none",
                                    "textAlign": "left"},
                        style_header={"fontWeight": "500", "color": "#666",
                                      "borderBottom": "0.5px solid #e0e0e0",
                                      "background": "white"},
                        style_data_conditional=[{
                            "if": {"row_index": "odd"},
                            "backgroundColor": "#fafafa",
                        }],
                        page_size=10,
                    ),
                ], width=5),
            ])
        ),

        # ── Section 4: Pipeline tracker ────────────────────────────────────
        section("Upcoming advertised tender deadlines",
            html.Div([
                html.P("Next 20 tenders by submission deadline",
                       style={"fontSize": "12px", "color": "#888"}),
                dash_table.DataTable(
                    data=stats["upcoming"].assign(
                        submission_deadline=stats["upcoming"]["submission_deadline"].dt.strftime("%Y-%m-%d")
                        if not stats["upcoming"].empty else []
                    ).to_dict("records") if not stats["upcoming"].empty else [],
                    columns=[
                        {"name": "Deadline", "id": "submission_deadline"},
                        {"name": "Title", "id": "title"},
                        {"name": "Org", "id": "org"},
                        {"name": "Category", "id": "category"},
                        {"name": "Class", "id": "contractor_class"},
                    ],
                    style_table={"overflowX": "auto"},
                    style_cell={"fontSize": "12px", "padding": "6px 8px",
                                "fontFamily": "inherit", "border": "none",
                                "maxWidth": "240px", "overflow": "hidden",
                                "textOverflow": "ellipsis"},
                    style_header={"fontWeight": "500", "color": "#666",
                                  "borderBottom": "0.5px solid #e0e0e0",
                                  "background": "white"},
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
                    ],
                    tooltip_data=[
                        {col: {"value": str(row[col]), "type": "markdown"}
                         for col in ["title", "org"]}
                        for row in stats["upcoming"].to_dict("records")
                    ] if not stats["upcoming"].empty else [],
                    tooltip_duration=None,
                    page_size=10,
                ),
            ])
        ),

        # ── Section 5: Org deep dive ───────────────────────────────────────
        section("Organisation deep dive",
            dbc.Row([
                dbc.Col([
                    dcc.Dropdown(
                        id="org-dropdown",
                        options=[{"label": o, "value": o} for o in all_orgs],
                        value=all_orgs[0] if all_orgs else None,
                        clearable=False,
                        style={"fontSize": "13px"},
                    ),
                ], width=6),
            ]),
            html.Div(id="org-detail", style={"marginTop": "1rem"}),
        ),

        # ── Section 6: Full-text search ────────────────────────────────────
        section("Full-text search across all datasets",
            dbc.Row([
                dbc.Col(dcc.Input(
                    id="search-input",
                    type="text",
                    placeholder="Search titles, organisations, descriptions…",
                    debounce=True,
                    style={"width": "100%", "fontSize": "13px",
                           "padding": "8px 12px", "borderRadius": "8px",
                           "border": "0.5px solid #ccc"},
                ), width=8),
                dbc.Col(dcc.Dropdown(
                    id="search-source",
                    options=[{"label": s, "value": s}
                             for s in ["All", "Awarded", "Minutes", "EOI", "Advertised"]],
                    value="All",
                    clearable=False,
                    style={"fontSize": "13px"},
                ), width=2),
            ]),
            html.Div(id="search-results", style={"marginTop": "1rem"}),
        ),

        # ── Section 7: Download ────────────────────────────────────────────
        section("Download raw data",
            dbc.Row([
                dbc.Col([
                    html.P("Dataset", style={"fontSize": "12px", "color": "#888",
                                             "marginBottom": "4px"}),
                    dcc.Dropdown(
                        id="dl-dataset",
                        options=[
                            {"label": "All datasets combined (master)",  "value": "master"},
                            {"label": "Awarded tenders",                 "value": "awarded"},
                            {"label": "Minutes of tenders (bids)",       "value": "minutes"},
                            {"label": "Expressions of interest",         "value": "eoi"},
                            {"label": "Advertised tenders",              "value": "advertised"},
                        ],
                        value="master",
                        clearable=False,
                        style={"fontSize": "13px"},
                    ),
                ], width=4),
                dbc.Col([
                    html.P("Format", style={"fontSize": "12px", "color": "#888",
                                            "marginBottom": "4px"}),
                    dcc.RadioItems(
                        id="dl-format",
                        options=[
                            {"label": " CSV",   "value": "csv"},
                            {"label": " Excel", "value": "excel"},
                            {"label": " JSON",  "value": "json"},
                        ],
                        value="csv",
                        inline=True,
                        inputStyle={"marginRight": "4px"},
                        labelStyle={"marginRight": "20px", "fontSize": "13px",
                                    "cursor": "pointer"},
                    ),
                ], width=4),
                dbc.Col([
                    html.P("\u00a0", style={"fontSize": "12px", "marginBottom": "4px"}),
                    html.Button(
                        "Download",
                        id="dl-btn",
                        n_clicks=0,
                        style={
                            "fontSize": "13px", "padding": "6px 20px",
                            "borderRadius": "8px", "cursor": "pointer",
                            "border": "0.5px solid #185FA5",
                            "background": "#185FA5", "color": "white",
                            "fontWeight": "500",
                        },
                    ),
                ], width=4, style={"display": "flex", "alignItems": "flex-end"}),
            ], className="g-3"),
            html.Div(id="dl-status", style={"marginTop": "10px", "fontSize": "12px",
                                             "color": "#888"}),
            dcc.Download(id="dl-download"),
        ),

        html.Div(style={"height": "3rem"}),

    ], fluid=True, style={"maxWidth": "1100px", "margin": "0 auto",
                           "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"})

    # ── Callbacks ────────────────────────────────────────────────────────────

    @app.callback(
        Output("org-detail", "children"),
        Input("org-dropdown", "value"),
    )
    def org_detail(org):
        if not org:
            return ""
        rows = []

        # Awarded SR
        if not aw.empty and "org" in aw.columns:
            aw_sub = aw[(aw["org"] == org) & (aw.get("currency", pd.Series()) == "SR")]
            if not aw_sub.empty:
                total = aw_sub["sr_value"].sum()
                rows.append(html.P([
                    html.Strong(f"Awarded contracts: "),
                    f"{len(aw_sub)} contracts totalling SR {total:,.0f}",
                ], style={"fontSize": "13px"}))

        # Minutes
        if not mn.empty and "org" in mn.columns:
            mn_sub = mn[mn["org"] == org]
            if not mn_sub.empty:
                n_tenders = mn_sub["detail_url"].nunique() if "detail_url" in mn_sub.columns else len(mn_sub)
                rows.append(html.P([
                    html.Strong("Tenders opened: "),
                    f"{n_tenders} tender openings recorded",
                ], style={"fontSize": "13px"}))

        # EOI
        if not eo.empty and "org" in eo.columns:
            eo_sub = eo[eo["org"] == org]
            if not eo_sub.empty:
                rows.append(html.P([
                    html.Strong("EOI / limited bids: "),
                    f"{len(eo_sub)} notices",
                ], style={"fontSize": "13px"}))

        # Advertised
        if not ad.empty and "org" in ad.columns:
            ad_sub = ad[ad["org"] == org]
            if not ad_sub.empty:
                rows.append(html.P([
                    html.Strong("Advertised tenders: "),
                    f"{len(ad_sub)} tenders",
                ], style={"fontSize": "13px"}))

        if not rows:
            return html.P("No data found for this organisation.", style={"color": "#aaa"})

        # Recent awarded contracts table
        if not aw.empty and "org" in aw.columns:
            aw_sub = aw[aw["org"] == org].copy()
            if not aw_sub.empty:
                aw_sub["sr_value"] = pd.to_numeric(aw_sub["sr_value"], errors="coerce")
                top = aw_sub.nlargest(10, "sr_value")[["title", "sr_value", "category"]]
                top["sr_value"] = top["sr_value"].apply(
                    lambda v: f"SR {v:,.0f}" if pd.notna(v) else "—"
                )
                rows.append(html.P("Top awarded contracts:", style={"fontWeight": "500", "fontSize": "12px", "marginTop": "12px", "color": "#666"}))
                rows.append(dash_table.DataTable(
                    data=top.to_dict("records"),
                    columns=[
                        {"name": "Title", "id": "title"},
                        {"name": "SR value", "id": "sr_value"},
                        {"name": "Category", "id": "category"},
                    ],
                    style_table={"overflowX": "auto"},
                    style_cell={"fontSize": "12px", "padding": "5px 8px",
                                "fontFamily": "inherit", "border": "none"},
                    style_header={"fontWeight": "500", "color": "#666",
                                  "borderBottom": "0.5px solid #e0e0e0",
                                  "background": "white"},
                    style_data_conditional=[
                        {"if": {"row_index": "odd"}, "backgroundColor": "#fafafa"},
                    ],
                    page_size=10,
                ))

        return rows

    @app.callback(
        Output("search-results", "children"),
        Input("search-input", "value"),
        Input("search-source", "value"),
    )
    def search(query, source_filter):
        if not query or len(query.strip()) < 2:
            return html.P("Type at least 2 characters to search.",
                          style={"color": "#aaa", "fontSize": "13px"})

        q = query.strip().lower()
        results = []

        source_map = {
            "Awarded": aw, "Minutes": mn, "EOI": eo, "Advertised": ad,
        }
        sources = list(source_map.keys()) if source_filter == "All" else [source_filter]

        for src in sources:
            df = source_map.get(src, pd.DataFrame())
            if df.empty:
                continue
            text_cols = [c for c in ["title", "org", "description", "tender_description"]
                         if c in df.columns]
            mask = df[text_cols].apply(
                lambda col: col.astype(str).str.lower().str.contains(q, na=False)
            ).any(axis=1)
            hits = df[mask].head(10)
            for _, row in hits.iterrows():
                title = row.get("title") or row.get("tender_description") or "—"
                org = row.get("org", "—")
                cat = row.get("category", "—")
                results.append(dbc.Card(dbc.CardBody([
                    html.Div([
                        html.Span(src, style={
                            "fontSize": "10px", "padding": "2px 8px",
                            "borderRadius": "10px", "marginRight": "8px",
                            "background": SOURCE_COLORS.get(src, "#888") + "22",
                            "color": SOURCE_COLORS.get(src, "#555"),
                            "fontWeight": "500",
                        }),
                        html.Span(cat, style={"fontSize": "11px", "color": "#999"}),
                    ]),
                    html.P(str(title)[:140], style={"fontSize": "13px", "fontWeight": "500",
                                                    "marginBottom": "2px", "marginTop": "4px"}),
                    html.P(str(org)[:80], style={"fontSize": "12px", "color": "#888",
                                                  "marginBottom": 0}),
                ]), style={"marginBottom": "8px", "border": "0.5px solid #e8e8e8",
                           "borderRadius": "8px"}))

        if not results:
            return html.P(f"No results found for '{query}'.",
                          style={"color": "#aaa", "fontSize": "13px"})

        return html.Div([
            html.P(f"{len(results)} results for '{query}'",
                   style={"fontSize": "12px", "color": "#888", "marginBottom": "12px"}),
            *results,
        ])

    # ── Download callback ─────────────────────────────────────────────────────

    # Build combined master frame once, available to the callback via closure
    def _build_master():
        common_cols = ["source", "org", "title", "category", "sr_value"]
        frames = []
        for key, df in dfs.items():
            if df.empty:
                continue
            sub = df.copy()
            sub["source"] = key.capitalize()
            for col in common_cols:
                if col not in sub.columns:
                    sub[col] = None
            frames.append(sub)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    _MASTER = _build_master()

    _DATASET_MAP = {
        "master":     _MASTER,
        "awarded":    aw,
        "minutes":    mn,
        "eoi":        eo,
        "advertised": ad,
    }

    _DATASET_LABELS = {
        "master":     "ntb_master",
        "awarded":    "ntb_awarded",
        "minutes":    "ntb_minutes",
        "eoi":        "ntb_eoi",
        "advertised": "ntb_advertised",
    }

    @app.callback(
        Output("dl-download", "data"),
        Output("dl-status", "children"),
        Input("dl-btn", "n_clicks"),
        State("dl-dataset", "value"),
        State("dl-format", "value"),
        prevent_initial_call=True,
    )
    def trigger_download(n_clicks, dataset, fmt):
        if not n_clicks:
            return None, ""

        df = _DATASET_MAP.get(dataset, pd.DataFrame())
        if df.empty:
            return None, "No data available for that dataset — run the scrapers first."

        stem = _DATASET_LABELS.get(dataset, "ntb_data")
        nrows = len(df)

        if fmt == "csv":
            content = df.to_csv(index=False, encoding="utf-8")
            filename = f"{stem}.csv"
            return (
                dcc.send_string(content, filename),
                f"Prepared {nrows:,} rows → {filename}",
            )

        elif fmt == "json":
            content = df.to_json(orient="records", force_ascii=False, indent=2)
            filename = f"{stem}.json"
            return (
                dcc.send_string(content, filename),
                f"Prepared {nrows:,} rows → {filename}",
            )

        elif fmt == "excel":
            buf = io.BytesIO()
            try:
                with pd.ExcelWriter(buf, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Data")
                    # Summary sheet — category counts
                    if "category" in df.columns:
                        (
                            df["category"].value_counts()
                            .reset_index()
                            .rename(columns={"index": "category", "category": "count"})
                            .to_excel(writer, index=False, sheet_name="By category")
                        )
                    # Org counts
                    if "org" in df.columns:
                        (
                            df["org"].value_counts()
                            .reset_index()
                            .rename(columns={"index": "org", "org": "count"})
                            .to_excel(writer, index=False, sheet_name="By org")
                        )
                    # SR spend summary (awarded only)
                    if "sr_value" in df.columns and "currency" in df.columns:
                        sr_df = df[df["currency"] == "SR"].copy()
                        sr_df["sr_value"] = pd.to_numeric(sr_df["sr_value"], errors="coerce")
                        if not sr_df.empty and "org" in sr_df.columns:
                            (
                                sr_df.groupby("org")["sr_value"]
                                .sum()
                                .sort_values(ascending=False)
                                .reset_index()
                                .rename(columns={"sr_value": "total_sr"})
                                .to_excel(writer, index=False, sheet_name="SR spend by org")
                            )
            except ImportError:
                return None, "openpyxl not installed. Run: pip install openpyxl"

            buf.seek(0)
            filename = f"{stem}.xlsx"
            return (
                dcc.send_bytes(buf.read(), filename),
                f"Prepared {nrows:,} rows → {filename} (with summary sheets)",
            )

        return None, "Unknown format."

    return app

# ---------------------------------------------------------------------------
# 5. Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="NTB Seychelles Combined Dashboard")
    parser.add_argument("--awarded",    default="ntb_tenders.csv")
    parser.add_argument("--minutes",    default="ntb_minutes.csv")
    parser.add_argument("--eoi",        default="ntb_eoi.csv")
    parser.add_argument("--advertised", default="ntb_advertised.csv")
    parser.add_argument("--port",       type=int, default=8050)
    parser.add_argument("--combine-only", action="store_true",
                        help="Only combine CSVs into ntb_master.csv, don't launch dashboard")
    args = parser.parse_args()

    print("\nLoading datasets…")
    dfs = combine(args.awarded, args.minutes, args.eoi, args.advertised)

    if args.combine_only:
        print("\nDone. ntb_master.csv written.")
        return

    print("\nComputing statistics…")
    stats = compute_stats(dfs)

    print(f"\nLaunching dashboard at http://localhost:{args.port}")
    print("Press Ctrl+C to stop.\n")

    app = build_app(dfs, stats)
    app.run(debug=False, port=args.port)


if __name__ == "__main__":
    main()
