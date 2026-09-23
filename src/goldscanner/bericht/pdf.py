"""Wochen-PDF (S4): die erklärte Matrix als Bericht.

Deterministische renderer — das LLM liefert nur Textbausteine, alle Zahlen
kommen aus der Matrix. Unicode-Schriften (Vera, liegt reportlab bei) für
Umlaute. Fehler beim Rendern werfen PdfFehler — der Wochenlauf läuft dann
ohne PDF weiter.
"""
from __future__ import annotations

import html
import threading
from datetime import datetime
from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .. import config

DISCLAIMER = ("Forschungs- und Projektionswerkzeug. Keine Anlageberatung. "
              "Prognosen sind kalibrierte Wahrscheinlichkeiten, keine Garantien. "
              "Engine rechnet, LLM zitiert: alle Kernwerte deterministisch berechnet.")

_FONT = "GLD-Vera"
_FONT_BOLD = "GLD-Vera-Bold"
_FONTS_REGISTERED = False
_FONT_LOCK = threading.Lock()

_GOLD = colors.HexColor("#B8860B")
_DUNKEL = colors.HexColor("#1A2432")
_HELL = colors.HexColor("#F5F0E1")


class PdfFehler(RuntimeError):
    """PDF konnte nicht gebaut werden."""


def _register_fonts() -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    with _FONT_LOCK:
        if _FONTS_REGISTERED:
            return
        font_dir = Path(reportlab.__file__).resolve().parent / "fonts"
        try:
            pdfmetrics.registerFont(TTFont(_FONT, str(font_dir / "Vera.ttf")))
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(font_dir / "VeraBd.ttf")))
        except Exception as exc:
            raise PdfFehler(f"Unicode-Schrift fehlt: {exc}") from exc
        _FONTS_REGISTERED = True


def _styles() -> dict:
    ss = getSampleStyleSheet()
    ss["Normal"].fontName = _FONT
    return {
        "titel": ParagraphStyle("titel", parent=ss["Title"], fontName=_FONT_BOLD,
                                fontSize=20, textColor=_DUNKEL, spaceAfter=2),
        "unter": ParagraphStyle("unter", parent=ss["Normal"], fontSize=9,
                                textColor=colors.HexColor("#5A6B80"),
                                spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=ss["Heading2"], fontName=_FONT_BOLD,
                             fontSize=13, textColor=_GOLD, spaceBefore=10,
                             spaceAfter=4),
        "text": ParagraphStyle("text", parent=ss["Normal"], fontSize=9.5,
                               leading=13),
        "klein": ParagraphStyle("klein", parent=ss["Normal"], fontSize=8,
                                textColor=colors.HexColor("#7A8AA0")),
    }


def _p(text: str) -> str:
    return html.escape(str(text or "")).replace("\n", "<br/>")


def baue_wochen_pdf(matrix: dict, ziel: Path | None = None) -> Path:
    """Matrix (inkl. llm-Fusion) → PDF. Rückgabe: Dateipfad."""
    _register_fonts()
    llm = matrix.get("llm") or {}
    fusion_je_tag = {t["datum"]: t for t in llm.get("tage", [])}
    ziel = ziel or (config.REPORTS_DIR /
                    f"wochenbericht_{matrix['woche']}.pdf")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    st = _styles()

    doc = SimpleDocTemplate(
        str(ziel), pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f"MqlGoldscanner Wochenanalyse {matrix['woche']}",
        author="MqlGoldscanner")
    story: list = []

    story.append(Paragraph("MqlGoldscanner — Wochenanalyse Gold", st["titel"]))
    kw = datetime.fromisoformat(matrix["woche"]).isocalendar()
    story.append(Paragraph(
        f"Woche {matrix['woche']} bis {matrix['bis']} (KW {kw[1]}/<br/>"
        f"Modell: {_p(matrix.get('modell', '?'))} · "
        f"Basisrate: {matrix['basis']['p_global'] * 100:.1f} % · "
        f"erzeugt {matrix['erzeugt_am'][:16].replace('T', ' ')} UTC",
        st["unter"]))

    # Kopfzeilen-Tabelle je Tag
    kopf = [["Tag", "P finale", "Basis", "Klima", "Schwelle $", "Q10-Q90 $",
             "KI-Richt.", "P(hoch)", "Events"]]
    for t in matrix["tage"]:
        f = fusion_je_tag.get(t["datum"], {})
        basis = f.get("basis_pct") if f else (
            round(t["p_stat"] * 100, 1) if t.get("p_stat") is not None else
            (round(t["p_klima"] * 100, 1) if t.get("p_klima") is not None else None))
        p_finale = f.get("p_finale_pct", basis)
        r = t.get("richtung") or {}
        kopf.append([
            f"{t['wochentag']} {t['datum'][8:10]}.{t['datum'][5:7]}.",
            f"{p_finale:.0f} %" if p_finale is not None else "–",
            f"{basis:.0f} %" if basis is not None else "–",
            f"{t['p_klima'] * 100:.0f} %" if t.get("p_klima") is not None else "–",
            f"{t['schwelle_usd']:.0f}" if t.get("schwelle_usd") else "–",
            (f"{t['q10_usd']:.0f}–{t['q90_usd']:.0f}"
             if t.get("q10_usd") is not None and t.get("q90_usd") is not None else "–"),
            (f.get("richtung") or "–") if f else "–",
            f"{r.get('p_hoch') * 100:.0f} %" if r.get("p_hoch") is not None else "–",
            str(t.get("events_count", 0)),
        ])
    tabelle = Table(kopf, hAlign="LEFT")
    tabelle.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTNAME", (0, 1), (-1, -1), _FONT),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), _DUNKEL),
        ("TEXTCOLOR", (0, 0), (-1, 0), _HELL),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#F7F4EC")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9C4B4")),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(tabelle)

    if llm.get("zusammenfassung"):
        story.append(Paragraph("Zusammenfassung (Analytiker-KI)", st["h2"]))
        story.append(Paragraph(_p(llm["zusammenfassung"]), st["text"]))

    story.append(Paragraph("Tage im Detail", st["h2"]))
    for t in matrix["tage"]:
        f = fusion_je_tag.get(t["datum"])
        zeilen = [Paragraph(
            f"<b>{t['wochentag']} {t['datum']}</b> · "
            f"P finale {f.get('p_finale_pct', '?')!s} % "
            f"(Basis {f.get('basis_pct', '?')!s} %, Δ {f.get('abweichung_pp', 0):+} pp) · "
            f"Richtung {f.get('richtung', 'neutral')} ({f.get('konfidenz', 'niedrig')})",
            st["text"])]
        if f and f.get("begruendung"):
            zeilen.append(Paragraph(f"Begründung: {_p(f['begruendung'])}",
                                    ParagraphStyle("b", parent=st["text"],
                                                   leftIndent=8, fontSize=8.5,
                                                   textColor=colors.HexColor("#44505F"))))
        for tr in (f or {}).get("treiber", []):
            zeilen.append(Paragraph(
                f"· {tr['name']} ({tr['quelle']}): {tr['einfluss_pp']:+.1f} pp "
                f"{tr['richtung']}", st["klein"]))
        if t.get("top_events"):
            events = "; ".join(f"{e['zeit']} {e['titel']}" for e in t["top_events"][:3])
            zeilen.append(Paragraph(f"Events: {_p(events)}", st["klein"]))
        story.extend(zeilen)
        story.append(Spacer(1, 3))

    if llm.get("risiken"):
        story.append(Paragraph("Risiken", st["h2"]))
        for r in llm["risiken"]:
            story.append(Paragraph(f"· {_p(r)}", st["text"]))
    marktlage = matrix.get("marktlage") or {}
    if marktlage.get("flags"):
        story.append(Paragraph("Marktlage (S5 — Quant-Feeds)", st["h2"]))
        for f in marktlage["flags"]:
            story.append(Paragraph(f"· {_p(f)}", st["text"]))
    if llm.get("verstoesse"):
        story.append(Paragraph(
            f"Band-Verstöße (automatisch abgewiesen): {len(llm['verstoesse'])}",
            st["h2"]))
        for v in llm["verstoesse"][:6]:
            story.append(Paragraph(f"· {_p(v)}", st["klein"]))

    story.append(Spacer(1, 8))
    story.append(Paragraph(_p(DISCLAIMER), st["klein"]))

    try:
        doc.build(story)
    except Exception as exc:
        raise PdfFehler(f"PDF-Bau fehlgeschlagen: {type(exc).__name__}: {exc}") from exc
    return ziel
