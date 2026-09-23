"""Gemeinsame visuelle Sprache (Port des KiScanner ui_design.py, Gold-Variante).

Calm forensic canvas: dunkles Navy, Gold als einziger Akzent, stabile Flächen
ohne Hover-Bewegung bei Informationskarten. Enthält: Theme-Stylesheet, Seiten-
Hero mit Radar-Grid, Workflow-Stepper (Knoten + Fortschrittsschiene),
Aktivitäts-Badge und Status-Feed.
"""
from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

import streamlit as st

from . import config


@lru_cache(maxsize=1)
def _stylesheet() -> str:
    assets = Path(config.ASSETS_DIR)
    radar_b64 = ""
    radar_datei = assets / "radar-grid.svg"
    if radar_datei.exists():
        radar_b64 = base64.b64encode(radar_datei.read_bytes()).decode("ascii")

    return f"""<style>
    /* Calm forensic canvas — Gold-Variante des KiScanner-Designs. */
    /* Streamlit-Eigenwerbung ausblenden (Deploy/Status) — gehört nicht ins Produkt. */
    #stDeployButton {{ display: none !important; }}
    [data-testid="stStatusWidget"] {{ display: none !important; }}
    .stApp {{
        background-color: #0A111E;
        background-image:
            radial-gradient(ellipse at 90% 0%, rgba(232, 184, 75, 0.07), transparent 32rem),
            linear-gradient(180deg, #0A111E 0%, #0B1422 100%);
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}
    [data-testid="stSidebar"] {{
        background-color: #080E1A !important;
        background-image: linear-gradient(180deg, #080E1A, #0A1220) !important;
        border-right: 1px solid rgba(39, 62, 91, 0.6) !important;
    }}
    .st-key-sidebar_brand h2, .st-key-sidebar_brand span {{
        letter-spacing: -.04em;
        color: #F8FAFC;
    }}
    .st-key-sidebar_brand {{
        border-bottom: 1px solid rgba(39, 62, 91, 0.7);
        padding-bottom: .9rem;
    }}

    /* Stabile Flächen: Karten ohne Hover-Bewegung. */
    [data-testid="stVerticalBlockBorderWrapper"] > div {{
        background: #101C2D !important;
        border: 1px solid rgba(71, 98, 130, 0.55) !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2) !important;
        border-radius: 14px !important;
    }}

    /* Seiten-Hero: Kontext einmal setzen, dann Platz machen. */
    .st-key-page_hero {{
        padding: 1.4rem 1.6rem;
        border: 1px solid rgba(71, 98, 130, 0.62);
        border-radius: 16px;
        background-color: #0E1A2C;
        background-image:
            linear-gradient(90deg, #0E1A2C 30%, #0E1A2CEB 66%, #0E1A2C80),
            url('data:image/svg+xml;base64,{radar_b64}');
        background-position: center, right center;
        background-size: cover, auto 115%;
        background-repeat: no-repeat;
        margin-bottom: 1rem;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.28);
    }}
    .st-key-page_hero h1 {{
        letter-spacing: -.035em;
        color: #F8FAFC;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.5);
    }}
    .st-key-page_hero p {{ max-width: 820px; color: #CBD5E1; line-height: 1.5; }}
    .st-key-page_hero [data-testid="stCaptionContainer"] {{
        color: #E8B84B; letter-spacing: .14em; font-weight: 700;
    }}

    /* Metrics: kompakt, tabellarisch, bewusst nicht interaktiv. */
    [data-testid="stMetric"] {{
        border: 1px solid rgba(71, 98, 130, 0.55) !important;
        border-radius: 14px !important;
        background: #101C2D !important;
        padding: 1rem 1.1rem !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2) !important;
    }}
    [data-testid="stMetricValue"] {{
        font-variant-numeric: tabular-nums;
        font-weight: 750 !important;
        letter-spacing: -0.02em;
        color: #F8FAFC !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: #94A3B8 !important;
        font-weight: 600 !important;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        font-size: 0.78rem !important;
    }}

    /* Stations-Stepper: Knoten + Fortschrittsschiene (Gold-Akzent). */
    .gld-stepper {{
        --gld-fill: 0%;
        position: relative;
        display: flex;
        gap: .5rem;
        padding: .3rem .2rem .15rem;
    }}
    .gld-rail {{
        position: absolute;
        top: 1.29rem; left: 10%; right: 10%;
        height: 5px; border-radius: 99px;
        background: rgba(148, 163, 184, .22);
        overflow: hidden;
    }}
    .gld-rail i {{
        display: block; height: 100%;
        width: var(--gld-fill);
        border-radius: inherit;
        background: linear-gradient(90deg, #B8860B, #E8B84B 70%, #F5D67B);
        box-shadow: 0 0 12px rgba(232, 184, 75, .7);
        transition: width .6s ease;
    }}
    .gld-step {{
        flex: 1 1 0; min-width: 0;
        display: flex; flex-direction: column; align-items: center;
        position: relative; z-index: 1;
    }}
    .gld-step-body {{
        display: flex; flex-direction: column; align-items: center;
        min-width: 0; flex: 1 1 auto;
    }}
    .gld-node {{
        width: 2.3rem; height: 2.3rem; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-weight: 800; font-size: 1rem; position: relative;
        border: 1px solid rgba(148, 163, 184, .28);
        background: #121E31; color: #64748B;
    }}
    .gld-step--running .gld-node {{
        background: linear-gradient(135deg, #E8B84B, #B8860B);
        color: #2B1F02;
        border-color: #F5D67B;
        box-shadow: 0 0 0 4px rgba(232, 184, 75, .15), 0 0 18px rgba(232, 184, 75, .45);
    }}
    .gld-step--running .gld-node::before {{
        content: ""; position: absolute; inset: -7px; border-radius: 50%;
        border: 2px dashed rgba(245, 214, 123, .65);
        animation: gld-spin 3.2s linear infinite;
    }}
    .gld-step--complete .gld-node {{
        background: linear-gradient(135deg, #10B981, #059669);
        color: #03271C; border-color: #6EE7B7;
        box-shadow: 0 0 12px rgba(16, 185, 129, .35);
    }}
    .gld-step--error .gld-node {{
        background: linear-gradient(135deg, #F43F5E, #E11D48);
        color: #2B040D; border-color: #FDA4AF;
        box-shadow: 0 0 12px rgba(244, 63, 94, .35);
    }}
    .gld-step--pending .gld-node {{ opacity: .75; }}
    .gld-step-title {{
        margin-top: .6rem; font-weight: 700; font-size: .95rem;
        color: #CBD5E1; max-width: 100%;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .gld-step--running .gld-step-title {{ color: #F5D67B; }}
    .gld-step--complete .gld-step-title {{ color: #A7F3D0; }}
    .gld-step-meta {{
        font-size: .78rem; line-height: 1.3; color: #8CA0B8;
        max-width: 100%; margin-top: .12rem; min-height: 1.02em;
        display: -webkit-box; -webkit-line-clamp: 2;
        -webkit-box-orient: vertical; overflow: hidden;
    }}
    @keyframes gld-spin {{ to {{ transform: rotate(360deg); }} }}
    @media(max-width:720px) {{
        .gld-stepper {{ flex-direction: column; gap: 1.05rem; }}
        .gld-rail {{ left: 1.03rem; right: auto; top: 1.45rem; bottom: 1.45rem;
                     width: 4px; height: auto; }}
        .gld-rail i {{ width: 100%; height: var(--gld-fill); transition: height .6s ease; }}
        .gld-step {{ flex-direction: row; align-items: flex-start; gap: .85rem; }}
        .gld-step-body {{ align-items: flex-start; }}
        .gld-step-title {{ margin-top: .1rem; }}
    }}

    /* Status-Feed: kompakte Zeilen statt Logfile-Wand. */
    .gld-feed {{
        margin-top: .4rem;
        border-left: 2px solid rgba(232, 184, 75, .35);
        padding: .12rem 0 .12rem .8rem;
        display: flex; flex-direction: column; gap: .2rem;
    }}
    .gld-feed__line {{
        font-size: .8rem; color: #7C8DA6;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .gld-feed__line::before {{ content: "· "; color: #E8B84B; font-weight: 800; }}

    /* Lauf-Zentrale (Port der KiScanner-Statusleiste): pulsierender Punkt,
       Stations-Text, Stoppuhr — zeigt WAHRLOS sichtbar, was gerade läuft. */
    .gld-strip {{
        display: flex; align-items: center; gap: .65rem; flex-wrap: wrap;
        margin: .35rem 0 .55rem; min-width: 0;
    }}
    .gld-strip__text b {{ font-size: 1.02rem; color: #F1F5F9; }}
    .gld-strip__text small {{
        display: block; color: #94A3B8; font-size: .85rem;
        margin-top: .12rem; line-height: 1.35;
    }}
    .gld-strip__side {{ margin-left: auto; }}
    .gld-dot {{
        flex: 0 0 auto; width: .8rem; height: .8rem; border-radius: 50%;
        background: #64748B; box-shadow: 0 0 0 3px rgba(100, 116, 139, .16);
    }}
    .gld-dot--running {{
        background: #E8B84B;
        box-shadow: 0 0 0 3px rgba(232, 184, 75, .18), 0 0 12px rgba(232, 184, 75, .6);
        animation: gld-dot-blink 1.2s ease-in-out infinite;
    }}
    .gld-dot--complete {{ background: #10B981; box-shadow: 0 0 0 3px rgba(16, 185, 129, .18); }}
    .gld-dot--error {{ background: #F43F5E; box-shadow: 0 0 0 3px rgba(244, 63, 94, .18); }}
    @keyframes gld-dot-blink {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .4; }} }}
    .gld-clock {{
        font-variant-numeric: tabular-nums; font-weight: 700; color: #F5D67B;
        background: rgba(232, 184, 75, .1);
        border: 1px solid rgba(232, 184, 75, .38);
        padding: .16rem .62rem; border-radius: 99px; font-size: .85rem;
        white-space: nowrap;
    }}

    /* KPI-Karten mit Bewegungs-Skala (grün ruhig → rot bewegt) */
    .gld-kpi-zeile {{ display: flex; gap: .8rem; flex-wrap: wrap; }}
    .gld-kpi {{
        flex: 1 1 150px; min-width: 140px;
        border: 1px solid rgba(71, 98, 130, .55); border-radius: 14px;
        background: #101C2D; padding: .8rem .9rem;
    }}
    .gld-kpi-label {{
        color: #94A3B8; font-weight: 600; letter-spacing: .03em;
        text-transform: uppercase; font-size: .72rem; margin-bottom: .25rem;
    }}
    .gld-kpi-wert {{
        font-size: 1.45rem; font-weight: 750; font-variant-numeric: tabular-nums;
    }}
    .gld-kpi-balken {{
        height: 6px; border-radius: 99px; margin-top: .45rem;
        background: rgba(148, 163, 184, .16); overflow: hidden;
    }}
    .gld-kpi-balken i {{ display: block; height: 100%; border-radius: inherit; }}
    .gld-kpi-neben {{ color: #7C8DA6; font-size: .74rem; margin-top: .3rem;
                      line-height: 1.3; }}

    /* Treiber-Wasserfall (S4): je Tag eine kompakte Balkenliste —
       Breite = |Einfluss| relativ zum Band, Gold = auf, Rot = ab. */
    .gld-wasserfall-liste {{ display: flex; flex-direction: column; gap: .28rem;
                             margin: .3rem 0 .55rem; }}
    .gld-wasserfall {{ display: flex; align-items: center; gap: .6rem; }}
    .gld-wf-name {{ flex: 0 0 40%; font-size: .78rem; color: #94A3B8;
                    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .gld-wf-balken {{ flex: 1 1 auto; height: 8px; border-radius: 99px;
                      background: rgba(148, 163, 184, .16); overflow: hidden; }}
    .gld-wf-balken i {{ display: block; height: 100%; border-radius: inherit;
                        transition: width .5s ease; }}
    .gld-wf-wert {{ flex: 0 0 auto; font-size: .78rem; font-weight: 700;
                    color: #CBD5E1; font-variant-numeric: tabular-nums;
                    min-width: 4.2rem; text-align: right; }}

    /* Actions: ein klarer Gold-Akzent, keine dekorative Bewegung. */
    button[kind="primary"], .stButton > button[type="primary"] {{
        background: #E8B84B !important;
        color: #1A1403 !important;
        font-weight: 750 !important;
        border: 1px solid #F5D67B !important;
        border-radius: 10px !important;
        box-shadow: 0 2px 8px rgba(232, 184, 75, 0.2) !important;
    }}
    button[kind="primary"]:hover, .stButton > button[type="primary"]:hover {{
        background: #F0C674 !important;
        box-shadow: 0 3px 10px rgba(232, 184, 75, 0.28) !important;
    }}
    button[kind="secondary"], .stButton > button[type="secondary"] {{
        background: #132238 !important;
        color: #F1F5F9 !important;
        border: 1px solid rgba(71, 98, 130, 0.72) !important;
        border-radius: 10px !important;
    }}
    button[kind="secondary"]:hover, .stButton > button[type="secondary"]:hover {{
        background: #182A43 !important;
        border-color: rgba(245, 214, 123, 0.5) !important;
    }}

    /* Aktivitäts-Badge: klebt an der Ecke, sagt WAS gerade läuft. */
    .gld-aktivitaet {{
        position: fixed; top: 4.6rem; right: 1rem; z-index: 999990;
        display: flex; align-items: center; gap: .5rem;
        background: rgba(232, 184, 75, .14);
        border: 1px solid rgba(232, 184, 75, .55);
        color: #F5D67B; padding: .34rem .85rem; border-radius: 999px;
        font-size: .86rem; font-weight: 600;
        backdrop-filter: blur(6px);
        box-shadow: 0 4px 18px rgba(0, 0, 0, .35);
        pointer-events: none; max-width: 26rem;
        white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }}
    .gld-aktivitaet i {{
        width: .55rem; height: .55rem; border-radius: 50%;
        background: #F5D67B; flex: none;
        animation: gld-aktivitaet-puls 1.1s infinite ease-in-out;
    }}
    @keyframes gld-aktivitaet-puls {{
        0%, 100% {{ opacity: .25; transform: scale(.75); }}
        50% {{ opacity: 1; transform: scale(1.2); }}
    }}
    @media(prefers-reduced-motion:reduce) {{
        .gld-aktivitaet i, .gld-step--running .gld-node::before,
        .gld-dot--running {{ animation: none !important; }}
        .gld-rail i {{ transition: none !important; }}
    }}
    </style>"""


def apply_theme() -> None:
    st.html(_stylesheet())


def page_header(eyebrow: str, title: str, description: str) -> None:
    """Seiten-Hero mit Radar-Grid (Vorbild: KiScanner page_header)."""
    with st.container(key="page_hero", gap="xsmall"):
        st.caption(eyebrow.upper())
        st.title(title)
        st.markdown(description)


def aktivitaets_banner(text: str):
    """Badge rendern; Rückgabe ist der Slot — nach der Arbeit `slot.empty()`."""
    slot = st.empty()
    slot.markdown(
        f'<div class="gld-aktivitaet"><i aria-hidden="true"></i>{html.escape(text)}</div>',
        unsafe_allow_html=True)
    return slot


# ------------------------------------------------------- Workflow-Stepper
_NODE_MARK = {
    "complete": '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" '
                'stroke="currentColor" stroke-width="3.4" stroke-linecap="round" '
                'stroke-linejoin="round" aria-hidden="true">'
                '<path d="M4.5 12.8l4.8 4.7L19.5 6.8"/></svg>',
    "error": '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" '
             'stroke="currentColor" stroke-width="3.2" stroke-linecap="round" '
             'aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>',
    "pending": "",
}


def workflow_stepper_html(steps: list[dict], overall: float = 0.0) -> str:
    """HTML für den Stations-Stepper.

    steps: [{nr, title, status(pending|running|complete|error), meta}] —
    overall (0..1) füllt die Schiene zwischen den Knoten proportional.
    """
    n = len(steps)
    fill = max(0.0, min(1.0, (overall * n - 0.5) / (n - 1))) if n > 1 else 0.0
    parts = [
        f'<div class="gld-stepper" style="--gld-fill:{fill * 100:.1f}%" '
        f'role="list" aria-label="Workflow-Fortschritt">',
        '<div class="gld-rail" aria-hidden="true"><i></i></div>',
    ]
    for s in steps:
        status = s.get("status", "pending")
        mark = _NODE_MARK.get(status) or str(s["nr"])
        title = html.escape(str(s["title"]))
        meta = html.escape(str(s.get("meta") or ""))
        parts.append(
            f'<div class="gld-step gld-step--{status}" role="listitem">'
            f'<div class="gld-node" role="img" aria-label="Station {s["nr"]}">{mark}</div>'
            f'<div class="gld-step-body">'
            f'<div class="gld-step-title">{title}</div>'
            f'<div class="gld-step-meta">{meta}</div></div></div>')
    parts.append("</div>")
    return "".join(parts)


def zeige_stepper(steps: list[dict], overall: float = 0.0) -> None:
    st.markdown(workflow_stepper_html(steps, overall), unsafe_allow_html=True)


def lauf_strip_html(status: str, haupttext: str, nebenzeile: str = "",
                    sekunden: int | None = None) -> str:
    """HTML der Lauf-Zentrale: pulsierender Punkt + Text + Stoppuhr."""
    uhr = (f'<span class="gld-clock">{sekunden // 60}:{sekunden % 60:02d}</span>'
           if sekunden is not None else "")
    neben = f"<small>{html.escape(nebenzeile)}</small>" if nebenzeile else ""
    return (f'<div class="gld-strip">'
            f'<span class="gld-dot gld-dot--{status}" aria-hidden="true"></span>'
            f'<span class="gld-strip__text"><b>{html.escape(haupttext)}</b>'
            f"{neben}</span>"
            f'<span class="gld-strip__side">{uhr}</span></div>')


def agenten_baum_html(status: dict[str, str] | None = None) -> str:
    """Der Wochenlauf als Baum (SVG): Quellen → Verdichtung → KI-Fusion →
    Ergebnisse. `status` mappt Knoten-Schlüssel auf pending|running|complete
    — läuft ein Knoten, pulsiert er gold; im Ruhezustand neutral."""
    status = status or {}
    # (schluessel, x, y, titel, unterzeile, breite, nutzt_ki)
    knoten = [
        ("kurse",     70,  30, "Kurse", "MT5 · D1/H4/H1", 110, False),
        ("kalender", 210,  30, "Kalender", "5 Quellen + Termine", 120, False),
        ("gvz",      350,  30, "Marktdaten", "GVZ · FRED · CFTC · GLD", 130, False),
        ("news",     500,  30, "News", "8 RSS-Feeds · Delta", 105, False),
        ("community",640,  30, "Community", "TV · Analysten · Kitco", 125, False),
        ("statistik",180, 160, "Statistik-Engine", "Klima · HAR · Richtung", 140, False),
        ("news_destill", 430, 160, "KI: News-Treiber", "glm-5.3-flash · belegt", 155, True),
        ("comm_destill", 615, 160, "KI: Community", "glm-5.3-flash · Stimmung", 165, True),
        ("fusion",   370, 270, "KI-Fusion", "glm-5.3 · ±10-pp-Band", 130, True),
        ("matrix",   150, 350, "Wochenmatrix", "Dashboard + REST", 120, False),
        ("pdf",      370, 350, "PDF-Bericht", "Wochenanalyse", 115, False),
        ("export",   590, 350, "MT5-Export", "CSV für EAs", 110, False),
    ]
    kanten = [("kurse", "statistik"), ("kalender", "statistik"),
              ("gvz", "statistik"), ("news", "news_destill"),
              ("community", "comm_destill"), ("statistik", "fusion"),
              ("news_destill", "fusion"), ("comm_destill", "fusion"),
              ("fusion", "matrix"), ("fusion", "pdf"), ("fusion", "export")]
    pos = {k: (x, y, b) for k, x, y, _, _, b, _ in knoten}
    hoehe_k = 46

    farben = {"pending": ("#243349", "#94A3B8", "#33415588"),
              "running": ("#4a3b14", "#F5D67B", "#E8B84B"),
              "complete": ("#12331f", "#6EE7B7", "#10B98188")}
    teile = [
        # Feste Maximalbreite (statt width:100%): Der Baum zoomt damit wie
        # normaler Text mit dem Browser-Zoom statt mit der Spaltenbreite zu
        # skalieren — Rauszoomen verkleinert auch die Knoten-Schrift.
        '<svg viewBox="0 0 820 420" style="width:100%;max-width:820px;'
        'height:auto;display:block;margin:0 auto" '
        'role="img" aria-label="Wochenlauf-Baum">',
        '<style>.gk-run{animation:gk-puls 1.2s ease-in-out infinite}'
        '@keyframes gk-puls{0%,100%{opacity:1}50%{opacity:.45}}'
        '@media(prefers-reduced-motion:reduce){.gk-run{animation:none}}</style>']
    for a, b in kanten:
        ax, ay, ab = pos[a]
        bx, by, bb = pos[b]
        x1, y1 = ax + ab / 2, ay + hoehe_k
        x2, y2 = bx + bb / 2, by
        aktiv = status.get(a) in ("running", "complete") and \
            status.get(b) in ("running", "complete")
        farbe = "#E8B84B" if status.get(a) == "running" else (
            "#10B98188" if aktiv else "#3b4a63")
        teile.append(f'<path d="M{x1} {y1} C{x1} {y1 + 40}, {x2} {y2 - 40}, '
                     f'{x2} {y2}" fill="none" stroke="{farbe}" '
                     f'stroke-width="{2.2 if status.get(a) == "running" else 1.4}" />')
    for schluessel, x, y, titel, unter, breite, nutzt_ki in knoten:
        zustand = status.get(schluessel, "pending")
        fuellung, textfarbe, rand = farben.get(zustand, farben["pending"])
        klasse = ' class="gk-run"' if zustand == "running" else ""
        badge = ""
        if nutzt_ki:
            # Violettes KI-Badge oben rechts: hier arbeitet ein Sprachmodell
            bx = x + breite - 34
            badge = (f'<rect x="{bx}" y="{y - 8}" rx="7" width="30" height="16" '
                     f'fill="#5d4ea6" stroke="#9d8fe0" stroke-width="1"/>'
                     f'<text x="{bx + 15}" y="{y + 3.5}" text-anchor="middle" '
                     f'font-size="9.5" font-weight="800" fill="#e6e0ff">KI</text>')
        teile.append(
            f'<g{klasse}><rect x="{x}" y="{y}" rx="10" width="{breite}" '
            f'height="{hoehe_k}" fill="{fuellung}" stroke="{rand}" '
            f'stroke-width="1.4"/>'
            f'<text x="{x + breite / 2}" y="{y + 20}" text-anchor="middle" '
            f'font-size="13" font-weight="700" fill="{textfarbe}">'
            f'{html.escape(titel)}</text>'
            f'<text x="{x + breite / 2}" y="{y + 36}" text-anchor="middle" '
            f'font-size="9.5" fill="#94A3B8">{html.escape(unter)}</text>'
            f'{badge}</g>')
    teile.append("</svg>")
    return "".join(teile)


def zeige_agenten_baum(status: dict[str, str] | None = None) -> None:
    st.markdown(agenten_baum_html(status), unsafe_allow_html=True)


def bewegungs_farbe(score: float) -> str:
    """Farbinterpolation grün (0, ruhig) → gelb (0,5) → rot (1, bewegt).
    Hex-Interpolation in 2 Segmenten."""
    score = max(0.0, min(1.0, score))

    def _mix(a, b, t):
        return "#%02x%02x%02x" % tuple(
            int(round(x + (y - x) * t)) for x, y in zip(a, b))
    gruen, gelb, rot = (16, 185, 129), (232, 184, 75), (244, 63, 94)
    if score <= 0.5:
        return _mix(gruen, gelb, score * 2)
    return _mix(gelb, rot, (score - 0.5) * 2)


def kpi_karte_html(titel: str, wert: str, score: float | None,
                   nebenzeile: str = "") -> str:
    """KPI-Karte im KiScanner-Look mit Bewegungs-Skala: farbiger Balken
    (Breite = score, grün→rot) statt nackter Zahl ohne Einordnung."""
    farbe = bewegungs_farbe(score) if score is not None else "#94A3B8"
    balken = (f'<div class="gld-kpi-balken"><i style="width:{score * 100:.0f}%;'
              f'background:{farbe}"></i></div>' if score is not None else "")
    neben = (f'<div class="gld-kpi-neben">{html.escape(nebenzeile)}</div>'
             if nebenzeile else "")
    return (f'<div class="gld-kpi"><div class="gld-kpi-label">'
            f'{html.escape(titel)}</div>'
            f'<div class="gld-kpi-wert" style="color:{farbe}">{html.escape(wert)}</div>'
            f'{balken}{neben}</div>')


def kpi_zeile_html(karten: list[str]) -> str:
    return (f'<div class="gld-kpi-zeile">{"".join(karten)}</div>')


def status_feed(zeilen: list[str]) -> None:
    """Kompakter Status-Feed (letzte Meldungen) im KiScanner-Look."""
    if not zeilen:
        zeilen = ["Noch keine Läufe."]
    html_zeilen = "".join(
        f'<div class="gld-feed__line">{html.escape(z)}</div>' for z in zeilen)
    st.markdown(f'<div class="gld-feed">{html_zeilen}</div>', unsafe_allow_html=True)


def section_header(title: str, description: str = "") -> None:
    st.subheader(title, width="content")
    if description:
        st.caption(description)
