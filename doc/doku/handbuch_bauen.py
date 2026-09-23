# -*- coding: utf-8 -*-
"""Baut das MqlGoldscanner-Handbuch (Laien-Erklärung der Prognosen) als PDF.
Route: pdf-Skill Report (ReportLab), Palette aus palette.cascade,
Grafiken aus doc/doku/grafiken (echte Daten)."""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

PDF_SKILL_DIR = r"C:\Users\tnickel\.zcode\cli\plugins\cache\zcode-plugins-official\pdf\0.1.7\skills\pdf"
_scripts = os.path.join(PDF_SKILL_DIR, "scripts")
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (CondPageBreak, Image, KeepTogether, PageBreak,
                                Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)
from reportlab.platypus.tableofcontents import TableOfContents
from PIL import Image as PILImage

# ━━ Color Palette (palette.cascade, unverändert übernommen) ━━
PAGE_BG = colors.HexColor('#f1f0ef')
SECTION_BG = colors.HexColor('#efefed')
CARD_BG = colors.HexColor('#eae9e4')
TABLE_STRIPE = colors.HexColor('#f0f0ed')
HEADER_FILL = colors.HexColor('#695f3f')
COVER_BLOCK = colors.HexColor('#6f6851')
BORDER = colors.HexColor('#c6bfac')
ICON = colors.HexColor('#a69151')
ACCENT = colors.HexColor('#5b31d7')
ACCENT_2 = colors.HexColor('#4cd08e')
TEXT_PRIMARY = colors.HexColor('#171715')
TEXT_MUTED = colors.HexColor('#78766f')
SEM_SUCCESS = colors.HexColor('#3b8554')
SEM_WARNING = colors.HexColor('#ac8841')
SEM_ERROR = colors.HexColor('#944e47')
SEM_INFO = colors.HexColor('#4a6c8d')

HIER = Path(__file__).resolve().parent
GRAFIKEN = HIER / "grafiken"
BODY_PDF = HIER / "handbuch_body.pdf"

# ── Fonts (lokal vorhanden: Calibri-Familie + DejaVu für Symbole) ──
pdfmetrics.registerFont(TTFont("Calibri", r"C:\Windows\Fonts\calibri.ttf"))
pdfmetrics.registerFont(TTFont("Calibri-Bold", r"C:\Windows\Fonts\calibrib.ttf"))
pdfmetrics.registerFont(TTFont("Calibri-Italic", r"C:\Windows\Fonts\calibrii.ttf"))
pdfmetrics.registerFont(TTFont("DejaVuSans", r"C:\Windows\Fonts\DejaVuSans.ttf"))
registerFontFamily("Calibri", normal="Calibri", bold="Calibri-Bold",
                   italic="Calibri-Italic")
registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans")

# ── Styles ──
BODY = ParagraphStyle("Body", fontName="Calibri", fontSize=10.5, leading=16,
                      alignment=TA_JUSTIFY, spaceAfter=8, textColor=TEXT_PRIMARY)
BODY_LEFT = ParagraphStyle("BodyLeft", parent=BODY, alignment=TA_LEFT)
H1 = ParagraphStyle("H1x", fontName="Calibri-Bold", fontSize=19, leading=24,
                    textColor=TEXT_PRIMARY, spaceBefore=16, spaceAfter=4)
H2 = ParagraphStyle("H2x", fontName="Calibri-Bold", fontSize=13.5, leading=18,
                    textColor=HEADER_FILL, spaceBefore=12, spaceAfter=6)
KICKER = ParagraphStyle("Kicker", fontName="Calibri", fontSize=9, leading=12,
                        textColor=TEXT_MUTED, spaceAfter=2)
CAPTION = ParagraphStyle("Caption", fontName="Calibri-Italic", fontSize=8.5,
                         leading=11.5, alignment=TA_CENTER, textColor=TEXT_MUTED,
                         spaceBefore=3, spaceAfter=6)
BULLET = ParagraphStyle("Bullet", parent=BODY_LEFT, leftIndent=14,
                        bulletIndent=2, spaceAfter=4)
QUOTE = ParagraphStyle("Quote", parent=BODY_LEFT, fontName="Calibri-Italic",
                       leftIndent=24, textColor=TEXT_PRIMARY, borderPadding=6,
                       spaceBefore=6, spaceAfter=10)
TAB_KOPF = ParagraphStyle("TabKopf", fontName="Calibri-Bold", fontSize=9.5,
                          leading=12.5, textColor=colors.white, alignment=TA_LEFT)
TAB_ZELLE = ParagraphStyle("TabZelle", fontName="Calibri", fontSize=9.5,
                           leading=12.5, textColor=TEXT_PRIMARY, alignment=TA_LEFT)
TAB_ZELLE_KURZ = ParagraphStyle("TabZelleKurz", parent=TAB_ZELLE, alignment=TA_CENTER)
STAT_GROSS = ParagraphStyle("StatGross", fontName="Calibri-Bold", fontSize=20,
                            leading=24, textColor=HEADER_FILL, alignment=TA_CENTER)
STAT_LABEL = ParagraphStyle("StatLabel", fontName="Calibri", fontSize=8.5,
                            leading=11, textColor=TEXT_MUTED, alignment=TA_CENTER)
TOC_H1 = ParagraphStyle("TOC1", fontName="Calibri-Bold", fontSize=10.5,
                        leading=14, leftIndent=6, textColor=TEXT_PRIMARY,
                        spaceBefore=3)
TOC_H2 = ParagraphStyle("TOC2", fontName="Calibri", fontSize=9, leading=12,
                        leftIndent=22, textColor=TEXT_MUTED)

VERFUEGBARE_BREITE = A4[0] - 2 * 2 * cm      # 2 cm Ränder
H1_VERWAIST = (A4[1] - 4 * cm) * 0.16


class TocVorlage(SimpleDocTemplate):
    def afterFlowable(self, flowable):
        # Nur Kapitelebene (H1) ins Inhaltsverzeichnis — H2-Unterpunkte
        # würden das TOC auf zwei Seiten ziehen und Seite 3 veröden lassen.
        if getattr(flowable, "bookmark_level", None) == 0:
            self.notify("TOCEntry", (0, flowable.bookmark_text, self.page,
                                     flowable.bookmark_key))


def ueberschrift(text, level=0):
    schluessel = "h_" + hashlib.md5(text.encode()).hexdigest()[:8]
    stil = H1 if level == 0 else H2
    p = Paragraph(f'<a name="{schluessel}"/><b>{text}</b>', stil)
    p.bookmark_name = text
    p.bookmark_level = level
    p.bookmark_text = text
    p.bookmark_key = schluessel
    return p


def _deutsch_haerter(text: str) -> str:
    """Geschütztes Leerzeichen vor Gedankenstrichen: verhindert, dass „—"
    an einen Zeilenanfang rutscht (deutsche Typografie)."""
    return text.replace(" — ", " — ")


def absatz(text, stil=BODY):
    return Paragraph(_deutsch_haerter(text), stil)


def stichpunkte(*zeilen):
    return [Paragraph(_deutsch_haerter(f"• {z}"), BULLET) for z in zeilen]


def bild(name, breite_max=None, hoehen_max=None, unterschrift=""):
    pfad = GRAFIKEN / name
    pil = PILImage.open(pfad)
    b, h = pil.size
    max_b = breite_max or VERFUEGBARE_BREITE
    max_h = hoehen_max or (A4[1] * 0.36)
    faktor = min(max_b / b, max_h / h, 1.0 if b < max_b else max_b / b)
    faktor = min(max_b / b, max_h / h)
    img = Image(str(pfad), width=b * faktor, height=h * faktor)
    img.hAlign = "CENTER"
    if unterschrift:
        return [Spacer(1, 6), KeepTogether([img, Paragraph(unterschrift, CAPTION)]),
                Spacer(1, 4)]
    return [Spacer(1, 6), img, Spacer(1, 4)]


def kallout(wert, label, breite=5.6):
    t = Table([[Paragraph(f"<b>{wert}</b>", STAT_GROSS)],
               [Paragraph(label, STAT_LABEL)]], colWidths=[breite * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CARD_BG),
        ("BOX", (0, 0), (-1, -1), 1, ICON),
        ("TOPPADDING", (0, 0), (-1, 0), 9), ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    t.hAlign = "CENTER"
    return t


def kallout_reihe(*paare):
    """Eine Tabelle mit n Spalten: Wert oben (fett, groß), Label unten —
    je Spalte eine Box. Eine Tabelle statt verschachtelter: keine
    Zentrierungs-Warnungen, gleiche Optik."""
    n = len(paare)
    spaltenbreite = VERFUEGBARE_BREITE / n - 8
    werte = [Paragraph(f"<b>{w}</b>", STAT_GROSS) for w, _ in paare]
    labels = [Paragraph(l, STAT_LABEL) for _, l in paare]
    t = Table([werte, labels], colWidths=[spaltenbreite] * n, hAlign="CENTER")
    stil = [("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, 0), 9),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 9),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8)]
    for spalte in range(n):
        stil += [("BACKGROUND", (spalte, 0), (spalte, 1), CARD_BG),
                 ("BOX", (spalte, 0), (spalte, 1), 1, ICON)]
    t.setStyle(TableStyle(stil))
    return t


def tabelle(kopf, zeilen, verhaeltnisse, kurz_spalten=()):
    daten = [[Paragraph(f"<b>{k}</b>", TAB_KOPF) for k in kopf]]
    for z in zeilen:
        daten.append([
            Paragraph(zelle, TAB_ZELLE_KURZ if i in kurz_spalten else TAB_ZELLE)
            for i, zelle in enumerate(z)])
    spalten = [v * VERFUEGBARE_BREITE for v in verhaeltnisse]
    t = Table(daten, colWidths=spalten, hAlign="CENTER", repeatRows=1)
    stil = [("BACKGROUND", (0, 0), (-1, 0), HEADER_FILL),
            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5)]
    for i in range(1, len(daten)):
        stil.append(("BACKGROUND", (0, i), (-1, i),
                     colors.white if i % 2 else TABLE_STRIPE))
    t.setStyle(TableStyle(stil))
    return t


def unterkap(titel):
    """H2 mit Verwaisten-Schutz: bricht um, wenn weniger als ~4 cm Rest."""
    from reportlab.platypus import CondPageBreak
    return [CondPageBreak(110), ueberschrift(titel, 1)]


def kapitel(story, titel):
    story.append(CondPageBreak(H1_VERWAIST))
    story.append(ueberschrift(titel, 0))
    story.append(_linie())


def _linie():
    from reportlab.platypus import HRFlowable
    return HRFlowable(width="100%", thickness=1.1, color=ICON, spaceBefore=0,
                      spaceAfter=10)


# ════════════════════════════════════════════════════════════════════════
story = []

# ── Inhaltsverzeichnis ──
story.append(Paragraph("<b>Inhaltsverzeichnis</b>",
                       ParagraphStyle("TOCTitel", parent=H1, spaceBefore=0)))
story.append(_linie())
toc = TableOfContents()
toc.levelStyles = [TOC_H1, TOC_H2]
story.append(toc)
story.append(PageBreak())

# ══ 1. Worum es geht ════════════════════════════════════════════════════
kapitel(story, "1. Worum es geht — und worum nicht")
story.append(absatz(
    "Der MqlGoldscanner beantwortet eine einzige, präzise Frage: "
    "<b>Mit welcher Wahrscheinlichkeit bewegt sich der Goldpreis an einem "
    "bestimmten Wochentag überdurchschnittlich stark?</b> Für jeden Tag der "
    "kommenden Woche erhalten Sie eine Zahl — zum Beispiel „Mittwoch: 10 %“ — "
    "plus eine erwartete Spannbreite (Range) in US-Dollar und eine Richtungstendenz."))
story.append(absatz(
    "Dieses Handbuch erklärt vollständig und ohne Vorwissen, wie diese Zahlen "
    "entstehen: welche Daten wir verwenden, welche mathematischen Modelle dahinter "
    "stehen, wie wir ehrlich überprüfen, dass die Prognosen besser sind als Raten — "
    "und wo die Grenzen liegen. Wer die Kapitel 3 bis 7 gelesen hat, kann jede "
    "Zahl der Wochenmatrix vom Rohkurs bis zum Endergebnis selbst nachrechnen."))
story.append(absatz(
    "Ebenso wichtig ist, was der Scanner <b>nicht</b> tut: Er gibt keine "
    "Kauf- oder Verkaufssignale, keine Kursziele und keine Anlageberatung. Er "
    "schätzt Wahrscheinlichkeiten — mehr nicht, und genau das macht ihn "
    "verlässlich einordenbar."))
story.append(kallout_reihe(
    ("≈ 40 %", "Basisrate: Anteil der Tage mit\rüberdurchschnittlicher Bewegung\r(17 Jahre Brokerdaten)"),
    ("+0,067", "Brier-Skill-Score des Modells\rgegenüber der Basisrate\r(Tor T3 bestanden)"),
    ("4.078", "Testtage im ehrlichen\rWalk-Forward-Verfahren\r(ohne Blick in die Zukunft)")))
story.append(Spacer(1, 6))

# ══ 2. Die Daten ════════════════════════════════════════════════════════
kapitel(story, "2. Die Daten: Womit der Scanner arbeitet")
story.append(absatz(
    "Jede Prognose ist nur so gut wie ihre Daten. Der Scanner bezieht seine "
    "Informationen ausschließlich aus offiziellen, maschinenlesbaren Quellen — "
    "keine gesperrten Webseiten, keine Browser-Vortäuschung, kein Kratzen von "
    "Seiten, die das verbieten. Alles wird lokal in einer Datenbank gespeichert "
    "und archiviert; jedes Modell rechnet nur mit dem, was bereits gespeichert "
    "ist („Der Analytiker liest nie live“)."))
story.extend(bild("fluss.png", unterschrift=
    "Abbildung 1: Der Weg von den Rohdaten bis zur verifizierten Prognose. "
    "Links der gestrichelten Trennung rechnet reiner Code — jede Zahl ist "
    "nachrechenbar; rechts erklärt die KI und verschiebt im engen Band."))
story.extend(unterkap("2.1 Die Quellen im Überblick"))
story.append(tabelle(
    ["Daten", "Quelle", "Umfang (Stand 23.09.2026)", "Wofür?"],
    [["Gold-Kurse (XAUUSD)", "MetaTrader-5-Terminal des Brokers (Tickmill), "
      "nur lesend", "4.354 Tageskerzen ≈ 17 Jahre; zusätzlich Stunden-/4h-Kurse",
      "Alles Statistische — Basis aller Modelle"],
     ["Wirtschaftskalender", "ForexFactory, US-Arbeitsamt (BLS), "
      "Wirtschaftsanalyse (BEA), Federal Reserve, US-Treasury",
      "2.513 Termine, dedupliziert über 6 Quellen",
      "Ereignis-Treiber, Tagesansicht, NFP-/FOMC-Merkmale"],
     ["Regeltermine", "Rechnerisch (kein Abruf): Gold-Future-Fälligkeiten, "
      "Optionsverfall, Feiertage, Zeitumstellung", "automatisch für jede Woche",
      "Gold-spezifische Termin-Merkmale"],
     ["Implizite Volatilität", "Cboe GVZ-Index (erwartete Gold-Schwankung "
      "aus Optionen)", "4.276 Tageswerte seit 2009",
      "Frühindikator für kommende Unruhe"],
     ["Zinsen & Dollar", "FRED (St. Louis Fed): Realzins, Inflationserwartung, "
      "Dollar-Index, VIX", "je 5.000–16.000 Tageswerte",
      "Marktlage-Signale"],
     ["Positionierung", "CFTC Commitments-of-Traders: Wetten von Fonds; "
      "GLD-ETF-Bestände in Tonnen", "1.058 Wochen / 5.493 Tage",
      "Crowding-Warnungen, Marktlage"],
     ["Nachrichten", "8 RSS-Feeds (u. a. FXStreet, Google News deutsch/"
      "englisch, FXEmpire)", "273 gespeicherte Artikel (wächst täglich)",
      "Rohstoff für die KI-Destillation"],
     ["Community", "TradingView-Ideen, Analysten-Sentiment, Kitco-Umfrage",
      "30 Ideen pro Abruf", "Stimmung, Kontra-Indikator"]],
    [0.16, 0.30, 0.27, 0.27]))
story.append(Paragraph("Tabelle 1: Datenquellen des Scanners", CAPTION))
story.append(absatz(
    "Ein Prinzip zieht sich durch alles: <b>Point-in-time</b> („zum damaligen "
    "Zeitpunkt“). Wenn der Scanner für einen historischen Tag eine Übung "
    "wiederholt, darf er nur Informationen benutzen, die an diesem Tag wirklich "
    "schon verfügbar waren. Verzögert veröffentlichte Daten (z. B. die "
    "Fondspositionen der CFTC erscheinen erst drei Tage nach Stichtag) werden "
    "entsprechend später eingespeist. So verhindern wir „Blick in die Zukunft“ "
    "(Look-ahead) — die häufigste Quelle schöner, aber nutzloser Backtests."))

# ══ 3. Bewegungstag ═════════════════════════════════════════════════════
kapitel(story, "3. Die zentrale Idee: Was ist ein „Bewegungstag“?")
story.append(absatz(
    "Bevor man Wahrscheinlichkeiten berechnen kann, muss man festlegen, was "
    "überhaupt als „starker Tag“ zählt. Unsere Definition ist bewusst "
    "einfach und überprüfbar: Ein Bewegungstag ist ein Tag, an dem die "
    "tatsächliche Handelsspanne (True Range) größer ist als das, was an diesem "
    "Wochentag in den letzten 13 Wochen üblich war."))
story.extend(unterkap("3.1 Die True Range — ehrlich messen, was sich bewegt hat"))
story.append(absatz(
    "Die Spanne eines Tages ist nicht einfach „Hoch minus Tief“: Wenn der Kurs "
    "heute über dem gestrigen Schluss eröffnet, beginnt die Bewegung eigentlich "
    "schon höher. Die True Range (wörtlich „wahre Spanne“) berücksichtigt das. "
    "Sie ist die größte der drei Distanzen: (a) Hoch minus Tief, "
    "(b) Hoch minus Schlusskurs von gestern, (c) Tief minus Schlusskurs von "
    "gestern. Diese Größe stammt aus dem klassischen Börsenhandwerk "
    "(J. Welles Wilder, 1978) und ist bis heute der Standard für "
    "Tagesvolatilität."))
story.extend(bild("kerze.png", unterschrift=
    "Abbildung 2: Anatomie einer Tageskerze. Die True Range misst die gesamte "
    "Bewegung — einschließlich der Lücke zum Vortagesschluss."))
story.extend(unterkap("3.2 Die Schwelle B — was ist „normal“ für diesen Wochentag?"))
story.append(absatz(
    "„Üblich“ wird für jeden Wochentag separat gemessen: Der Scanner mittelt "
    "die True Range der letzten 13 Montage (bzw. Dienstage, …) und legt diese "
    "Schwelle B auf den kommenden Montag. Zwei Feinheiten machen die Messung "
    "robust: Erstens rechnen wir mit der <b>relativen</b> Range (Range ÷ "
    "Kurs), denn bei einem Goldpreis von 4.300 USD bedeuten 40 USD etwas ganz "
    "anderes als bei 1.800 USD. Zweitens vergleichen wir nur mit der "
    "Vergangenheit — die Schwelle für nächsten Mittwoch kennt keinen einzigen "
    "Mittwoch der Zukunft."))
story.extend(bild("verteilung.png", unterschrift=
    "Abbildung 3: Die Verteilung von rund 4.200 echten Tages-Ranges. Die "
    "meisten Tage liegen links der Schwelle — Bewegungstage (rechts der "
    "Linie) sind die Minderheit. Genau diese Minderheit interessiert uns."))
story.append(absatz(
    "Abbildung 3 zeigt, warum die Frage überhaupt spannend ist: Die rechte "
    "Ränder-Fläche — die Bewegungstage — macht historisch nur rund 40 % der "
    "Tage aus. Wüsste man vorab, welche Tage dazugehören, hätte man einen "
    "echten Informationsvorsprung. Genau das versucht das Modell."))

# ══ 4. Klimatologie ═════════════════════════════════════════════════════
kapitel(story, "4. Die Klimatologie: Was die Geschichte allein schon sagt")
story.append(absatz(
    "Der Name ist Programm: Wie die Klimakunde beim Wetter betrachtet die "
    "Klimatologie lange Messreihen und sagt, was „normal“ ist — bevor irgendein "
    "schlaues Modell anfängt. Sie ist gleichzeitig unsere erste Prognose und "
    "unsere Messlatte: Ein Modell darf sich nur dann nützlich nennen, wenn es "
    "die Klimatologie schlägt."))
story.extend(bild("klima.png", unterschrift=
    "Abbildung 4: Anteil der Bewegungstage je Wochentag über 17 Jahre. Die "
    "Unterschiede sind klein, aber stabil messbar — der Mittwoch war "
    "historisch der bewegteste Tag."))
story.append(absatz(
    "Warum Mittelung über Wochentage? Weilm Saisonalität im Goldmarkt real "
    "ist: Wochenmitte häufen sich wichtige US-Daten, freitags fließen "
    "Gewinne ab. Die Klimatologie nutzt das, ohne irgendetwas zu behaupten, "
    "das nicht in den Daten stünde.".replace("weilm", "weil")))
story.extend(unterkap("4.1 Shrinkage — die Kunst, bei wenig Daten bescheiden zu sein"))
story.append(absatz(
    "Ein Wochentag liefert in 17 Jahren rund 850 Beobachtungen — genug. Aber "
    "in kürzeren Fenstern oder spezielleren Fragen wird die Stichprobe dünn, "
    "und rohe Mittelwerte werden then spiegeln Zufall statt Struktur. Shrinkage "
    "(„Schrumpfen“) zieht jede Wochentags-Rate ein wenig Richtung Gesamtrate: "
    "p = (Treffer + 2 × Gesamtrate) ÷ (Anzahl + 2). Bei 850 Beobachtungen ist "
    "der Effekt winzig; bei 20 Beobachtungen verhindert er, dass ein einmal "
    "aufgefallener Ausreißer eine dreiste Prognose erzeugt. Wer möchte, kann "
    "sich das wie einen vorsichtigen Statistiker vorstellen: „Bis ich mehr "
    "sehe, gehe ich vom Durchschnitt aus.“"))
story.extend(unterkap("4.2 Die Warnstufen"))
story.append(tabelle(
    ["Warnstufe", "P(Bewegungstag)", "Bedeutung"],
    [["ruhig", "unter 33 %", "Deutlich ruhiger als üblich"],
     ["normal", "33 % bis 45 %", "Wie es die Basisrate erwartet"],
     ["erhöht", "45 % bis 55 %", "Überdurchschnittlich bewegungsgefährdet"],
     ["hoch", "55 % bis 65 %", "Ernsthaft unruhig zu rechnen"],
     ["extrem", "über 65 %", "Sehr seltene Ausnahmelage (Konflikte, Schocks)"]],
    [0.2, 0.3, 0.5], kurz_spalten=(1,)))
story.append(Paragraph("Tabelle 2: Die fünf Warnstufen sind um die Basisrate "
                       "gelegt, nicht um 50 % — das ist ehrlicher.", CAPTION))

# ══ 5. Mathe I ══════════════════════════════════════════════════════════
kapitel(story, "5. Mathematische Grundlagen I: Verteilungen und Regression")
story.append(absatz(
    "Dieses Kapitel holt alle auf, die mit Statistik wenig am Hut haben. Wer "
    "die Begriffe kennt, kann es überspringen — aber die zwei Ideen hier "
    "tragen das ganze Gebäude."))
story.extend(unterkap("5.1 Verteilungen: Mehr als ein Mittelwert"))
story.append(absatz(
    "Ein Mittelwert allein sagt wenig. Wichtig ist auch, wie stark die Werte "
    "um ihn herum streuen und ob sie symmetrisch verteilt sind. Die berühmte "
    "Normalverteilung ist die Glockenkurve: symmetrisch, Werte links und "
    "rechts gleich wahrscheinlich. Tages-Ranges verhalten sich anders: Sie "
    "können nie negativ sein, sind meist nahe am Minimum und haben gelegentlich "
    "extreme Ausreißer nach rechts — sie folgen eher einer "
    "<b>Lognormalverteilung</b>. Der Trick, der das Rechnen erleichtert: Man "
    "nimmt den Logarithmus der Range — und schon benimmt sich der transformed "
    "Wert wieder wie eine Normalverteilung. Deshalb rechnet das Modell durchweg "
    "mit ln(Range)."))
story.extend(bild("lognormal.png", unterschrift=
    "Abbildung 5: Normal- (blau) versus Lognormalverteilung (rot). Tages-Ranges "
    "sind rechtsschief: viele kleine, wenige riesige Werte."))
story.extend(unterkap("5.2 Regression: Eine Linie durch die Punktwolke"))
story.append(absatz(
    "Eine Regression ist nichts weiter als die Suche nach der Geraden (oder "
    "Ebene), die eine Punktwolke am besten beschreibt — „am besten“ im Sinne "
    "der kleinsten quadratischen Abstände. Die Abstände zwischen Punkt und "
    "Linie heißen Residuen: genau das, was der Einfluss der Erklärung nicht "
    "erklärt. Bei mehreren Einflussgrößen („Merkmalen“) wird aus der Geraden "
    "eine Ebene — die Rechnung bleibt dieselbe: Koeffizienten so wählen, dass "
    "die Residuen quadratisch minimal sind (die „Methode der kleinsten "
    "Quadrate“, ca. 1805 von Gauß und Legendre entwickelt)."))
story.extend(bild("regression.png", unterschrift=
    "Abbildung 6: Das Grundprinzip jeder Regression — das Modell ist die "
    "Linie, der Zufall steckt in den Abständen."))

# ══ 6. HAR-Modell ═══════════════════════════════════════════════════════
kapitel(story, "6. Das Herzstück: Das HAR-Modell der Volatilität")
story.append(absatz(
    "2006 schlugen die Forscher Corsi und Andersen ein erstaunlich einfaches "
    "Modell für Finanzvolatilität vor: HAR — Heterogeneous AutoRegressive, "
    "„zeitlich gemischte Selbstbezüglichkeit“. Die Kernbeobachtung: "
    "<b>Volatilität hat ein Gedächtnis.</b> Unruhige Wochen werden eher von "
    "unruhigen Tagen gefolgt, ruhige von ruhigen — Händler reagieren auf "
    "Händler, Nachrichten kommen in Wellen, Positionen werden schrittweise "
    "ab- und aufgebaut."))
story.extend(unterkap("6.1 Die Idee in einem Satz"))
story.append(absatz(
    "Die erwartete Range von morgen ist eine gewichtete Mischung aus drei "
    "Blickwinkeln: <b>gestern</b> (Tages-Gedächtnis), dem <b>Durchschnitt der "
    "letzten 5 Handelstage</b> (Wochen-Gedächtnis) und dem <b>Durchschnitt der "
    "letzten 22 Tage</b> (Monats-Gedächtnis) — plus Wochentags-Effekte, plus "
    "Termin-Merkmale, plus optional die erwartete Schwankung aus dem "
    "Optionenmarkt (GVZ) und ein Regime-Indikator (wie sehr „gestern“ vom "
    "Monatsdurchschnitt abweicht)."))
story.append(tabelle(
    ["Baustein (Merkmal)", "Alltagssprache", "Warum plausibel?"],
    [["ln(TR) gestern", "Wie bewegte sich der letzte Handelstag?",
      "Unruhe pflanzt sich fort (Klusiv­effekt)".replace("Klusiv­effekt", "Ansteckungseffekt")],
     ["Ø letzte 5 Tage", "Wie war die letzte Handelswoche?",
      "Wochen haben Themen (Datenlagen, Positionierungen)"],
     ["Ø letzte 22 Tage", "Wie ist der laufende Monat?",
      "Marktphasen (Spannung vs. Entspannung) dauern an"],
     ["Wochentags-Variablen", "Di/Mi/Do/Fr ja oder nein?",
      "Saisonalität: Wochenmitte datenreicher"],
     ["NFP / FOMC / Gold-Termin", "Großer Termin heute?",
      "Gemessene, echte Wirkungen (Kapitel 8)"],
     ["GVZ (Optionsmarkt)", "Was erwartet der Markt an Schwankung?",
      "Frühindikator, unabhängig vom Kursverlauf"]],
    [0.28, 0.36, 0.36]))
story.append(Paragraph("Tabelle 3: Die Zutaten des HAR-Modells — alles "
                       "Informationen, die vor dem Prognosetag bekannt sind.",
                       CAPTION))
story.extend(unterkap("6.2 Von der Linie zur Wahrscheinlichkeit"))
story.append(absatz(
    "Die Regression liefert zwei Zahlen: μ (mü) — die erwartete logarithmierte "
    "Range — und σ (sigma) — die typische Streuung, geschätzt aus den "
    "Residuen der Vergangenheit. Die Wahrscheinlichkeit eines Bewegungstags "
    "ist dann schlicht die <b>Fläche unter der Lognormal-Kurve rechts der "
    "Schwelle B</b> (Abbildung 7). Mathematisch ist das eine Zeile: "
    "P = 1 − Φ((ln B − μ) ÷ σ), wobei Φ die Verteilungsfunktion der "
    "Standardnormalverteilung ist — aber die Fläche ist das anschauliche "
    "Bild: Wie viel von der Wahrscheinlichkeitsmasse jenseits der Schwelle "
    "liegt."))
story.extend(bild("p_berechnung.png", unterschrift=
    "Abbildung 7: Die Kernrechnung. Verschiebt sich μ nach rechts (mehr "
    "erwartete Bewegung) oder wächst σ (mehr Unsicherheit), wächst die rote "
    "Fläche — und damit die Prognose."))
story.extend(unterkap("6.3 Das Range-Band (Q10–Q90)"))
story.append(absatz(
    "Neben der Wahrscheinlichkeit liefert dieselbe Verteilung ein "
    "Erwartungsband: In 80 % der Fälle sollte die echte Range zwischen Q10 "
    "und Q90 liegen (die 10 %- und 90 %-Grenzen der Verteilung), der Median "
    "Q50 ist die „typischste“ Tagesrange. Damit hat jeder Tag nicht nur ein "
    "„ob“, sondern ein „wie viel“ — in Dollar, direkt am aktuellen Kurs "
    "gerechnet."))
story.extend(unterkap("6.4 Die Mehr-Tages-Prognose"))
story.append(absatz(
    "Für Dienstag muss der Scanner den Montag erst prognostizieren — denn "
    "dessen Range ist ja Montags Eingang in „gestern“. Das Verfahren ist "
    "rekursiv: Prognose Montag → daraus Merkmale Dienstag → Prognose Dienstag "
    "usw. Die Unsicherheit wächst dabei mit jedem Prognosetag leicht — "
    "spätere Wochentage sind also automatisch vorsichtiger zu lesen, "
    "was die Bandbreiten ehrlich widerspiegeln."))

# ══ 7. Ehrlich testen ═══════════════════════════════════════════════════
kapitel(story, "7. Ehrlich testen: Walk-Forward, Brier-Score und Tor T3")
story.append(absatz(
    "Ein Modell, das seine eigene Geschichte schönrechnet, ist wertlos. "
    "Deshalb testen wir so, wie man Prognosen im Alltag prüfen würde: Man "
    "stellt sich an jeden vergangenen Tag, tut so, als wäre er Zukunft — und "
    "vergleicht dann, was das Modell gesagt hätte mit dem, was wirklich "
    "geschah."))
story.extend(unterkap("7.1 Walk-Forward: Rückwärts durch die Zeit"))
story.extend(bild("walkforward.png", unterschrift=
    "Abbildung 8: Der Walk-Forward-Test. Das Trainingsfenster wächst Schritt "
    "für Schritt; bewertet wird immer nur der nächste kleine Abschnitt — mit "
    "Daten, die davor liegen."))
story.append(absatz(
    "Konkret: Das Modell wird zunächst nur auf den ersten 120 Tagen trainiert "
    "und sagt die folgenden 5 Tage voraus; dann wächst das Training um diese "
    "Tage und die nächsten 5 werden getestet — über 4.078 Testtage hinweg. "
    "Die Modellanpassung („Refit“) wiederholt sich alle 5 Tage, damit das "
    "Modell langsam mitlernt, ohne jemals die Zukunft zu sehen."))
story.extend(unterkap("7.2 Der Brier-Score: Bestrafung falscher Sicherheit"))
story.append(absatz(
    "Wie misst man die Qualität von Wahrscheinlichkeiten? Der Brier-Score "
    "(1950, ursprünglich für Wettervorhersagen) bestraft jede Prognose mit "
    "dem Quadrat ihres Fehlers: Sagt man „70 %“ und es passiert, ist der "
    "Fehler 0,3<super>2</super> = 0,09; sagt man „70 %“ und es passiert nicht, ist er "
    "0,7<super>2</super> = 0,49. Wer also übertrieben selbstsicher in die falsche Richtung "
    "liegt, wird hart bestraft. Der Wert 0,25 gehört zur reinen „Ich weiß es "
    "nicht“-Antwort von 50 %."))
story.extend(bild("brier.png", unterschrift=
    "Abbildung 9: Derselbe Anlass, zwei Prognostiker. Der Kenner ist nicht "
    "öfter „richtig“ — er ist besser kalibriert, und genau das belohnt der "
    "Brier-Score."))
story.extend(unterkap("7.3 Der Brier-Skill-Score und Tor T3"))
story.append(absatz(
    "Um „besser“ greifbar zu machen, stellen wir die entscheidende Frage: "
    "Schlägt das Modell die simple Basisrate? Der Brier-Skill-Score (BSS) "
    "misiert genau das: BSS = 1 − Brier(Modell) ÷ Brier(Basisrate). Positiv "
    "heißt: echter Zugewinn gegenüber dem klassischen „historisch war es an "
    "diesem Wochentag zu X % beweglich“. Unser Entscheidungstor T3 verlangt "
    "BSS > 0 im Walk-Forward — und nur dann darf das Modell überhaupt auf "
    "die Wochenmatrix."))
story.append(kallout_reihe(
    ("bestanden", "Tor T3 am 23.09.2026:\rKonfiguration har_D (HAR + Ereignisse\r+ Optionsvolatilität)"),
    ("BSS +0,067", "≈ 6,7 % weniger Prognosefehler\rals die Klimatologie —\rauf 4.078 ehrlichen Testtagen"),
    ("17 Jahre", "Umfang der Testhistorie\r(Tickmill-Brokerdaten,\r4.354 Tageskerzen)")))
story.append(Spacer(1, 4))
story.append(absatz(
    "Ehrliche Anmerkung: Auf den ersten 4 Jahren Geschichte sah der Vorteil "
    "größer aus (BSS +0,16 mit der schlankeren Variante); über 17 Jahre "
    "gewinnt die Variante mit Ereignis- und Optionsmerkmalen, der Vorsprung "
    "insgesamt ist kleiner. Beides dokumentieren wir — Modelle müssen ihre "
    "Grenzen aushalten, sonst hält man Zufall für Können."))
story.extend(unterkap("7.4 Kalibrierung: „70 %“ muss 70 % bedeuten"))
story.append(absatz(
    "Eine Prognose von 70 % ist nur dann brauchbar, wenn über viele Fälle "
    "hinweg tatsächlich rund 70 % eintreten (Abbildung 10). Gibt das Modell "
    "systematisch zu hohe oder zu tiefe Zahlen, korrigiert die Kalibrierung "
    "nach: Platt-Skalierung (zwei Parameter) sofort, Isotone Regression (eine "
    "monotone Treppenfunktion) ab etwa 500 Beobachtungen. Auch das geschieht "
    "ausschließlich auf Daten, die dem Modell vorher nicht zum Training "
    "dienten."))
story.extend(bild("reliability.png", breite_max=10.5 * cm, unterschrift=
    "Abbildung 10: Das Zuverlässigkeits-Diagramm — der schiefe Winkel zur "
    "Diagonalen zeigt, wo das Modell über- oder unterschätzt."))

# ══ 8. Ereignisse ═══════════════════════════════════════════════════════
kapitel(story, "8. Ereignisse: Was NFP und FOMC wirklich bewegen")
story.append(absatz(
    "Wirtschaftstermine sind die Taktgeber des Goldmarkts. Der Scanner nutzt "
    "sie doppelt: als Merkmale im Modell (Kapitel 6) und als harte, gemessene "
    "Zahlen für die Tagesansicht. Die Messung ist simpel und überprüfbar: "
    "Mittel der Tages-Range an allen Ereignistagen ÷ Mittel an allen "
    "vergleichbaren Normaltagen."))
story.extend(bild("events.png", unterschrift=
    "Abbildung 11: Gemessene Wirkungen über 17 Jahre. Die Arbeitsdaten "
    "(NFP) machen die durchschnittliche Tages-Range rund 24 % größer, eine "
    "Fed-Sitzung (FOMC) rund 12 %."))
story.append(absatz(
    "Zwei Lesarten sind wichtig: Erstens sind das <b>Durchschnitte</b>, keine "
    "Garantien — eine bestimmte Fed-Sitzung kann auch zur Friedhofsruhe "
    "führen. Zweitens zeigt der GC-Termin (Fälligkeit der Gold-Futures), dass "
    "nicht jeder „wichtige“ Kalendereintrag wirklich wichtig ist: ×1,04 und "
    "sogar ein leicht negativer Effekt auf die Bewegungswahrscheinlichkeit — "
    "genau solche ehrlichen Nullbefunde verhindern, dass das Modell an "
    "Rauschen feinjustiert wird."))

# ══ 9. KI-Schicht ═══════════════════════════════════════════════════════
kapitel(story, "9. Die KI-Schicht: Erklären statt Raten")
story.append(absatz(
    "Bis hierher rechnete reiner Code — nachvollziehbar, aber stumm. Die "
    "KI-Schicht (Sprachmodell GLM von Z.ai) fügt zwei Dinge hinzu: Sie "
    "destilliert Nachrichten und Community-Stimmung zu einer kurzen Liste "
    "belegter Treiber, und sie schreibt die Erklärung, die Sie unter jeder "
    "Prognose lesen. Unser eisernes Prinzip heißt: <b>Die Engine rechnet, die "
    "KI zitiert.</b> Keine freie KI-Zahl fließt je unbegrenzt in die Prognose "
    "ein."))
story.extend(unterkap("9.1 Destillation: aus 80 Schlagzeilen werden 8 Treiber"))
story.append(absatz(
    "Das schnelle Modell erhält maximal 80 neue Artikel (als Titel, Kurztext "
    "und Quelle) und liefert strukturiert zurück: bis zu 8 Treiber mit "
    "Richtung, Zeithorizont, Konfidenz und Quellenlink. Kaputte oder "
    "unvollständige Antworten werden verworfen — nie gespeichert; nach drei "
    "Fehlversuchen bricht der Schritt ab und der Lauf fährt ohne KI-Teil "
    "weiter. Ein wichtiger Sparsamkeitsmechanismus ist das Delta-Prinzip: "
    "Jeder Artikel hat einen digitalen Fingerabdruck; unveränderte Artikel "
    "kosten keinen einzigen Token."))
story.extend(unterkap("9.2 Analytiker-Fusion und das Band"))
story.append(absatz(
    "Das starke Modell erhält die Matrix (Modellwahrscheinlichkeit, Schwelle, "
    "Range-Band, Termine je Tag), die News-Treiber und den Community-Konsens. "
    "Es darf die Modellwahrscheinlichkeit je Tag anpassen — aber nur innerhalb "
    "eines Bandes von ±10 Prozentpunkten, und jede Abweichung über 1 Punkt "
    "braucht eine konkrete Begründung. Verstöße verwirft das System "
    "automatisch: Der Tag fällt zurück auf die Modellzahl, der Verstoß wird "
    "protokolliert. Ungültige Antworten (falsches Format, abgebrochene "
    "Ausgaben) werden grundsätzlich nie übernommen."))
story.extend(bild("band.png", unterschrift=
    "Abbildung 12: Band-Disziplin am Beispiel einer realen Woche. Die KI "
    "verschiebt meist nur wenige Punkte — und nur, wo sie begründen kann."))
story.extend(unterkap("9.3 Warum das so streng ist"))
story.append(absatz(
    "Sprachmodelle sind überzeugende Erzähler. Ohne Leitplanke würden sie "
    "gern „aus dem Bauch“ verschieben — und niemand könnte hinterher sagen, "
    "ob das half. Das Band macht das Ganze messbar: Jede Verschiebung wird "
    "gespeichert, und der Track-Record vergleicht später, ob die KI-Version "
    "oder die reine Modellzahl näher an der Realität lag (Kapitel 11). "
    "Fällt die Bilanz negativ aus, dreht man das Band in den Einstellungen "
    "auf null — und die KI erklärt nur noch, ohne zu verschieben."))

# ══ 10. Richtung ════════════════════════════════════════════════════════
kapitel(story, "10. Die Richtung: ein ehrliches Kapitel")
story.append(absatz(
    "Ob der Tag oben oder unten endet, wäre noch wertvoller zu wissen als das "
    "„ob bewegt“. Wir haben es ernsthaft versucht: mit einer logistischen "
    "Regression — vereinfacht das Geschwister der Linie aus Kapitel 5, nur "
    "dass diesmal keine Range, sondern eine Wahrscheinlichkeit („Tag endet "
    "oben“) erklärt wird. Als Einflüsse dienten Trendlage, Momentum, "
    "Realzins-, Dollar- und Optionsdaten sowie die Fonds-Positionierung."))
story.extend(bild("richtung.png", unterschrift=
    "Abbildung 13: Das Ergebnis über 4.078 Testtage: keine Variante schlägt "
    "die simple Basisrate von 52,4 %. Die Richtung des Goldpreises von Tag zu "
    "Tag ist mit diesen Mitteln nicht vorhersagbar."))
story.append(absatz(
    "Das klingt ernüchternd, ist aber der wertvollste Befund des Projekts: "
    "Wir <b>könnten</b> Richtungspfeile zeigen und sie würden seriös "
    "aussehen — aber sie wären nicht besser als eine Münze mit leichtem "
    "Drift. Der Scanner kennzeichnet Richtungssymbole deshalb ausdrücklich "
    "als „nicht verifiziert“ und unternimmt keine weiteren Anstrengungen in "
    "diese Richtung. Ehrliche Entertauen schlagen hübsche Täuschungen."
    .replace("Entertauen", "Enthaltungen")))
story.append(absatz(
    "Übrigens: Quant-Feeds sind deshalb nicht nutzlos. Als <b>Marktlage</b> "
    "(Realzins-Bewegung, Dollar-Schwankung, Fonds-Crowding, ETF-Ströme) "
    "liefern sie den Kontext, den auch die KI-Erklärungen zitieren — nur "
    "eben ohne eine Richtungs-Prognose daraus zu fabrizieren."))

# ══ 11. Verifikation ════════════════════════════════════════════════════
kapitel(story, "11. Kontrolle: Verifikation und Track-Record")
story.append(absatz(
    "Am Ende jeder Woche stellt sich die Frage, die zählt: Stimmten die "
    "Prognosen? Der Verifikations-Agent vergleicht dafür jeden vergangenen "
    "Tag mit der Prognose, die <b>damals gültig war</b> — aus dem Archiv der "
    "versionierten Matrizen, nicht mit der späteren „besseren“ Version. "
    "Gemessen wird dreierlei:"))
story.extend(stichpunkte(
    "<b>Bewegungstag:</b> War die echte True Range über der damaligen Schwelle B? "
    "(verglichen mit Klimatologie-, Modell- und KI-Zahl)",
    "<b>Richtung:</b> Endete der Tag über dem Vortag? (als Erinnerung an Kapitel 10)",
    "<b>Range-Band:</b> Lag die echte Range im prognostizierten Q10–Q90? "
    "(ideal sind rund 80 %)"))
story.append(absatz(
    "Daraus entsteht der Track-Record: das Zuverlässigkeits-Diagramm aus der "
    "Vergangenheit wird zur Lebensausweise, der Brier-Vergleich zeigt, ob das "
    "Modell die Basisrate auch im Echtbetrieb schlägt — und die vielleicht "
    "wichtigste Zahl heißt <b>LLM-Delta-Nutzen</b> (Tor T4): Hat die "
    "KI-Anpassung aus Kapitel 9 historisch geholfen oder geschadet? Diese "
    "Sammlung füllt sich automatisch: Der Daemon verifiziert jede Woche, "
    "jeder vergangene Tag zählt genau einmal."))
story.append(absatz(
    "Weil Ehrlichkeit Zeit braucht: Der Track-Record beginnt bei null — "
    "Prognosen existieren erst seit Projektstart, und ein Tag wird erst "
    "bewertet, wenn seine Kerze vollständig geschlossen ist. In ein paar "
    "Wochen stehen dort erste belastbare Zahlen; in einigen Monaten "
    "entscheidet sich Tor T4."))

# ══ 12. Alltag ══════════════════════════════════════════════════════════
kapitel(story, "12. Der Alltag mit dem Scanner")
story.extend(unterkap("12.1 Der Daemon: Der Scanner läuft von selbst"))
story.append(tabelle(
    ["Wann", "Was passiert", "Dauer"],
    [["jeden Tag 06:30", "Kurse aktualisieren, Kalender prüfen, Ist-Werte "
      "nachziehen (Tageslauf)", "wenige Minuten"],
     ["sonntags 17:00", "Quellen-Scout: Vorschläge für neue Nachrichtenquellen",
      "unter 1 Minute"],
     ["sonntags 18:00", "Der große Wochenlauf: alles — inklusive KI-Fusion, "
      "PDF-Bericht und MT5-Export", "5–10 Minuten"],
     ["samstags 09:00", "Verifikation: vergangene Woche gegen Prognosen "
      "rechnen (Track-Record füllen)", "unter 1 Minute"]],
    [0.22, 0.58, 0.2]))
story.append(Paragraph("Tabelle 4: Der automatische Wochenrhythmus (Daemon). "
                       "Er läuft als eigener Prozess und überlebt das "
                       "Schließen der Oberfläche.", CAPTION))
story.extend(unterkap("12.2 Die Ansichten"))
story.extend(stichpunkte(
    "<b>Dashboard:</b> Die Wochenmatrix mit P je Tag, Warnstufe, Schwelle, "
    "Range-Band, KI-Erklärung mit Treiber-Wasserfall, Marktlage-Signale.",
    "<b>Tagessicht:</b> Termin-Zeitleiste des Tages (Berliner Zeit) und — "
    "untertags — die Session-Lage: Wie weit ist die heutige Range schon, und "
    "wie endeten Tage mit ähnlichem Vormittag historisch?",
    "<b>Track-Record:</b> die Qualitätszahlen aus Kapitel 11, plus "
    "Daemon-Steuerung (Start/Stopp).",
    "<b>Was-wäre-wenn:</b> Regler für Volatilität, Range-Niveau und "
    "Ereignis-Zuschlag — reine Simulation, verändert nichts Gespeichertes."))
story.extend(unterkap("12.3 Anbindung eigener Programme"))
story.append(absatz(
    "Für eigene Werkzeuge gibt es zwei Wege: Der MT5-Export schreibt eine "
    "CSV-Datei (goldscanner_prognose.csv) in den gemeinsamen Ordner aller "
    "MetaTrader-Terminals — ein eigener EA kann sie lesen und z. B. an "
    "bewegungsarmen Tagen das Handelsvolumen drosseln. Zusätzlich bietet ein "
    "kleiner Nur-Lese-Dienst im Netzwerk des Rechners (REST, Adresse "
    "127.0.0.1:8606) die aktuelle Matrix als Datei und Kennzahlen als "
    "Status-Abfrage — bewusst ohne jede Schreibmöglichkeit von außen."))
story.extend(unterkap("12.4 Der Wochen-Summenwert"))
story.append(absatz(
    "Auf einen Blick: Wie wahrscheinlich ist mindestens ein Bewegungstag in "
    "der gesamten Woche? Unter der (bewusst einfachen) Annahme unabhängiger "
    "Tage multipliziert der Scanner die Gegenwahrscheinlichkeiten — aktuell "
    "87 % laut Modell gegenüber 92 % nach Klimatologie. Weil Bewegungstage "
    "real dazu neigen, zu Clustern (Unruhe kommt in Wellen), ist der echte "
    "Wert tendenziell etwas niedriger; der Hinweis steht mit dabei."))

# ══ 13. Grenzen ═════════════════════════════════════════════════════════
kapitel(story, "13. Grenzen und ehrliche Einschätzung")
story.extend(stichpunkte(
    "<b>Kein Handelssystem.</b> Der Scanner schätzt Wahrscheinlichkeiten von "
    "Tagesbewegungen. Er sagt nicht, ob Gold in einem Monat höher oder tiefer "
    "steht, und er kennt keine Einstiege, Stopps oder Positionsgrößen.",
    "<b>Prognosen sind keine Gewissheit.</b> Selbst ein perfekt kalibriertes "
    "„70 %“ geht in 3 von 10 Fällen nicht ein. Der Wert zeigt sich erst über "
    "viele Wochen — genau dafür existiert der Track-Record.",
    "<b>Die Richtung ist ungelöst.</b> Kapitel 10 ist kein Versehen: "
    "Tagessprünge sind mit unseren Mitteln nicht vorhersagbar, und wir geben "
    "vor, was wir nicht können.",
    "<b>Kalibrierung am Rand.</b> Extreme Wahrscheinlichkeiten (nahe 0 oder "
    "100 %) sind seltener und deshalb schwerer zu eichen; die "
    "Nachkalibrierung verbessert das laufend.",
    "<b>Daten sind Broker-spezifisch.</b> Alle Rechnungen basieren auf den "
    "XAUUSD-Kursen des eigenen Brokers (inklusive dessen Handelspausen und "
    "Spreads). Andere Broker liefern leicht andere Zahlen.",
    "<b>Strukturbrüche.</b> Kriege, Schocks oder Regeländerungen können "
    "Muster brechen, auf denen das Modell ruht. Der Walk-Forward über 17 "
    "Jahre (inklusive Finanzkrise, Corona, Inflationsschub) ist unser bester "
    "Beleg für Robustheit — kein Beweis für die Zukunft."))
story.append(absatz(
    "Und zum Schluss das Wichtigste in einem Satz: Dieses Werkzeug ist "
    "Forschung — keine Anlageberatung. Es macht eine gut kalibrierte Frage "
    "sichtbar und beantwortet sie so ehrlich, wie wir es können."))

# ══ 14. Glossar ═════════════════════════════════════════════════════════
kapitel(story, "14. Glossar — die wichtigsten Begriffe kurz")
story.append(tabelle(
    ["Begriff", "Bedeutung in diesem Handbuch"],
    [["Bewegungstag", "Tag, dessen True Range die Schwelle B des Wochentags "
      "übersteigt (Ø der letzten 13 gleichen Wochentage)"],
     ["True Range (TR)", "Größte Tagesbewegung: max(Hoch−Tief, |Hoch−Schluss "
      "gestern|, |Tief−Schluss gestern|)"],
     ["Schwelle B", "Das „Normalmaß“ des Wochentags; darüber gilt der Tag "
      "als Bewegungstag"],
     ["Klimatologie", "Prognose aus reinen Häufigkeiten der Vergangenheit "
      "(Basisrate je Wochentag)"],
     ["Basisrate", "Grundanteil eines Ereignisses ohne jedes Modell "
      "(hier: ≈ 40–43 % Bewegungstage je nach Zeitraum)"],
     ["HAR-Modell", "Regressionsmodell, das Range-Erwartungen aus Gestern-, "
      "Wochen- und Monats-Gedächtnis mischt"],
     ["μ und σ", "Erwartungswert und Streuung der (logarithmierten) Range; "
      "aus ihnen wird die Fläche P gerechnet"],
     ["Q10 / Q50 / Q90", "Untere, mittlere, obere Grenze des erwarteten "
      "Range-Bands (80 %-Band)"],
     ["Walk-Forward", "Ehrlicher Test: nur mit Vergangenheit trainieren, "
      "nächste Tage vorhersagen, wiederholen"],
     ["Brier-Score", "Mittlerer quadratischer Prognosefehler von "
      "Wahrscheinlichkeiten (kleiner = besser; 0,25 = „weiß nicht“)"],
     ["BSS", "Brier-Skill-Score: Zugewinn gegenüber der Basisrate; positiv "
      "= echter Mehrwert"],
     ["Kalibrierung", "Nachjustierung, damit „70 %“ auch in 70 % der Fälle "
      "eintritt (Platt, isoton)"],
     ["Point-in-time", "Nur Informationen nutzen, die zum Rechenzeitpunkt "
      "wirklich verfügbar waren"],
     ["Band-Disziplin", "Die KI darf P je Tag nur ±10 Punkte verschieben "
      "und muss Abweichungen begründen"],
     ["Tor (T1–T5)", "Vordefinierte Go/No-Go-Prüfungen zwischen den "
      "Ausbaustufen; erst nach Bestehen geht es weiter"],
     ["LLM / GLM", "Großes Sprachmodell (hier: GLM von Z.ai) für "
      "Destillation und Erklärtexte"],
     ["GVZ", "Cboe Gold Volatility Index: erwartete 30-Tage-Schwankung aus "
      "Optionen"],
     ["COT", "Commitments of Traders: wöchentliche Fonds-Positionen an der "
      "US-Terminbörse"],
     ["Daemon", "Hintergrundprozess, der den Wochenrhythmus automatisch "
      "fährt"]],
    [0.24, 0.76]))

# ── Build ──
doc = TocVorlage(
    str(BODY_PDF), pagesize=A4,
    leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.9 * cm, bottomMargin=1.9 * cm,
    title="MqlGoldscanner — Handbuch: Wie die Prognosen entstehen",
    author="Z.ai", creator="Z.ai",
    subject="Laienverständliche Methodik-Dokumentation des MqlGoldscanner")
doc.multiBuild(story)
print("Body-PDF:", BODY_PDF)
