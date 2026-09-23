# -*- coding: utf-8 -*-
"""Hilfe-Texte für die i-Buttons (Port der KiScanner-Hilfe).
Jeder Eintrag: Schlüssel → (Titel, Erklärung als Markdown)."""
from __future__ import annotations

HELP: dict[str, tuple[str, str]] = {
    "wochenlauf": ("Wochenlauf — was passiert da?",
        "Der komplette Durchlauf: **Kurse** vom Broker holen → **Kalender** aus "
        "5 Quellen + Regeltermine → **Marktdaten** (GVZ, FRED, CFTC, GLD) → "
        "**Matrix** neu berechnen (Klimatologie + HAR-Modell + Richtung) → "
        "**News & Community** abrufen → **KI-Fusion** (erklärt und verschiebt "
        "im ±10-pp-Band) → **PDF-Bericht** und MT5-Export schreiben.\n\n"
        "Dauert typisch 3–8 Minuten (die KI-Aufrufe sind das Langsamste). "
        "Der Daemon macht das automatisch sonntags 18:00."),
    "matrix_neu": ("Matrix neu bauen — was ist das?",
        "Berechnet **nur die Statistik** neu (Klimatologie, HAR-Modell, "
        "Richtung) aus den **bereits gespeicherten** Kursen — ohne neue "
        "Abrufe, ohne KI, ohne PDF.\n\n"
        "**Wann sinnvoll?** Wenn sich z. B. der Schwellen-Parameter (k) oder "
        "das Fenster in den Einstellungen geändert hat, oder nach dem "
        "Import längerer Historie. Für aktuelle Daten lieber den vollen "
        "**Wochenlauf** starten.\n\n"
        "Die KI-Analyse (P_finale) der letzten Fusion bleibt dabei "
        "sichtbar, bis ein neuer Wochenlauf sie ersetzt."),
    "kpi_kennzahlen": ("Kennzahlen einordnen (Farbskala)",
        "Die Farbe zeigt die **Bewegungsintensität** — grün = ruhig, gelb = "
        "normal, rot = stark bewegt:\n\n"
        "- **ATR 14 / TR heute**: eingestuft gegen die eigenen Werte der "
        "letzten 12 Monate (Perzentil). Der Balken zeigt, wie viele Tage "
        "historisch RUHIGER waren.\n"
        "- **RSI 14**: Farbe nach Distanz zu 50 — je weiter von der Mitte, "
        "desto deutlicher die Kursbewegung.\n"
        "- **Kalender-Events**: hochrelevante Termine (★≥4) der laufenden "
        "Woche.\n\n"
        "Achtung: grün/rot ist KEIN Kauf-/Verkaufssignal, nur ein "
        "Bewegtheits-Maß."),
    "kpi_atr": ("ATR 14 (D1) — Average True Range",
        "Die durchschnittliche **Tagesbewegung** der letzten 14 Tage, in "
        "US-Dollar. Beispiel: ATR 40 heißt: in den letzten zwei Wochen "
        "schwankte Gold im Schnitt etwa 40 USD pro Tag.\n\n"
        "Die Farbe ordnet den Wert ein: **Perzentil gegen die eigenen "
        "Werte der letzten 12 Monate** — bei „Perzentil 84“ war Gold an "
        "84 % der Tage ruhiger als aktuell. Grün = unteres Drittel, "
        "rot = oberes."),
    "kpi_rsi": ("RSI 14 (D1) — Relative Strength Index",
        "Oszillator zwischen 0 und 100: Werte weit über 50 = letzte Tage "
        "deutlich aufwärts, weit unter 50 = deutlich abwärts, um 50 = "
        "ausgeglichen.\n\n"
        "Die Farbe zeigt hier die **Bewegtheit** (Distanz zu 50), keine "
        "Kauf-/Verkaufsempfehlung."),
    "richtung_marktlage": ("Richtung & Marktlage (Stufe 5)",
        "Links die P(hoch)-Prognosen der Richtungsmodelle (ehrlich: als "
        "„nicht verifiziert“ gekennzeichnet — sie schlagen die Basisrate "
        "nicht), rechts die aktuellen Quant-Signale: Δ Realzins und Δ "
        "Dollar (5 Tage), COT-Fondspositionen mit Perzentil, GLD-ETF-Flüsse "
        "sowie Crowding-Warnungen."),
    "ki_analyse": ("KI-Analyse (Stufe 4)",
        "Der Analytiker-Agent erhält die Modell-Matrix, Termine, die "
        "News-Treiber und den Community-Konsens. Er darf P_stat je Tag nur "
        "im ±10-pp-Band verschieben und muss jede Abweichung begründen — "
        "Verstöße verwirft das System automatisch. Der Treiber-Wasserfall "
        "zeigt, welche Einflüsse die Verschiebung tragen."),
    "wochen_summe": ("Wochen-Summenwert",
        "Wahrscheinlichkeit, dass **mindestens ein** Tag der Woche ein "
        "Bewegungstag wird — berechnet als 1 − ∏(1 − p) unter der "
        "vereinfachenden Annahme unabhängiger Tage. Weil Bewegungstage "
        "real clustern, liegt der wahre Wert eher etwas darunter."),
    "was_waere_wenn": ("Was-wäre-wenn — Simulation",
        "Schiebt die Modell-Verteilung (μ und σ der erwarteten Range) und "
        "rechnet P je Tag mit derselben Formel neu. Reine Sandbox: nichts "
        "davon wird gespeichert, exportiert oder verifiziert."),
}
