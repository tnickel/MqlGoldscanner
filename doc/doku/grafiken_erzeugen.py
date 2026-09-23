# -*- coding: utf-8 -*-
"""Erzeugt alle Grafiken für das Goldscanner-Handbuch (PDF) — mit ECHTEN
Daten aus der Projekt-Datenbank. Stil: Palette aus palette.cascade,
charts.md-Regeln (keine top/right-Spines, gestrichelte Gitternetze,
kollisionsfreie Labels)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from goldscanner import config
from goldscanner.db import Db
from goldscanner.klimatologie import (punkte_in_time_bewertungen,
                                      wochentags_statistik)
from goldscanner.modell.event_multiplikatoren import multiplikatoren
from goldscanner.modell.features import tages_zeilen

# Palette (palette.cascade-Ausgabe, übernommen)
PAGE_BG = "#f1f0ef"
CARD_BG = "#eae9e4"
HEADER_FILL = "#695f3f"
BORDER = "#c6bfac"
ICON = "#a69151"
ACCENT = "#5b31d7"
TEXT = "#171715"
MUTED = "#78766f"
SEM_INFO = "#4a6c8d"
SEM_SUCCESS = "#3b8554"
SEM_ERROR = "#944e47"
SEM_WARNING = "#ac8841"

OUT = Path(__file__).resolve().parent / "grafiken"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "text.color": TEXT,
    "axes.edgecolor": BORDER,
    "axes.labelcolor": TEXT,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})


def _clean(ax, grid_axis="y"):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if grid_axis:
        ax.grid(axis=grid_axis, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.set_axisbelow(True)


def speichern(fig, name):
    fig.savefig(OUT / name, facecolor="white")
    plt.close(fig)
    print("OK", name)


db = Db()
settings = config.load_settings()
d1 = db.raten_laden("XAUUSD", "d1")

# ── 1. Pipeline-Diagramm ────────────────────────────────────────────────
# Titel bewusst kurz/zweizeilig: 9 schmale Kästen nebeneinander — jedes
# Wort muss in die Kastenbreite passen, sonst überragt der Titel den Rahmen.
fig, ax = plt.subplots(figsize=(9.2, 2.9))
stationen = [
    ("Kurse", "MT5-\nBroker\n17 Jahre"),
    ("Kalender", "6 Quellen\n+ Termine"),
    ("Markt-\ndaten", "GVZ · FRED\nCOT · GLD"),
    ("Statistik", "Klima-\ntologie, B"),
    ("HAR-\nModell", "P je Tag\nRange-Band"),
    ("News +\nCommun.", "RSS-Feeds\nDelta"),
    ("KI-\nFusion", "±10-pp\nBegründung"),
    ("Matrix\n+ PDF", "Woche auf\neinen Blick"),
    ("Verifi-\nkation", "vs.\nRealität"),
]
n = len(stationen)
breite, hoehe = 0.98 / n, 0.60
for i, (titel, unter) in enumerate(stationen):
    x = i / n
    farbe = CARD_BG if i < 5 else "#e7e3d5"
    ax.add_patch(plt.Rectangle((x + 0.004, 0.26), breite - 0.012, hoehe,
                               facecolor=farbe, edgecolor=HEADER_FILL,
                               linewidth=1.1,
                               joinstyle="round"))
    ax.text(x + breite / 2, 0.26 + hoehe - 0.16, titel, ha="center", va="center",
            fontsize=7.8, fontweight="bold", color=TEXT, linespacing=1.05)
    ax.text(x + breite / 2, 0.26 + 0.13, unter, ha="center", va="center",
            fontsize=7.0, color=MUTED, linespacing=1.1)
    if i < n - 1:
        ax.annotate("", xy=(x + breite + 0.002, 0.56), xytext=(x + breite - 0.006, 0.56),
                    arrowprops=dict(arrowstyle="-|>", color=HEADER_FILL, lw=1.2))
ax.text(0.5, 0.94, "Deterministisch (reiner Code — jede Zahl nachrechenbar)",
        ha="center", fontsize=8.6, color=HEADER_FILL, style="italic",
        transform=ax.transAxes)
ax.text(0.72, 0.05, "KI-Schicht (erklärt & gewichtet im Band)",
        ha="center", fontsize=8.6, color=SEM_INFO, style="italic",
        transform=ax.transAxes)
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.axis("off")
speichern(fig, "fluss.png")

# ── 2. Kerzen-Anatomie mit True Range ───────────────────────────────────
fig, ax = plt.subplots(figsize=(7.4, 4.4))
# Vortages-Kerze
ax.add_patch(plt.Rectangle((0.8, 100), 0.5, 12, facecolor="#dfd9c8",
                           edgecolor=HEADER_FILL, linewidth=1.2))
ax.plot([1.05, 1.05], [96, 117], color=HEADER_FILL, linewidth=1.2)
ax.plot([1.05, 1.05], [97, 99], color=HEADER_FILL, linewidth=1.2)
# heutige Kerze (größere Range)
ax.add_patch(plt.Rectangle((1.9, 104), 0.5, 22, facecolor=HEADER_FILL,
                           edgecolor=HEADER_FILL, linewidth=1.2))
ax.plot([2.15, 2.15], [98, 133], color=HEADER_FILL, linewidth=1.2)
# Close Vortag-Linie
ax.axhline(112, xmin=0.08, xmax=0.97, color=SEM_INFO, linestyle="--", linewidth=1.3)
ax.text(0.70, 113.5, "Schlusskurs Vortag", fontsize=9, color=SEM_INFO)
# TR-Klammer: max(Hoch, Vortag) bis min(Tief, Vortag)
oben, unten = 133, 98
ax.annotate("", xy=(2.85, oben), xytext=(2.55, oben),
            arrowprops=dict(arrowstyle="-", color=SEM_ERROR, lw=1.4))
ax.annotate("", xy=(2.85, unten), xytext=(2.55, unten),
            arrowprops=dict(arrowstyle="-", color=SEM_ERROR, lw=1.4))
ax.annotate("", xy=(2.82, oben), xytext=(2.82, unten),
            arrowprops=dict(arrowstyle="<|-|>", color=SEM_ERROR, lw=1.6))
ax.text(2.90, (oben + unten) / 2,
        "True Range\nTR = größte der\ndrei Distanzen", fontsize=9, va="center",
        color=SEM_ERROR)
ax.text(2.24, 134.5, "Hoch", fontsize=9, color=MUTED)
ax.text(2.24, 93.4, "Tief", fontsize=9, color=MUTED)
ax.text(1.32, 96.6, "Kerze\nVortag", fontsize=9, ha="center", color=MUTED)
ax.text(2.15, 90.5, "Kerze heute (bewegter Tag)", fontsize=9.5, ha="center",
        color=TEXT)
ax.set_xlim(0.4, 4.1)
ax.set_ylim(88, 140)
ax.set_ylabel("Kurs (z. B. XAUUSD in USD)")
ax.set_xticks([])
_clean(ax)
speichern(fig, "kerze.png")

# ── 3. Verteilung: Range im Verhältnis zum Normalmaß (echte Daten) ──────
bew = punkte_in_time_bewertungen(d1, k=1.0, fenster=13)
fig, ax = plt.subplots(figsize=(7.4, 3.9))
verhaeltnis = np.array([b["tr_rel"] / b["schwelle_rel"] for b in bew])
verhaeltnis = verhaeltnis[verhaeltnis < 3.2]
ax.hist(verhaeltnis, bins=70, color=CARD_BG, edgecolor=BORDER, linewidth=0.4)
anteil = float(np.mean([b["bewegung"] for b in bew]))
ax.axvline(1.0, color=SEM_ERROR, linewidth=1.8)
ax.text(1.05, ax.get_ylim()[1] * 0.90,
        "1,0 = Normalmaß des\nWochentags (Schwelle B)",
        fontsize=8.8, color=SEM_ERROR)
ax.text(1.45, ax.get_ylim()[1] * 0.42,
        f"Fläche rechts der Linie\n= Bewegungstage\n= {anteil * 100:.0f} % aller Tage",
        fontsize=9.5, color=TEXT)
ax.set_xlabel("Tages-Range ÷ Normalmaß des Wochentags   (1,0 = genau „normal“)")
ax.set_ylabel("Anzahl Tage")
ax.set_title("Wie oft ist ein Tag „bewegter als normal“?")
_clean(ax)
speichern(fig, "verteilung.png")

# ── 4. Klimatologie je Wochentag (echte Daten) ──────────────────────────
stat = wochentags_statistik(d1, k=1.0, fenster=13)
wt_namen = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
ps = [stat["je_wochentag"].get(w, {}).get("p", 0) * 100 for w in range(5)]
ns = [stat["je_wochentag"].get(w, {}).get("n", 0) for w in range(5)]
fig, ax = plt.subplots(figsize=(7.4, 3.8))
balken = ax.bar(wt_namen, ps, color=CARD_BG, edgecolor=HEADER_FILL, linewidth=1.1,
                width=0.62)
for b, p, n_ in zip(balken, ps, ns):
    ax.text(b.get_x() + b.get_width() / 2, p + 0.6, f"{p:.1f} %\n(n={n_})",
            ha="center", fontsize=9, color=TEXT)
glob = stat["p_global"] * 100
ax.axhline(glob, color=SEM_INFO, linestyle="--", linewidth=1.4)
ax.set_ylabel("Anteil Bewegungstage (17 Jahre)")
ax.set_ylim(0, max(ps) + 9)
ax.set_title("Klimatologie: Manche Wochentage sind historisch bewegter")
# Gesamt-Label weit oben rechts — weg von allen Balkenbeschriftungen
ax.text(4.45, max(ps) + 6.4, f"gesamt: {glob:.1f} %", fontsize=8.8,
        color=SEM_INFO, ha="right")
_clean(ax)
speichern(fig, "klima.png")

# ── 5. Regression für Laien (Punktwolke + Gerade) ───────────────────────
rng = np.random.default_rng(42)
x = np.linspace(0, 10, 60)
y = 0.8 * x + 1 + rng.normal(0, 1.0, 60)
fig, ax = plt.subplots(figsize=(7.4, 4.0))
ax.scatter(x, y, s=26, color=SEM_INFO, alpha=0.65, label="Beobachtungen (Tage)")
b, a = np.polyfit(x, y, 1)
linie = a + b * x
ax.plot(x, linie, color=SEM_ERROR, linewidth=2.2,
        label="Regressionsgerade (Modell)")
for i in (5, 18, 33, 50):
    ax.plot([x[i], x[i]], [y[i], linie[i]], color=BORDER, linewidth=1.0,
            linestyle=":")
ax.text(6.4, 4.3, "Abstände (Residuen)\n= das, was das\nModell NICHT erklärt",
        fontsize=8.8, color=MUTED)
ax.set_xlabel("Einflussgröße (z. B. durchschnittliche Range der letzten Tage)")
ax.set_ylabel("Beobachtete Tages-Range")
ax.set_title("Eine Regression legt die „beste Linie“ durch die Punktwolke")
ax.legend(frameon=False, loc="upper left", fontsize=9)
_clean(ax)
speichern(fig, "regression.png")

# ── 6. Normal vs. lognormal ─────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.4, 3.6))
xs = np.linspace(-3.6, 5.2, 400)
normal = np.exp(-xs ** 2 / 2) / np.sqrt(2 * np.pi)
lognorm = np.exp(-(np.log(np.clip(xs, 0.01, None)) - 0.2) ** 2 / 2) \
    / (np.clip(xs, 0.01, None) * np.sqrt(2 * np.pi)) * 0.55
ax.plot(xs, normal, color=SEM_INFO, linewidth=2.2,
        label="Normalverteilung (symmetrisch, auch negativ möglich)")
ax.plot(xs, lognorm, color=SEM_ERROR, linewidth=2.2,
        label="Lognormalverteilung (nur positiv, Rechtschief — wie Tagesranges)")
ax.fill_between(xs, lognorm, color=SEM_ERROR, alpha=0.08)
ax.set_ylim(0, 0.47)
ax.set_yticks([])
ax.set_xlabel("Wert (z. B. Tages-Range)      negativ ←                → positiv")
ax.set_title("Warum wir mit dem Logarithmus rechnen: Ranges können nie negativ sein")
ax.legend(frameon=False, fontsize=8.8, loc="upper right")
_clean(ax, grid_axis=None)
speichern(fig, "lognormal.png")

# ── 7. Von μ und σ zur Wahrscheinlichkeit (Kerngrafik) ──────────────────
fig, ax = plt.subplots(figsize=(7.6, 4.1))
mu, sigma = 0.0, 0.5
xs = np.linspace(-2.2, 2.6, 500)
dichte = np.exp(-((xs - mu) / sigma) ** 2 / 2) / (sigma * np.sqrt(2 * np.pi))
schwelle = 0.62
ax.plot(xs, dichte, color=TEXT, linewidth=2.0)
maske = xs >= schwelle
ax.fill_between(xs[maske], dichte[maske], color=SEM_ERROR, alpha=0.30)
ax.axvline(schwelle, color=SEM_ERROR, linewidth=1.8)
ax.axvline(mu, color=MUTED, linestyle=":", linewidth=1.2)
ax.annotate("", xy=(mu, 0.40), xytext=(mu + sigma, 0.40),
            arrowprops=dict(arrowstyle="<|-|>", color=HEADER_FILL, lw=1.4))
ax.text(mu + sigma / 2, 0.435, "σ (typische\nStreuung)", ha="center",
        fontsize=8.6, color=HEADER_FILL)
ax.text(mu + 0.03, 0.11, "μ\n(erwartete\nRange)", fontsize=9, color=MUTED)
p_fläche = 1 - 0.5 * (1 + np.vectorize(lambda z: __import__("math").erf(
    z / np.sqrt(2)))((schwelle - mu) / sigma))
ax.text(schwelle + 0.09, 0.30, f"P(TR > B) = rote Fläche\n≈ {p_fläche * 100:.0f} %",
        fontsize=11, color=SEM_ERROR, fontweight="bold")
ax.text(schwelle + 0.04, 0.62, "B (Schwelle)", fontsize=10, color=SEM_ERROR,
        ha="left")
ax.set_xticks([])
ax.set_yticks([])
ax.set_title("Aus Erwartungswert (μ) und Streuung (σ) wird eine Wahrscheinlichkeit")
ax.spines["left"].set_visible(False)
_clean(ax, grid_axis=None)
speichern(fig, "p_berechnung.png")

# ── 8. Walk-Forward ─────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.8, 3.4))
segmente = [(0.05, 0.30, "Training\n(nur Vergangenheit)"), (0.35, 0.08, None),
            (0.05, 0.50, "Training (gewachsen)"), (0.55, 0.08, None),
            (0.05, 0.70, "Training (noch größer)"), (0.75, 0.08, None)]
for y_off, (x0, breite, label) in zip([0.55, 0.55, 0.32, 0.32, 0.09, 0.09], segmente):
    if label:
        ax.add_patch(plt.Rectangle((x0, y_off), breite, 0.20,
                                   facecolor=CARD_BG, edgecolor=HEADER_FILL,
                                   linewidth=1.0))
        ax.text(x0 + breite / 2, y_off + 0.10, label, ha="center", va="center",
                fontsize=8.4, color=TEXT)
    else:
        ax.add_patch(plt.Rectangle((x0, y_off), breite, 0.20,
                                   facecolor="#d9c9c4", edgecolor=SEM_ERROR,
                                   linewidth=1.2))
        ax.text(x0 + breite / 2, y_off + 0.10, "Test", ha="center", va="center",
                fontsize=8.6, color=SEM_ERROR, fontweight="bold")
ax.annotate("", xy=(0.93, 0.02), xytext=(0.05, 0.02),
            arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.2))
ax.text(0.49, -0.055, "Zeit: das Fenster wächst — jeder Testtag wird nur mit "
        "Daten DAVOR bewertet", ha="center", fontsize=9, color=MUTED)
ax.set_xlim(0, 1)
ax.set_ylim(-0.09, 0.98)
ax.axis("off")
ax.set_title("Walk-Forward-Test: ehrlich in die Zukunft schauen")
speichern(fig, "walkforward.png")

# ── 9. Brier-Score für Laien ────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.4, 3.7))
# Beispiel: 10 Tagen, 6 beweglich; Forecaster A immer 50 %, B 70 % an beweglichen
# A: Mittel (0.5-1)^2/(0.5-0)^2 = 0.25; B: (0.3^2*6 + 0.7^2*4)/10
brier_a = (6 * 0.25 + 4 * 0.25) / 10
brier_b = (6 * 0.09 + 4 * 0.49) / 10
balken = ax.bar(["Wetterfrosch:\nimmer „50 %“", "Kenner:\n70 % an beweglichen,\n30 % an ruhigen Tagen"],
                [brier_a, brier_b], color=[CARD_BG, "#dfd0e0"],
                edgecolor=[HEADER_FILL, ACCENT], linewidth=1.2, width=0.5)
for b, v in zip(balken, [brier_a, brier_b]):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.008, f"{v:.3f}",
            ha="center", fontsize=11, fontweight="bold", color=TEXT)
ax.set_ylabel("Brier-Score (kleiner = besser)")
ax.set_ylim(0, 0.32)
ax.set_title(f"Beispiel an 10 Tagen (6 beweglich): Bestrafung falscher Sicherheit")
ax.text(0.5, 0.295, "Perfekt = 0,000 · Schätzen = 0,250 · Immer falsch sicher = 1,000",
        ha="center", fontsize=8.6, color=MUTED, transform=ax.transAxes)
_clean(ax)
speichern(fig, "brier.png")

# ── 10. Reliability-Diagramm-Konzept ────────────────────────────────────
fig, ax = plt.subplots(figsize=(5.6, 4.4))
ax.plot([0, 1], [0, 1], linestyle="--", color=BORDER, linewidth=1.4,
        label="ideal (gesagt = gekommen)")
punkte_x = [0.2, 0.4, 0.6, 0.8]
punkte_y = [0.22, 0.36, 0.58, 0.76]
ax.scatter(punkte_x, punkte_y, s=90, color=ACCENT, zorder=3,
           label="Modell (Beispiel)")
for px, py in zip(punkte_x, punkte_y):
    ax.plot([px, px], [py, px], color=ACCENT, alpha=0.3, linewidth=1)
ax.set_xlabel("gesagte Wahrscheinlichkeit")
ax.set_ylabel("tatsächlich eingetreten")
ax.set_xlim(0, 1)
ax.set_ylim(0, 1)
ax.set_title("Zuverlässigkeit: sagte „60 %“, kam es in 60 % der Fälle?")
ax.legend(frameon=False, fontsize=8.8, loc="upper left")
_clean(ax, grid_axis="both")
speichern(fig, "reliability.png")

# ── 11. Event-Multiplikatoren (echte Daten) ─────────────────────────────
zeilen = tages_zeilen(d1, db, k=1.0, fenster=13)
mult = {m["event"]: m for m in multiplikatoren(zeilen)}
labels = {"nfp": "NFP\n(Arbeitsdaten, 1. Freitag)", "fomc": "FOMC\n(Fed-Sitzung)",
          "gold_termin": "GC-Termin\n(Future-Fälligkeit)"}
fig, ax = plt.subplots(figsize=(7.4, 3.9))
keys = ["nfp", "fomc", "gold_termin"]
werte = [mult[k]["multiplikator"] for k in keys]
lifts = [mult[k]["lift_pp"] for k in keys]
ns_m = [mult[k]["n"] for k in keys]
balken = ax.bar([labels[k] for k in keys], werte,
                color=["#dfd9c8"] * 3, edgecolor=HEADER_FILL, linewidth=1.2,
                width=0.5)
ax.axhline(1.0, color=SEM_INFO, linestyle="--", linewidth=1.4)
ax.text(2.42, 1.005, "Normaltag = 1,0", fontsize=8.8, color=SEM_INFO, ha="right")
for b, w, l, n_ in zip(balken, werte, lifts, ns_m):
    ax.text(b.get_x() + b.get_width() / 2, w + 0.015,
            f"×{w:.2f}\n{l:+.1f} pp\n(n={n_})", ha="center", fontsize=9,
            color=TEXT)
ax.set_ylabel("Ø Tages-Range gegenüber Normaltagen")
ax.set_ylim(0.9, max(werte) + 0.16)
ax.set_title("Gemessene Wirkung großer Ereignisse (17 Jahre Brokerdaten)")
_clean(ax)
speichern(fig, "events.png")

# ── 12. Band-Disziplin ──────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.6, 3.9))
tage_b = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag"]
p_stat = [36, 19, 8, 19, 19]
p_fin = [36, 19, 10, 22, 21]
xpos = np.arange(len(tage_b))
ax.fill_between(xpos, np.array(p_stat) - 10, np.array(p_stat) + 10,
                color=CARD_BG, label="Freiraum der KI (±10 Prozentpunkte)")
for i, (ps, pf) in enumerate(zip(p_stat, p_fin)):
    ax.plot(i, ps, "o", color=TEXT, markersize=8)
    ax.annotate("", xy=(i, pf), xytext=(i, ps),
                arrowprops=dict(arrowstyle="-|>", color=ACCENT, lw=1.8))
    ax.plot(i, pf, "D", color=ACCENT, markersize=7)
ax.plot([], [], "o", color=TEXT, label="P_stat (Modell-Anker)")
ax.plot([], [], "D", color=ACCENT, label="P_finale (KI, mit Begründung)")
ax.set_xticks(xpos, tage_b)
ax.set_ylabel("Wahrscheinlichkeit Bewegungstag (%)")
ax.set_ylim(-4, 52)
ax.set_title("Band-Disziplin: Die KI darf den Anker nur begrenzt verschieben")
ax.legend(frameon=False, fontsize=8.8, loc="upper right")
_clean(ax)
speichern(fig, "band.png")

# ── 13. Richtung: ehrliches Ergebnis (echte Daten) ──────────────────────
fig, ax = plt.subplots(figsize=(7.4, 3.8))
konfigs = ["R1\nTrend", "R2\n+ Makro", "R3\n+ Positionierung"]
bss = [-0.0028, -0.0072, -0.0104]
farben = [SEM_WARNING if v < 0 else SEM_SUCCESS for v in bss]
balken = ax.bar(konfigs, bss, color=farben, edgecolor=HEADER_FILL, linewidth=1.1,
                width=0.5)
for b, v in zip(balken, bss):
    ax.text(b.get_x() + b.get_width() / 2, v - 0.0012, f"{v * 100:+.2f} pp",
            ha="center", fontsize=10, color=TEXT, fontweight="bold")
ax.axhline(0, color=TEXT, linewidth=1.2)
ax.text(1.0, 0.0018, "Null = genauso gut wie die einfache Basisrate (52,4 % „Tag endet oben“)",
        ha="center", fontsize=8.8, color=MUTED)
ax.set_ylabel("BSS (negativ = schlechter als Basisrate)")
ax.set_ylim(-0.016, 0.006)
ax.set_title("Richtung: 4.078 Testtage lang KEIN Modell besser als die Basisrate")
_clean(ax)
speichern(fig, "richtung.png")

db.close()
print("\nAlle Grafiken in", OUT)
